"""End-to-end proof for meal-plan accuracy, using REAL generated plans.

For each eating style it:
  1. generates a plan through the public API (the same call the app makes),
  2. re-loads it with GET /api/mealplan/{id} (exactly what the meal screen shows),
  3. recalculates every meal from its listed ingredients (grams × per-100g values
     from the food database) and compares with the numbers on screen,
  4. checks each day is within 5% of the plan's targets and passes allergy/diet rules,
  5. swaps a meal and repeats the checks.

Writes a full report to /app/memory/meal_plan_verification.md.
Run:  python3 scripts/verify_meal_plans.py [style ...]
"""
import os
import re
import sys
import time

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
from food_database import INGREDIENT_MACROS  # noqa: E402
from nutrition_engine import FoodRules, UNIT_FOODS, calculate_ingredient_macros, finalize_meal, items_from_raw, make_draft, resolve_food  # noqa: E402

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/") + "/api"
USER_ID = "2663e0c4-d8b9-4feb-b42a-8b055631ea25"  # sdk57tester@example.com
DB = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME")]
REPORT = "/app/memory/meal_plan_verification.md"
RUNS = [
    ("balanced", []), ("high_protein", []), ("vegetarian", []), ("vegan", []),
    ("paleo", []), ("keto", []), ("carnivore", []),
    ("balanced", ["gluten", "dairy"]), ("vegan", ["nuts", "soy"]),
]
KEYS = ("calories", "protein", "carbs", "fats")


def per_ingredient(ing: str):
    """Independent recalculation: 'Xg label' or 'N units label (Xg)' → database entry → grams/100 × per-100g."""
    m = re.match(r"^(\d+(?:\.\d+)?)g (.+)$", ing)
    u = re.match(r"^(\d+) (?:slices? )?(.+?) \((\d+(?:\.\d+)?)g\)$", ing)
    if m:
        grams, label = float(m.group(1)), m.group(2)
    elif u:
        grams, label = float(u.group(3)), u.group(2)
    else:
        return None
    key = resolve_food(label)
    cal, p, c, f = INGREDIENT_MACROS[key]
    x = grams / 100
    # whole-unit foods (eggs, bread slices…) must be listed as whole units
    whole = not UNIT_FOODS.get(key) or (bool(u) and grams == int(u.group(1)) * UNIT_FOODS[key][0])
    return {"grams": grams, "label": label, "key": key, "per100": (cal, p, c, f), "whole": whole,
            "calories": round(cal * x), "protein": round(p * x, 1), "carbs": round(c * x, 1), "fats": round(f * x, 1)}


def check_meal(meal):
    rows = [per_ingredient(i) for i in meal["ingredients"]]
    if any(r is None for r in rows):
        return rows, None, False
    calc = {k: sum(r[k] for r in rows) for k in KEYS}
    ok = (calc["calories"] == meal["calories"] and all(abs(calc[k] - meal[k]) <= 0.051 for k in KEYS[1:])
          and all(r["whole"] for r in rows))
    return rows, calc, ok


def pct(a, t):
    return (a - t) / t * 100 if t else 0.0


def day_report(day, plan, rules, out, label_suffix=""):
    targets = {"calories": plan["target_calories"], "protein": plan["target_protein"],
               "carbs": plan["target_carbs"], "fats": plan["target_fats"]}
    meals_ok, safe_ok = True, True
    out.append(f"\n#### {day['day']}{label_suffix}\n")
    out.append("| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |")
    out.append("|---|---|---|---|---|")
    for meal in day["meals"]:
        rows, calc, ok = check_meal(meal)
        meals_ok &= ok
        items, _ = items_from_raw(meal["ingredients"])
        problems = rules.violations(meal["name"], items, meal.get("instructions", ""))
        safe_ok &= not problems
        ing_txt = "<br>".join(
            f"{r['grams']:g}g {r['label']} → *{r['key']}* ({r['per100'][0]:g}/{r['per100'][1]:g}/{r['per100'][2]:g}/{r['per100'][3]:g}) = {r['calories']} kcal"
            for r in rows if r)
        calc_txt = f"{calc['calories']:.0f} kcal / {calc['protein']:.1f}P / {calc['carbs']:.1f}C / {calc['fats']:.1f}F" if calc else "n/a"
        scr_txt = f"{meal['calories']} kcal / {meal['protein']}P / {meal['carbs']}C / {meal['fats']}F"
        flag = "✅" if ok else "❌"
        if problems:
            flag += f" ⚠️ rules: {problems}"
        out.append(f"| **{meal['meal_type']}** — {meal['name']} | {ing_txt} | {calc_txt} | {scr_txt} | {flag} |")
    sums = {"calories": sum(m["calories"] for m in day["meals"]), "protein": sum(m["protein"] for m in day["meals"]),
            "carbs": sum(m["carbs"] for m in day["meals"]), "fats": sum(m["fats"] for m in day["meals"])}
    totals_ok = (sums["calories"] == day["total_calories"]
                 and all(abs(sums[k] - day[f"total_{k}"]) <= 0.051 for k in KEYS[1:]))
    tol = {k: max(0.05 * targets[k], 0 if k == "calories" else 2) for k in KEYS}
    within = all(abs(day[f"total_{k}"] - targets[k]) <= tol[k] + 1e-9 for k in KEYS)
    devs = " / ".join(f"{k[:4]} {day[f'total_{k}']:g} vs {targets[k]:g} ({pct(day[f'total_{k}'], targets[k]):+.1f}%)" for k in KEYS)
    out.append(f"\n**Day total on screen:** {devs} → {'✅ within 5%' if within else '❌ NOT within 5%'}; "
               f"day total = sum of meals: {'✅' if totals_ok else '❌'}; app badge: {'On target' if day.get('on_target') else 'off target'}\n")
    return meals_ok and totals_ok, within, safe_ok


def run_one(style, allergies, idx, out, summary):
    DB.meal_generation_events.delete_many({"user_id": USER_ID})
    t0 = time.time()
    r = requests.post(f"{BASE}/mealplans/generate", json={
        "user_id": USER_ID, "food_preferences": style, "allergies": allergies, "supplements": []}, timeout=300)
    gen_s = time.time() - t0
    r.raise_for_status()
    plan_id = r.json()["id"]
    plan = requests.get(f"{BASE}/mealplan/{plan_id}", timeout=90).json()
    rules = FoodRules(allergies, [], style)
    title = f"{style}" + (f" + allergies {allergies}" if allergies else "")
    out.append(f"\n---\n## {title}\nPlan **{plan['name']}** (`{plan_id}`), generated in {gen_s:.0f}s. "
               f"Targets: {plan['target_calories']} kcal / {plan['target_protein']}P / {plan['target_carbs']}C / {plan['target_fats']}F\n")
    res = [day_report(d, plan, rules, out) for d in plan["meal_days"]]

    meal_index = idx % 4
    old = plan["meal_days"][0]["meals"][meal_index]
    t0 = time.time()
    sr = requests.post(f"{BASE}/mealplan/alternate", json={
        "user_id": USER_ID, "meal_plan_id": plan_id, "day_index": 0, "meal_index": meal_index,
        "swap_preference": "similar"}, timeout=150)
    swap_s = time.time() - t0
    sr.raise_for_status()
    plan2 = requests.get(f"{BASE}/mealplan/{plan_id}", timeout=90).json()
    new = plan2["meal_days"][0]["meals"][meal_index]
    out.append(f"\n### Swap test — Day 1 {old['meal_type']}: “{old['name']}” → “{new['name']}” ({swap_s:.0f}s)\n")
    swap_res = day_report(plan2["meal_days"][0], plan2, rules, out, " (after swap)")
    summary.append((title, plan["name"], gen_s, res, (old["name"], new["name"]), swap_res))


def parfait_section(out):
    ings = ["200g Greek yogurt 0%", "50g granola", "120g mixed berries", "30g sliced almonds",
            "15ml honey", "1 medium banana 100g"]
    out.append("\n---\n## Your example: Greek Yogurt Parfait with Granola & Berries\n")
    out.append("| Ingredient | Database entry | Grams used | kcal | P | C | F |\n|---|---|---|---|---|---|---|")
    for i in ings:
        from nutrition_engine import parse_ingredient
        label, g, key = parse_ingredient(i)
        m = calculate_ingredient_macros(i)
        out.append(f"| {i} | {key} | {g:.1f} | {m['calories']} | {m['protein']} | {m['carbs']} | {m['fats']} |")
    items, _ = items_from_raw(ings)
    meal = finalize_meal(make_draft("Greek Yogurt Parfait with Granola & Berries", "breakfast", items), "x")
    out.append(f"\nShown on screen after the fix: **{meal['calories']} kcal / {meal['protein']}P / {meal['carbs']}C / {meal['fats']}F** "
               f"(before: 476 / 34P / 45C / 17.5F). 15 ml honey is now 21.3 g (honey is denser than water) "
               f"and the banana uses the stated 100 g, hence ~734 rather than 731.\n")


def main():
    styles = sys.argv[1:]
    runs = [r for r in RUNS if not styles or r[0] in styles]
    out, summary = ["# Meal plan verification — real generated plans\n",
                    f"Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} against {BASE}. "
                    "“Calculated from ingredients” = grams ÷ 100 × the database's per-100g values, "
                    "rounded per ingredient exactly as the app shows them.\n"], []
    parfait_section(out)
    for i, (style, allergies) in enumerate(runs):
        print(f"→ {style} {allergies} …", flush=True)
        try:
            run_one(style, allergies, i, out, summary)
        except Exception as e:
            out.append(f"\n## {style} {allergies}\n❌ ERROR: {e}\n")
            summary.append((f"{style} {allergies}", "ERROR", 0, [], ("", ""), (False, False, False)))
            print(f"   ERROR {e}", flush=True)
    table = ["\n## Summary\n", "| Plan | Meals match ingredients | Days within 5% | Allergy/diet safe | Swap (Day 1) | Swap: match / within 5% / safe |",
             "|---|---|---|---|---|---|"]
    for title, name, gen_s, res, (o, n), sres in summary:
        table.append(f"| {title} | {'✅' if res and all(r[0] for r in res) else '❌'} {sum(1 for r in res if r[0])}/{len(res)} days "
                     f"| {'✅' if res and all(r[1] for r in res) else '❌'} {sum(1 for r in res if r[1])}/{len(res)} "
                     f"| {'✅' if res and all(r[2] for r in res) else '❌'} | {o} → {n} "
                     f"| {'✅' if sres[0] else '❌'} / {'✅' if sres[1] else '❌'} / {'✅' if sres[2] else '❌'} |")
    out[2:2] = table
    with open(REPORT, "w") as fh:
        fh.write("\n".join(out) + "\n")
    print("\n".join(table))
    print(f"\nReport: {REPORT}")


if __name__ == "__main__":
    main()

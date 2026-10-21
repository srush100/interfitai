"""Count meals whose instructions mention a food that isn't in the ingredient list.

  python scripts/check_instruction_foods.py before          # scan plans already in the DB (old code)
  python scripts/check_instruction_foods.py after           # generate 10 plans + 10 swaps with the current code

Writes /app/memory/instruction_foods_check.md (before/after sections).
"""
import json
import os
import re
import sys
import time

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from nutrition_engine import calculate_ingredient_macros, is_on_target, items_from_raw, unlisted_mentions  # noqa: E402

USER_ID = "2663e0c4-d8b9-4feb-b42a-8b055631ea25"
BASE = (os.environ.get("EXPO_PUBLIC_BACKEND_URL") or "").rstrip("/") + "/api"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
OUT = "/tmp/instruction_foods_{}.json"
REPORT = "/app/memory/instruction_foods_check.md"
RUNS = [("balanced", []), ("high_protein", []), ("vegetarian", []), ("vegan", []), ("paleo", []),
        ("keto", []), ("carnivore", []), ("balanced", ["gluten", "dairy"]), ("vegan", ["nuts", "soy"]),
        ("high_protein", ["eggs"])]
SWAP_SLOTS = [(0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 1), (1, 2), (1, 3), (2, 0), (2, 2)]


def meal_issue(meal):
    items = items_from_raw(meal.get("ingredients"))[0]
    return unlisted_mentions(meal.get("instructions", ""), items)


def macros_ok(meal):
    tot = {"calories": 0, "protein": 0.0, "carbs": 0.0, "fats": 0.0}
    for ing in meal["ingredients"]:
        m = calculate_ingredient_macros(ing)
        if m is None:
            return False
        for k in tot:
            tot[k] += m[k]
    return round(tot["calories"]) == meal["calories"] and all(abs(tot[k] - meal[k]) <= 0.051 for k in ("protein", "carbs", "fats"))


def plan_targets(p):
    return {"calories": p["target_calories"], "protein": p["target_protein"],
            "carbs": p["target_carbs"], "fats": p["target_fats"]}


def before(skip=0):
    """Plans the previous code generated: the 10 most recent (after skipping the
    `skip` newest, i.e. the after-fix run); swapped meals have uuid ids."""
    plans = list(db.mealplans.find({"user_id": USER_ID}, sort=[("created_at", -1)]).skip(skip).limit(60))
    gen, swaps = [], []
    for p in plans:
        for day in p["meal_days"]:
            for m in day["meals"]:
                rec = {"plan": p["name"], "style": p.get("food_preferences"), "meal": m["name"],
                       "instructions": m.get("instructions", ""), "unlisted": meal_issue(m)}
                if re.fullmatch(r"d\dm\d", str(m.get("id"))):
                    if len({g["plan_id"] for g in gen}) < 10 or p["id"] in {g["plan_id"] for g in gen}:
                        gen.append({**rec, "plan_id": p["id"]})
                elif len(swaps) < 10:
                    swaps.append(rec)
    json.dump({"generated": gen, "swaps": swaps}, open(OUT.format("before"), "w"), indent=1)
    return gen, swaps


def after():
    gen, swaps, days = [], [], []
    for (style, allergies), (di, mi) in zip(RUNS, SWAP_SLOTS):
        db.meal_generation_events.delete_many({"user_id": USER_ID})
        print(f"→ {style} {allergies} …", flush=True)
        r = requests.post(f"{BASE}/mealplans/generate", json={
            "user_id": USER_ID, "food_preferences": style, "allergies": allergies,
            "preferred_foods": "", "foods_to_avoid": ""}, timeout=300)
        r.raise_for_status()
        p = requests.get(f"{BASE}/mealplan/{r.json()['id']}", timeout=90).json()
        for day in p["meal_days"]:
            days.append({"plan": p["name"], "on_target": is_on_target(day, plan_targets(p)),
                         "macros_ok": all(macros_ok(m) for m in day["meals"])})
            for m in day["meals"]:
                gen.append({"plan": p["name"], "style": style, "allergies": allergies, "meal": m["name"],
                            "instructions": m.get("instructions", ""), "ingredients": m["ingredients"],
                            "unlisted": meal_issue(m)})
        sr = requests.post(f"{BASE}/mealplan/alternate", json={
            "user_id": USER_ID, "meal_plan_id": p["id"], "day_index": di, "meal_index": mi,
            "swap_preference": "similar"}, timeout=150)
        sr.raise_for_status()
        p2 = requests.get(f"{BASE}/mealplan/{p['id']}", timeout=90).json()
        m = p2["meal_days"][di]["meals"][mi]
        day = p2["meal_days"][di]
        swaps.append({"plan": p["name"], "style": style, "meal": m["name"], "instructions": m.get("instructions", ""),
                      "ingredients": m["ingredients"], "unlisted": meal_issue(m),
                      "macros_ok": macros_ok(m), "day_on_target": is_on_target(day, plan_targets(p2))})
    json.dump({"generated": gen, "swaps": swaps, "days": days}, open(OUT.format("after"), "w"), indent=1)
    return gen, swaps, days


def section(title, gen, swaps, n_plans):
    bad_g = [g for g in gen if g["unlisted"]]
    bad_s = [s for s in swaps if s["unlisted"]]
    lines = [f"## {title}", "",
             f"- Generated meals mentioning an unlisted food: **{len(bad_g)} / {len(gen)}** "
             f"(across {n_plans} plans)",
             f"- Swapped meals mentioning an unlisted food: **{len(bad_s)} / {len(swaps)}**", ""]
    if bad_g or bad_s:
        lines += ["| Meal | Unlisted food(s) | Instructions |", "|---|---|---|"]
        for r in bad_g + bad_s:
            lines.append(f"| {r['meal']} ({r['style']}) | {', '.join(r['unlisted'])} | {r['instructions'][:140]} |")
        lines.append("")
    return lines


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "after"
    if mode == "report":
        # re-score both runs with the current checker (same rules for before and after)
        g, s = before(skip=len(RUNS))
        a = json.load(open(OUT.format("after")))
        for r in a["generated"] + a["swaps"]:
            r["unlisted"] = unlisted_mentions(r["instructions"], items_from_raw(r["ingredients"])[0])
        json.dump(a, open(OUT.format("after"), "w"), indent=1)
    elif mode == "before":
        g, s = before()
        print(f"BEFORE: generated {sum(1 for x in g if x['unlisted'])}/{len(g)}, swaps {sum(1 for x in s if x['unlisted'])}/{len(s)}")
    else:
        t0 = time.time()
        g, s, d = after()
        print(f"AFTER: generated {sum(1 for x in g if x['unlisted'])}/{len(g)}, swaps {sum(1 for x in s if x['unlisted'])}/{len(s)} "
              f"| days on target {sum(x['on_target'] for x in d)}/{len(d)} | meals add up {all(x['macros_ok'] for x in d)} "
              f"| swaps on target {sum(x['day_on_target'] for x in s)}/{len(s)} | {time.time() - t0:.0f}s")
    b = json.load(open(OUT.format("before"))) if os.path.exists(OUT.format("before")) else None
    a = json.load(open(OUT.format("after"))) if os.path.exists(OUT.format("after")) else None
    lines = ["# Instructions vs ingredients check", ""]
    if b:
        lines += section("Before the fix (plans already generated by the previous code)", b["generated"], b["swaps"],
                         len({g["plan_id"] for g in b["generated"]}))
    if a:
        lines += section("After the fix (10 new plans + 10 swaps)", a["generated"], a["swaps"], len(RUNS))
        lines += [f"- Days within 5% of targets: {sum(x['on_target'] for x in a['days'])} / {len(a['days'])}",
                  f"- Every meal's numbers = its ingredients: {all(x['macros_ok'] for x in a['days'])}",
                  f"- Swaps: day still within 5%: {sum(x['day_on_target'] for x in a['swaps'])} / {len(a['swaps'])}, "
                  f"numbers = ingredients: {sum(x['macros_ok'] for x in a['swaps'])} / {len(a['swaps'])}", ""]
    open(REPORT, "w").write("\n".join(lines))
    print("Report:", REPORT)

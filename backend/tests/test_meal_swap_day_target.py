"""
Meal swaps keep the DAY on target: when no dish fits around the other meals as
they are, the other meals' portions are re-tuned a little (and shown).
"""
import asyncio, copy
import pytest
import server
from server import calculate_macros

class Cur:
    def __init__(s, d): s.d=d
    def sort(s,*a,**k): return s
    def limit(s,n): return s
    async def to_list(s,n=None): return s.d
def match(doc,q):
    for k,v in q.items():
        if isinstance(v,dict):
            val=doc.get(k)
            for op,x in v.items():
                if op=="$gte" and not (val is not None and val>=x): return False
                if op=="$ne" and val==x: return False
                if op=="$in" and val not in x: return False
        elif doc.get(k)!=v: return False
    return True
class Coll:
    def __init__(s): s.docs=[]
    async def find_one(s,q,*a,**k): return next((copy.deepcopy(d) for d in s.docs if match(d,q)),None)
    async def insert_one(s,d): s.docs.append(copy.deepcopy(d))
    async def update_one(s,q,u,upsert=False):
        for d in s.docs:
            if match(d,q): d.update(copy.deepcopy(u.get("$set",{}))); return
        if upsert: s.docs.append({**q,**u.get("$set",{})})
    async def count_documents(s,q): return sum(match(d,q) for d in s.docs)
    def find(s,q=None,*a,**k): return Cur([copy.deepcopy(d) for d in s.docs if match(d,q or {})])
    async def delete_one(s,q): pass
class DB:
    def __init__(s): s.c={}
    def __getattr__(s,n):
        if n=="c": raise AttributeError
        return s.c.setdefault(n,Coll())


@pytest.mark.parametrize("style", ["vegetarian", "high_protein"])
def test_every_swap_keeps_the_day_on_target(monkeypatch, style):
    db = DB()
    monkeypatch.setattr(server, "db", db)

    async def no_ai(*a, **k):
        raise RuntimeError("AI offline in tests: meal templates are used")

    async def ok(_):
        return {"has_access": True}
    monkeypatch.setattr(server, "call_claude_sonnet", no_ai)
    monkeypatch.setattr(server, "call_claude_haiku", no_ai)
    monkeypatch.setattr(server, "check_subscription_access", ok)
    m = calculate_macros(82.5, 178, 30, "male", "moderate", "weight_loss", False)

    async def go():
        await db.profiles.insert_one({"id": "u", "email": "x@y.com", "weight": 82.5, "height": 178, "age": 30,
                                      "gender": "male", "activity_level": "moderate", "goal": "weight_loss",
                                      "calculated_macros": m})
        plan = await server.generate_meal_plan(server.MealPlanGenerateRequest(
            user_id="u", food_preferences=style, allergies=[], foods_to_avoid=""))
        plan = plan.model_dump() if hasattr(plan, "model_dump") else plan
        results = []
        for di, day in enumerate(plan["meal_days"]):
            for mi in range(len(day["meals"])):
                r = await server.generate_alternate_meal(server.AlternateMealRequest(
                    meal_plan_id=plan["id"], user_id="u", day_index=di, meal_index=mi, swap_preference="similar"))
                results.append(r)
        saved = await db.mealplans.find_one({"id": plan["id"]})
        return results, saved
    results, saved = asyncio.run(go())
    assert all(r["day_totals"]["on_target"] for r in results)
    for day in saved["meal_days"]:                       # what's stored matches what's shown
        assert day["on_target"]
        assert abs(day["total_calories"] - sum(x["calories"] for x in day["meals"])) <= 1

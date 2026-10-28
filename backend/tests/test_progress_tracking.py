"""
Progress tracking: streaks over rest days and in the user's time zone, empty
workouts, personal records (first time, bodyweight, full history), saved sets
following their exercise, phone step totals, and the body-weight log.
Uses a small in-memory stand-in for MongoDB.
"""
import asyncio
import copy
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

import server


# ── in-memory Mongo stand-in ──────────────────────────────────────────────
def _get(doc, path):
    vals = [doc]
    for part in path.split("."):
        nxt = []
        for v in vals:
            if isinstance(v, list):
                nxt += [x.get(part) for x in v if isinstance(x, dict)]
            elif isinstance(v, dict):
                nxt.append(v.get(part))
        vals = nxt
    flat = []
    for v in vals:
        flat += v if isinstance(v, list) else [v]
    return flat


def _match(doc, q):
    for k, cond in q.items():
        vals = _get(doc, k)
        if isinstance(cond, dict):
            if "$in" in cond and not any(v in cond["$in"] for v in vals):
                return False
            if "$gte" in cond and not any(v is not None and v >= cond["$gte"] for v in vals):
                return False
            if "$ne" in cond and cond["$ne"] in vals:
                return False
        elif cond not in vals:
            return False
    return True


class Cursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, key, direction=1):
        if isinstance(key, list):
            key, direction = key[0]
        self.docs.sort(key=lambda d: d.get(key), reverse=direction == -1)
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    async def to_list(self, n):
        return [copy.deepcopy(d) for d in (self.docs if n is None else self.docs[:n])]


class Coll:
    def __init__(self):
        self.docs = []

    def find(self, q=None, proj=None):
        return Cursor([d for d in self.docs if _match(d, q or {})])

    async def find_one(self, q, sort=None, **kw):
        c = self.find(q)
        if sort:
            c.sort(sort)
        return copy.deepcopy(c.docs[0]) if c.docs else None

    async def insert_one(self, doc):
        self.docs.append(copy.deepcopy(doc))

    async def count_documents(self, q):
        return len([d for d in self.docs if _match(d, q)])

    async def update_one(self, q, upd):
        for d in self.docs:
            if _match(d, q):
                d.update(copy.deepcopy(upd.get("$set", {})))
                return type("R", (), {"matched_count": 1})()
        return type("R", (), {"matched_count": 0})()

    async def replace_one(self, q, doc, upsert=False):
        for i, d in enumerate(self.docs):
            if _match(d, q):
                self.docs[i] = copy.deepcopy(doc)
                return
        if upsert:
            self.docs.append(copy.deepcopy(doc))

    async def delete_one(self, q):
        for i, d in enumerate(self.docs):
            if _match(d, q):
                self.docs.pop(i)
                return type("R", (), {"deleted_count": 1})()
        return type("R", (), {"deleted_count": 0})()


class FakeDB:
    def __init__(self):
        for name in ("workout_sessions", "workouts", "steps", "weight_logs", "profiles"):
            setattr(self, name, Coll())


@pytest.fixture
def db(monkeypatch):
    d = FakeDB()
    monkeypatch.setattr(server, "db", d)
    return d


def run(coro):
    return asyncio.run(coro)


def _ex(name, sets):
    return server.SessionExercise(exercise_name=name, sets=[
        server.SessionSet(set_number=i + 1, weight=w, reps=r, completed=c) for i, (w, r, c) in enumerate(sets)])


def _finish(db, exercises, local_date="2026-10-05", workout_id="w1"):
    if not db.workouts.docs:
        db.workouts.docs.append({"id": workout_id, "user_id": "u", "days_per_week": 3, "performance": {},
                                 "updated_at": datetime(2026, 1, 1)})
    req = server.CompleteSessionRequest(user_id="u", day_index=0, completed_exercises=exercises,
                                        local_date=local_date)
    return run(server.complete_workout_session(workout_id, req))


# ── streaks and days ─────────────────────────────────────────────────────
def _session(day, done=True):
    return {"user_id": "u", "date": datetime.strptime(day, "%Y-%m-%d") + timedelta(hours=8),
            "local_date": day,
            "completed_exercises": [{"exercise_name": "Squat", "sets": [{"completed": done, "weight": 100, "reps": 5}]}]}


def _stats(db, today, tz=0):
    class FakeDT(datetime):
        @classmethod
        def utcnow(cls):
            return today
    orig = server.datetime
    server.datetime = FakeDT
    try:
        return run(server.get_workout_stats("u", tz_offset_minutes=tz))
    finally:
        server.datetime = orig


def test_streak_survives_planned_rest_days(db):
    db.workouts.docs.append({"user_id": "u", "days_per_week": 3, "updated_at": datetime(2026, 1, 1)})
    for d in ["2026-10-05", "2026-10-07", "2026-10-09", "2026-10-12", "2026-10-14", "2026-10-16"]:
        db.workout_sessions.docs.append(_session(d))
    # Sunday and Monday morning after a Mon/Wed/Fri week
    assert _stats(db, datetime(2026, 10, 18, 2))["current_streak"] == 6
    assert _stats(db, datetime(2026, 10, 19, 2))["current_streak"] == 6
    # a whole missed week ends it
    assert _stats(db, datetime(2026, 10, 25, 2))["current_streak"] == 0


def test_week_uses_users_day(db):
    db.workouts.docs.append({"user_id": "u", "days_per_week": 3, "updated_at": datetime(2026, 1, 1)})
    # Monday 8am Sydney = Sunday 21:00 UTC; the app sends its local date
    s = _session("2026-10-19")
    s["date"] = datetime(2026, 10, 18, 21)
    db.workout_sessions.docs.append(s)
    st = _stats(db, datetime(2026, 10, 19, 1), tz=660)   # Monday midday in Sydney
    assert st["sessions_this_week"] == 1


def test_old_sessions_without_local_date_use_offset(db):
    db.workouts.docs.append({"user_id": "u", "days_per_week": 3, "updated_at": datetime(2026, 1, 1)})
    s = _session("2026-10-19")
    s.pop("local_date")
    s["date"] = datetime(2026, 10, 18, 21)        # Monday 8am in Sydney
    db.workout_sessions.docs.append(s)
    assert _stats(db, datetime(2026, 10, 19, 1), tz=660)["sessions_this_week"] == 1
    assert _stats(db, datetime(2026, 10, 19, 1), tz=0)["sessions_this_week"] == 0


def test_empty_sessions_do_not_count(db):
    db.workouts.docs.append({"user_id": "u", "days_per_week": 3, "updated_at": datetime(2026, 1, 1)})
    db.workout_sessions.docs.append(_session("2026-10-19", done=False))
    st = _stats(db, datetime(2026, 10, 19, 12))
    assert st["total_sessions"] == 0 and st["current_streak"] == 0


def test_finish_needs_a_ticked_set(db):
    with pytest.raises(HTTPException) as e:
        _finish(db, [_ex("Squat", [(100, 5, False)])])
    assert e.value.status_code == 422


# ── personal records ─────────────────────────────────────────────────────
def test_first_time_is_not_a_record(db):
    r = _finish(db, [_ex("Bench Press", [(60, 8, True)])])
    assert r["personal_records"] == []


def test_weight_and_rep_records(db):
    _finish(db, [_ex("Bench Press", [(60, 8, True), (62.5, 6, True)])], "2026-10-05")
    r = _finish(db, [_ex("Bench Press", [(65, 3, True)])], "2026-10-07")
    assert r["personal_records"][0]["type"] == "weight" and r["personal_records"][0]["new_value"] == 65
    # more reps at a weight already lifted
    r = _finish(db, [_ex("Bench Press", [(62.5, 8, True)])], "2026-10-09")
    assert r["personal_records"][0]["type"] == "reps" and r["personal_records"][0]["previous_value"] == 6
    # 8 reps at 60 is not a record: 8 reps at 62.5 already done
    r = _finish(db, [_ex("Bench Press", [(60, 8, True)])], "2026-10-12")
    assert r["personal_records"] == []


def test_bodyweight_rep_records(db):
    _finish(db, [_ex("Pull-Up", [(None, 8, True)])], "2026-10-05")
    r = _finish(db, [_ex("Pull-Up", [(None, 10, True)])], "2026-10-07")
    assert r["personal_records"][0] == {"exercise_name": "Pull-Up", "type": "reps", "new_value": 10,
                                        "previous_value": 8, "reps": 10, "weight": None}


def test_records_use_full_history(db):
    # an old best from more than 100 sessions ago still counts
    _finish(db, [_ex("Squat", [(140, 3, True)])], "2025-01-01")
    for i in range(120):
        _finish(db, [_ex("Leg Press", [(100, 10, True)])], f"2025-06-{(i % 28) + 1:02d}")
    r = _finish(db, [_ex("Squat", [(120, 3, True)])], "2026-10-05")
    assert r["personal_records"] == []


def test_weights_rounded_to_2_decimals(db):
    r = _finish(db, [_ex("Curl", [(45.359237, 10, True)])])
    assert r["completed_exercises"][0]["sets"][0]["weight"] == 45.36


def test_all_time_records_list(db):
    _finish(db, [_ex("Bench Press", [(60, 8, True), (70, 3, True)]), _ex("Pull-Up", [(None, 12, True)])], "2026-10-05")
    recs = {r["exercise_name"]: r for r in run(server.get_personal_records("u"))}
    assert recs["Bench Press"]["best_weight"] == 70 and recs["Bench Press"]["best_reps_at_weight"] == 3
    assert recs["Bench Press"]["date"] == "2026-10-05"
    assert recs["Pull-Up"]["best_bodyweight_reps"] == 12 and recs["Pull-Up"]["best_weight"] == 0


# ── saved sets follow their exercise ─────────────────────────────────────
def test_remap_on_reorder_delete_replace():
    perf = {"0-0-0": "A", "0-1-0": "B", "0-2-0": "C", "1-0-0": "other day"}
    swapped = server._remap_day_performance(perf, 0, {0: 1, 1: 0})
    assert swapped["0-0-0"] == "B" and swapped["0-1-0"] == "A" and swapped["1-0-0"] == "other day"
    deleted = server._remap_day_performance(perf, 0, {0: 0, 1: None, 2: 1})
    assert deleted == {"0-0-0": "A", "0-1-0": "C", "1-0-0": "other day"}
    replaced = server._remap_day_performance(perf, 0, {1: None})
    assert "0-1-0" not in replaced and replaced["0-2-0"] == "C"


def test_reorder_endpoint_moves_saved_sets(db):
    db.workouts.docs.append({"id": "w", "workout_days": [{"exercises": [{"name": "A"}, {"name": "B"}]}],
                             "performance": {"0-0-0": {"weight": "60"}, "0-1-0": {"weight": "20"}}})
    run(server.reorder_exercises("w", server.ReorderExercisesRequest(day_index=0, exercise_order=[1, 0])))
    w = db.workouts.docs[0]
    assert w["workout_days"][0]["exercises"][0]["name"] == "B"
    assert w["performance"]["0-0-0"] == {"weight": "20"}


# ── steps ────────────────────────────────────────────────────────────────
def test_phone_steps_are_a_daily_total(db):
    for n in (3000, 5000, 5000):
        run(server.log_steps("u", n, date="2026-10-21"))
    assert db.steps.docs[0]["steps"] == 5000
    run(server.log_steps("u", 1000, source="manual", date="2026-10-21"))
    assert db.steps.docs[0]["steps"] == 6000


# ── weight log ───────────────────────────────────────────────────────────
def _profile(db, weight=90.0):
    db.profiles.docs.append({"id": "u", "weight": weight, "height": 180, "age": 30, "gender": "male",
                             "activity_level": "moderate", "goal": "lose_fat", "calculated_macros": {"calories": 1}})


def test_weight_log_one_per_day_and_profile_follows_average(db):
    _profile(db)
    run(server.log_weight(server.WeightLogRequest(user_id="u", weight_kg=89.0, date="2026-10-19")))
    run(server.log_weight(server.WeightLogRequest(user_id="u", weight_kg=88.6, date="2026-10-20")))
    run(server.log_weight(server.WeightLogRequest(user_id="u", weight_kg=88.0, date="2026-10-20")))  # replaces
    logs = run(server.get_weight_logs("u", days=36500))
    assert [l["weight_kg"] for l in logs] == [89.0, 88.0]
    prof = db.profiles.docs[0]
    assert prof["weight"] == 88.5 and prof["calculated_macros"]["calories"] != 1


def test_small_daily_swings_dont_move_targets(db):
    _profile(db, weight=88.5)
    run(server.log_weight(server.WeightLogRequest(user_id="u", weight_kg=88.8, date="2026-10-21")))
    assert db.profiles.docs[0]["weight"] == 88.5 and db.profiles.docs[0]["calculated_macros"]["calories"] == 1


def test_weight_out_of_range_rejected(db):
    with pytest.raises(HTTPException):
        run(server.log_weight(server.WeightLogRequest(user_id="u", weight_kg=5, date="2026-10-21")))


def test_delete_weight_entry(db):
    _profile(db)
    e = run(server.log_weight(server.WeightLogRequest(user_id="u", weight_kg=89, date="2026-10-21")))
    run(server.delete_weight_log(e.id, user_id="u"))
    assert db.weight_logs.docs == []


# ── macro targets: protein for higher BMI, safe calorie floor ─────────────
@pytest.mark.parametrize("args, protein", [
    ((130, 175, 40, "male", "sedentary", "weight_loss"), 168),     # healthy-weight reference
    ((110, 165, 35, "female", "light", "weight_loss"), 149),
    ((115, 180, 28, "male", "moderate", "muscle_building"), 162),
    ((80, 180, 30, "male", "moderate", "weight_loss"), 160),       # lean-mass estimate
])
def test_protein_uses_healthy_weight_reference_above_bmi_30(args, protein):
    assert server.calculate_macros(*args)["protein"] == protein


# ── protein from estimated lean mass (women get less than men, same stats) ──
@pytest.mark.parametrize("args, protein", [
    ((85, 178, 26, "female", "moderate", "weight_loss"), 149),     # was 187g (1g/lb)
    ((85, 178, 26, "male", "moderate", "weight_loss"), 164),
    ((60, 165, 28, "female", "moderate", "weight_loss"), 117),
    ((101, 179, 27, "male", "moderate", "weight_loss"), 176),      # BMI 31.5: unchanged
])
def test_protein_from_estimated_lean_mass(args, protein):
    m = server.calculate_macros(*args)
    assert m["protein"] == protein
    assert m["protein"] * 4 + m["carbs"] * 4 + m["fats"] * 9 == pytest.approx(m["calories"], abs=6)


def test_protein_never_raised_and_mostly_muscle_keeps_full_weight():
    for w, h, sex in ((50, 160, "female"), (65, 190, "male"), (150, 165, "female"), (120, 200, "male")):
        for goal, per_kg in (("weight_loss", 2.2), ("maintenance", 1.8), ("muscle_building", 2.0)):
            m = server.calculate_macros(w, h, 30, sex, "moderate", goal)
            bmi = w / (h / 100) ** 2                     # healthy-weight reference over BMI 30
            ref = min(w, 25 * (h / 100) ** 2) if bmi > 30 else w
            assert round(ref * 1.5) <= m["protein"] <= round(ref * per_kg)
    ruby = server.calculate_macros(85, 178, 26, "female", "moderate", "weight_loss", True)
    assert ruby["protein"] == 187 and ruby["protein_from_lean_mass"] is False
    assert server.calculate_macros(85, 178, 26, "female", "moderate", "weight_loss")["protein_from_lean_mass"] is True


@pytest.mark.parametrize("args, calories, floor", [
    ((50, 155, 55, "female", "sedentary", "weight_loss"), 1200, True),
    ((52, 160, 62, "female", "light", "weight_loss"), 1200, True),
    ((58, 163, 70, "male", "sedentary", "weight_loss"), 1500, True),   # capped at maintenance (1504)
    ((130, 175, 40, "male", "sedentary", "weight_loss"), 2199, True),  # floor = BMR, 17% deficit
    ((80, 180, 30, "male", "moderate", "weight_loss"), 2207, False),
    ((60, 165, 30, "female", "light", "weight_loss"), 1452, False),
])
def test_weight_loss_calorie_floor(args, calories, floor):
    m = server.calculate_macros(*args)
    assert m["calories"] == calories and m["calorie_floor_applied"] == floor
    assert m["calories"] <= m["tdee"]


# ── website Stripe checkout matches the app's plans ──────────────────────
def test_website_checkout_uses_app_prices(db, monkeypatch):
    db.profiles.docs.append({"id": "u", "email": "a@b.com", "name": "A", "stripe_customer_id": "cus_1"})
    made = []

    class Session:
        @staticmethod
        def create(**kw):
            made.append(kw)
            return type("S", (), {"url": "https://checkout", "id": "cs_1"})()

    monkeypatch.setattr(server, "STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(server.stripe, "Customer", type("C", (), {"retrieve": staticmethod(lambda i: type("X", (), {"id": i})())}))
    monkeypatch.setattr(server.stripe.checkout, "Session", Session)
    for plan in ("monthly", "yearly"):
        run(server.create_stripe_checkout_session("u", plan, "https://s", "https://c"))
    monthly, yearly = made
    assert monthly["line_items"][0]["price_data"]["unit_amount"] == 1499
    assert monthly["line_items"][0]["price_data"]["recurring"] == {"interval": "month"}
    assert monthly["subscription_data"]["trial_period_days"] == 7
    assert yearly["line_items"][0]["price_data"]["unit_amount"] == 9999
    with pytest.raises(HTTPException):
        run(server.create_stripe_checkout_session("u", "quarterly", "https://s", "https://c"))


def test_monthly_website_payment_buys_a_month():
    assert server._stripe_plan_days("monthly") == 31
    assert server._stripe_plan_days("yearly") == 365


# ── "Is your weight mostly muscle?" (asked only when BMI is over 30) ──────
@pytest.mark.parametrize("args, muscle, protein", [
    ((120, 185, 30, "male", "active", "muscle_building"), True, 240),    # muscular lifter: full weight
    ((120, 185, 30, "male", "active", "muscle_building"), False, 171),   # default: healthy-weight reference
    ((120, 185, 30, "male", "active", "weight_loss"), True, 260),        # 264 → higher cap 260
    ((130, 175, 40, "male", "sedentary", "weight_loss"), None, 168),     # not asked / not sure
    ((80, 180, 30, "male", "moderate", "weight_loss"), True, 176),       # BMI under 30: answer ignored
])
def test_mostly_muscle_protein(args, muscle, protein):
    assert server.calculate_macros(*args, mostly_muscle=muscle)["protein"] == protein


def test_changing_the_answer_updates_targets(db):
    db.profiles.docs.append({"id": "u", "weight": 120, "height": 185, "age": 30, "gender": "male",
                             "activity_level": "active", "goal": "muscle_building",
                             "calculated_macros": server.calculate_macros(120, 185, 30, "male", "active", "muscle_building")})
    assert db.profiles.docs[0]["calculated_macros"]["protein"] == 171
    run(server.update_profile("u", server.UserProfileUpdate(mostly_muscle=True)))
    assert db.profiles.docs[0]["calculated_macros"]["protein"] == 240


# ── body analyzer prompt ─────────────────────────────────────────────────
def test_body_analysis_prompt_and_retry_keep_context(db, monkeypatch):
    db.profiles.docs.append({"id": "u", "weight": 80, "height": 180, "age": 30, "gender": "male",
                             "goal": "weight_loss", "calorie_adjustment": -100,
                             "calculated_macros": {"calories": 2207, "protein": 176}})
    db.body_analyses = Coll()

    async def paid(_uid):
        return {"has_access": True}
    monkeypatch.setattr(server, "check_subscription_access", paid)
    calls = []

    async def fake(**kw):
        calls.append(kw)
        if len(calls) == 1:
            return "Sure! Here's your analysis: not json"
        return '{"overall_assessment": "ok", "estimated_progress_score": 6, "analysis_confidence": "medium"}'
    monkeypatch.setattr(server, "call_claude_sonnet", fake)

    req = server.BodyAnalysisRequest(user_id="u", before_image_base64="b", after_image_base64="a",
                                     time_period="3 months")
    out = run(server.analyze_body_progress(req))
    assert out["analysis"]["estimated_progress_score"] == 6
    first, retry = calls
    assert "FIRST image is BEFORE" in first["system_message"] and "Image 1 is BEFORE" in first["user_message"]
    assert "2107 kcal, 176g protein" in first["system_message"]          # target incl. adjustment
    assert "under 18" in first["system_message"]
    assert retry["system_message"].startswith(first["system_message"])   # retry keeps all context
    assert first["temperature"] == retry["temperature"] == 0.3


# ── Ask AI chat ──────────────────────────────────────────────────────────
class _FakeChat:
    seen = []
    fail = False

    def __init__(self, api_key=None, session_id=None, system_message=None, initial_messages=None):
        _FakeChat.seen.append(initial_messages)

    def with_model(self, *a):
        return self

    def with_params(self, **k):
        return self

    async def send_message(self, msg):
        if _FakeChat.fail:
            raise RuntimeError("upstream budget exceeded: key sk-123")
        return "Aim for your 176g protein target."


@pytest.fixture
def chat_env(db, monkeypatch):
    db.chat_history = Coll()
    _FakeChat.seen, _FakeChat.fail = [], False
    monkeypatch.setattr(server, "LlmChat", _FakeChat)
    access = {"has_access": True}

    async def check(_uid):
        return access
    monkeypatch.setattr(server, "check_subscription_access", check)
    db.profiles.docs.append({"id": "u", "age": 30, "gender": "male", "height": 180, "weight": 80,
                             "activity_level": "moderate", "goal": "weight_loss", "calorie_adjustment": -100,
                             "calculated_macros": {"calories": 2207, "protein": 176, "carbs": 239, "fats": 61}})
    db.workouts.docs.append({"user_id": "u", "name": "Fat Loss Plan", "days_per_week": 4,
                             "session_duration_minutes": 45, "fitness_level": "intermediate",
                             "injuries": ["knee pain"], "created_at": datetime(2026, 10, 1)})
    return db, access


def _chat(text="How much protein should I eat?"):
    return run(server.chat_with_ai(server.ChatRequest(user_id="u", message=text)))


def test_chat_knows_the_apps_targets_and_injuries(chat_env):
    reply = _chat()
    system = _FakeChat.seen[0][0]["content"]
    assert "2107 kcal, 176g protein, 214g carbs, 61g fat" in system
    assert "knee pain" in system and "never invent different numbers" in system
    assert "steroids" in system and "1,200 kcal" in system
    assert reply.content.startswith("Aim for")


def test_chat_needs_premium(chat_env):
    _, access = chat_env
    access["has_access"] = False
    with pytest.raises(HTTPException) as e:
        _chat()
    assert e.value.status_code == 403


def test_chat_daily_limit(chat_env):
    db, _ = chat_env
    for _ in range(server.CHAT_DAILY_LIMIT):
        db.chat_history.docs.append({"user_id": "u", "role": "user", "content": "x", "created_at": datetime.utcnow()})
    with pytest.raises(HTTPException) as e:
        _chat()
    assert e.value.status_code == 429


def test_removed_messages_dont_steer_answers(chat_env):
    db, _ = chat_env
    db.chat_history.docs += [
        {"user_id": "u", "role": "user", "content": "hidden question", "chat_visible": False, "created_at": datetime.utcnow()},
        {"user_id": "u", "role": "user", "content": "visible question", "created_at": datetime.utcnow()},
    ]
    _chat()
    contents = [m["content"] for m in _FakeChat.seen[0][1:]]
    assert "visible question" in contents and "hidden question" not in contents


def test_chat_errors_are_friendly(chat_env):
    _FakeChat.fail = True
    with pytest.raises(HTTPException) as e:
        _chat()
    assert e.value.status_code == 503 and "sk-123" not in str(e.value.detail)


def test_chat_rejects_huge_messages(chat_env):
    with pytest.raises(HTTPException) as e:
        _chat("x" * 5000)
    assert e.value.status_code == 400


@pytest.mark.parametrize("label", ["Female", "FEMALE", " female ", "F", "woman"])
def test_macros_female_spellings(label):
    from server import calculate_macros
    exact = calculate_macros(70, 170, 30, "female", "moderate", "weight_loss")
    assert calculate_macros(70, 170, 30, label, "moderate", "weight_loss")["calories"] == exact["calories"]
    assert exact["calories"] < calculate_macros(70, 170, 30, "Male", "moderate", "weight_loss")["calories"]


def test_protein_at_most_40_percent_of_calories():
    m = server.calculate_macros(110, 150, 60, "female", "sedentary", "weight_loss", True)
    assert m["protein"] * 4 <= m["calories"] * 0.40 + 2 and m["carbs"] * 4 >= m["calories"] * 0.30
    # real lifters are unaffected
    assert server.calculate_macros(101, 179, 27, "male", "moderate", "weight_loss", True)["protein"] == 222

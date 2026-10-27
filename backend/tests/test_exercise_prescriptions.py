"""
Holds, carries and one-sided exercises get prescriptions that match how they're
measured, and lifters past beginner get loaded core work instead of the plank.
"""
import pytest

from server import EliteCoachingEngine, WorkoutGenerateRequest

E = EliteCoachingEngine


@pytest.mark.parametrize("name, level, expected", [
    ("Plank", "beginner", "20-30s hold"),
    ("Plank", "intermediate", "30-45s hold"),
    ("Plank", "advanced", "45-60s hold"),
    ("Side Plank", "intermediate", "30-45s hold each side"),
    ("Wall Sit", "intermediate", "30-45s hold"),
    ("Farmer's Carry", "intermediate", "30-40 m walk"),
    ("Suitcase Carry", "intermediate", "30-40 m walk each side"),
    ("Dead Bug", "intermediate", "10-15 each side"),
    ("Ab Rollout", "intermediate", "10-15"),
])
def test_reps_follow_the_exercise(name, level, expected):
    assert E.reps_for_exercise(name, "10-15", level) == expected


def test_per_side_reps_not_doubled():
    assert E.reps_for_exercise("Dead Bug", "10-12 each", "beginner") == "10-12 each"


@pytest.mark.parametrize("level, equipment, first_three", [
    ("intermediate", ["full_gym"], ["Ab Rollout", "Pallof Press", "Cable Wood Chop"]),
    ("advanced", ["full_gym"], ["Ab Rollout", "Pallof Press", "Cable Wood Chop"]),
    ("intermediate", ["dumbbells"], ["Weighted Dead Bug", "Renegade Row", "Plank"]),
    ("beginner", ["full_gym"], ["Plank", "Dead Bug", "Bird Dog"]),
])
def test_core_options_by_level(level, equipment, first_three):
    opts = E().get_exercise_options("core_stability", equipment, "weights", [], level)
    assert opts[:3] == first_three


def test_build_muscle_quad_day_core_is_not_a_plank():
    bp = E().build_blueprint(WorkoutGenerateRequest(
        user_id="u", goal="build_muscle", training_style="weights", focus_areas=["full_body"],
        equipment=["full_gym"], days_per_week=4, duration_minutes=60, fitness_level="intermediate"))
    core = [s for d in bp["day_blueprints"] for s in d["slots"] if s["pattern"] == "core_stability"]
    assert core and all("Plank" not in s["options"][:3] for s in core)


# ── Advanced lifters: 4 sets on main lifts, longer rest, Romanian deadlift ──
def _bp(goal, days=5, level="advanced"):
    return E().build_blueprint(WorkoutGenerateRequest(
        user_id="u", goal=goal, training_style="weights", focus_areas=["full_body"],
        equipment=["full_gym"], days_per_week=days, duration_minutes=60, fitness_level=level))


@pytest.mark.parametrize("goal", ["build_muscle", "body_recomp", "lose_fat", "general_fitness"])
def test_main_lifts_capped_at_4_sets(goal):
    slots = [s for d in _bp(goal)["day_blueprints"] for s in d["slots"]]
    assert max(s["sets"] for s in slots if s["type"] == "primary_compound") == 4


def test_strength_keeps_5_sets():
    slots = [s for d in _bp("strength", days=4)["day_blueprints"] for s in d["slots"]]
    assert max(s["sets"] for s in slots if s["type"] == "primary_compound") == 5


@pytest.mark.parametrize("goal", ["build_muscle", "body_recomp"])
def test_main_lift_rest_is_2_30(goal):
    slots = [s for d in _bp(goal)["day_blueprints"] for s in d["slots"]]
    assert {s["rest_seconds"] for s in slots if s["type"] == "primary_compound"} == {150}


def test_hip_day_leads_with_romanian_deadlift():
    hip = next(d for d in _bp("build_muscle")["day_blueprints"] if "Hip" in d["label"])
    hinge = next(s for s in hip["slots"] if s["pattern"] == "hip_hinge")
    assert hinge["options"][0] == "Romanian Deadlift"
    assert "Conventional Deadlift" not in hinge["options"][:3]


def test_bench_press_repeats_across_the_week():
    firsts = [s["options"][0] for d in _bp("build_muscle")["day_blueprints"] for s in d["slots"]
              if s["type"] == "primary_compound" and s["pattern"] == "horizontal_push"]
    assert firsts.count("Barbell Bench Press") == 2


def test_recomp_upper_days_keep_biceps_triceps_and_side_delts():
    # Upper days with a cardio finisher still keep their arm and lateral-raise work:
    # the finisher is shortened before those exercises are dropped
    for d in _bp("body_recomp")["day_blueprints"]:
        pats = {s["pattern"] for s in d["slots"]}
        if d["archetype_id"] == "upper_full":
            assert {"bicep_curl", "tricep_push"} <= pats
        if any(s["type"] == "conditioning" for s in d["slots"]):
            assert d["slots"][-1]["type"] == "conditioning"


# ── "No deadlifts or squats" typed as a limitation ──
@pytest.mark.parametrize("text", [["no deadlifts or squats"], ["No deadlifts", "no squats"],
                                  ["can't squat or deadlift"]])
def test_named_movements_are_left_out(text):
    bp = E().build_blueprint(WorkoutGenerateRequest(
        user_id="u", goal="body_recomp", training_style="weights", focus_areas=["full_body"],
        equipment=["full_gym"], days_per_week=5, duration_minutes=60,
        fitness_level="intermediate", injuries=text))
    names = [o.lower() for d in bp["day_blueprints"] for s in d["slots"] for o in s["options"]]
    assert not [n for n in names if "squat" in n or "deadlift" in n or "rdl" in n]
    hinge = [s["options"] for d in bp["day_blueprints"] for s in d["slots"] if s["pattern"] == "hip_hinge"]
    assert hinge and all("Back Extension Machine" in o for o in hinge)
    assert any("Leg Press" in s["options"] for d in bp["day_blueprints"] for s in d["slots"]
               if s["pattern"] == "squat")


def test_lunges_kept_when_only_squats_are_ruled_out():
    opts = E().get_exercise_options("lunge", ["full_gym"], "weights", ["no squats"])
    assert opts and not any("squat" in o.lower() for o in opts)


@pytest.mark.parametrize("text, gone, kept", [
    ("no barbell bench press", "Barbell Bench Press", "Dumbbell Bench Press"),
    ("No skull crushers", "Skull Crusher", "Cable Tricep Pushdown"),
    ("no leg extensions please", "Leg Extension", "Spanish Squat"),
])
def test_one_named_exercise_is_left_out(text, gone, kept):
    pattern = {"Barbell Bench Press": "horizontal_push", "Skull Crusher": "tricep_push",
               "Leg Extension": "knee_extension"}[gone]
    opts = E().get_exercise_options(pattern, ["full_gym"], "weights", [text], "intermediate")
    assert gone not in opts and kept in opts


def test_injury_words_do_not_remove_exercises_by_name():
    assert E._blocked_movements(["lower back pain", "bad knee"]) == []


# ── Workout flow: each day is built like a coach would order it ──
def _days(goal="build_muscle", days=5, split="ai_choose", style="weights"):
    return E().build_blueprint(WorkoutGenerateRequest(
        user_id="u", goal=goal, training_style=style, focus_areas=["full_body"],
        equipment=["full_gym"], days_per_week=days, duration_minutes=60,
        fitness_level="intermediate", preferred_split=split))["day_blueprints"]


@pytest.mark.parametrize("goal, days, split", [
    ("body_recomp", 5, "upper_lower"), ("build_muscle", 5, "push_pull_legs"),
    ("build_muscle", 5, "bro_split"), ("strength", 3, "full_body"), ("lose_fat", 4, "ai_choose")])
def test_close_grip_is_never_the_main_chest_press(goal, days, split):
    for d in _days(goal, days, split):
        for s in d["slots"]:
            if s["pattern"] in ("horizontal_push", "incline_push"):
                assert "Close-Grip Bench Press" not in s["options"]


def test_bro_split_days_train_one_muscle_group():
    days = {d["archetype_id"]: [s["pattern"] for s in d["slots"]] for d in _days(split="bro_split")}
    chest, back, shoulders = days["bro_chest"], days["bro_back"], days["bro_shoulders"]
    arms = {"bicep_curl", "hammer_curl", "tricep_push", "tricep_compound"}
    assert not arms & set(chest + back + shoulders)        # Arms Day covers them
    assert "chest_fly" in chest and chest.count("incline_push") == 1
    assert "lat_isolation" in back
    assert shoulders.count("vertical_push") == 2 and "shrug" in shoulders


def test_four_day_bro_split_keeps_one_arm_finisher():
    days = {d["archetype_id"]: [s["pattern"] for s in d["slots"]] for d in _days(days=4, split="bro_split")}
    assert days["bro_chest"][-1] == "tricep_push" and days["bro_back"][-1] == "bicep_curl"


def test_arms_day_starts_heavy_and_rests_less_than_main_lifts():
    arms = next(d for d in _days(split="bro_split") if d["archetype_id"] == "bro_arms")
    assert arms["slots"][0]["pattern"] == "tricep_compound"
    assert all(s["rest_seconds"] <= 120 for s in arms["slots"])


def test_pull_day_second_curl_is_a_hammer_curl():
    pull = next(d for d in _days(split="push_pull_legs") if d["archetype_id"] == "pull_session")
    pats = [s["pattern"] for s in pull["slots"]]
    assert pats.count("bicep_curl") == 1 and pats[-1] == "hammer_curl"


@pytest.mark.parametrize("split", ["bro_split", "push_pull_legs", "upper_lower"])
def test_calves_come_after_the_other_leg_work(split):
    for d in _days(days=6 if split != "bro_split" else 5, split=split):
        pats = [s["pattern"] for s in d["slots"] if s["type"] not in ("core", "conditioning")]
        if "calf" in pats:
            assert pats[-1] == "calf"


@pytest.mark.parametrize("style, goal", [("hybrid", "build_muscle"), ("calisthenics", "build_muscle"),
                                         ("weights", "athletic_performance")])
def test_jumps_and_core_keep_their_own_reps_and_rest(style, goal):
    for d in _days(goal=goal, days=4, style=style):
        for s in d["slots"]:
            if s["pattern"] == "explosive":
                assert s["reps"] in ("3-5", "4-6", "5-8")
            if s["pattern"].startswith("core_"):
                assert s["rest_seconds"] <= 75


@pytest.mark.parametrize("goal, style, days", [("athletic_performance", "weights", 5),
                                               ("athletic_performance", "weights", 6),
                                               ("build_muscle", "hybrid", 5), ("build_muscle", "hybrid", 6)])
def test_no_jump_day_straight_after_a_heavy_leg_day(goal, style, days):
    legs = {"squat", "hip_hinge", "glute", "lunge"}
    bp = E().build_blueprint(WorkoutGenerateRequest(
        user_id="u", goal=goal, training_style=style, focus_areas=["full_body"],
        equipment=["full_gym"], days_per_week=days, duration_minutes=60,
        fitness_level="intermediate"))
    week = [w.split(":")[0] for w in bp["weekly_structure"]]
    plan = iter(bp["day_blueprints"])
    kinds = []
    for w in bp["weekly_structure"]:
        if w.endswith("Rest"):
            kinds.append("rest")
            continue
        pats = {s["pattern"] for s in next(plan)["slots"] if s["type"] in ("primary_compound", "secondary_compound")}
        kinds.append("jump" if "explosive" in pats else "legs" if pats & legs else "upper")
    for a, b in zip(kinds, kinds[1:]):
        assert not (a == "legs" and b == "jump"), (week, kinds)

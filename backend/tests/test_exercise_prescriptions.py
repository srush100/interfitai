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

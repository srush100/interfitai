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

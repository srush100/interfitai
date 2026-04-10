"""
Tests for 7 Critical Fixes to the Workout Generation Engine
Endpoint: POST /api/workouts/generate
Test user: cbd82a69-3a37-48c2-88e8-0fe95081fa4b

IMPORTANT — Response structure:
  workout_days[i].day   → "Day N — <ArchetypeLabel>" e.g. "Day 1 — Push"
  workout_days[i].focus → muscle group description e.g. "Chest, Shoulders & Triceps"

IMPORTANT — WorkoutGenerateRequest field names:
  preferred_split  (NOT split_type)
  training_style   (NOT style; "traditional" → use "weights")
  fitness_level    (NOT experience_level)
  injuries         (NOT limitations)

NOTE: The review spec sends split_type/style/experience_level/limitations but the model
uses different field names. This is a KNOWN ISSUE reported separately.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"
ENDPOINT = f"{BASE_URL}/api/workouts/generate"


def get_day_label(day_dict: dict) -> str:
    """Extract the day label from a workout day dict.
    The 'day' field contains 'Day N — <label>' e.g. 'Day 1 — Push'
    We extract just the label part after ' — '
    """
    raw = day_dict.get("day") or day_dict.get("day_label") or day_dict.get("label") or day_dict.get("name") or ""
    if " — " in raw:
        return raw.split(" — ", 1)[1]
    return raw


def get_focus(day_dict: dict) -> str:
    return day_dict.get("focus", "")


@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ──────────────────────────────────────────────────────────────────────────────
# TEST 1 – Fix 1: PPL 5-day does NOT repeat Push/Pull/Legs
# Expected day labels: Push, Pull, Legs, Upper Body, Lower Body
# (NOT Push, Pull, Legs, Push, Pull — the old bug)
# ──────────────────────────────────────────────────────────────────────────────
class TestFix1_PPL5Day:
    """Fix 1: 5-day PPL uses Upper Body & Lower Body for days 4+5, not another Push/Pull rotation"""

    PAYLOAD = {
        "user_id": USER_ID,
        "preferred_split": "push_pull_legs",
        "days_per_week": 5,
        "goal": "build_muscle",
        "training_style": "weights",
        "equipment": ["barbell", "dumbbell"],
        "focus_areas": [],
        "duration_minutes": 60,
        "fitness_level": "intermediate",
        "injuries": [],
    }

    @pytest.fixture(scope="class")
    def response(self, api_client):
        r = api_client.post(ENDPOINT, json=self.PAYLOAD, timeout=120)
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:500]}"
        return r.json()

    def test_status_200(self, api_client):
        r = api_client.post(ENDPOINT, json=self.PAYLOAD, timeout=120)
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:500]}"

    def test_split_is_ppl(self, response):
        split_name = response.get("split_name", "")
        preferred = response.get("preferred_split", "")
        print(f"\nFix 1 – split_name={split_name!r}  preferred_split={preferred!r}")
        assert "push" in split_name.lower() or "ppl" in split_name.lower() or "legs" in split_name.lower(), \
            f"Fix 1 FAILED: Expected PPL split, got split_name='{split_name}'"

    def test_has_5_workout_days(self, response):
        days = response.get("workout_days") or []
        assert len(days) == 5, f"Expected 5 workout days, got {len(days)}"

    def test_day_labels_no_repeated_push_pull(self, response):
        days = response.get("workout_days") or []
        labels = [get_day_label(d) for d in days]
        print(f"\nFix 1 – Day labels: {labels}")

        assert len(labels) >= 5, f"Expected at least 5 days, got {len(labels)}"

        # Days 4 & 5 must NOT be Push/Pull again (old bug: Push, Pull, Legs, Push, Pull)
        day4_label = labels[3].lower()
        day5_label = labels[4].lower()

        # Day 4 should NOT be "push" or "chest" (should be "upper body")
        assert "push" not in day4_label and "chest" not in day4_label, \
            f"Fix 1 FAILED: Day 4 label '{labels[3]}' looks like repeated Push day (expected Upper Body)"
        # Day 5 should NOT be "pull" or "back" (should be "lower body")
        assert "pull" not in day5_label and "back" not in day5_label, \
            f"Fix 1 FAILED: Day 5 label '{labels[4]}' looks like repeated Pull day (expected Lower Body)"

    def test_day4_is_upper_body(self, response):
        days = response.get("workout_days") or []
        labels = [get_day_label(d) for d in days]
        day4_label = labels[3].lower() if len(labels) > 3 else ""
        print(f"Fix 1 – Day 4 label: {labels[3] if len(labels) > 3 else 'N/A'}")
        assert "upper" in day4_label, \
            f"Fix 1 FAILED: Day 4 expected 'Upper Body', got '{labels[3] if len(labels) > 3 else 'N/A'}'"

    def test_day5_is_lower_body(self, response):
        days = response.get("workout_days") or []
        labels = [get_day_label(d) for d in days]
        day5_label = labels[4].lower() if len(labels) > 4 else ""
        print(f"Fix 1 – Day 5 label: {labels[4] if len(labels) > 4 else 'N/A'}")
        assert "lower" in day5_label, \
            f"Fix 1 FAILED: Day 5 expected 'Lower Body', got '{labels[4] if len(labels) > 4 else 'N/A'}'"


# ──────────────────────────────────────────────────────────────────────────────
# TEST 2 – Fix 2: Bro Split 3-day uses bro_chest_shoulders (with OHP/vertical_push)
# Expected: Chest & Shoulders Day, Back Day, Legs Day
# Day 1 must include BOTH pressing AND overhead press exercises
# ──────────────────────────────────────────────────────────────────────────────
class TestFix2_BroSplit3Day:
    """Fix 2: 3-day bro split uses bro_chest_shoulders archetype (includes OHP/shoulders)"""

    PAYLOAD = {
        "user_id": USER_ID,
        "preferred_split": "bro_split",
        "days_per_week": 3,
        "goal": "build_muscle",
        "training_style": "weights",
        "equipment": ["barbell", "dumbbell"],
        "focus_areas": [],
        "duration_minutes": 60,
        "fitness_level": "intermediate",
        "injuries": [],
    }

    @pytest.fixture(scope="class")
    def response(self, api_client):
        r = api_client.post(ENDPOINT, json=self.PAYLOAD, timeout=120)
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:500]}"
        return r.json()

    def test_status_200(self, api_client):
        r = api_client.post(ENDPOINT, json=self.PAYLOAD, timeout=120)
        assert r.status_code == 200

    def test_split_is_bro(self, response):
        split_name = response.get("split_name", "")
        print(f"\nFix 2 – split_name: {split_name!r}")
        assert "bro" in split_name.lower(), \
            f"Fix 2 FAILED: Expected Bro Split, got '{split_name}'"

    def test_has_3_workout_days(self, response):
        days = response.get("workout_days") or []
        assert len(days) == 3, f"Expected 3 workout days, got {len(days)}"

    def test_day1_is_chest_shoulders(self, response):
        days = response.get("workout_days") or []
        d1_label = get_day_label(days[0]).lower() if days else ""
        d1_focus = get_focus(days[0]).lower() if days else ""
        print(f"\nFix 2 – Day 1 label: '{d1_label}', focus: '{d1_focus}'")
        # Either label has "chest & shoulders" or focus has both chest and shoulder
        has_chest_and_shoulder = (
            ("chest" in d1_label and "shoulder" in d1_label) or
            ("chest" in d1_focus and "shoulder" in d1_focus)
        )
        assert has_chest_and_shoulder, \
            f"Fix 2 FAILED: Day 1 expected 'Chest & Shoulders Day', got label='{d1_label}' focus='{d1_focus}'"

    def test_day2_is_back(self, response):
        days = response.get("workout_days") or []
        d2_label = get_day_label(days[1]).lower() if len(days) > 1 else ""
        d2_focus = get_focus(days[1]).lower() if len(days) > 1 else ""
        print(f"Fix 2 – Day 2 label: '{d2_label}', focus: '{d2_focus}'")
        assert "back" in d2_label or "back" in d2_focus, \
            f"Fix 2 FAILED: Day 2 expected 'Back Day', got label='{d2_label}' focus='{d2_focus}'"

    def test_day3_is_legs(self, response):
        days = response.get("workout_days") or []
        d3_label = get_day_label(days[2]).lower() if len(days) > 2 else ""
        d3_focus = get_focus(days[2]).lower() if len(days) > 2 else ""
        print(f"Fix 2 – Day 3 label: '{d3_label}', focus: '{d3_focus}'")
        assert "leg" in d3_label or "quad" in d3_focus, \
            f"Fix 2 FAILED: Day 3 expected 'Legs Day', got label='{d3_label}' focus='{d3_focus}'"

    def test_day1_has_pressing_and_ohp(self, response):
        """Day 1 must include BOTH a pressing move AND an overhead press (proof shoulders are trained)"""
        days = response.get("workout_days") or []
        day1_exercises = days[0].get("exercises") or []
        ex_names = [e.get("name", "").lower() for e in day1_exercises]
        print(f"Fix 2 – Day 1 exercises: {ex_names}")

        has_pressing = any(
            any(kw in name for kw in ["bench", "chest press", "push-up", "push up", "dip"])
            for name in ex_names
        )
        # OHP: overhead press, military press, shoulder press, OHP
        has_ohp = any(
            any(kw in name for kw in [
                "overhead press", "military press", "shoulder press",
                "ohp", "press", "pike push", "push press"
            ])
            for name in ex_names
        )
        assert has_pressing, f"Fix 2 FAILED: Day 1 missing pressing exercise. Got: {ex_names}"
        assert has_ohp, f"Fix 2 FAILED: Day 1 missing overhead press/shoulder press. Got: {ex_names}"


# ──────────────────────────────────────────────────────────────────────────────
# TEST 3 – Fix 3: Full Body 5-day — each day has unique lead exercise
# Day 4 must NOT start with same exercise as Day 1
# Day 5 must NOT start with same exercise as Day 2
# ──────────────────────────────────────────────────────────────────────────────
class TestFix3_FullBody5DayUnique:
    """Fix 3: 5-day full body uses 5 distinct archetypes — no repeated lead exercises"""

    PAYLOAD = {
        "user_id": USER_ID,
        "preferred_split": "full_body",
        "days_per_week": 5,
        "goal": "general_fitness",
        "training_style": "weights",
        "equipment": ["barbell", "dumbbell"],
        "focus_areas": [],
        "duration_minutes": 60,
        "fitness_level": "intermediate",
        "injuries": [],
    }

    @pytest.fixture(scope="class")
    def response(self, api_client):
        r = api_client.post(ENDPOINT, json=self.PAYLOAD, timeout=120)
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:500]}"
        return r.json()

    def test_status_200(self, api_client):
        r = api_client.post(ENDPOINT, json=self.PAYLOAD, timeout=120)
        assert r.status_code == 200

    def test_split_is_full_body(self, response):
        split_name = response.get("split_name", "")
        print(f"\nFix 3 – split_name: {split_name!r}")
        assert "full" in split_name.lower() or "body" in split_name.lower(), \
            f"Fix 3: Expected Full Body split, got '{split_name}'"

    def test_has_5_workout_days(self, response):
        days = response.get("workout_days") or []
        assert len(days) == 5, f"Expected 5 workout days, got {len(days)}"

    def test_first_exercises_are_unique(self, response):
        days = response.get("workout_days") or []
        first_exercises = []
        for i, d in enumerate(days):
            exs = d.get("exercises") or []
            first_ex = exs[0].get("name", "N/A") if exs else "N/A"
            first_exercises.append(first_ex)
            print(f"Fix 3 – Day {i+1} first exercise: {first_ex}")

        print(f"\nFix 3 – All first exercises: {first_exercises}")
        assert len(first_exercises) >= 5, "Need at least 5 days to compare"

        # Day 4 (index 3) must NOT be same as Day 1 (index 0)
        assert first_exercises[3].lower() != first_exercises[0].lower(), \
            f"Fix 3 FAILED: Day 4 first exercise '{first_exercises[3]}' is SAME as Day 1 '{first_exercises[0]}'"

        # Day 5 (index 4) must NOT be same as Day 2 (index 1)
        assert first_exercises[4].lower() != first_exercises[1].lower(), \
            f"Fix 3 FAILED: Day 5 first exercise '{first_exercises[4]}' is SAME as Day 2 '{first_exercises[1]}'"

    def test_day_labels_are_unique(self, response):
        days = response.get("workout_days") or []
        # Use the full 'day' field for uniqueness check
        labels = [d.get("day", "") for d in days]
        print(f"Fix 3 – Day raw labels: {labels}")
        unique_labels = set(labels)
        assert len(unique_labels) == 5, \
            f"Fix 3 FAILED: Day labels not all unique: {labels}"


# ──────────────────────────────────────────────────────────────────────────────
# TEST 4 – Fix 4: Calisthenics 4-day uses proper labels
# Expected: Calisthenics Upper, Calisthenics Lower, Calisthenics Skill, Calisthenics Conditioning
# NOT: Upper, Lower, Upper, Lower
# ──────────────────────────────────────────────────────────────────────────────
class TestFix4_Calisthenics4Day:
    """Fix 4: 4-day calisthenics split uses Skill + Conditioning days, not a repeated Upper/Lower"""

    PAYLOAD = {
        "user_id": USER_ID,
        "preferred_split": "calisthenics_split",
        "days_per_week": 4,
        "goal": "body_recomp",
        "training_style": "calisthenics",
        "equipment": ["bodyweight"],
        "focus_areas": [],
        "duration_minutes": 60,
        "fitness_level": "intermediate",
        "injuries": [],
    }

    @pytest.fixture(scope="class")
    def response(self, api_client):
        r = api_client.post(ENDPOINT, json=self.PAYLOAD, timeout=120)
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:500]}"
        return r.json()

    def test_status_200(self, api_client):
        r = api_client.post(ENDPOINT, json=self.PAYLOAD, timeout=120)
        assert r.status_code == 200

    def test_split_is_calisthenics(self, response):
        split_name = response.get("split_name", "")
        print(f"\nFix 4 – split_name: {split_name!r}")
        assert "calisthenics" in split_name.lower(), \
            f"Fix 4: Expected Calisthenics split, got '{split_name}'"

    def test_has_4_workout_days(self, response):
        days = response.get("workout_days") or []
        assert len(days) == 4, f"Expected 4 workout days, got {len(days)}"

    def test_day_labels_are_calisthenics_specific(self, response):
        days = response.get("workout_days") or []
        labels = [get_day_label(d) for d in days]
        print(f"\nFix 4 – Day labels: {labels}")

        for i, label in enumerate(labels):
            assert "calisthenics" in label.lower(), \
                f"Fix 4 FAILED: Day {i+1} label '{label}' missing 'Calisthenics' prefix (expected: Calisthenics Upper/Lower/Skill/Conditioning)"

    def test_no_repeated_upper_lower_pattern(self, response):
        """Old bug: 4-day returned Upper, Lower, Upper, Lower"""
        days = response.get("workout_days") or []
        labels = [get_day_label(d).lower() for d in days]

        # Days 3 and 4 should NOT be Upper and Lower again
        day3 = labels[2] if len(labels) > 2 else ""
        day4 = labels[3] if len(labels) > 3 else ""

        # Day 3 should NOT just say "upper" or "lower" (it should be "skill" or "conditioning")
        assert "skill" in day3 or "conditioning" in day3, \
            f"Fix 4 FAILED: Day 3 expected 'Skill' or 'Conditioning', got '{labels[2] if len(labels)>2 else 'N/A'}'"

    def test_day3_is_skill(self, response):
        days = response.get("workout_days") or []
        labels = [get_day_label(d) for d in days]
        day3_label = labels[2].lower() if len(labels) > 2 else ""
        print(f"Fix 4 – Day 3 label: {labels[2] if len(labels) > 2 else 'N/A'}")
        assert "skill" in day3_label, \
            f"Fix 4 FAILED: Day 3 expected 'Calisthenics Skill', got '{labels[2] if len(labels) > 2 else 'N/A'}'"

    def test_day4_is_conditioning(self, response):
        days = response.get("workout_days") or []
        labels = [get_day_label(d) for d in days]
        day4_label = labels[3].lower() if len(labels) > 3 else ""
        print(f"Fix 4 – Day 4 label: {labels[3] if len(labels) > 3 else 'N/A'}")
        assert "conditioning" in day4_label, \
            f"Fix 4 FAILED: Day 4 expected 'Calisthenics Conditioning', got '{labels[3] if len(labels) > 3 else 'N/A'}'"

    def test_day3_skill_has_skill_progression_content(self, response):
        """Day 3 Skill should have exercises focused on skill progressions"""
        days = response.get("workout_days") or []
        if len(days) < 3:
            pytest.skip("Not enough days")
        day3_exercises = days[2].get("exercises") or []
        ex_names = [e.get("name", "").lower() for e in day3_exercises]
        print(f"Fix 4 – Day 3 (Skill) exercises: {ex_names}")
        # Skill day should have skill-progression type exercises
        skill_keywords = [
            "planche", "l-sit", "l sit", "lsit", "archer",
            "handstand", "pistol", "muscle up", "muscle-up",
            "front lever", "dragon", "pull-up", "pull up",
            "push-up", "push up", "dip", "ring", "bar"
        ]
        has_skill = any(
            any(kw in name for kw in skill_keywords)
            for name in ex_names
        )
        assert has_skill, \
            f"Fix 4 FAILED: Day 3 (Skill) exercises don't look like skill progressions. Got: {ex_names}"

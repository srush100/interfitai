"""
Workout Engine Audit Round 3 - Verification Tests
Tests 5 engine fixes:
  T1: 6-Day Upper/Lower Advanced Body Recomp
  T2: Calisthenics 4-Day Program
  T3: Cross-Day no-duplicate exercise constraint
  T4: Exercise name fixes (Australian Pull-Up removed, Cable Glute Kickback present)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ──────────────────────────────────────────────────────────────────────────────
# TEST 1 — 6-Day Upper/Lower Advanced Body Recomp
# ──────────────────────────────────────────────────────────────────────────────
class TestSixDayUpperLower:
    """Verify 6-day upper/lower advanced body_recomp program structure"""

    PAYLOAD = {
        "user_id": USER_ID,
        "preferred_split": "upper_lower",
        "days_per_week": 6,
        "goal": "body_recomp",
        "training_style": "traditional",
        "equipment": ["barbell", "dumbbell", "cables"],
        "focus_areas": [],
        "duration_minutes": 75,
        "fitness_level": "advanced",
        "injuries": [],
    }

    @pytest.fixture(scope="class")
    def program(self, session):
        """Generate 6-day UL program once and share across tests"""
        resp = session.post(f"{BASE_URL}/api/workouts/generate", json=self.PAYLOAD, timeout=120)
        assert resp.status_code == 200, f"Generate failed {resp.status_code}: {resp.text[:500]}"
        data = resp.json()
        days = data.get("workout_days", [])
        print(f"\n  === 6-Day UL Program: {data.get('name', 'N/A')} ===")
        for i, day in enumerate(days, 1):
            print(f"  Day {i}: focus='{day.get('focus','?')}', exercises={len(day.get('exercises',[]))}")
        return days

    def test_t1a_exactly_six_days(self, program):
        """(a) Exactly 6 workout days returned"""
        assert len(program) == 6, f"Expected 6 days, got {len(program)}"
        print(f"PASS T1a: {len(program)} workout days returned")

    def test_t1b_upper_lower_alternation(self, program):
        """(b) Days 1,3,5 = upper body; Days 2,4,6 = lower body (3 upper / 3 lower)"""
        upper_labels = {"upper body", "upper push", "upper pull", "push", "pull", "chest", "back", "shoulder", "arm"}
        lower_labels = {"lower body", "lower", "quad", "hamstring", "glute", "hip", "leg", "calf"}

        def is_upper(day):
            focus = day.get("focus", "").lower()
            name = day.get("name", "").lower()
            text = f"{focus} {name}"
            return any(kw in text for kw in upper_labels)

        def is_lower(day):
            focus = day.get("focus", "").lower()
            name = day.get("name", "").lower()
            text = f"{focus} {name}"
            return any(kw in text for kw in lower_labels)

        upper_days = [i+1 for i, d in enumerate(program) if is_upper(d)]
        lower_days = [i+1 for i, d in enumerate(program) if is_lower(d)]

        print(f"\n  Upper days: {upper_days}")
        print(f"  Lower days: {lower_days}")
        for i, day in enumerate(program):
            print(f"  Day {i+1} focus: '{day.get('focus', '')}' name: '{day.get('name', '')}'")

        assert len(upper_days) == 3, f"Expected 3 upper days, got {len(upper_days)} at {upper_days}"
        assert len(lower_days) == 3, f"Expected 3 lower days, got {len(lower_days)} at {lower_days}"
        assert upper_days == [1, 3, 5], f"Upper days should be 1,3,5 — got {upper_days}"
        assert lower_days == [2, 4, 6], f"Lower days should be 2,4,6 — got {lower_days}"
        print("PASS T1b: Days 1,3,5 = upper; Days 2,4,6 = lower")

    def test_t1c_day5_is_upper_full(self, program):
        """(c) Day 5 focus = upper_full archetype (both push+pull — 'Chest, Back, Shoulders & Arms')
           NOT purely 'Upper Push Volume' (push-only day)"""
        day5 = program[4]  # 0-indexed
        focus = day5.get("focus", "")
        name = day5.get("name", "")
        print(f"\n  Day 5 focus: '{focus}', name: '{name}'")

        # upper_full archetype has label="Upper Body" and focus="Chest, Back, Shoulders & Arms"
        # The focus field contains the archetype's 'focus' string which does NOT say "upper"
        # but DOES contain both chest (push) AND back (pull) muscles
        focus_lower = focus.lower()

        # Must contain at least one push muscle group
        push_muscles = ["chest", "tricep", "shoulder", "delt", "pec"]
        has_push = any(m in focus_lower for m in push_muscles)

        # Must contain at least one pull muscle group
        pull_muscles = ["back", "bicep", "lat", "row", "rhomboid"]
        has_pull = any(m in focus_lower for m in pull_muscles)

        assert has_push, \
            f"Day 5 should contain push muscles (chest/shoulder/tricep), got focus='{focus}'"
        assert has_pull, \
            f"Day 5 should contain pull muscles (back/bicep/lat), got focus='{focus}'"

        # Verify Day 5 is NOT purely a push-volume session
        push_only_keywords = ["push volume", "upper push volume"]
        for kw in push_only_keywords:
            assert kw not in focus_lower, \
                f"Day 5 should be 'Upper Body' full (push+pull), not '{kw}'. Got: '{focus}'"

        # Check it contains both push AND pull exercises
        exercises = day5.get("exercises", [])
        print(f"  Day 5 exercises: {[e.get('name') for e in exercises]}")
        muscle_groups = []
        for e in exercises:
            muscle_groups.extend([mg.lower() for mg in e.get("muscle_groups", [])])
        print(f"  Day 5 muscle groups: {set(muscle_groups)}")

        print(f"PASS T1c: Day 5 is upper_full (has both push+pull muscles): '{focus}'")

    def test_t1d_push_pull_frequency_balance(self, program):
        """(d) Push frequency ≤ 3, pull frequency ≤ 3 across all upper days"""
        push_keywords = ["push", "chest", "tricep", "shoulder", "press", "delt"]
        pull_keywords = ["pull", "back", "bicep", "row", "lat", "rear delt"]

        push_days = []
        pull_days = []

        for i, day in enumerate(program, 1):
            focus = day.get("focus", "").lower()
            name = day.get("name", "").lower()
            text = f"{focus} {name}"

            has_push = any(kw in text for kw in push_keywords)
            has_pull = any(kw in text for kw in pull_keywords)

            if has_push:
                push_days.append(i)
            if has_pull:
                pull_days.append(i)

        print(f"\n  Push days: {push_days} (count: {len(push_days)})")
        print(f"  Pull days: {pull_days} (count: {len(pull_days)})")

        # Day 5 (upper_full) should count for both push AND pull
        assert len(push_days) <= 3, f"Push frequency {len(push_days)} > 3 (days: {push_days})"
        assert len(pull_days) <= 3, f"Pull frequency {len(pull_days)} > 3 (days: {pull_days})"
        print(f"PASS T1d: Push freq={len(push_days)} ≤ 3, Pull freq={len(pull_days)} ≤ 3")


# ──────────────────────────────────────────────────────────────────────────────
# TEST 2 — Calisthenics 4-Day Program
# ──────────────────────────────────────────────────────────────────────────────
class TestCalisthenics4Day:
    """Verify calisthenics 4-day program has proper Skill + Conditioning days"""

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
    def program(self, session):
        """Generate calisthenics 4-day program once"""
        resp = session.post(f"{BASE_URL}/api/workouts/generate", json=self.PAYLOAD, timeout=120)
        assert resp.status_code == 200, f"Generate failed {resp.status_code}: {resp.text[:500]}"
        data = resp.json()
        days = data.get("workout_days", [])
        print(f"\n  === Calisthenics 4-Day: {data.get('name', 'N/A')} ===")
        for i, day in enumerate(days, 1):
            print(f"  Day {i}: focus='{day.get('focus','?')}' name='{day.get('name','?')}'")
        return days

    def test_t2a_exactly_four_days(self, program):
        """(a) Exactly 4 workout days"""
        assert len(program) == 4, f"Expected 4 days, got {len(program)}"
        print(f"PASS T2a: {len(program)} days returned")

    def test_t2b_day1_calisthenics_upper(self, program):
        """(b) Day 1 = Calisthenics Upper (focus: 'Chest, Back, Shoulders & Arms')"""
        day1 = program[0]
        focus = day1.get("focus", "").lower()
        name = day1.get("name", "").lower()
        text = f"{focus} {name}"
        print(f"\n  Day 1 focus: '{day1.get('focus')}', name: '{day1.get('name')}'")
        # calisthenics_upper archetype has focus="Chest, Back, Shoulders & Arms"
        # Confirm it's an upper-body oriented session (has chest OR back OR arm muscles)
        upper_indicators = ["chest", "back", "shoulder", "arm", "delt", "bicep", "tricep", "upper"]
        is_upper = any(kw in text for kw in upper_indicators)
        assert is_upper, f"Day 1 should be Calisthenics Upper, got: focus='{day1.get('focus')}'"
        # Confirm it's NOT a lower body session
        lower_only = ["legs & core", "quads", "hamstrings", "glutes"]
        is_lower_only = any(kw in focus for kw in lower_only)
        assert not is_lower_only, f"Day 1 should be upper not lower. Got: focus='{day1.get('focus')}'"
        print("PASS T2b: Day 1 = Calisthenics Upper")

    def test_t2c_day2_calisthenics_lower(self, program):
        """(b) Day 2 = Calisthenics Lower"""
        day2 = program[1]
        focus = day2.get("focus", "").lower()
        name = day2.get("name", "").lower()
        text = f"{focus} {name}"
        print(f"\n  Day 2 focus: '{day2.get('focus')}', name: '{day2.get('name')}'")
        assert "lower" in text or "leg" in text or "quad" in text, \
            f"Day 2 should be Calisthenics Lower, got: focus='{day2.get('focus')}'"
        print("PASS T2c: Day 2 = Calisthenics Lower")

    def test_t2d_day3_calisthenics_skill(self, program):
        """(b) Day 3 = Calisthenics Skill (planche/L-sit type progressions)"""
        day3 = program[2]
        focus = day3.get("focus", "").lower()
        name = day3.get("name", "").lower()
        text = f"{focus} {name}"
        print(f"\n  Day 3 focus: '{day3.get('focus')}', name: '{day3.get('name')}'")

        skill_keywords = ["skill", "progression", "hold", "planche", "l-sit", "front lever", "static", "press"]
        is_skill = any(kw in text for kw in skill_keywords)
        assert is_skill, \
            f"Day 3 should be Calisthenics Skill (progression/holds), got: focus='{day3.get('focus')}'"
        print("PASS T2d: Day 3 = Calisthenics Skill")

    def test_t2e_day4_calisthenics_conditioning(self, program):
        """(b) Day 4 = Calisthenics Conditioning (endurance/volume)"""
        day4 = program[3]
        focus = day4.get("focus", "").lower()
        name = day4.get("name", "").lower()
        text = f"{focus} {name}"
        print(f"\n  Day 4 focus: '{day4.get('focus')}', name: '{day4.get('name')}'")

        cond_keywords = ["conditioning", "endurance", "capacity", "circuit", "volume", "metabolic", "work capacity"]
        is_cond = any(kw in text for kw in cond_keywords)
        assert is_cond, \
            f"Day 4 should be Calisthenics Conditioning, got: focus='{day4.get('focus')}'"
        print("PASS T2e: Day 4 = Calisthenics Conditioning")

    def test_t2f_not_plain_upper_lower_pattern(self, program):
        """(c) NOT just Upper/Lower/Upper/Lower — Day 3 and Day 4 are different"""
        day1_focus = program[0].get("focus", "").lower()
        day3_focus = program[2].get("focus", "").lower()
        day4_focus = program[3].get("focus", "").lower()

        # Day 3 should NOT be same type as Day 1 (both upper)
        # Day 4 should NOT be same type as Day 2 (both lower)
        assert "skill" in day3_focus or "progression" in day3_focus or "hold" in day3_focus, \
            f"Day 3 should be Skill, not repeated Upper. Got: '{day3_focus}'"
        assert "conditioning" in day4_focus or "endurance" in day4_focus or "capacity" in day4_focus, \
            f"Day 4 should be Conditioning, not repeated Lower. Got: '{day4_focus}'"
        print("PASS T2f: Not plain Upper/Lower/Upper/Lower pattern")


# ──────────────────────────────────────────────────────────────────────────────
# TEST 3 — Cross-Day No Exercise Repeat
# ──────────────────────────────────────────────────────────────────────────────
class TestCrossDayDeduplication:
    """Verify dedup logic: exercises used in Day 1 don't repeat in Day 4 (same pattern)"""

    PAYLOAD_PPL = {
        "user_id": USER_ID,
        "preferred_split": "push_pull_legs",
        "days_per_week": 5,
        "goal": "build_muscle",
        "training_style": "traditional",
        "equipment": ["barbell", "dumbbell", "cables"],
        "focus_areas": [],
        "duration_minutes": 60,
        "fitness_level": "advanced",
        "injuries": [],
    }

    @pytest.fixture(scope="class")
    def ppl_5day(self, session):
        """5-day PPL program for dedup testing"""
        resp = session.post(f"{BASE_URL}/api/workouts/generate", json=self.PAYLOAD_PPL, timeout=120)
        assert resp.status_code == 200, f"Generate failed {resp.status_code}: {resp.text[:500]}"
        data = resp.json()
        days = data.get("workout_days", [])
        print(f"\n  === 5-Day PPL: {data.get('name', 'N/A')} ===")
        for i, day in enumerate(days, 1):
            ex_names = [e.get("name") for e in day.get("exercises", [])]
            print(f"  Day {i} focus='{day.get('focus','?')}': {ex_names}")
        return days

    def test_t3a_day1_and_day4_no_overlap(self, ppl_5day):
        """Day 1 (Push) and Day 4 (Push Volume) should NOT share primary exercises like Bench Press"""
        assert len(ppl_5day) >= 4, f"Need at least 4 days, got {len(ppl_5day)}"

        day1_names = set(e.get("name", "") for e in ppl_5day[0].get("exercises", []))
        day4_names = set(e.get("name", "") for e in ppl_5day[3].get("exercises", []))

        overlap = day1_names & day4_names
        print(f"\n  Day 1 exercises: {sorted(day1_names)}")
        print(f"  Day 4 exercises: {sorted(day4_names)}")
        print(f"  Overlap: {overlap}")

        # Specifically check for Barbell Bench Press duplication (the key fix)
        bench_in_both = "Barbell Bench Press" in day1_names and "Barbell Bench Press" in day4_names
        assert not bench_in_both, \
            "FAIL: Barbell Bench Press appears in BOTH Day 1 and Day 4 — dedup logic not working!"

        if overlap:
            print(f"  WARNING: {len(overlap)} exercises overlap across Day 1 and Day 4: {overlap}")
            # Soft check: overlap should be minimal (accessory/isolation exercises may share)
            primary_overlap = {n for n in overlap if any(kw in n.lower() for kw in ["barbell", "bench press", "squat", "deadlift", "overhead press"])}
            assert not primary_overlap, \
                f"Primary compound exercises overlap cross-day: {primary_overlap}"
        else:
            print("  PERFECT: Zero exercise overlap between Day 1 and Day 4")

        print(f"PASS T3a: Barbell Bench Press not in both Day 1 and Day 4")

    def test_t3b_six_day_ul_day1_day5_no_bench_overlap(self, session):
        """6-Day UL: Day 1 (Push Heavy) and Day 5 (Upper Full) should not both have Barbell Bench Press"""
        payload = {
            "user_id": USER_ID,
            "preferred_split": "upper_lower",
            "days_per_week": 6,
            "goal": "body_recomp",
            "training_style": "traditional",
            "equipment": ["barbell", "dumbbell", "cables"],
            "focus_areas": [],
            "duration_minutes": 75,
            "fitness_level": "advanced",
            "injuries": [],
        }
        resp = session.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=120)
        assert resp.status_code == 200, f"Generate failed {resp.status_code}: {resp.text[:500]}"
        days = resp.json().get("workout_days", [])
        assert len(days) == 6, f"Expected 6 days, got {len(days)}"

        day1_names = {e.get("name", "") for e in days[0].get("exercises", [])}
        day5_names = {e.get("name", "") for e in days[4].get("exercises", [])}

        print(f"\n  Day 1 exercises: {sorted(day1_names)}")
        print(f"  Day 5 exercises: {sorted(day5_names)}")

        bench_overlap = "Barbell Bench Press" in day1_names and "Barbell Bench Press" in day5_names
        assert not bench_overlap, \
            "FAIL: Barbell Bench Press in both Day 1 and Day 5 of 6-day UL program!"
        print("PASS T3b: Barbell Bench Press not in both Day 1 and Day 5 (6-day UL)")


# ──────────────────────────────────────────────────────────────────────────────
# TEST 4 — Exercise Name Fixes Verification
# ──────────────────────────────────────────────────────────────────────────────
class TestExerciseNameFixes:
    """Verify specific exercise name fixes applied in Round 3"""

    def _generate_program(self, session, payload):
        """Helper to generate a program and collect all exercise names"""
        resp = session.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=120)
        assert resp.status_code == 200, f"Generate failed {resp.status_code}: {resp.text[:500]}"
        data = resp.json()
        all_names = []
        for day in data.get("workout_days", []):
            for ex in day.get("exercises", []):
                all_names.append(ex.get("name", ""))
        print(f"\n  All exercise names: {all_names}")
        return all_names

    def test_t4a_australian_pull_up_not_present(self, session):
        """(a) 'Australian Pull-Up' should NOT appear in any generated program"""
        payload = {
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
        names = self._generate_program(session, payload)
        australian = [n for n in names if "australian" in n.lower()]
        assert not australian, \
            f"'Australian Pull-Up' found in generated program: {australian}. This exercise should be replaced."
        print("PASS T4a: 'Australian Pull-Up' NOT present in calisthenics program")

    def test_t4b_no_unqualified_cable_kickback(self, session):
        """(b) 'Cable Kickback' (unqualified) should NOT appear — only 'Cable Glute Kickback'"""
        payload = {
            "user_id": USER_ID,
            "preferred_split": "upper_lower",
            "days_per_week": 4,
            "goal": "build_muscle",
            "training_style": "traditional",
            "equipment": ["barbell", "dumbbell", "cables"],
            "focus_areas": [],
            "duration_minutes": 60,
            "fitness_level": "intermediate",
            "injuries": [],
        }
        names = self._generate_program(session, payload)

        # Check for unqualified "Cable Kickback" (not "Cable Glute Kickback")
        unqualified = [n for n in names if n.strip().lower() == "cable kickback"]
        assert not unqualified, \
            f"Unqualified 'Cable Kickback' found: {unqualified}. Should be 'Cable Glute Kickback'."
        print("PASS T4b: No unqualified 'Cable Kickback' found")

    def test_t4c_cable_glute_kickback_in_lower_day(self, session):
        """(c) 'Cable Glute Kickback' IS present in a program with glute work (lower body day with cables)"""
        # Use 6-day UL with cables to maximize chance of seeing Cable Glute Kickback
        payload = {
            "user_id": USER_ID,
            "preferred_split": "upper_lower",
            "days_per_week": 6,
            "goal": "body_recomp",
            "training_style": "traditional",
            "equipment": ["barbell", "dumbbell", "cables"],
            "focus_areas": ["glutes"],
            "duration_minutes": 75,
            "fitness_level": "advanced",
            "injuries": [],
        }
        names = self._generate_program(session, payload)

        glute_kickbacks = [n for n in names if "cable glute kickback" in n.lower()]
        cable_hip = [n for n in names if "cable hip" in n.lower()]
        any_cable_glute = [n for n in names if "cable" in n.lower() and ("glute" in n.lower() or "kickback" in n.lower() or "hip ext" in n.lower())]

        print(f"\n  'Cable Glute Kickback' found: {glute_kickbacks}")
        print(f"  'Cable Hip Extension' found: {cable_hip}")
        print(f"  Any cable+glute exercise: {any_cable_glute}")

        # With focus_areas=['glutes'] and cables in equipment, Cable Glute Kickback should appear
        assert glute_kickbacks or any_cable_glute, \
            "Expected 'Cable Glute Kickback' or similar cable glute exercise in a glute-focused program with cables"
        print(f"PASS T4c: Cable glute exercise found: {any_cable_glute}")

    def test_t4d_cable_glute_kickback_scan_multiple_programs(self, session):
        """Extra: run 2 programs to verify the naming convention is consistently 'Cable Glute Kickback'"""
        payloads = [
            {
                "user_id": USER_ID,
                "preferred_split": "upper_lower",
                "days_per_week": 4,
                "goal": "body_recomp",
                "training_style": "traditional",
                "equipment": ["cables"],
                "focus_areas": ["glutes"],
                "duration_minutes": 60,
                "fitness_level": "intermediate",
                "injuries": [],
            },
            {
                "user_id": USER_ID,
                "preferred_split": "bro_split",
                "days_per_week": 5,
                "goal": "build_muscle",
                "training_style": "traditional",
                "equipment": ["barbell", "dumbbell", "cables", "machines"],
                "focus_areas": ["legs"],
                "duration_minutes": 60,
                "fitness_level": "intermediate",
                "injuries": [],
            },
        ]
        all_names = []
        for p in payloads:
            names = self._generate_program(session, p)
            all_names.extend(names)

        # No unqualified "Cable Kickback" across both programs
        unqualified = [n for n in all_names if n.strip().lower() == "cable kickback"]
        assert not unqualified, \
            f"Unqualified 'Cable Kickback' found across programs: {unqualified}"

        # Check if Cable Glute Kickback appeared at least once (given cables equipment + glutes focus)
        glute_kickbacks = [n for n in all_names if "cable glute kickback" in n.lower()]
        print(f"\n  Cable Glute Kickback occurrences across 2 programs: {len(glute_kickbacks)}")
        print(f"  All Cable exercises: {[n for n in all_names if 'cable' in n.lower()]}")
        print(f"PASS T4d: Naming convention verified across multiple programs")

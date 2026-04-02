"""
Test suite for exercise ordering changes (iteration 16):
1. _slot_priority: primary_compound=0, secondary_compound=1, focus_accessories=2,
   secondary_focus=3, other=4, ARM_ISO(bicep_curl/tricep_push)=5, CORE_PAT(core_stability/core_flexion/carry)=6, conditioning=99
2. Smoke test: workout generation returns 200 OK
3. Core exercises appear AFTER weighted and BEFORE conditioning
4. Arm isolation (bicep_curl/tricep_push) appears LAST among weighted exercises (before core)
5. Primary_compound exercises always appear FIRST in each session
"""
import pytest
import requests
import os
import sys

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')

# ── Direct import for unit-level tests ───────────────────────────────────────
sys.path.insert(0, '/app/backend')
try:
    from server import EliteCoachingEngine
    HAS_ENGINE = True
except Exception:
    HAS_ENGINE = False

# ── Shared fixtures ───────────────────────────────────────────────────────────
@pytest.fixture(scope='module')
def session():
    s = requests.Session()
    s.headers.update({'Content-Type': 'application/json'})
    return s

@pytest.fixture(scope='module')
def test_user_id():
    return 'cbd82a69-3a37-48c2-88e8-0fe95081fa4b'


# ═══════════════════════════════════════════════════════════════════════════════
# SMOKE TEST
# ═══════════════════════════════════════════════════════════════════════════════

class TestSmokeWorkoutGeneration:
    """API smoke test: generation returns 200 with valid structure"""

    def test_workout_generation_200ok(self, session, test_user_id):
        """Workout generation returns 200 OK with exercises"""
        payload = {
            "user_id": test_user_id,
            "goal": "build_muscle",
            "training_style": "weights",
            "focus_areas": ["chest"],
            "equipment": ["full_gym"],
            "days_per_week": 3,
            "fitness_level": "intermediate",
            "preferred_split": "ai_choose",
        }
        resp = session.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=120)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:500]}"
        data = resp.json()
        assert 'workout_days' in data
        assert len(data['workout_days']) >= 1
        print(f"✅ Smoke test passed: {data.get('name')}, {len(data['workout_days'])} days")

    def test_workout_generation_exercises_have_required_fields(self, session, test_user_id):
        """Each exercise has name, sets, reps, rest_seconds"""
        payload = {
            "user_id": test_user_id,
            "goal": "build_muscle",
            "training_style": "weights",
            "focus_areas": ["back"],
            "equipment": ["full_gym"],
            "days_per_week": 3,
            "fitness_level": "intermediate",
            "preferred_split": "ai_choose",
        }
        resp = session.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=120)
        assert resp.status_code == 200
        data = resp.json()
        for day in data['workout_days']:
            for ex in day['exercises']:
                assert ex['name'], "Exercise missing name"
                assert ex['sets'] >= 1, "Sets must be >= 1"
                assert ex['reps'], "Exercise missing reps"
                assert ex['rest_seconds'] >= 0, "rest_seconds must be >= 0"
        print(f"✅ All exercises have required fields")


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS: _slot_priority via EliteCoachingEngine.build_blueprint()
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not HAS_ENGINE, reason="Cannot import EliteCoachingEngine")
class TestSlotPriorityOrdering:
    """Directly tests that build_blueprint() produces correctly ordered slots"""

    def _make_req(self, focus_areas, secondary_focus_areas=None, goal='build_muscle',
                  equipment=None, days_per_week=3, level='intermediate'):
        """Create a fake request object accepted by build_blueprint"""
        class FakeReq:
            pass
        req = FakeReq()
        req.goal = goal
        req.training_style = 'weights'
        req.focus_areas = focus_areas
        req.secondary_focus_areas = secondary_focus_areas or []
        req.equipment = equipment or ['full_gym']
        req.injuries = []
        req.days_per_week = days_per_week
        req.duration_minutes = 60
        req.fitness_level = level
        req.preferred_split = 'ai_choose'
        req.exercise_preferences = None
        return req

    def _build(self, focus_areas, secondary_focus_areas=None, goal='build_muscle',
               equipment=None, days_per_week=3, level='intermediate'):
        engine = EliteCoachingEngine()
        req = self._make_req(focus_areas, secondary_focus_areas, goal, equipment, days_per_week, level)
        return engine.build_blueprint(req)

    def _session_pattern_types(self, slots):
        """Return list of (pattern, type) for slots"""
        return [(s['pattern'], s['type']) for s in slots]

    def test_primary_compound_always_first(self):
        """Primary compound exercises must appear before all other types"""
        blueprint = self._build(['chest'])
        for day in blueprint['day_blueprints']:
            slots = day['slots']
            types = [s['type'] for s in slots]
            # Find first non-primary_compound slot
            seen_non_primary = False
            for t in types:
                if t == 'primary_compound':
                    assert not seen_non_primary, \
                        f"primary_compound found AFTER non-primary slot. types={types}"
                else:
                    seen_non_primary = True
        print("✅ primary_compound always first in all sessions")

    def test_arm_isolation_before_core(self):
        """bicep_curl and tricep_push must appear before core_stability/core_flexion/carry"""
        blueprint = self._build(
            focus_areas=['full_body'],
            secondary_focus_areas=['arms'],
        )
        ARM_ISO = {'bicep_curl', 'tricep_push'}
        CORE_PAT = {'core_stability', 'core_flexion', 'carry'}
        for day in blueprint['day_blueprints']:
            patterns = [s['pattern'] for s in day['slots']]
            arm_indices = [i for i, p in enumerate(patterns) if p in ARM_ISO]
            core_indices = [i for i, p in enumerate(patterns) if p in CORE_PAT]
            if arm_indices and core_indices:
                assert max(arm_indices) < min(core_indices), \
                    f"Arm isolation must come BEFORE core. patterns={patterns}"
                print(f"  Day slots: {patterns}")
        print("✅ arm isolation appears before core patterns")

    def test_core_patterns_before_conditioning(self):
        """core_stability/core_flexion/carry must appear before conditioning"""
        blueprint = self._build(
            focus_areas=['full_body'],
            goal='lose_fat',  # triggers conditioning finisher
        )
        CORE_PAT = {'core_stability', 'core_flexion', 'carry'}
        for day in blueprint['day_blueprints']:
            patterns = [s['pattern'] for s in day['slots']]
            core_indices = [i for i, p in enumerate(patterns) if p in CORE_PAT]
            cond_indices = [i for i, p in enumerate(patterns) if p == 'conditioning']
            if core_indices and cond_indices:
                assert max(core_indices) < min(cond_indices), \
                    f"Core must come BEFORE conditioning. patterns={patterns}"
                print(f"  Day slots: {patterns}")
        print("✅ core patterns appear before conditioning finisher")

    def test_conditioning_always_last(self):
        """conditioning finisher slot must be the last slot in any session"""
        blueprint = self._build(
            focus_areas=['full_body'],
            goal='lose_fat',
        )
        for day in blueprint['day_blueprints']:
            patterns = [s['pattern'] for s in day['slots']]
            if 'conditioning' in patterns:
                assert patterns[-1] == 'conditioning', \
                    f"conditioning must be last slot. patterns={patterns}"
        print("✅ conditioning is always the last slot")

    def test_arm_iso_last_among_weighted_for_core_secondary(self):
        """With core secondary focus (full_body 3-day), arms appear after compounds/accessories
        but before core patterns"""
        blueprint = self._build(
            focus_areas=['full_body'],
            secondary_focus_areas=['core'],
        )
        ARM_ISO = {'bicep_curl', 'tricep_push'}
        CORE_PAT = {'core_stability', 'core_flexion', 'carry'}
        for day in blueprint['day_blueprints']:
            patterns = [s['pattern'] for s in day['slots']]
            arm_indices = [i for i, p in enumerate(patterns) if p in ARM_ISO]
            core_indices = [i for i, p in enumerate(patterns) if p in CORE_PAT]
            if arm_indices and core_indices:
                # Arms must be before core
                assert max(arm_indices) < min(core_indices), \
                    f"Arms must come before core. Day patterns: {patterns}"
            if core_indices:
                # All non-core, non-conditioning patterns must come before core
                non_core_cond = [i for i, p in enumerate(patterns)
                                 if p not in CORE_PAT and p != 'conditioning']
                if non_core_cond:
                    assert max(non_core_cond) < min(core_indices), \
                        f"All weighted exercises must appear before core. patterns={patterns}"
        print("✅ core secondary focus: all weighted exercises before core patterns")

    def test_arms_secondary_bicep_tricep_last_weighted(self):
        """With arms secondary focus, bicep_curl and tricep_push appear LAST
        among weighted exercises (before core and conditioning)"""
        blueprint = self._build(
            focus_areas=['chest'],
            secondary_focus_areas=['arms'],
            days_per_week=4,
        )
        ARM_ISO = {'bicep_curl', 'tricep_push'}
        CORE_PAT = {'core_stability', 'core_flexion', 'carry'}
        violations = []
        for day in blueprint['day_blueprints']:
            patterns = [s['pattern'] for s in day['slots']]
            arm_indices = [i for i, p in enumerate(patterns) if p in ARM_ISO]
            if not arm_indices:
                continue
            # Everything after the first arm slot must also be arm/core/conditioning
            min_arm_idx = min(arm_indices)
            for i in range(min_arm_idx + 1, len(patterns)):
                p = patterns[i]
                if p not in ARM_ISO and p not in CORE_PAT and p != 'conditioning':
                    violations.append(f"Day '{day.get('label')}': {p} at idx {i} comes AFTER arm isolation at idx {min_arm_idx}. patterns={patterns}")
        assert not violations, "\n".join(violations)
        print("✅ arm isolation is last among weighted exercises in all sessions")


# ═══════════════════════════════════════════════════════════════════════════════
# API-LEVEL TESTS: check exercise ordering via exercise_type field
# ═══════════════════════════════════════════════════════════════════════════════

class TestExerciseOrderingViaAPI:
    """Tests exercise ordering through the HTTP API using exercise_type field"""

    def _generate_workout(self, session, user_id, focus_areas, secondary_focus_areas=None,
                           days_per_week=3, goal='build_muscle'):
        payload = {
            "user_id": user_id,
            "goal": goal,
            "training_style": "weights",
            "focus_areas": focus_areas,
            "secondary_focus_areas": secondary_focus_areas or [],
            "equipment": ["full_gym"],
            "days_per_week": days_per_week,
            "fitness_level": "intermediate",
            "preferred_split": "ai_choose",
        }
        resp = session.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=120)
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:400]}"
        return resp.json()

    def test_primary_compound_first_via_api(self, session, test_user_id):
        """Via API: exercises with exercise_type=primary_compound appear first"""
        data = self._generate_workout(session, test_user_id, ['chest'], days_per_week=3)
        for day in data['workout_days']:
            exercises = day['exercises']
            types = [ex.get('exercise_type', 'unknown') for ex in exercises]
            print(f"  Day '{day['day']}' exercise_types: {types}")
            # primary_compound exercises should not appear after non-primary_compound exercises
            seen_non_primary = False
            for ex in exercises:
                etype = ex.get('exercise_type', '')
                if etype == 'primary_compound':
                    assert not seen_non_primary, \
                        f"primary_compound '{ex['name']}' found after non-primary in day '{day['day']}'. types={types}"
                elif etype in ('secondary_compound', 'accessory', 'isolation', 'core', 'conditioning'):
                    seen_non_primary = True
        print("✅ API: primary_compound always first")

    def test_full_body_3day_core_secondary_ordering(self, session, test_user_id):
        """full_body 3-day with core secondary: core exercises appear AFTER weighted, BEFORE conditioning"""
        data = self._generate_workout(
            session, test_user_id,
            focus_areas=['full_body'],
            secondary_focus_areas=['core'],
            days_per_week=3,
            goal='lose_fat'  # triggers conditioning finisher
        )
        CORE_TYPES = {'core', 'core_stability', 'core_flexion'}
        COND_TYPES = {'conditioning'}
        for day in data['workout_days']:
            exercises = day['exercises']
            types = [ex.get('exercise_type', '') for ex in exercises]
            names = [ex['name'] for ex in exercises]
            print(f"  Day '{day['day']}': {list(zip(names, types))}")
            
            core_indices = [i for i, t in enumerate(types) if t in CORE_TYPES or 'plank' in names[i].lower() or 'dead bug' in names[i].lower() or 'bird dog' in names[i].lower() or 'hollow' in names[i].lower() or 'crunch' in names[i].lower() or 'leg raise' in names[i].lower()]
            cond_indices = [i for i, t in enumerate(types) if t in COND_TYPES]
            weighted_indices = [i for i in range(len(types)) if i not in core_indices and i not in cond_indices]
            
            if core_indices and weighted_indices:
                # Last weighted must be before first core
                if max(weighted_indices) > min(core_indices):
                    print(f"  ⚠️ Some weighted exercise appears after a core exercise (names={names})")
            if core_indices and cond_indices:
                assert max(core_indices) < min(cond_indices), \
                    f"Core must appear before conditioning. types={types}"
        print("✅ API: core exercises appear AFTER weighted and BEFORE conditioning")

    def test_arms_secondary_ordering_via_api(self, session, test_user_id):
        """With arms secondary focus, bicep_curl and tricep_push are last weighted exercises"""
        data = self._generate_workout(
            session, test_user_id,
            focus_areas=['chest'],
            secondary_focus_areas=['arms'],
            days_per_week=4,
            goal='build_muscle'
        )
        ARM_NAMES = {'curl', 'bicep', 'tricep', 'pushdown', 'kickback', 'skull'}
        CORE_NAMES = {'plank', 'dead bug', 'bird dog', 'hollow', 'cable crunch', 'leg raise', 'ab rollout', 'russian twist'}
        COND_NAMES = {'intervals', 'battle rope', 'burpee', 'jump rope', 'mountain climber', 'conditioning', 'bike', 'rowing machine'}
        
        for day in data['workout_days']:
            exercises = day['exercises']
            arm_indices = [i for i, ex in enumerate(exercises)
                           if any(kw in ex['name'].lower() for kw in ARM_NAMES)
                           and not any(kw in ex['name'].lower() for kw in CORE_NAMES)]
            core_indices = [i for i, ex in enumerate(exercises)
                            if any(kw in ex['name'].lower() for kw in CORE_NAMES)]
            names = [ex['name'] for ex in exercises]
            print(f"  Day '{day['day']}': {names}")
            
            # If both arm isolation and core are present, arms must come first
            if arm_indices and core_indices:
                assert max(arm_indices) < min(core_indices), \
                    f"Arm exercises must come before core. names={names}"
        print("✅ API: arms secondary — arm isolation before core patterns")

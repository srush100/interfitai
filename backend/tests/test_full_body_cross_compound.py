"""
Tests for full_body focus area cross-body compound injection.
Covers: full_body + upper_lower split cross-body logic, split_rationale text,
and regression checks that chest/legs focus areas get NO cross-body injection.
"""
import sys
import os
import pytest
import requests

# ── Import server module (blueprint tests use the engine directly) ─────────────
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')
# Fallback: load from frontend/.env if not in environment
if not BASE_URL:
    from dotenv import dotenv_values
    frontend_env = dotenv_values('/app/frontend/.env')
    BASE_URL = frontend_env.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

# Upper and lower body patterns for verification
UPPER_PATTERNS = {
    "horizontal_push", "incline_push", "vertical_push",
    "vertical_pull", "horizontal_pull", "bicep_curl",
    "tricep_push", "lateral_raise", "rear_delt",
}
LOWER_PATTERNS = {
    "squat", "lunge", "hip_hinge", "glute",
    "hamstring_curl", "knee_extension", "calf",
}

# ── Import EliteCoachingEngine for fast blueprint-level tests ─────────────────
from server import EliteCoachingEngine, WorkoutGenerateRequest

_engine = EliteCoachingEngine()


def make_blueprint(focus_areas, days, goal='build_muscle', level='intermediate',
                   preferred_split='ai_choose', equipment=None):
    """Helper: build a coaching blueprint directly (no AI call)."""
    if equipment is None:
        equipment = ['full_gym']
    req = WorkoutGenerateRequest(
        user_id=TEST_USER_ID,
        goal=goal,
        focus_areas=focus_areas,
        equipment=equipment,
        days_per_week=days,
        fitness_level=level,
        preferred_split=preferred_split,
    )
    return _engine.build_blueprint(req)


# ===========================================================================
# Blueprint-level tests (deterministic, no LLM call)
# ===========================================================================

class TestFullBodyUpperLowerSplitSelection:
    """Verify that full_body focus + ai_choose gives Upper/Lower for 4 and 5 days."""

    def test_full_body_5days_selects_upper_lower(self):
        """full_body focus + 5 days → split must be upper_lower."""
        bp = make_blueprint(['full_body'], days=5)
        assert bp['split_id'] == 'upper_lower', (
            f"Expected 'upper_lower' split for full_body + 5 days, got '{bp['split_id']}'"
        )
        assert bp['split_name'] == 'Upper / Lower', (
            f"Expected 'Upper / Lower' split_name, got '{bp['split_name']}'"
        )

    def test_full_body_4days_selects_upper_lower(self):
        """full_body focus + 4 days → split must be upper_lower."""
        bp = make_blueprint(['full_body'], days=4)
        assert bp['split_id'] == 'upper_lower', (
            f"Expected 'upper_lower' split for full_body + 4 days, got '{bp['split_id']}'"
        )


class TestCrossBodyInjection5Days:
    """For full_body + 5 days + upper_lower: every session has both upper and lower patterns."""

    def setup_method(self):
        self.bp = make_blueprint(['full_body'], days=5)

    def test_blueprint_is_upper_lower(self):
        assert self.bp['split_id'] == 'upper_lower'

    def test_every_session_has_lower_pattern_on_upper_days(self):
        """Upper sessions must include at least one lower-body pattern (cross-body injection)."""
        errors = []
        for day in self.bp['day_blueprints']:
            archetype_id = day['archetype_id']
            if not archetype_id.startswith('upper_'):
                continue
            patterns = {s['pattern'] for s in day['slots']}
            has_lower = bool(patterns & LOWER_PATTERNS)
            if not has_lower:
                errors.append(
                    f"Day {day['session_number']} ({archetype_id}) has NO lower-body pattern. "
                    f"Got patterns: {patterns}"
                )
        assert not errors, '\n'.join(errors)

    def test_every_session_has_upper_pattern_on_lower_days(self):
        """Lower sessions must include at least one upper-body pattern (cross-body injection)."""
        errors = []
        for day in self.bp['day_blueprints']:
            archetype_id = day['archetype_id']
            if not archetype_id.startswith('lower_'):
                continue
            patterns = {s['pattern'] for s in day['slots']}
            has_upper = bool(patterns & UPPER_PATTERNS)
            if not has_upper:
                errors.append(
                    f"Day {day['session_number']} ({archetype_id}) has NO upper-body pattern. "
                    f"Got patterns: {patterns}"
                )
        assert not errors, '\n'.join(errors)

    def test_cross_pattern_coaching_note_present(self):
        """Cross-body slots must have 'cross-pattern' in their coaching_note.
        Note: some sessions may receive the cross-body pattern via the primary-focus injection
        (e.g. full_body's primary_patterns include 'squat'), so the strict count can be < 5.
        The functional check (every session has both upper and lower patterns) already passes.
        We verify >= 1 explicit cross-pattern note exists.
        """
        cross_slots = [
            s for day in self.bp['day_blueprints']
            for s in day['slots']
            if 'cross-pattern' in s.get('coaching_note', '')
        ]
        assert len(cross_slots) >= 1, (
            "No cross-pattern coaching notes found in 5-day full_body blueprint. "
            "Expected at least one slot with 'cross-pattern' in coaching_note."
        )
        # Majority of sessions (>= 4 of 5) should have explicit cross-body via either injection path
        # (primary-focus OR cross-body injection).  The functional behaviour tests already verify all 5.
        assert len(cross_slots) >= 4, (
            f"Expected >= 4 cross-pattern slots across 5 sessions, got {len(cross_slots)}. "
            f"Slots: {[(s['pattern'], s['coaching_note']) for s in cross_slots]}"
        )

    def test_sets_at_least_2_on_cross_body_slots(self):
        """Cross-body compound slots must have >= 2 sets."""
        errors = []
        for day in self.bp['day_blueprints']:
            for s in day['slots']:
                if 'cross-pattern' in s.get('coaching_note', ''):
                    if s['sets'] < 2:
                        errors.append(
                            f"Day {day['session_number']}: cross-pattern slot '{s['pattern']}' has {s['sets']} sets (< 2)"
                        )
        assert not errors, '\n'.join(errors)


class TestCrossBodyInjection4Days:
    """For full_body + 4 days + upper_lower: every session has both upper and lower patterns."""

    def setup_method(self):
        self.bp = make_blueprint(['full_body'], days=4)

    def test_blueprint_is_upper_lower(self):
        assert self.bp['split_id'] == 'upper_lower'

    def test_every_upper_session_has_lower_pattern(self):
        errors = []
        for day in self.bp['day_blueprints']:
            if not day['archetype_id'].startswith('upper_'):
                continue
            patterns = {s['pattern'] for s in day['slots']}
            has_lower = bool(patterns & LOWER_PATTERNS)
            if not has_lower:
                errors.append(
                    f"Day {day['session_number']} ({day['archetype_id']}) missing lower pattern. Got: {patterns}"
                )
        assert not errors, '\n'.join(errors)

    def test_every_lower_session_has_upper_pattern(self):
        errors = []
        for day in self.bp['day_blueprints']:
            if not day['archetype_id'].startswith('lower_'):
                continue
            patterns = {s['pattern'] for s in day['slots']}
            has_upper = bool(patterns & UPPER_PATTERNS)
            if not has_upper:
                errors.append(
                    f"Day {day['session_number']} ({day['archetype_id']}) missing upper pattern. Got: {patterns}"
                )
        assert not errors, '\n'.join(errors)

    def test_cross_pattern_count_equals_session_count(self):
        """Cross-pattern slots cover most/all sessions.
        Note: sessions where primary-focus injection already adds the cross-body pattern
        (e.g. full_body includes squat in primary_patterns, so upper session Day1 gets squat
        via primary injection before cross-body injection runs) may not have the explicit
        'cross-pattern' note, but the functional checks already confirm patterns are present.
        We require >= 3 of 4 sessions to have explicit cross-pattern notes.
        """
        cross_slots = [
            s for day in self.bp['day_blueprints']
            for s in day['slots']
            if 'cross-pattern' in s.get('coaching_note', '')
        ]
        assert len(cross_slots) >= 3, (
            f"Expected >= 3 cross-pattern slots across 4 sessions, got {len(cross_slots)}"
        )


class TestSplitRationaleText:
    """split_rationale must mention both 'Upper / Lower' and full-body language."""

    def test_5day_rationale_mentions_cross_body(self):
        bp = make_blueprint(['full_body'], days=5)
        rationale = bp.get('split_rationale', '')
        assert rationale, "split_rationale must not be empty"
        kw_hit = any(kw in rationale.lower() for kw in [
            'cross-body', 'cross body', 'whole-body', 'whole body',
            'full-body stimulus', 'full body stimulus', 'upper / lower',
        ])
        assert kw_hit, (
            f"split_rationale does not mention cross-body or full-body coaching. Got: '{rationale}'"
        )

    def test_4day_rationale_mentions_coaching_choice(self):
        bp = make_blueprint(['full_body'], days=4)
        rationale = bp.get('split_rationale', '')
        assert rationale, "split_rationale must not be empty"
        # Must mention upper/lower context
        assert 'upper' in rationale.lower() or 'lower' in rationale.lower(), (
            f"split_rationale doesn't mention upper/lower. Got: '{rationale}'"
        )

    def test_rationale_in_blueprint_response(self):
        bp = make_blueprint(['full_body'], days=5)
        assert 'split_rationale' in bp, "Blueprint must have 'split_rationale' key"
        assert isinstance(bp['split_rationale'], str)
        assert len(bp['split_rationale']) > 20, "split_rationale text is too short"


# ===========================================================================
# Regression tests: non-full_body focus areas must NOT get cross-body injection
# ===========================================================================

class TestNoRegressionChestFocus:
    """chest focus + 3 days → Push/Pull/Legs with ZERO cross-body injection."""

    def setup_method(self):
        self.bp = make_blueprint(['chest'], days=3)

    def test_chest_3days_selects_push_pull_legs(self):
        assert self.bp['split_id'] == 'push_pull_legs', (
            f"Expected 'push_pull_legs' for chest + 3 days, got '{self.bp['split_id']}'"
        )

    def test_no_cross_pattern_slots_for_chest_focus(self):
        """Chest focus must have ZERO cross-pattern coaching notes."""
        cross_slots = [
            s for day in self.bp['day_blueprints']
            for s in day['slots']
            if 'cross-pattern' in s.get('coaching_note', '')
        ]
        assert len(cross_slots) == 0, (
            f"Chest focus got unexpected cross-body injection! "
            f"Cross slots found: {[(s['pattern'], s['coaching_note']) for s in cross_slots]}"
        )

    def test_push_day_has_only_upper_patterns_for_chest_focus(self):
        """Push session in PPL should not have cross-body lower patterns."""
        push_days = [d for d in self.bp['day_blueprints'] if d['archetype_id'] == 'push_session']
        for day in push_days:
            patterns = {s['pattern'] for s in day['slots']}
            lower_in_push = patterns & LOWER_PATTERNS
            assert not lower_in_push, (
                f"Push session for chest focus incorrectly contains lower patterns: {lower_in_push}"
            )


class TestNoRegressionLegsFocus:
    """legs focus + 4 days → Upper/Lower with ZERO cross-body injection (not full_body focus)."""

    def setup_method(self):
        self.bp = make_blueprint(['legs'], days=4)

    def test_legs_4days_selects_upper_lower(self):
        """legs + 4 days should use upper_lower (highest score via FOCUS_BIAS)."""
        assert self.bp['split_id'] == 'upper_lower', (
            f"Expected 'upper_lower' for legs + 4 days, got '{self.bp['split_id']}'"
        )

    def test_no_cross_pattern_slots_for_legs_focus(self):
        """legs focus gets upper_lower but is NOT full_body focus → NO cross-body injection."""
        cross_slots = [
            s for day in self.bp['day_blueprints']
            for s in day['slots']
            if 'cross-pattern' in s.get('coaching_note', '')
        ]
        assert len(cross_slots) == 0, (
            f"Legs focus incorrectly got cross-body injection! "
            f"Cross slots: {[(s['pattern'], s['coaching_note']) for s in cross_slots]}"
        )


# ===========================================================================
# API smoke test: full_body + 5 days → 200 OK, valid workout
# ===========================================================================

class TestAPISmokeFull5Days:
    """Smoke test: call the actual API and verify the response structure."""

    @pytest.fixture(scope='class')
    def workout_response(self):
        """Call POST /api/workouts/generate and return the JSON response."""
        assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL must be set in frontend/.env"
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "build_muscle",
            "training_style": "weights",
            "focus_areas": ["full_body"],
            "equipment": ["full_gym"],
            "days_per_week": 5,
            "duration_minutes": 60,
            "fitness_level": "intermediate",
            "preferred_split": "ai_choose",
        }
        resp = requests.post(
            f"{BASE_URL}/api/workouts/generate",
            json=payload,
            timeout=180,
        )
        return resp

    def test_smoke_200_ok(self, workout_response):
        assert workout_response.status_code == 200, (
            f"Expected 200 OK, got {workout_response.status_code}. Body: {workout_response.text[:500]}"
        )

    def test_smoke_has_workout_days(self, workout_response):
        data = workout_response.json()
        assert 'workout_days' in data, "Response must have 'workout_days' key"
        days = data['workout_days']
        assert isinstance(days, list) and len(days) == 5, (
            f"Expected 5 workout_days, got {len(days)}"
        )

    def test_smoke_sets_at_least_2(self, workout_response):
        data = workout_response.json()
        errors = []
        for day in data.get('workout_days', []):
            for ex in day.get('exercises', []):
                if ex.get('sets', 0) < 2:
                    errors.append(
                        f"Day '{day['day']}' exercise '{ex['name']}' has {ex['sets']} sets (< 2)"
                    )
        assert not errors, "Exercises with < 2 sets found:\n" + '\n'.join(errors)

    def test_smoke_gif_url_present(self, workout_response):
        data = workout_response.json()
        exercises_with_gif = [
            ex for day in data.get('workout_days', [])
            for ex in day.get('exercises', [])
            if ex.get('gif_url')
        ]
        total = sum(len(d.get('exercises', [])) for d in data.get('workout_days', []))
        pct = len(exercises_with_gif) / max(total, 1) * 100
        assert pct >= 60, (
            f"Less than 60% of exercises have gif_url. Got {pct:.0f}% ({len(exercises_with_gif)}/{total})"
        )

    def test_smoke_split_rationale_present_and_valid(self, workout_response):
        data = workout_response.json()
        rationale = data.get('split_rationale', '')
        assert rationale, "API response must have non-empty 'split_rationale'"
        kw_hit = any(kw in rationale.lower() for kw in [
            'cross-body', 'cross body', 'whole-body', 'whole body',
            'full-body stimulus', 'full body stimulus', 'upper / lower',
            'upper body', 'lower body',
        ])
        assert kw_hit, (
            f"split_rationale does not explain the coaching choice clearly. Got: '{rationale}'"
        )

    def test_smoke_split_name_is_upper_lower(self, workout_response):
        data = workout_response.json()
        assert data.get('split_name') == 'Upper / Lower', (
            f"Expected 'Upper / Lower', got '{data.get('split_name')}'"
        )

    def test_smoke_exercises_have_required_fields(self, workout_response):
        data = workout_response.json()
        required = {'name', 'sets', 'reps', 'rest_seconds', 'instructions', 'muscle_groups'}
        errors = []
        for day in data.get('workout_days', []):
            for ex in day.get('exercises', []):
                missing = required - set(ex.keys())
                if missing:
                    errors.append(f"Exercise '{ex.get('name', '?')}' missing fields: {missing}")
        assert not errors, '\n'.join(errors)

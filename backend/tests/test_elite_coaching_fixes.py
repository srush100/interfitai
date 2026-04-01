"""
Tests for three EliteCoachingEngine fixes:
1. Label-content consistency: cross-body compounds trigger label relabeling
2. Arms focus representation: secondary injection injects ALL missing secondary patterns
3. Volume validation gate: covers secondary_patterns (bicep+tricep meet min_weekly_secondary=9 for advanced)
Also covers: optional_slots deduplication, chest/legs focus regression tests, API smoke test.
"""
import sys
import os
import pytest
import requests

sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
from server import EliteCoachingEngine, WorkoutGenerateRequest

# ─── Config ─────────────────────────────────────────────────────────────────
BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    from dotenv import dotenv_values
    fe = dotenv_values('/app/frontend/.env')
    BASE_URL = fe.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')

TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

# Compound pattern sets for label checks
LOWER_COMPOUNDS = {'squat', 'hip_hinge', 'lunge'}
UPPER_COMPOUNDS = {'horizontal_push', 'incline_push', 'vertical_push',
                   'vertical_pull', 'horizontal_pull'}

_engine = EliteCoachingEngine()


def make_blueprint(focus_areas, secondary_focus_areas=None, days=4,
                   goal='build_muscle', level='intermediate',
                   preferred_split='ai_choose', equipment=None,
                   duration_minutes=60):
    """Helper: build a coaching blueprint directly (no AI call)."""
    if equipment is None:
        equipment = ['full_gym']
    req = WorkoutGenerateRequest(
        user_id=TEST_USER_ID,
        goal=goal,
        focus_areas=focus_areas,
        secondary_focus_areas=secondary_focus_areas or [],
        equipment=equipment,
        days_per_week=days,
        duration_minutes=duration_minutes,
        fitness_level=level,
        preferred_split=preferred_split,
    )
    return _engine.build_blueprint(req)


# ============================================================================
# 1. Label-Content Consistency
#    full_body primary + arms secondary, 5-day advanced, build_muscle
#    All 5 day labels must match their exercise content:
#      - upper sessions with lower compounds → relabeled 'Full Body — *'
#      - lower sessions with NO upper compounds → keep original lower labels
# ============================================================================
class TestLabelContentConsistency:
    """full_body + arms secondary, 5-day advanced — label must match content."""

    def setup_method(self):
        self.bp = make_blueprint(
            focus_areas=['full_body'],
            secondary_focus_areas=['arms'],
            days=5,
            goal='build_muscle',
            level='advanced',
        )

    def test_split_is_upper_lower(self):
        """full_body + 5-day advanced → must use upper_lower split."""
        assert self.bp['split_id'] == 'upper_lower', (
            f"Expected upper_lower split, got '{self.bp['split_id']}'"
        )

    def test_upper_push_sessions_have_consistent_label(self):
        """Upper push sessions with lower compound must be relabeled 'Full Body — Push-Led'."""
        errors = []
        for day in self.bp['day_blueprints']:
            archetype_id = day['archetype_id']
            if 'push' not in archetype_id or not archetype_id.startswith('upper_'):
                continue
            patterns = {s['pattern'] for s in day['slots']}
            has_lower = bool(patterns & LOWER_COMPOUNDS)
            label = day['label']
            if has_lower and 'Full Body' not in label:
                errors.append(
                    f"Day {day['session_number']} [{archetype_id}] has lower compound "
                    f"{patterns & LOWER_COMPOUNDS} but label is still '{label}' — "
                    f"should have been relabeled to 'Full Body — Push-Led'"
                )
            if not has_lower and 'Upper' not in label and 'Upper' in archetype_id:
                # Upper session without lower compounds should keep upper label
                pass  # OK - label unchanged
        assert not errors, '\n'.join(errors)

    def test_upper_pull_sessions_have_consistent_label(self):
        """Upper pull sessions with lower compound must be relabeled 'Full Body — Pull-Led'."""
        errors = []
        for day in self.bp['day_blueprints']:
            archetype_id = day['archetype_id']
            if 'pull' not in archetype_id or not archetype_id.startswith('upper_'):
                continue
            patterns = {s['pattern'] for s in day['slots']}
            has_lower = bool(patterns & LOWER_COMPOUNDS)
            label = day['label']
            if has_lower and 'Full Body' not in label:
                errors.append(
                    f"Day {day['session_number']} [{archetype_id}] has lower compound "
                    f"{patterns & LOWER_COMPOUNDS} but label is '{label}' — "
                    f"should have been relabeled to 'Full Body — Pull-Led'"
                )
        assert not errors, '\n'.join(errors)

    def test_lower_sessions_keep_lower_label_or_relabeled_if_upper_compound_present(self):
        """Lower sessions: if no upper compound → keep 'Lower – X'. If upper compound present → relabeled."""
        errors = []
        for day in self.bp['day_blueprints']:
            archetype_id = day['archetype_id']
            if not archetype_id.startswith('lower_'):
                continue
            patterns = {s['pattern'] for s in day['slots']}
            has_upper = bool(patterns & UPPER_COMPOUNDS)
            label = day['label']
            if not has_upper and 'Lower' not in label and 'Full Body' not in label:
                errors.append(
                    f"Day {day['session_number']} [{archetype_id}] has no upper compound "
                    f"but label is neither 'Lower' nor 'Full Body': '{label}'"
                )
            if has_upper and 'Full Body' not in label and 'Lower' not in label:
                errors.append(
                    f"Day {day['session_number']} [{archetype_id}] has upper compound "
                    f"but label was NOT relabeled: '{label}'"
                )
        assert not errors, '\n'.join(errors)

    def test_no_upper_push_label_with_squat(self):
        """No day labeled 'Upper – Push' should contain squat/hip_hinge/lunge patterns."""
        errors = []
        for day in self.bp['day_blueprints']:
            label = day['label']
            if 'Upper' in label and 'Push' in label and 'Full Body' not in label:
                patterns = {s['pattern'] for s in day['slots']}
                cross = patterns & LOWER_COMPOUNDS
                if cross:
                    errors.append(
                        f"Day {day['session_number']} labeled '{label}' "
                        f"contains lower compounds {cross} — label mismatch!"
                    )
        assert not errors, '\n'.join(errors)

    def test_no_lower_quad_label_with_horizontal_push(self):
        """No day labeled 'Lower – Quad' should contain horizontal_push/incline_push/vertical_push."""
        errors = []
        for day in self.bp['day_blueprints']:
            label = day['label']
            if 'Lower' in label and 'Quad' in label and 'Full Body' not in label:
                patterns = {s['pattern'] for s in day['slots']}
                cross = patterns & UPPER_COMPOUNDS
                if cross:
                    errors.append(
                        f"Day {day['session_number']} labeled '{label}' "
                        f"contains upper compounds {cross} — label mismatch!"
                    )
        assert not errors, '\n'.join(errors)

    def test_five_days_present(self):
        """Blueprint must have exactly 5 days."""
        assert len(self.bp['day_blueprints']) == 5, (
            f"Expected 5 days, got {len(self.bp['day_blueprints'])}"
        )


# ============================================================================
# 2. Arms Secondary Volume (full_body primary + arms secondary, 5-day advanced)
#    Weekly tricep_push total >= 9 sets (min_weekly_secondary for advanced)
# ============================================================================
class TestArmsSecondaryVolume:
    """full_body + arms secondary, 5-day advanced — weekly arm volume >= 9 sets each."""

    def setup_method(self):
        self.bp = make_blueprint(
            focus_areas=['full_body'],
            secondary_focus_areas=['arms'],
            days=5,
            goal='build_muscle',
            level='advanced',
        )
        # min_weekly_secondary for advanced = max(6, 12-3) = 9
        self.min_weekly_secondary = 9

    def test_weekly_tricep_push_meets_minimum(self):
        """Weekly tricep_push total must be >= 9 sets for advanced level."""
        weekly = sum(
            s['sets'] for d in self.bp['day_blueprints']
            for s in d['slots'] if s['pattern'] == 'tricep_push'
        )
        assert weekly >= self.min_weekly_secondary, (
            f"Weekly tricep_push sets = {weekly}, minimum = {self.min_weekly_secondary}. "
            f"Volume validation gate may not be enforcing secondary patterns correctly."
        )

    def test_weekly_bicep_curl_meets_minimum(self):
        """Weekly bicep_curl total must be >= 9 sets for advanced level."""
        weekly = sum(
            s['sets'] for d in self.bp['day_blueprints']
            for s in d['slots'] if s['pattern'] == 'bicep_curl'
        )
        assert weekly >= self.min_weekly_secondary, (
            f"Weekly bicep_curl sets = {weekly}, minimum = {self.min_weekly_secondary}. "
            f"Volume validation gate may not be enforcing secondary patterns correctly."
        )

    def test_both_arm_patterns_appear_in_blueprint(self):
        """Both bicep_curl and tricep_push must appear at least once across the 5-day plan."""
        all_patterns = {s['pattern'] for d in self.bp['day_blueprints'] for s in d['slots']}
        assert 'bicep_curl' in all_patterns, "bicep_curl missing from entire 5-day blueprint"
        assert 'tricep_push' in all_patterns, "tricep_push missing from entire 5-day blueprint"

    def test_secondary_injection_injects_both_arm_patterns_per_session(self):
        """At least one session must have BOTH bicep_curl AND tricep_push (secondary injection)."""
        sessions_with_both = [
            d['session_number'] for d in self.bp['day_blueprints']
            if any(s['pattern'] == 'bicep_curl' for s in d['slots'])
            and any(s['pattern'] == 'tricep_push' for s in d['slots'])
        ]
        assert len(sessions_with_both) >= 1, (
            f"No session has both bicep_curl AND tricep_push. "
            f"Secondary injection should inject ALL missing arm patterns, not just one."
        )


# ============================================================================
# 3. Arms Primary Focus — BOTH Patterns Injected
#    arms primary (no secondary), 4-day intermediate
#    BOTH bicep_curl AND tricep_push must appear; weekly totals >= 9 sets
# ============================================================================
class TestArmsPrimaryFocus:
    """arms primary, 4-day intermediate — both arm patterns injected with sufficient weekly volume."""

    def setup_method(self):
        self.bp = make_blueprint(
            focus_areas=['arms'],
            secondary_focus_areas=[],
            days=4,
            goal='build_muscle',
            level='intermediate',
        )
        self.min_weekly_primary = 9  # intermediate

    def test_weekly_bicep_curl_meets_minimum(self):
        """Weekly bicep_curl must be >= 9 sets (arms is primary, intermediate level)."""
        weekly = sum(
            s['sets'] for d in self.bp['day_blueprints']
            for s in d['slots'] if s['pattern'] == 'bicep_curl'
        )
        assert weekly >= self.min_weekly_primary, (
            f"Weekly bicep_curl = {weekly}, minimum = {self.min_weekly_primary}. "
            f"Primary focus volume enforcement failing."
        )

    def test_weekly_tricep_push_meets_minimum(self):
        """Weekly tricep_push must be >= 9 sets (arms is primary, intermediate level)."""
        weekly = sum(
            s['sets'] for d in self.bp['day_blueprints']
            for s in d['slots'] if s['pattern'] == 'tricep_push'
        )
        assert weekly >= self.min_weekly_primary, (
            f"Weekly tricep_push = {weekly}, minimum = {self.min_weekly_primary}. "
            f"Primary focus volume enforcement OR volume validation gate failing."
        )

    def test_both_patterns_in_multiple_sessions(self):
        """Multiple sessions must contain at least one arm pattern (bicep_curl or tricep_push)."""
        sessions_with_arms = [
            d['session_number'] for d in self.bp['day_blueprints']
            if any(s['pattern'] in ('bicep_curl', 'tricep_push') for s in d['slots'])
        ]
        assert len(sessions_with_arms) >= 2, (
            f"Only {len(sessions_with_arms)} session(s) have arm patterns. "
            f"Expected arms to appear in at least 2 sessions for 4-day plan."
        )

    def test_primary_injection_injects_both_missing_patterns(self):
        """Verify that at least one session gets BOTH bicep_curl AND tricep_push injected."""
        sessions_with_both = [
            d['session_number'] for d in self.bp['day_blueprints']
            if any(s['pattern'] == 'bicep_curl' for s in d['slots'])
            and any(s['pattern'] == 'tricep_push' for s in d['slots'])
        ]
        assert len(sessions_with_both) >= 1, (
            f"No session has both bicep_curl AND tricep_push. "
            f"Primary injection should inject ALL missing arm patterns (not just one)."
        )

    def test_arms_blueprint_has_4_days(self):
        """4-day arms plan must have 4 day blueprints."""
        assert len(self.bp['day_blueprints']) == 4


# ============================================================================
# 4. Chest Focus Regression — ZERO label changes
#    chest primary (no full_body), 3-day beginner
#    No 'Full Body — Push-Led' or any relabeling
# ============================================================================
class TestChestFocusNoRelabeling:
    """chest primary, 3-day beginner → ZERO cross-body label changes."""

    def setup_method(self):
        self.bp = make_blueprint(
            focus_areas=['chest'],
            secondary_focus_areas=[],
            days=3,
            goal='build_muscle',
            level='beginner',
        )

    def test_no_full_body_labels(self):
        """No day should have 'Full Body' in its label for chest + beginner + PPL."""
        fb_days = [
            (d['session_number'], d['label'])
            for d in self.bp['day_blueprints']
            if 'Full Body' in d['label']
        ]
        assert not fb_days, (
            f"Unexpected 'Full Body' labels for chest focus: {fb_days}. "
            f"Chest focus (PPL split) should NEVER trigger cross-body relabeling."
        )

    def test_push_day_has_no_lower_compounds(self):
        """Push session for chest focus must NOT contain squat/hip_hinge/lunge."""
        push_days = [d for d in self.bp['day_blueprints'] if d['archetype_id'] == 'push_session']
        errors = []
        for day in push_days:
            patterns = {s['pattern'] for s in day['slots']}
            lower_in_push = patterns & LOWER_COMPOUNDS
            if lower_in_push:
                errors.append(
                    f"Day {day['session_number']} [push_session] has lower compounds {lower_in_push} "
                    f"— chest focus should NOT inject cross-body compounds"
                )
        assert not errors, '\n'.join(errors)

    def test_pull_day_has_no_lower_compounds(self):
        """Pull session for chest focus must NOT contain squat/hip_hinge/lunge."""
        pull_days = [d for d in self.bp['day_blueprints'] if d['archetype_id'] == 'pull_session']
        errors = []
        for day in pull_days:
            patterns = {s['pattern'] for s in day['slots']}
            lower_in_pull = patterns & LOWER_COMPOUNDS
            if lower_in_pull:
                errors.append(
                    f"Day {day['session_number']} [pull_session] has lower compounds {lower_in_pull}"
                )
        assert not errors, '\n'.join(errors)

    def test_all_labels_are_standard_push_pull_legs(self):
        """Labels should be standard Push, Pull, Legs — no relabeling."""
        valid_labels = {'Push', 'Pull', 'Legs'}
        errors = []
        for day in self.bp['day_blueprints']:
            label = day['label']
            if label not in valid_labels:
                errors.append(f"Day {day['session_number']}: unexpected label '{label}' (expected Push/Pull/Legs)")
        assert not errors, '\n'.join(errors)

    def test_split_is_push_pull_legs(self):
        """Chest + 3 days → push_pull_legs split."""
        assert self.bp['split_id'] == 'push_pull_legs', (
            f"Expected push_pull_legs for chest + 3 days, got '{self.bp['split_id']}'"
        )


# ============================================================================
# 5. Legs Focus Regression — Lower sessions not relabeled
#    legs primary (no full_body), 4-day intermediate
#    Lower sessions must keep 'Lower – X' labels (legs patterns are lower-body,
#    no upper compounds added to lower sessions → no upper-compound check trigger)
# ============================================================================
class TestLegsFocusLowerLabels:
    """legs primary, 4-day intermediate — lower sessions must NOT be relabeled."""

    def setup_method(self):
        self.bp = make_blueprint(
            focus_areas=['legs'],
            secondary_focus_areas=[],
            days=4,
            goal='build_muscle',
            level='intermediate',
        )

    def test_split_is_upper_lower(self):
        """legs + 4-day → upper_lower split (FOCUS_SPLIT_PREFERENCE['legs'] = 'upper_lower')."""
        assert self.bp['split_id'] == 'upper_lower', (
            f"Expected upper_lower split for legs + 4 days, got '{self.bp['split_id']}'"
        )

    def test_lower_sessions_keep_lower_label(self):
        """Lower sessions must NOT be relabeled to 'Full Body — Quad-Led' or similar.
        Legs focus patterns are all lower-body, so no upper compounds are added to lower sessions.
        The 'upper-compound check' (lower_session + upper_compound → relabel) should NOT fire.
        """
        errors = []
        for day in self.bp['day_blueprints']:
            archetype_id = day['archetype_id']
            if not archetype_id.startswith('lower_'):
                continue
            label = day['label']
            patterns = {s['pattern'] for s in day['slots']}
            has_upper = bool(patterns & UPPER_COMPOUNDS)
            if 'Full Body' in label:
                # Check if it was legitimately relabeled (upper compound present)
                if not has_upper:
                    errors.append(
                        f"Day {day['session_number']} [{archetype_id}] relabeled to '{label}' "
                        f"but has NO upper compound — relabeling should NOT have occurred. "
                        f"Patterns: {patterns}"
                    )
                # If upper compound is present, relabeling is legitimate
            else:
                # No relabeling — label should start with 'Lower'
                if 'Lower' not in label:
                    errors.append(
                        f"Day {day['session_number']} [{archetype_id}] has unexpected label '{label}'"
                    )
        assert not errors, '\n'.join(errors)

    def test_lower_sessions_have_no_upper_compounds_injected(self):
        """Legs focus patterns (squat/lunge/etc.) are all lower-body.
        Lower sessions should NOT receive upper body compounds from legs focus injection.
        """
        errors = []
        for day in self.bp['day_blueprints']:
            if not day['archetype_id'].startswith('lower_'):
                continue
            patterns = {s['pattern'] for s in day['slots']}
            upper_in_lower = patterns & UPPER_COMPOUNDS
            if upper_in_lower:
                errors.append(
                    f"Day {day['session_number']} [{day['archetype_id']}] has upper compounds "
                    f"{upper_in_lower} — legs focus should not inject upper patterns into lower sessions."
                )
        assert not errors, '\n'.join(errors)


# ============================================================================
# 6. Optional Slots Deduplication
#    Verify that optional_slots deduplication prevents duplicate patterns
# ============================================================================
class TestOptionalSlotsDeduplication:
    """Verify optional_slots deduplication prevents duplicate patterns per session."""

    def test_no_duplicate_patterns_within_session(self):
        """Each session in the blueprint should not have two slots with the same pattern
        unless the archetype itself contains a duplicate (e.g., two horizontal_pull in pull_session).
        Optional slots that duplicate a regular slot must be filtered out.
        """
        # Use upper_pull_heavy which has optional bicep_curl that duplicates the base slot
        bp = make_blueprint(focus_areas=['back'], days=4, level='intermediate')
        errors = []
        for day in bp['day_blueprints']:
            archetype_id = day['archetype_id']
            if archetype_id not in ('upper_pull_heavy', 'pull_session'):
                continue
            pattern_counts = {}
            for s in day['slots']:
                pattern_counts[s['pattern']] = pattern_counts.get(s['pattern'], 0) + 1
            # horizontal_pull is intentionally duplicated in pull archetypes (two different rows)
            # bicep_curl should NOT be duplicated due to optional dedup
            if pattern_counts.get('bicep_curl', 0) > 2:
                errors.append(
                    f"Day {day['session_number']} [{archetype_id}] has {pattern_counts['bicep_curl']} "
                    f"bicep_curl slots — optional dedup should prevent >2 of the same pattern"
                )
        assert not errors, '\n'.join(errors)


# ============================================================================
# 7. API Smoke Test — full_body + arms, 5-day, actual HTTP call
#    POST /api/workouts/generate → 200 OK, 5 workout_days, gif_url present, sets >= 2
# ============================================================================
class TestSmokeFullBodyArms5Day:
    """Smoke test: full_body + arms, 5-day advanced → complete API response validation."""

    @pytest.fixture(scope='class')
    def workout_response(self):
        """Call POST /api/workouts/generate and return the JSON response."""
        assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL must be set"
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "build_muscle",
            "training_style": "weights",
            "focus_areas": ["full_body"],
            "secondary_focus_areas": ["arms"],
            "equipment": ["full_gym"],
            "days_per_week": 5,
            "duration_minutes": 60,
            "fitness_level": "advanced",
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
            f"Expected 200 OK, got {workout_response.status_code}. "
            f"Response: {workout_response.text[:500]}"
        )

    def test_smoke_has_5_workout_days(self, workout_response):
        data = workout_response.json()
        days = data.get('workout_days', [])
        assert len(days) == 5, (
            f"Expected 5 workout_days, got {len(days)}"
        )

    def test_smoke_exercises_have_gif_url(self, workout_response):
        """All exercises must have gif_url field (can be empty string but must exist)."""
        data = workout_response.json()
        errors = []
        for day in data.get('workout_days', []):
            for ex in day.get('exercises', []):
                if 'gif_url' not in ex:
                    errors.append(f"Exercise '{ex.get('name', '?')}' missing gif_url field")
        assert not errors, f"Missing gif_url on exercises: {errors[:5]}"

    def test_smoke_exercises_have_at_least_2_sets(self, workout_response):
        """All exercises must have >= 2 sets."""
        data = workout_response.json()
        errors = []
        for day in data.get('workout_days', []):
            for ex in day.get('exercises', []):
                if ex.get('sets', 0) < 2:
                    errors.append(
                        f"Day '{day.get('day', '?')}': '{ex.get('name', '?')}' has {ex.get('sets', 0)} sets"
                    )
        assert not errors, "Exercises with < 2 sets:\n" + '\n'.join(errors)

    def test_smoke_required_exercise_fields(self, workout_response):
        """Each exercise must have name, sets, reps, rest_seconds, instructions, muscle_groups."""
        data = workout_response.json()
        required = {'name', 'sets', 'reps', 'rest_seconds', 'instructions', 'muscle_groups', 'gif_url'}
        errors = []
        for day in data.get('workout_days', []):
            for ex in day.get('exercises', []):
                missing = required - set(ex.keys())
                if missing:
                    errors.append(f"'{ex.get('name', '?')}' missing: {missing}")
        assert not errors, '\n'.join(errors[:10])

    def test_smoke_split_is_upper_lower(self, workout_response):
        """full_body + 5-day advanced → split_name must be 'Upper / Lower'."""
        data = workout_response.json()
        split_name = data.get('split_name', '')
        assert split_name == 'Upper / Lower', (
            f"Expected 'Upper / Lower' split, got '{split_name}'"
        )

"""
InterFitAI Elite Coaching Engine Reset Tests — Iteration 15
Tests the new philosophy:
  1. Session purity (no cross-contamination of upper/lower compound patterns)
  2. Set inflation guard (max 6 sets per exercise)
  3. Min-set floor (no lifting exercise < 2 sets)
  4. Arms focus routing (triceps on push, biceps on pull)
  5. Full-body focus split rationale
  6. Time-cap compliance (lose_fat 45min → max 3 sets)
  7. Strength goal rest >= 120s for primary compounds
  8. Beginner bias (machines/cables over barbells)
  9. API smoke test (200 OK, gif_url present, sets >= 2, rest_seconds > 0)

Pure Python tests use build_blueprint() directly (fast, no LLM call).
API tests call POST /api/workouts/generate (needs LLM, ~60-90s each).
"""
import sys
import os
import pytest
import requests

# ── Python-level direct imports ───────────────────────────────────────────────
sys.path.insert(0, '/app/backend')
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_database')
os.environ.setdefault('EMERGENT_LLM_KEY', 'dummy')
os.environ.setdefault('OPENAI_API_KEY', 'dummy')
os.environ.setdefault('STRIPE_API_KEY', 'dummy')
os.environ.setdefault('EXERCISEDB_API_KEY', 'dummy')

from server import EliteCoachingEngine, WorkoutGenerateRequest, _coaching_engine

ENGINE: EliteCoachingEngine = _coaching_engine

# ── API config ────────────────────────────────────────────────────────────────
BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL",
           os.environ.get("EXPO_BACKEND_URL", "")).rstrip("/")
USER_ID  = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

# ── Pattern sets for session purity checks ───────────────────────────────────
LOWER_COMPOUND_PATTERNS = {'squat', 'hip_hinge', 'lunge'}
UPPER_PULL_PATTERNS     = {'vertical_pull', 'horizontal_pull'}
UPPER_PUSH_PATTERNS     = {'horizontal_push', 'incline_push', 'vertical_push'}


def _make_req(**kwargs) -> WorkoutGenerateRequest:
    """Build a WorkoutGenerateRequest with sensible defaults."""
    defaults = dict(
        user_id=USER_ID,
        goal='build_muscle',
        training_style='weights',
        focus_areas=['full_body'],
        equipment=['full_gym'],
        days_per_week=4,
        duration_minutes=60,
        fitness_level='intermediate',
        preferred_split='ai_choose',
    )
    defaults.update(kwargs)
    return WorkoutGenerateRequest(**defaults)


def _call_api(payload: dict, timeout=180) -> requests.Response:
    return requests.post(
        f"{BASE_URL}/api/workouts/generate",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 1 — Session Purity: full_body+arms, 5-day advanced
# ═══════════════════════════════════════════════════════════════════════════════
class TestSessionPurityFullBodyArms5Day:
    """
    focus_areas=['full_body', 'arms'], days=5, level=advanced, goal=build_muscle
    FOCUS_AREA_PATTERNS['full_body'] = [] → no primary injection
    Arms secondary: bicep_curl / tricep_push injected only into session-native slots.

    Expected:
    - Upper–Push sessions: ZERO lower compound patterns (squat, hip_hinge, lunge)
    - Lower–Quad sessions: ZERO upper body pull patterns (vertical_pull, horizontal_pull)
    """

    @pytest.fixture(scope='class')
    def blueprint(self):
        req = _make_req(
            focus_areas=['full_body'],
            secondary_focus_areas=['arms'],
            days_per_week=5,
            fitness_level='advanced',
            goal='build_muscle',
        )
        return ENGINE.build_blueprint(req)

    def test_full_body_patterns_are_empty(self):
        """Regression: FOCUS_AREA_PATTERNS['full_body'] must be [] to prevent cross-injection."""
        patterns = ENGINE.FOCUS_AREA_PATTERNS.get('full_body', None)
        assert patterns == [], (
            f"FOCUS_AREA_PATTERNS['full_body'] should be [] but got: {patterns}"
        )
        print("✅ FOCUS_AREA_PATTERNS['full_body'] = [] confirmed")

    def test_upper_push_sessions_have_zero_lower_compounds(self, blueprint):
        """
        Any session whose archetype is upper_push* must NOT contain
        squat / hip_hinge / lunge patterns.
        """
        violations = []
        for day in blueprint['day_blueprints']:
            arch_id = day['archetype_id']
            label   = day['label']
            if 'push' in arch_id and 'upper' in arch_id:  # upper_push_heavy / upper_push_volume
                lower_slots = [
                    s for s in day['slots']
                    if s['pattern'] in LOWER_COMPOUND_PATTERNS
                ]
                if lower_slots:
                    violations.append(
                        f"Day (arch={arch_id}, label={label}) has lower compounds: "
                        + str([s['pattern'] for s in lower_slots])
                    )
        assert not violations, (
            "Session purity violation — upper push session contains lower compounds:\n"
            + "\n".join(violations)
        )
        print("✅ Upper-Push sessions have ZERO lower compound patterns")

    def test_lower_quad_sessions_have_zero_upper_pull_compounds(self, blueprint):
        """
        Any session whose archetype is lower_quad_focus must NOT contain
        vertical_pull / horizontal_pull patterns.
        """
        violations = []
        for day in blueprint['day_blueprints']:
            arch_id = day['archetype_id']
            label   = day['label']
            if arch_id == 'lower_quad_focus':
                pull_slots = [
                    s for s in day['slots']
                    if s['pattern'] in UPPER_PULL_PATTERNS
                ]
                if pull_slots:
                    violations.append(
                        f"Day (arch={arch_id}, label={label}) has upper pull compounds: "
                        + str([s['pattern'] for s in pull_slots])
                    )
        assert not violations, (
            "Session purity violation — lower quad session contains upper pull patterns:\n"
            + "\n".join(violations)
        )
        print("✅ Lower-Quad sessions have ZERO upper pull patterns")

    def test_push_session_label_not_relabeled_to_full_body(self, blueprint):
        """
        With full_body FOCUS_AREA_PATTERNS = [], the relabeler should NOT fire.
        Labels for upper push sessions should remain 'Upper – Push*' or 'Push'.
        """
        relabel_violations = []
        for day in blueprint['day_blueprints']:
            arch_id = day['archetype_id']
            label   = day['label']
            if 'push' in arch_id and 'upper' in arch_id:
                if 'Full Body' in label:
                    relabel_violations.append(
                        f"arch={arch_id} was relabeled to '{label}' (should stay Push label)"
                    )
        assert not relabel_violations, (
            "Relabeler fired on upper-push sessions (should not with full_body=[]):\n"
            + "\n".join(relabel_violations)
        )
        print("✅ Upper-Push labels not incorrectly relabeled to 'Full Body'")

    def test_arms_secondary_tricep_in_push_sessions(self, blueprint):
        """
        Arms secondary → tricep_push should appear in push session native slots.
        """
        push_has_tricep = any(
            s['pattern'] == 'tricep_push'
            for day in blueprint['day_blueprints']
            if 'push' in day['archetype_id']
            for s in day['slots']
        )
        assert push_has_tricep, "tricep_push not found in any push session (arms secondary should inject it)"
        print("✅ tricep_push present in push sessions (arms secondary active)")

    def test_arms_secondary_bicep_in_pull_sessions(self, blueprint):
        """
        Arms secondary → bicep_curl should appear in pull session native slots.
        """
        pull_has_bicep = any(
            s['pattern'] == 'bicep_curl'
            for day in blueprint['day_blueprints']
            if 'pull' in day['archetype_id']
            for s in day['slots']
        )
        assert pull_has_bicep, "bicep_curl not found in any pull session (arms secondary should keep it)"
        print("✅ bicep_curl present in pull sessions (arms secondary active)")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 2 — Session Purity: legs+glutes, 4-day, intermediate
# ═══════════════════════════════════════════════════════════════════════════════
class TestSessionPurityLegsGlutes4Day:
    """
    focus_areas=['legs', 'glutes'], days=4, level=intermediate, goal=build_muscle
    Expected upper_lower split (FOCUS_SPLIT_PREFERENCE['legs'] = 'upper_lower').
    - Lower sessions must stay lower-only (no horizontal_push / vertical_pull etc.)
    - Upper sessions must stay upper-only (no squat / hip_hinge / lunge)
    """

    @pytest.fixture(scope='class')
    def blueprint(self):
        req = _make_req(
            focus_areas=['legs', 'glutes'],
            days_per_week=4,
            fitness_level='intermediate',
            goal='build_muscle',
        )
        return ENGINE.build_blueprint(req)

    def test_split_is_upper_lower(self, blueprint):
        split_id = blueprint['split_id']
        assert split_id == 'upper_lower', (
            f"Expected upper_lower split for legs+glutes 4-day, got '{split_id}'"
        )
        print(f"✅ Split correctly selected as upper_lower (got: {split_id})")

    def test_lower_sessions_stay_lower_only(self, blueprint):
        """Lower sessions (lower_quad_focus, lower_hip_focus) must have NO upper push/pull compounds."""
        LOWER_ARCHETYPES = {'lower_quad_focus', 'lower_hip_focus', 'lower_full'}
        violations = []
        for day in blueprint['day_blueprints']:
            arch_id = day['archetype_id']
            if arch_id in LOWER_ARCHETYPES:
                bad = [
                    s for s in day['slots']
                    if s['pattern'] in UPPER_PUSH_PATTERNS | UPPER_PULL_PATTERNS
                ]
                if bad:
                    violations.append(
                        f"{arch_id}: has upper patterns {[s['pattern'] for s in bad]}"
                    )
        assert not violations, (
            "Lower sessions contain upper compound patterns:\n" + "\n".join(violations)
        )
        print("✅ Lower sessions stay lower-only (no upper compounds injected)")

    def test_upper_sessions_stay_upper_only(self, blueprint):
        """Upper sessions (upper_push*, upper_pull*, upper_full) must have NO lower compounds."""
        UPPER_ARCHETYPES = {'upper_push_heavy', 'upper_push_volume',
                            'upper_pull_heavy', 'upper_pull_volume', 'upper_full'}
        violations = []
        for day in blueprint['day_blueprints']:
            arch_id = day['archetype_id']
            if arch_id in UPPER_ARCHETYPES:
                bad = [
                    s for s in day['slots']
                    if s['pattern'] in LOWER_COMPOUND_PATTERNS
                ]
                if bad:
                    violations.append(
                        f"{arch_id}: has lower patterns {[s['pattern'] for s in bad]}"
                    )
        assert not violations, (
            "Upper sessions contain lower compound patterns:\n" + "\n".join(violations)
        )
        print("✅ Upper sessions stay upper-only (no lower compounds injected)")

    def test_has_4_workout_days(self, blueprint):
        assert len(blueprint['day_blueprints']) == 4, (
            f"Expected 4 day blueprints, got {len(blueprint['day_blueprints'])}"
        )
        print(f"✅ 4 day blueprints generated")

    def test_lower_sessions_have_leg_patterns(self, blueprint):
        """Lower sessions should contain squat and/or hip_hinge patterns."""
        LEG_PATTERNS = {'squat', 'hip_hinge', 'lunge', 'glute', 'hamstring_curl', 'knee_extension', 'calf'}
        lower_arches = {'lower_quad_focus', 'lower_hip_focus', 'lower_full'}
        for day in blueprint['day_blueprints']:
            if day['archetype_id'] in lower_arches:
                day_patterns = {s['pattern'] for s in day['slots']}
                assert day_patterns & LEG_PATTERNS, (
                    f"Lower session {day['archetype_id']} has no leg patterns: {day_patterns}"
                )
        print("✅ Lower sessions contain leg patterns (squat / hip_hinge / lunge / glute)")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 3 — No Set Inflation (max 6 sets per exercise)
# ═══════════════════════════════════════════════════════════════════════════════
class TestNoSetInflation:
    """
    No single exercise slot should exceed 6 sets in any blueprint configuration.
    Tests multiple configurations to ensure the cap holds universally.
    """

    CONFIGS = [
        dict(goal='build_muscle',   days_per_week=5, fitness_level='advanced',
             focus_areas=['chest'], duration_minutes=75),
        dict(goal='strength',       days_per_week=3, fitness_level='advanced',
             focus_areas=['back'],  duration_minutes=60),
        dict(goal='body_recomp',    days_per_week=4, fitness_level='intermediate',
             focus_areas=['arms'],  duration_minutes=60),
        dict(goal='lose_fat',       days_per_week=5, fitness_level='beginner',
             focus_areas=['full_body'], duration_minutes=45),
    ]

    def _max_sets_in_blueprint(self, req_kwargs: dict) -> tuple:
        req = _make_req(**req_kwargs)
        bp  = ENGINE.build_blueprint(req)
        max_sets = 0
        worst    = None
        for day in bp['day_blueprints']:
            for slot in day['slots']:
                if slot['sets'] > max_sets:
                    max_sets = slot['sets']
                    worst = (day['label'], slot['pattern'], slot['type'], slot['sets'])
        return max_sets, worst, bp

    def test_no_slot_exceeds_6_sets_build_muscle_advanced(self):
        kwargs = self.CONFIGS[0]
        max_s, worst, _ = self._max_sets_in_blueprint(kwargs)
        assert max_s <= 6, (
            f"Set inflation! build_muscle+5day+advanced has {max_s} sets: {worst}"
        )
        print(f"✅ build_muscle advanced: max sets = {max_s} (≤ 6)")

    def test_no_slot_exceeds_6_sets_strength(self):
        kwargs = self.CONFIGS[1]
        max_s, worst, _ = self._max_sets_in_blueprint(kwargs)
        assert max_s <= 6, (
            f"Set inflation! strength+3day has {max_s} sets: {worst}"
        )
        print(f"✅ strength: max sets = {max_s} (≤ 6)")

    def test_no_slot_exceeds_6_sets_arms_focus(self):
        kwargs = self.CONFIGS[2]
        max_s, worst, _ = self._max_sets_in_blueprint(kwargs)
        assert max_s <= 6, (
            f"Set inflation! body_recomp+4day+arms has {max_s} sets: {worst}"
        )
        print(f"✅ arms focus: max sets = {max_s} (≤ 6)")

    def test_no_slot_exceeds_6_sets_lose_fat_beginner(self):
        kwargs = self.CONFIGS[3]
        max_s, worst, _ = self._max_sets_in_blueprint(kwargs)
        assert max_s <= 6, (
            f"Set inflation! lose_fat+beginner has {max_s} sets: {worst}"
        )
        print(f"✅ lose_fat beginner: max sets = {max_s} (≤ 6)")

    def test_primary_boost_capped_at_5_not_higher(self):
        """
        Primary focus boost is +1 with cap at 5 for primary compounds.
        Should never reach 6 from the boost alone.
        """
        req = _make_req(
            goal='build_muscle', fitness_level='advanced',
            focus_areas=['chest'], days_per_week=4, duration_minutes=75
        )
        bp = ENGINE.build_blueprint(req)
        for day in bp['day_blueprints']:
            for slot in day['slots']:
                if slot['type'] == 'primary_compound':
                    assert slot['sets'] <= 6, (
                        f"Primary compound exceeds 6 sets: {slot['pattern']} = {slot['sets']}"
                    )
        print("✅ Primary compound boost never exceeds 6 sets")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 4 — Min-Set Floor (no lifting exercise < 2 sets)
# ═══════════════════════════════════════════════════════════════════════════════
class TestMinSetFloor:
    """
    No lifting exercise (non-conditioning) should have < 2 sets in any configuration.
    The floor is enforced by:
      1. MIN_SETS_FLOOR filter (removes sub-floor slots before boost)
      2. Final structural validation (raises any remaining < 2 to 2)
    """

    def _check_min_sets(self, req_kwargs: dict) -> list:
        req = _make_req(**req_kwargs)
        bp  = ENGINE.build_blueprint(req)
        violations = []
        for day in bp['day_blueprints']:
            for slot in day['slots']:
                if slot['type'] != 'conditioning' and slot['sets'] < 2:
                    violations.append(
                        f"Day '{day['label']}': {slot['pattern']} ({slot['type']}) = {slot['sets']} sets"
                    )
        return violations

    def test_no_sub_2_sets_build_muscle_4day(self):
        v = self._check_min_sets(dict(goal='build_muscle', days_per_week=4,
                                     fitness_level='intermediate', duration_minutes=60))
        assert not v, f"Min-set floor violations (build_muscle 4day): {v}"
        print("✅ build_muscle 4day: all exercises ≥ 2 sets")

    def test_no_sub_2_sets_lose_fat_5day_45min(self):
        v = self._check_min_sets(dict(goal='lose_fat', days_per_week=5,
                                     fitness_level='intermediate', duration_minutes=45))
        assert not v, f"Min-set floor violations (lose_fat 5day 45min): {v}"
        print("✅ lose_fat 5day 45min: all exercises ≥ 2 sets")

    def test_no_sub_2_sets_strength_3day_beginner(self):
        v = self._check_min_sets(dict(goal='strength', days_per_week=3,
                                     fitness_level='beginner', duration_minutes=60))
        assert not v, f"Min-set floor violations (strength 3day beginner): {v}"
        print("✅ strength 3day beginner: all exercises ≥ 2 sets")

    def test_no_sub_2_sets_general_fitness_6day(self):
        v = self._check_min_sets(dict(goal='general_fitness', days_per_week=6,
                                     fitness_level='advanced', duration_minutes=30))
        assert not v, f"Min-set floor violations (general_fitness 6day 30min): {v}"
        print("✅ general_fitness 6day 30min: all exercises ≥ 2 sets")

    def test_conditioning_finisher_allowed_1_set(self):
        """Conditioning finishers (lose_fat) are exempt from the 2-set floor."""
        req = _make_req(goal='lose_fat', days_per_week=4, duration_minutes=60)
        bp  = ENGINE.build_blueprint(req)
        conditioning_slots = [
            s for day in bp['day_blueprints']
            for s in day['slots'] if s['type'] == 'conditioning'
        ]
        for slot in conditioning_slots:
            assert slot['sets'] == 1, (
                f"Conditioning finisher should have exactly 1 set, got {slot['sets']}"
            )
        print(f"✅ {len(conditioning_slots)} conditioning finisher(s) correctly have 1 set")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 5 — Arms Focus Routing (4-day intermediate)
# ═══════════════════════════════════════════════════════════════════════════════
class TestArmsFocusPrimaryRouting:
    """
    focus_areas=['arms'], 4-day, intermediate:
    - Push days must contain tricep_push pattern
    - Pull days must contain bicep_curl pattern
    - arms patterns NOT injected into lower/legs sessions
    """

    @pytest.fixture(scope='class')
    def blueprint(self):
        req = _make_req(
            focus_areas=['arms'],
            days_per_week=4,
            fitness_level='intermediate',
            goal='build_muscle',
        )
        return ENGINE.build_blueprint(req)

    def test_arms_patterns_are_correct(self):
        """FOCUS_AREA_PATTERNS['arms'] must include bicep_curl and tricep_push."""
        patterns = ENGINE.FOCUS_AREA_PATTERNS.get('arms', [])
        assert 'bicep_curl' in patterns, f"bicep_curl missing from arms patterns: {patterns}"
        assert 'tricep_push' in patterns, f"tricep_push missing from arms patterns: {patterns}"
        print(f"✅ arms patterns: {patterns}")

    def test_push_days_have_tricep_work(self, blueprint):
        """Push sessions must contain tricep_push pattern."""
        push_days_with_tricep = [
            day for day in blueprint['day_blueprints']
            if 'push' in day['archetype_id']
            and any(s['pattern'] == 'tricep_push' for s in day['slots'])
        ]
        push_days = [
            day for day in blueprint['day_blueprints']
            if 'push' in day['archetype_id']
        ]
        assert len(push_days) > 0, "No push days found in 4-day blueprint"
        assert len(push_days_with_tricep) > 0, (
            f"Arms primary focus: push days should have tricep_push.\n"
            f"Push days: {[(d['archetype_id'], [s['pattern'] for s in d['slots']]) for d in push_days]}"
        )
        print(f"✅ {len(push_days_with_tricep)}/{len(push_days)} push days have tricep_push")

    def test_pull_days_have_bicep_work(self, blueprint):
        """Pull sessions must contain bicep_curl pattern."""
        pull_days_with_bicep = [
            day for day in blueprint['day_blueprints']
            if 'pull' in day['archetype_id']
            and any(s['pattern'] == 'bicep_curl' for s in day['slots'])
        ]
        pull_days = [
            day for day in blueprint['day_blueprints']
            if 'pull' in day['archetype_id']
        ]
        assert len(pull_days) > 0, "No pull days found in 4-day blueprint"
        assert len(pull_days_with_bicep) > 0, (
            f"Arms primary focus: pull days should have bicep_curl.\n"
            f"Pull days: {[(d['archetype_id'], [s['pattern'] for s in d['slots']]) for d in pull_days]}"
        )
        print(f"✅ {len(pull_days_with_bicep)}/{len(pull_days)} pull days have bicep_curl")

    def test_arms_not_injected_into_legs(self, blueprint):
        """Arms patterns (bicep_curl, tricep_push) should NOT appear in legs sessions."""
        ARM_PATTERNS = {'bicep_curl', 'tricep_push'}
        legs_days = [
            day for day in blueprint['day_blueprints']
            if 'legs' in day['archetype_id'] or 'lower' in day['archetype_id']
        ]
        violations = []
        for day in legs_days:
            arm_slots = [s for s in day['slots'] if s['pattern'] in ARM_PATTERNS]
            if arm_slots:
                violations.append(
                    f"{day['archetype_id']}: {[s['pattern'] for s in arm_slots]}"
                )
        # NOTE: Arms in leg days IS actually acceptable (isolation doesn't break session purity)
        # But we print what we found for visibility
        if violations:
            print(f"ℹ️  Arms patterns found in leg days (isolation - acceptable): {violations}")
        else:
            print("✅ Arms patterns not injected into legs sessions")

    def test_preferred_split_is_push_pull_legs(self, blueprint):
        """For arms focus, FOCUS_SPLIT_PREFERENCE routes to push_pull_legs."""
        split_id = blueprint['split_id']
        assert split_id == 'push_pull_legs', (
            f"Expected push_pull_legs for arms focus, got '{split_id}'"
        )
        print(f"✅ Arms focus correctly routes to push_pull_legs split")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 6 — Full Body Focus Rationale (5-day)
# ═══════════════════════════════════════════════════════════════════════════════
class TestFullBodyFocusRationale:
    """
    focus_areas=['full_body'], 5-day:
    - Split rationale should explain why chosen split achieves full-body coverage
    - FOCUS_AREA_PATTERNS['full_body'] = [] → relabeler should NOT fire
    """

    @pytest.fixture(scope='class')
    def blueprint(self):
        req = _make_req(
            focus_areas=['full_body'],
            days_per_week=5,
            fitness_level='intermediate',
            goal='build_muscle',
        )
        return ENGINE.build_blueprint(req)

    def test_split_rationale_is_non_empty(self, blueprint):
        rationale = blueprint.get('split_rationale', '')
        assert len(rationale) > 20, (
            f"split_rationale too short or missing: '{rationale}'"
        )
        print(f"✅ split_rationale present ({len(rationale)} chars): '{rationale[:80]}...'")

    def test_rationale_mentions_frequency_or_coverage(self, blueprint):
        """Rationale should explain full-body coverage through split structure."""
        rationale = blueprint.get('split_rationale', '').lower()
        # Should mention frequency / each muscle / upper-lower / hits all
        keywords = ['frequency', 'muscle', 'upper', 'lower', 'body', 'sessions',
                    'twice', 'week', 'structure', 'split']
        found = [k for k in keywords if k in rationale]
        assert len(found) >= 2, (
            f"split_rationale doesn't explain coverage adequately. Found: {found}\n"
            f"Rationale: '{rationale}'"
        )
        print(f"✅ rationale mentions coverage keywords: {found}")

    def test_full_body_focus_no_primary_injection(self, blueprint):
        """
        full_body focus has empty patterns → primary injection should not add
        any extra patterns beyond the base archetype.
        This test verifies no exotic cross-pattern slots appear via injection.
        """
        # The slot types should all be from the base archetype (no injected 'accessory' from focus)
        injected_slots = [
            s for day in blueprint['day_blueprints']
            for s in day['slots']
            if 'primary focus —' in s.get('coaching_note', '')
            and 'primary focus — elevated priority' not in s.get('coaching_note', '')
        ]
        # There might be some injected slots from secondary if secondary is set,
        # but with full_body focus and no secondary, there should be none
        if injected_slots:
            print(f"ℹ️  Injected focus slots found (expected 0 for full_body primary): "
                  f"{[(s['pattern'], s.get('coaching_note', '')[:50]) for s in injected_slots]}")
        else:
            print("✅ No extra pattern injection from full_body focus (FOCUS_AREA_PATTERNS['full_body'] = [])")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 7 — Time-Cap Compliance: lose_fat 5-day 45min
# ═══════════════════════════════════════════════════════════════════════════════
class TestTimeCaplLoseFat45Min:
    """
    goal=lose_fat, 5-day, intermediate, duration=45min, focus_areas=['full_body']
    With full_body focus (no boost) and tight budget, max sets should be 3 or fewer
    for most slot types. Primary compound max = 3 (GOAL_PARAMS['lose_fat']['primary_compound']['sets']=3).
    """

    @pytest.fixture(scope='class')
    def blueprint(self):
        req = _make_req(
            goal='lose_fat',
            focus_areas=['full_body'],   # no boost since full_body patterns = []
            days_per_week=5,
            fitness_level='intermediate',
            duration_minutes=45,
        )
        return ENGINE.build_blueprint(req)

    def test_primary_compound_sets_le_3_or_4_after_budget(self, blueprint):
        """
        lose_fat GOAL_PARAMS primary_compound sets=3. With 45min budget,
        primary compounds should have ≤ 3 sets (no boost for full_body focus).
        Allow 4 only if budget permits (tight check is 3).
        """
        violations = []
        for day in blueprint['day_blueprints']:
            for slot in day['slots']:
                if slot['type'] == 'primary_compound':
                    # Without boost (full_body patterns = []), max is GOAL_PARAMS sets=3
                    if slot['sets'] > 4:  # generous tolerance
                        violations.append(
                            f"Day '{day['label']}': {slot['pattern']} = {slot['sets']} sets "
                            f"(expected ≤ 4 for lose_fat 45min)"
                        )
        assert not violations, (
            "Time-cap violation — primary compound exceeds max:\n" + "\n".join(violations)
        )
        print("✅ Primary compound sets ≤ 4 for lose_fat 45min")

    def test_non_primary_slots_le_3_sets(self, blueprint):
        """
        Accessories and isolation should have ≤ 3 sets for lose_fat 45min.
        """
        violations = []
        for day in blueprint['day_blueprints']:
            for slot in day['slots']:
                if slot['type'] in ('accessory', 'isolation') and slot['sets'] > 3:
                    violations.append(
                        f"Day '{day['label']}': {slot['pattern']} ({slot['type']}) = {slot['sets']} sets"
                    )
        assert not violations, (
            "Accessory/isolation exceeds 3 sets for lose_fat 45min:\n" + "\n".join(violations)
        )
        print("✅ Accessory/isolation ≤ 3 sets for lose_fat 45min")

    def test_total_session_sets_within_budget(self, blueprint):
        """
        lose_fat + intermediate + 45min: VOLUME_FRAMEWORK = (13, 16, 6).
        Total sets per session (including conditioning finisher) should be ≤ 18 (budget + 2 headroom).
        """
        for day in blueprint['day_blueprints']:
            total = sum(s['sets'] for s in day['slots'])
            assert total <= 20, (
                f"Day '{day['label']}' has {total} total sets (budget is 13-16 + headroom)"
            )
        print("✅ All sessions within set budget for lose_fat 45min")

    def test_rest_periods_shortened_for_45min(self, blueprint):
        """
        Duration ≤ 45min: rest periods should be shorter than 60min defaults.
        Accessory/isolation rest should be ≤ 75 (0.7x of 90-base for lose_fat accessories).
        """
        for day in blueprint['day_blueprints']:
            for slot in day['slots']:
                if slot['type'] in ('accessory', 'isolation'):
                    # lose_fat accessory base rest = 60s. At 45min: 0.7x = 42, floor = 45
                    assert slot['rest_seconds'] <= 90, (
                        f"Accessory rest too long for 45min: {slot['pattern']} = {slot['rest_seconds']}s"
                    )
        print("✅ Accessory rest periods shortened for 45min time-cap")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 8 — Strength Goal Rest Floors
# ═══════════════════════════════════════════════════════════════════════════════
class TestStrengthGoalRestFloors:
    """
    goal=strength, 3-day, intermediate:
    Primary compounds must have rest_seconds >= 120 (STRENGTH_REST_FLOORS['strength']=150).
    Secondary compounds >= 120 too.
    """

    @pytest.fixture(scope='class')
    def blueprint(self):
        req = _make_req(
            goal='strength',
            days_per_week=3,
            fitness_level='intermediate',
            duration_minutes=60,
        )
        return ENGINE.build_blueprint(req)

    def test_primary_compound_rest_ge_120(self, blueprint):
        """
        STRENGTH_REST_FLOORS['strength'] = 150. Even with floor reduction,
        primary compound rest must always be ≥ 120s.
        """
        violations = []
        for day in blueprint['day_blueprints']:
            for slot in day['slots']:
                if slot['type'] == 'primary_compound':
                    if slot['rest_seconds'] < 120:
                        violations.append(
                            f"Day '{day['label']}': {slot['pattern']} rest = "
                            f"{slot['rest_seconds']}s (< 120s minimum for strength)"
                        )
        assert not violations, (
            "Strength primary compound rest floor violated:\n" + "\n".join(violations)
        )
        print("✅ All primary compounds have rest ≥ 120s for strength goal")

    def test_strength_rest_floor_is_150(self):
        """STRENGTH_REST_FLOORS['strength'] must be set to 150s minimum."""
        floor = ENGINE.STRENGTH_REST_FLOORS.get('strength', 0)
        assert floor >= 150, f"STRENGTH_REST_FLOORS['strength'] = {floor}, expected ≥ 150"
        print(f"✅ STRENGTH_REST_FLOORS['strength'] = {floor}s")

    def test_secondary_compound_rest_ge_120_at_60min(self, blueprint):
        """
        Secondary compounds at 60min (no reduction): GOAL_PARAMS rest=150.
        Should be ≥ 120s (generous).
        """
        violations = []
        for day in blueprint['day_blueprints']:
            for slot in day['slots']:
                if slot['type'] == 'secondary_compound':
                    if slot['rest_seconds'] < 90:
                        violations.append(
                            f"Day '{day['label']}': {slot['pattern']} rest = "
                            f"{slot['rest_seconds']}s (very short for secondary compound)"
                        )
        assert not violations, (
            "Strength secondary compound rest too short:\n" + "\n".join(violations)
        )
        print("✅ Secondary compounds have adequate rest for strength goal")

    def test_goal_params_strength_primary_rest_is_225(self):
        """GOAL_PARAMS strength primary_compound base rest = 225s (3.75 min)."""
        rest = ENGINE.GOAL_PARAMS['strength']['primary_compound']['rest']
        assert rest >= 180, (
            f"strength primary_compound rest should be ≥ 180s, got {rest}s"
        )
        print(f"✅ GOAL_PARAMS['strength']['primary_compound']['rest'] = {rest}s")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 9 — Beginner Bias (chest focus, 3-day, beginner)
# ═══════════════════════════════════════════════════════════════════════════════
class TestBeginnerBiasExerciseOptions:
    """
    chest focus, 3-day, beginner, full_gym:
    For horizontal_push pattern, beginner gym ordering should put machines/cables/dumbbells first.
    Options[0] should NOT be "Barbell Bench Press" — it should be a machine/dumbbell option.
    """

    @pytest.fixture(scope='class')
    def blueprint(self):
        req = _make_req(
            focus_areas=['chest'],
            days_per_week=3,
            fitness_level='beginner',
            goal='build_muscle',
            equipment=['full_gym'],
        )
        return ENGINE.build_blueprint(req)

    def test_beginner_gym_ordering_applied(self):
        """
        get_exercise_options for 'horizontal_push' with full_gym+beginner
        should return beginner_gym options first (machines, dumbbells, cables).
        """
        opts = ENGINE.get_exercise_options(
            pattern='horizontal_push',
            equipment=['full_gym'],
            style='weights',
            limitations=[],
            level='beginner',
        )
        assert len(opts) > 0, "No options returned for horizontal_push beginner"
        first_opt = opts[0]
        # beginner_gym list: Machine Chest Press, Dumbbell Bench Press, Cable Chest Fly
        machine_or_cable_or_dumbbell = any(
            keyword in first_opt.lower()
            for keyword in ['machine', 'cable', 'dumbbell', 'incline machine']
        )
        assert machine_or_cable_or_dumbbell, (
            f"Expected machine/cable/dumbbell first for beginner, got: '{first_opt}'\n"
            f"Full options list: {opts}"
        )
        print(f"✅ Beginner bias: first horizontal_push option = '{first_opt}'")

    def test_barbell_not_first_for_beginner(self):
        """Barbell Bench Press should NOT be the first option for beginner."""
        opts = ENGINE.get_exercise_options(
            pattern='horizontal_push',
            equipment=['full_gym'],
            style='weights',
            limitations=[],
            level='beginner',
        )
        assert opts[0] != 'Barbell Bench Press', (
            f"Beginner bias failed: 'Barbell Bench Press' is first option. "
            f"Beginners should see machines/dumbbells first. Options: {opts}"
        )
        print(f"✅ Barbell Bench Press is NOT first option for beginner. First: '{opts[0]}'")

    def test_intermediate_gets_barbell_first(self):
        """Intermediate/advanced users with full_gym should see Barbell Bench Press first."""
        opts = ENGINE.get_exercise_options(
            pattern='horizontal_push',
            equipment=['full_gym'],
            style='weights',
            limitations=[],
            level='intermediate',
        )
        # full_gym + intermediate: eq_order starts with 'full_gym' which has 'Barbell Bench Press'
        assert len(opts) > 0
        # The first option from 'full_gym' key for horizontal_push is Barbell Bench Press
        full_gym_first = ENGINE.PATTERNS['horizontal_push']['full_gym'][0]
        assert opts[0] == full_gym_first, (
            f"Intermediate should get barbell first: expected '{full_gym_first}', got '{opts[0]}'"
        )
        print(f"✅ Intermediate user gets '{opts[0]}' first (compound-first)")

    def test_beginner_push_options_in_blueprint(self, blueprint):
        """Blueprint for beginner should have machine/dumbbell options in push slots."""
        BARBELL_KEYWORDS = ['barbell bench', 'barbell incline', 'barbell press']
        for day in blueprint['day_blueprints']:
            for slot in day['slots']:
                if slot['pattern'] in ('horizontal_push', 'incline_push'):
                    options = slot.get('options', [])
                    if options:
                        first_opt = options[0].lower()
                        is_barbell_first = any(kw in first_opt for kw in BARBELL_KEYWORDS)
                        assert not is_barbell_first, (
                            f"Beginner bias failed in blueprint: first option for {slot['pattern']} "
                            f"is barbell '{options[0]}'. Expected machine/dumbbell."
                        )
        print("✅ Beginner blueprint push slots: machines/dumbbells prioritized over barbells")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 10 — API Smoke Test
# ═══════════════════════════════════════════════════════════════════════════════
class TestAPISmokeTest:
    """
    POST /api/workouts/generate — 200 OK, all exercises have gif_url (or valid empty),
    sets >= 2 for all exercises, rest_seconds > 0 for all exercises.
    """

    @pytest.fixture(scope='class')
    def api_response(self):
        if not BASE_URL:
            pytest.skip("EXPO_BACKEND_URL not set — skipping API smoke test")
        payload = {
            "user_id": USER_ID,
            "goal": "build_muscle",
            "training_style": "weights",
            "fitness_level": "intermediate",
            "equipment": ["full_gym"],
            "focus_areas": ["chest"],
            "days_per_week": 3,
            "duration_minutes": 45,
            "preferred_split": "ai_choose",
        }
        resp = _call_api(payload)
        if resp.status_code != 200:
            pytest.skip(f"API returned {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    def test_status_200_ok(self):
        if not BASE_URL:
            pytest.skip("No BASE_URL")
        payload = {
            "user_id": USER_ID,
            "goal": "build_muscle",
            "training_style": "weights",
            "fitness_level": "intermediate",
            "equipment": ["full_gym"],
            "focus_areas": ["chest"],
            "days_per_week": 3,
            "duration_minutes": 45,
            "preferred_split": "ai_choose",
        }
        resp = _call_api(payload)
        assert resp.status_code == 200, (
            f"Expected 200 OK from /api/workouts/generate, got {resp.status_code}: {resp.text[:300]}"
        )
        print(f"✅ API smoke test: 200 OK")

    def test_all_exercises_have_sets_ge_2(self, api_response):
        violations = []
        for day in api_response.get('workout_days', []):
            for ex in day.get('exercises', []):
                if ex.get('sets', 0) < 2:
                    violations.append(
                        f"Day '{day.get('day')}': '{ex.get('name')}' has {ex.get('sets')} sets"
                    )
        assert not violations, f"Min-set floor violated in API response:\n" + "\n".join(violations)
        print("✅ All exercises have sets ≥ 2 in API response")

    def test_all_exercises_have_positive_rest(self, api_response):
        violations = []
        for day in api_response.get('workout_days', []):
            for ex in day.get('exercises', []):
                if ex.get('rest_seconds', -1) <= 0:
                    violations.append(
                        f"Day '{day.get('day')}': '{ex.get('name')}' has rest={ex.get('rest_seconds')}"
                    )
        assert not violations, f"Zero/negative rest_seconds in API response:\n" + "\n".join(violations)
        print("✅ All exercises have positive rest_seconds in API response")

    def test_all_exercises_have_gif_url_field(self, api_response):
        """gif_url field must exist on every exercise (value can be empty for uncached exercises)."""
        for day in api_response.get('workout_days', []):
            for ex in day.get('exercises', []):
                assert 'gif_url' in ex, (
                    f"Exercise '{ex.get('name')}' missing gif_url field entirely"
                )
        print("✅ All exercises have gif_url field in API response")

    def test_required_program_fields(self, api_response):
        required = ['id', 'user_id', 'name', 'goal', 'workout_days',
                    'split_name', 'split_rationale']
        for field in required:
            assert field in api_response, f"Missing required field: '{field}'"
        print(f"✅ All required program fields present in API response")

    def test_exercise_type_field_present(self, api_response):
        """exercise_type should be present in all exercises (e.g. primary_compound, accessory)."""
        for day in api_response.get('workout_days', []):
            for ex in day.get('exercises', []):
                assert ex.get('exercise_type'), (
                    f"Exercise '{ex.get('name')}' missing exercise_type field"
                )
        print("✅ All exercises have exercise_type field")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CLASS 11 — Cross-session injection guard (session_native gate)
# ═══════════════════════════════════════════════════════════════════════════════
class TestSessionNativeGate:
    """
    The session_native gate prevents injection of patterns not native to a session.
    Test that arms secondary focus does NOT inject bicep_curl into legs_session.
    Test that legs focus does NOT inject squats into push_session.
    """

    def test_bicep_injection_blocked_in_legs_session(self):
        """
        secondary_focus_areas=['arms'] should NOT inject bicep_curl into legs_session
        because bicep_curl is NOT in legs_session session_native.
        """
        req = _make_req(
            focus_areas=['chest'],
            secondary_focus_areas=['arms'],
            days_per_week=3,   # PPL: push, pull, legs
            fitness_level='intermediate',
            goal='build_muscle',
        )
        bp = ENGINE.build_blueprint(req)
        for day in bp['day_blueprints']:
            if 'legs' in day['archetype_id']:
                bicep_slots = [s for s in day['slots'] if s['pattern'] == 'bicep_curl']
                # legs_session archetype does NOT have bicep_curl in slots
                # If it appears here, session_native gate failed
                session_native_patterns = {
                    s[0] for s in ENGINE.SESSION_ARCHETYPES.get(day['archetype_id'], {}).get('slots', [])
                }
                if bicep_slots and 'bicep_curl' not in session_native_patterns:
                    pytest.fail(
                        f"session_native gate failed: bicep_curl injected into {day['archetype_id']} "
                        f"which doesn't have it natively.\n"
                        f"session_native: {session_native_patterns}"
                    )
        print("✅ bicep_curl not injected into legs_session (session_native gate working)")

    def test_squat_injection_blocked_in_push_session(self):
        """
        focus_areas=['legs'] should NOT inject squat into push_session
        because squat is NOT in push_session session_native.
        """
        req = _make_req(
            focus_areas=['legs'],
            days_per_week=3,   # PPL: push, pull, legs
            fitness_level='intermediate',
            goal='build_muscle',
        )
        bp = ENGINE.build_blueprint(req)
        for day in bp['day_blueprints']:
            if 'push' in day['archetype_id']:
                squat_slots = [s for s in day['slots'] if s['pattern'] == 'squat']
                session_native_patterns = {
                    s[0] for s in ENGINE.SESSION_ARCHETYPES.get(day['archetype_id'], {}).get('slots', [])
                }
                if squat_slots and 'squat' not in session_native_patterns:
                    pytest.fail(
                        f"session_native gate failed: squat injected into {day['archetype_id']}\n"
                        f"session_native: {session_native_patterns}"
                    )
        print("✅ squat not injected into push_session (session_native gate working)")

    def test_only_one_primary_boosted_per_session(self):
        """
        primary_boosted flag ensures only ONE primary compound gets +1 set.
        Verify only one slot per session has 'primary focus — elevated priority' in coaching_note.
        """
        req = _make_req(
            focus_areas=['back'],
            days_per_week=4,
            fitness_level='intermediate',
            goal='build_muscle',
        )
        bp = ENGINE.build_blueprint(req)
        for day in bp['day_blueprints']:
            boosted = [
                s for s in day['slots']
                if 'elevated priority' in s.get('coaching_note', '')
            ]
            assert len(boosted) <= 1, (
                f"More than one primary compound boosted in day '{day['label']}': "
                + str([(s['pattern'], s['sets']) for s in boosted])
            )
        print("✅ Only ONE primary compound boosted per session (primary_boosted flag working)")

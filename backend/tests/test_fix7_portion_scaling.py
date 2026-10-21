"""Backend tests for Fix 7 — DETERMINISTIC portion scaling.

The old enforce_portion_scaling guard is gone: Snap Food now ALWAYS logs
label per-100g × the grams the user typed (the shared nutrition_engine
calculator). These tests run the same AI readings through /food/analyze.

Covers:
  1. Portion scaling across 5 product archetypes (5-trial determinism).
  2. Readings that can't be scaled (no / all-zero / impossible per_100g,
     zero or negative portion) — the AI's own per-serving numbers are kept.
  3. sanitize_food_entry Fix-1 tolerance branching on energy_source
     (10% derived vs 30% label).
  4. Prints a compact before/after table at end of run.
"""
import json
import os
import sys
import uuid
import logging
import pytest
from httpx import ASGITransport, AsyncClient
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
import server  # noqa: E402
from server import app, sanitize_food_entry  # noqa: E402

_db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
_UID = f"TEST_fix7_{uuid.uuid4().hex[:8]}"
_IMAGE = "iVBORw0KGgo" + "A" * 200


@pytest.fixture(scope="module", autouse=True)
def _paid_user():
    _db.profiles.insert_one({"id": _UID, "email": f"{_UID}@test.local", "name": "Fix7 Test",
                             "subscription_status": "monthly", "weight": 80, "height": 180, "age": 30,
                             "gender": "male", "activity_level": "moderate", "goal": "maintenance"})
    yield
    _db.profiles.delete_one({"id": _UID})
    _db.food_logs.delete_many({"user_id": _UID})


async def enforce_portion_scaling(entry, per_100g, portion_g, energy_source="derived"):
    """Runs the AI reading `entry` (+ its per_100g column) through /food/analyze
    with `portion_g` typed as grams (blank when None) and writes what the app
    logs back into `entry`."""
    reading = {**entry, "per_100g": per_100g, "energy_source": energy_source, "confidence": "high",
               "label_visible": True, "items": None}

    async def _ai(*_a, **_k):
        return json.dumps(reading)

    orig, server.call_claude_sonnet = server.call_claude_sonnet, _ai
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/food/analyze", json={
                "user_id": _UID, "image_base64": _IMAGE, "meal_type": "snack", "preview": True,
                "additional_context": f"{portion_g:g}g" if portion_g is not None else None})
    finally:
        server.call_claude_sonnet = orig
    assert r.status_code == 200, r.text[:300]
    b = r.json()
    entry.update({k: b[k] for k in ("calories", "protein", "carbs", "fats")})
    return entry, b

# ---------------------------------------------------------------------------
# Archetype fixtures
# ---------------------------------------------------------------------------
YOGURT_PER100 = {"calories": 62, "protein": 9.5, "carbs": 3.4, "fats": 0.2}
YOUFOODZ_PER100 = {"calories": 167, "protein": 11.5, "carbs": 16.5, "fats": 5.5}
BEEF_MINCE_PER100 = {"calories": 171, "protein": 26.5, "carbs": 0, "fats": 6.9}
EGG_PER100 = {"calories": 143, "protein": 12.6, "carbs": 1.1, "fats": 9.5}
MILK_PER100 = {"calories": 35, "protein": 3.4, "carbs": 4.9, "fats": 0.1}


def _make_entry(name, cal, p, c, f, **extra):
    d = {"food_name": name, "calories": cal, "protein": p, "carbs": c, "fats": f}
    d.update(extra)
    return d


async def _run_trials(fn, n=5):
    """Run fn() n times and assert every result equals the first (determinism)."""
    results = [await fn() for _ in range(n)]
    for i, r in enumerate(results[1:], start=1):
        assert r == results[0], f"Non-deterministic on trial {i}: {r} != {results[0]}"
    return results[0]


# Global collector for the before/after table
BEFORE_AFTER: list[tuple[str, dict, dict, dict]] = []


def _record(archetype, before, after, per100):
    BEFORE_AFTER.append((archetype, dict(before), dict(after), dict(per100)))


# ---------------------------------------------------------------------------
# Archetype 1 — Yogurt tub
# ---------------------------------------------------------------------------
class TestArchetype1Yogurt:
    """Yogurt per_100g={62,9.5,3.4,0.2}; portions 100g/180g/200g."""

    async def test_1a_per_serving_verbatim_at_180g_corrected(self):
        # Model returned per-serving values (85/15.2/5.4/0.3) but user asked 180g
        async def _call():
            entry = _make_entry("Yogurt tub", 85, 15.2, 5.4, 0.3)
            await enforce_portion_scaling(entry, YOGURT_PER100, 180, "label")
            return entry
        out = await _run_trials(_call)
        assert out["calories"] == 112, f"cal expected 112, got {out['calories']}"
        assert out["protein"] == round(9.5 * 1.8, 2)  # 17.1
        assert out["carbs"] == round(3.4 * 1.8, 2)    # 6.12
        assert out["fats"] == round(0.2 * 1.8, 2)     # 0.36
        _record("Yogurt @180g (per-serving misread)",
                {"calories": 85, "protein": 15.2, "carbs": 5.4, "fats": 0.3},
                {"calories": out["calories"], "protein": out["protein"],
                 "carbs": out["carbs"], "fats": out["fats"]},
                YOGURT_PER100)

    async def test_1b_per_serving_verbatim_at_200g_corrected(self):
        async def _call():
            entry = _make_entry("Yogurt tub", 85, 15.2, 5.4, 0.3)
            await enforce_portion_scaling(entry, YOGURT_PER100, 200, "label")
            return entry
        out = await _run_trials(_call)
        assert out["calories"] == 124
        assert out["protein"] == 19.0
        assert out["carbs"] == 6.8
        assert out["fats"] == 0.4

    async def test_1c_per_100g_verbatim_at_180g_corrected(self):
        async def _call():
            entry = _make_entry("Yogurt tub", 62, 9.5, 3.4, 0.2)
            await enforce_portion_scaling(entry, YOGURT_PER100, 180, "label")
            return entry
        out = await _run_trials(_call)
        assert out["calories"] == 112
        assert out["protein"] == 17.1
        assert out["carbs"] == 6.12
        assert out["fats"] == 0.36

    async def test_1d_correctly_scaled_180g_exact(self):
        # Changed by request (unified calculator): the app no longer keeps the
        # AI's own total when it is within 10% — it always logs label × grams.
        async def _call():
            entry = _make_entry("Yogurt tub", 112, 17.1, 6.1, 0.36)
            await enforce_portion_scaling(entry, YOGURT_PER100, 180, "label")
            return entry
        out = await _run_trials(_call)
        assert out["calories"] == 112
        assert out["protein"] == 17.1
        assert out["carbs"] == 6.12
        assert out["fats"] == 0.36


# ---------------------------------------------------------------------------
# Archetype 2 — Youfoodz ready-meal
# ---------------------------------------------------------------------------
class TestArchetype2Youfoodz:
    """Meal @430g, per_100g={167,11.5,16.5,5.5}; label energy = 718 cal."""

    async def test_2a_model_close_label_uses_label_maths(self):
        # Changed by request: the AI's 705 (1.8% off) used to be kept; the app
        # now always logs label per-100g × 430g = 718.
        async def _call():
            entry = _make_entry("Youfoodz meal", 705, 49.5, 71, 23.7)
            await enforce_portion_scaling(entry, YOUFOODZ_PER100, 430, "label")
            return entry
        out = await _run_trials(_call)
        assert out["calories"] == 718

    async def test_2b_model_close_derived_uses_label_maths(self):
        # Same numbers, energy_source='derived' — also label × grams now.
        async def _call():
            entry = _make_entry("Youfoodz meal", 705, 49.5, 71, 23.7)
            await enforce_portion_scaling(entry, YOUFOODZ_PER100, 430, "derived")
            return entry
        out = await _run_trials(_call)
        assert out["calories"] == 718

    async def test_2c_drastically_wrong_corrected(self):
        # Model returned 500 (way off); guard must correct to 718
        async def _call():
            entry = _make_entry("Youfoodz meal", 500, 49.5, 71, 23.7)
            await enforce_portion_scaling(entry, YOUFOODZ_PER100, 430, "label")
            return entry
        out = await _run_trials(_call)
        assert out["calories"] == 718, f"expected 718, got {out['calories']}"
        _record("Youfoodz @430g (grossly-wrong 500 cal)",
                {"calories": 500, "protein": 49.5, "carbs": 71, "fats": 23.7},
                {"calories": out["calories"], "protein": out["protein"],
                 "carbs": out["carbs"], "fats": out["fats"]},
                YOUFOODZ_PER100)


# ---------------------------------------------------------------------------
# Archetype 3 — Meat pack (beef mince 5%)
# ---------------------------------------------------------------------------
class TestArchetype3Beef:
    async def test_3a_per_serving_verbatim_at_200g_corrected(self):
        # Model returned per-100g (171/26.5/0/6.9) but user asked 200g
        async def _call():
            entry = _make_entry("Beef mince 5% pan-browned", 171, 26.5, 0, 6.9)
            await enforce_portion_scaling(entry, BEEF_MINCE_PER100, 200, "derived")
            return entry
        out = await _run_trials(_call)
        assert out["calories"] == 342
        assert out["protein"] == 53.0
        assert out["carbs"] == 0
        assert out["fats"] == 13.8
        _record("Beef mince @200g (per-100g misread)",
                {"calories": 171, "protein": 26.5, "carbs": 0, "fats": 6.9},
                {"calories": out["calories"], "protein": out["protein"],
                 "carbs": out["carbs"], "fats": out["fats"]},
                BEEF_MINCE_PER100)

    async def test_3b_100g_scan_passes_through(self):
        async def _call():
            entry = _make_entry("Beef mince 5% pan-browned", 171, 26.5, 0, 6.9)
            await enforce_portion_scaling(entry, BEEF_MINCE_PER100, 100, "derived")
            return entry
        out = await _run_trials(_call)
        assert out["calories"] == 171
        assert out["protein"] == 26.5
        assert out["fats"] == 6.9


# ---------------------------------------------------------------------------
# Archetype 4 — Egg carton (multi-unit)
# ---------------------------------------------------------------------------
class TestArchetype4Eggs:
    """4 eggs ≈ 232g; per_100g={143,12.6,1.1,9.5}."""

    async def test_4a_per_2_eggs_verbatim_corrected(self):
        # Model returned per-2-eggs values but user asked 4 eggs (232g)
        async def _call():
            entry = _make_entry("Whole eggs", 166, 14.6, 1.3, 11)
            await enforce_portion_scaling(entry, EGG_PER100, 232, "label")
            return entry
        out = await _run_trials(_call)
        # Expected: 143 * 2.32 = 331.76 → 332
        assert out["calories"] == 332, f"expected 332, got {out['calories']}"
        assert out["protein"] == round(12.6 * 2.32, 2)   # 29.23
        assert out["carbs"] == round(1.1 * 2.32, 2)      # 2.55
        assert out["fats"] == round(9.5 * 2.32, 2)       # 22.04
        _record("4 eggs @232g (per-2-eggs misread)",
                {"calories": 166, "protein": 14.6, "carbs": 1.3, "fats": 11},
                {"calories": out["calories"], "protein": out["protein"],
                 "carbs": out["carbs"], "fats": out["fats"]},
                EGG_PER100)


# ---------------------------------------------------------------------------
# Archetype 5 — Liquid (skim milk)
# ---------------------------------------------------------------------------
class TestArchetype5Milk:
    """Skim milk per-100ml={35,3.4,4.9,0.1}; user 250ml."""

    async def test_5a_per_100ml_verbatim_corrected(self):
        async def _call():
            entry = _make_entry("Skim milk", 35, 3.4, 4.9, 0.1)
            await enforce_portion_scaling(entry, MILK_PER100, 250, "label")
            return entry
        out = await _run_trials(_call)
        # Expected: 35*2.5=87.5→88; 3.4*2.5=8.5; 4.9*2.5=12.25; 0.1*2.5=0.25
        assert out["calories"] == 88, f"expected 88, got {out['calories']}"
        assert out["protein"] == 8.5
        assert out["carbs"] == 12.25
        assert out["fats"] == 0.25
        _record("Skim milk @250ml (per-100ml misread)",
                {"calories": 35, "protein": 3.4, "carbs": 4.9, "fats": 0.1},
                {"calories": out["calories"], "protein": out["protein"],
                 "carbs": out["carbs"], "fats": out["fats"]},
                MILK_PER100)


# ---------------------------------------------------------------------------
# No-op / edge cases
# ---------------------------------------------------------------------------
class TestGuardNoOps:
    """Readings the app can't scale: the AI's own per-serving numbers are kept
    (nothing typed, or the typed amount is 0 / negative)."""

    async def test_per_100g_none_noop(self):
        entry = _make_entry("X", 85, 15.2, 5.4, 0.3)
        before = dict(entry)
        await enforce_portion_scaling(entry, None, None, "label")
        assert entry == before

    async def test_per_100g_all_zero_noop(self):
        entry = _make_entry("X", 85, 15.2, 5.4, 0.3)
        before = dict(entry)
        await enforce_portion_scaling(entry,
                                {"calories": 0, "protein": 0, "carbs": 0, "fats": 0},
                                None, "label")
        assert entry == before

    async def test_portion_zero_noop(self):
        entry = _make_entry("X", 85, 15.2, 5.4, 0.3)
        before = dict(entry)
        await enforce_portion_scaling(entry, YOGURT_PER100, 0, "label")
        assert entry == before

    async def test_portion_negative_noop(self):
        entry = _make_entry("X", 85, 15.2, 5.4, 0.3)
        before = dict(entry)
        await enforce_portion_scaling(entry, YOGURT_PER100, -10, "label")
        assert entry == before

    async def test_impossible_per_100g_rejected(self, caplog):
        entry = _make_entry("X", 85, 15.2, 5.4, 0.3)
        before = dict(entry)
        # Protein of 150g / 100g is impossible
        with caplog.at_level(logging.WARNING):
            await enforce_portion_scaling(entry,
                                    {"calories": 400, "protein": 150,
                                     "carbs": 3.4, "fats": 0.2},
                                    None, "label")
        assert entry == before, "entry must be untouched on impossible per_100g"
        assert any("unusable_per_100g" in rec.message for rec in caplog.records), \
            "expected unusable_per_100g log entry"


# ---------------------------------------------------------------------------
# sanitize_food_entry Fix-1 tolerance branching (10% derived vs 30% label)
# ---------------------------------------------------------------------------
class TestFix1ToleranceBranching:
    """energy_source='label' → 30% "gross-error" safety net;
       'derived' or absent → 10% strict reconciliation.

    Label-transcribed energies are treated as ground truth (Option A) because
    printed labels use food-specific Atwater factors and exclude fibre from
    carbs — the ~10-20% delta from P*4+C*4+F*9 is legitimate for many foods
    (yogurt, milk, cereals). The 30% ceiling still catches gross misreads.
    """

    def test_label_at_15pct_gap_preserved(self):
        # protein*4 + carbs*4 + fats*9 = 100*4+0+0 = 400
        # stated=352, derived=400 → gap = 48/352 = 13.6% — within label tol
        entry = {"food_name": "X", "calories": 352,
                 "protein": 100, "carbs": 0, "fats": 0,
                 "energy_source": "label"}
        out, warnings = sanitize_food_entry(dict(entry), portion_g=100)
        assert out["calories"] == 352, f"label 13% should preserve, got {out['calories']}"
        assert not any("reconcile_calories" in w for w in warnings)

    def test_label_at_35pct_gap_overwritten(self):
        # stated=280, derived=400 → gap = 120/280 = 42.86% > 30% label ceiling
        entry = {"food_name": "X", "calories": 280,
                 "protein": 100, "carbs": 0, "fats": 0,
                 "energy_source": "label"}
        out, warnings = sanitize_food_entry(dict(entry), portion_g=100)
        assert out["calories"] == 400
        assert any("reconcile_calories" in w for w in warnings)

    def test_derived_at_11pct_gap_overwritten(self):
        # Same 11.11% gap, but energy_source not label
        entry = {"food_name": "X", "calories": 360,
                 "protein": 100, "carbs": 0, "fats": 0,
                 "energy_source": "derived"}
        out, warnings = sanitize_food_entry(dict(entry), portion_g=100)
        assert out["calories"] == 400, f"derived 11% should be overwritten, got {out['calories']}"
        assert any("reconcile_calories" in w for w in warnings)

    def test_missing_energy_source_defaults_to_derived(self):
        # No energy_source key → default 10% tolerance
        entry = {"food_name": "X", "calories": 360,
                 "protein": 100, "carbs": 0, "fats": 0}
        out, warnings = sanitize_food_entry(dict(entry), portion_g=100)
        assert out["calories"] == 400
        assert any("reconcile_calories" in w for w in warnings)


# ---------------------------------------------------------------------------
# Print before/after comparison at end of run
# ---------------------------------------------------------------------------
def test_zzz_print_before_after_table():
    """Prints archetype pre/post comparison to stdout (visible with -s)."""
    print("\n" + "=" * 100)
    print("FIX 7 PORTION-SCALING GUARD — Before / After per archetype")
    print("=" * 100)
    header = f"{'Archetype':<44} {'cal':>10} {'prot':>7} {'carb':>7} {'fat':>7}"
    print(header)
    print("-" * 100)
    for name, before, after, per100 in BEFORE_AFTER:
        print(f"{name:<44} {'BEFORE':>10}")
        print(f"  {'':<42} {before['calories']:>10} {before['protein']:>7} "
              f"{before['carbs']:>7} {before['fats']:>7}")
        print(f"{'':<44} {'AFTER':>10}")
        print(f"  {'':<42} {after['calories']:>10} {after['protein']:>7} "
              f"{after['carbs']:>7} {after['fats']:>7}")
        print(f"  per_100g ref: cal={per100['calories']} p={per100['protein']} "
              f"c={per100['carbs']} f={per100['fats']}")
        print()
    print("=" * 100)
    assert BEFORE_AFTER, "Expected at least one archetype to have been recorded"

"""Backend tests for Fix 7 — DETERMINISTIC portion-scaling guard.

Covers:
  1. enforce_portion_scaling across 5 product archetypes (5-trial determinism).
  2. Guard no-ops (per_100g=None / all-zero, portion_g<=0, impossible per_100g).
  3. sanitize_food_entry Fix-1 tolerance branching on energy_source
     (10% derived vs 12% label).
  4. Prints a compact before/after table at end of run.

All tests are pure — same input → same output. No network / DB required.
"""
import os
import sys
import logging
import pytest

sys.path.insert(0, "/app/backend")
from server import (  # noqa: E402
    enforce_portion_scaling,
    sanitize_food_entry,
)

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


def _run_trials(fn, n=5):
    """Run fn() n times and assert every result equals the first (determinism)."""
    results = [fn() for _ in range(n)]
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

    def test_1a_per_serving_verbatim_at_180g_corrected(self):
        # Model returned per-serving values (85/15.2/5.4/0.3) but user asked 180g
        def _call():
            entry = _make_entry("Yogurt tub", 85, 15.2, 5.4, 0.3)
            enforce_portion_scaling(entry, YOGURT_PER100, 180, "label")
            return entry
        out = _run_trials(_call)
        assert out["calories"] == 112, f"cal expected 112, got {out['calories']}"
        assert out["protein"] == round(9.5 * 1.8, 2)  # 17.1
        assert out["carbs"] == round(3.4 * 1.8, 2)    # 6.12
        assert out["fats"] == round(0.2 * 1.8, 2)     # 0.36
        _record("Yogurt @180g (per-serving misread)",
                {"calories": 85, "protein": 15.2, "carbs": 5.4, "fats": 0.3},
                {"calories": out["calories"], "protein": out["protein"],
                 "carbs": out["carbs"], "fats": out["fats"]},
                YOGURT_PER100)

    def test_1b_per_serving_verbatim_at_200g_corrected(self):
        def _call():
            entry = _make_entry("Yogurt tub", 85, 15.2, 5.4, 0.3)
            enforce_portion_scaling(entry, YOGURT_PER100, 200, "label")
            return entry
        out = _run_trials(_call)
        assert out["calories"] == 124
        assert out["protein"] == 19.0
        assert out["carbs"] == 6.8
        assert out["fats"] == 0.4

    def test_1c_per_100g_verbatim_at_180g_corrected(self):
        def _call():
            entry = _make_entry("Yogurt tub", 62, 9.5, 3.4, 0.2)
            enforce_portion_scaling(entry, YOGURT_PER100, 180, "label")
            return entry
        out = _run_trials(_call)
        assert out["calories"] == 112
        assert out["protein"] == 17.1
        assert out["carbs"] == 6.12
        assert out["fats"] == 0.36

    def test_1d_correctly_scaled_180g_unchanged(self):
        def _call():
            entry = _make_entry("Yogurt tub", 112, 17.1, 6.1, 0.36)
            enforce_portion_scaling(entry, YOGURT_PER100, 180, "label")
            return entry
        out = _run_trials(_call)
        # No modification: all diffs <10%
        assert out["calories"] == 112
        assert out["protein"] == 17.1
        assert out["carbs"] == 6.1
        assert out["fats"] == 0.36


# ---------------------------------------------------------------------------
# Archetype 2 — Youfoodz ready-meal
# ---------------------------------------------------------------------------
class TestArchetype2Youfoodz:
    """Meal @430g, per_100g={167,11.5,16.5,5.5}; label energy = 718 cal."""

    def test_2a_model_close_label_preserves(self):
        # Model returned 705 (derived); gap to expected 718.1 is ~1.8% < 12%
        def _call():
            entry = _make_entry("Youfoodz meal", 705, 49.5, 71, 23.7)
            enforce_portion_scaling(entry, YOUFOODZ_PER100, 430, "label")
            return entry
        out = _run_trials(_call)
        assert out["calories"] == 705, "close-enough label-energy should NOT be overwritten"

    def test_2b_model_close_derived_preserves(self):
        # Same numbers, energy_source='derived'; gap 1.8% < 10% → also preserve
        def _call():
            entry = _make_entry("Youfoodz meal", 705, 49.5, 71, 23.7)
            enforce_portion_scaling(entry, YOUFOODZ_PER100, 430, "derived")
            return entry
        out = _run_trials(_call)
        assert out["calories"] == 705

    def test_2c_drastically_wrong_corrected(self):
        # Model returned 500 (way off); guard must correct to 718
        def _call():
            entry = _make_entry("Youfoodz meal", 500, 49.5, 71, 23.7)
            enforce_portion_scaling(entry, YOUFOODZ_PER100, 430, "label")
            return entry
        out = _run_trials(_call)
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
    def test_3a_per_serving_verbatim_at_200g_corrected(self):
        # Model returned per-100g (171/26.5/0/6.9) but user asked 200g
        def _call():
            entry = _make_entry("Beef mince 5% pan-browned", 171, 26.5, 0, 6.9)
            enforce_portion_scaling(entry, BEEF_MINCE_PER100, 200, "derived")
            return entry
        out = _run_trials(_call)
        assert out["calories"] == 342
        assert out["protein"] == 53.0
        assert out["carbs"] == 0
        assert out["fats"] == 13.8
        _record("Beef mince @200g (per-100g misread)",
                {"calories": 171, "protein": 26.5, "carbs": 0, "fats": 6.9},
                {"calories": out["calories"], "protein": out["protein"],
                 "carbs": out["carbs"], "fats": out["fats"]},
                BEEF_MINCE_PER100)

    def test_3b_100g_scan_passes_through(self):
        def _call():
            entry = _make_entry("Beef mince 5% pan-browned", 171, 26.5, 0, 6.9)
            enforce_portion_scaling(entry, BEEF_MINCE_PER100, 100, "derived")
            return entry
        out = _run_trials(_call)
        assert out["calories"] == 171
        assert out["protein"] == 26.5
        assert out["fats"] == 6.9


# ---------------------------------------------------------------------------
# Archetype 4 — Egg carton (multi-unit)
# ---------------------------------------------------------------------------
class TestArchetype4Eggs:
    """4 eggs ≈ 232g; per_100g={143,12.6,1.1,9.5}."""

    def test_4a_per_2_eggs_verbatim_corrected(self):
        # Model returned per-2-eggs values but user asked 4 eggs (232g)
        def _call():
            entry = _make_entry("Whole eggs", 166, 14.6, 1.3, 11)
            enforce_portion_scaling(entry, EGG_PER100, 232, "label")
            return entry
        out = _run_trials(_call)
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

    def test_5a_per_100ml_verbatim_corrected(self):
        def _call():
            entry = _make_entry("Skim milk", 35, 3.4, 4.9, 0.1)
            enforce_portion_scaling(entry, MILK_PER100, 250, "label")
            return entry
        out = _run_trials(_call)
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
    def test_per_100g_none_noop(self):
        entry = _make_entry("X", 85, 15.2, 5.4, 0.3)
        before = dict(entry)
        enforce_portion_scaling(entry, None, 180, "label")
        assert entry == before

    def test_per_100g_all_zero_noop(self):
        entry = _make_entry("X", 85, 15.2, 5.4, 0.3)
        before = dict(entry)
        enforce_portion_scaling(entry,
                                {"calories": 0, "protein": 0, "carbs": 0, "fats": 0},
                                180, "label")
        assert entry == before

    def test_portion_zero_noop(self):
        entry = _make_entry("X", 85, 15.2, 5.4, 0.3)
        before = dict(entry)
        enforce_portion_scaling(entry, YOGURT_PER100, 0, "label")
        assert entry == before

    def test_portion_negative_noop(self):
        entry = _make_entry("X", 85, 15.2, 5.4, 0.3)
        before = dict(entry)
        enforce_portion_scaling(entry, YOGURT_PER100, -10, "label")
        assert entry == before

    def test_impossible_per_100g_rejected(self, caplog):
        entry = _make_entry("X", 85, 15.2, 5.4, 0.3)
        before = dict(entry)
        # Protein of 150g / 100g is impossible
        with caplog.at_level(logging.WARNING):
            enforce_portion_scaling(entry,
                                    {"calories": 400, "protein": 150,
                                     "carbs": 3.4, "fats": 0.2},
                                    180, "label")
        assert entry == before, "entry must be untouched on impossible per_100g"
        assert any("portion_scaling_skip" in rec.message for rec in caplog.records), \
            "expected portion_scaling_skip log entry"

    def test_correction_log_shape(self, caplog):
        entry = _make_entry("Yogurt tub", 85, 15.2, 5.4, 0.3)
        with caplog.at_level(logging.WARNING):
            enforce_portion_scaling(entry, YOGURT_PER100, 180, "label")
        joined = " ".join(rec.message for rec in caplog.records)
        assert "portion_scaling" in joined
        assert "Yogurt tub" in joined
        assert "→" in joined  # X → Y deltas
        assert "per_100g" in joined

    def test_protein_g_alias_supported(self):
        # Entry uses *_g variants (as some upstream code paths do)
        entry = {
            "food_name": "Yogurt", "calories": 85,
            "protein_g": 15.2, "carbs_g": 5.4, "fat_g": 0.3,
        }
        enforce_portion_scaling(entry, YOGURT_PER100, 180, "label")
        assert entry["calories"] == 112
        assert entry["protein_g"] == 17.1
        assert entry["carbs_g"] == 6.12
        # 'fat_g' is not in the canonical macro list — enforce_portion_scaling
        # uses 'fats' as canonical; if not present it will write 'fats'.
        # Verify either path corrected.
        fats_val = entry.get("fats", entry.get("fat_g"))
        assert abs(fats_val - 0.36) < 0.05


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

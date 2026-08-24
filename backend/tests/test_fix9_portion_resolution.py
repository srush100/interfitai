"""Backend tests for Fix 9 — DETERMINISTIC PORTION RESOLUTION.

The model returns:
  • per_100g
  • serving_size_g       (e.g. 104)
  • units_per_serving    (e.g. 2 from "Edible Portion of 2 Eggs")
  • unit_name            (e.g. "egg")

The APP resolves the user's stated portion (amount + unit) to grams:
  • "200 grams"    → 200
  • "2 servings"   → 2 × serving_size_g
  • "4 eggs"       → (4 / units_per_serving) × serving_size_g   (label wins)
  • "4 eggs" but label lacks units_per_serving → fallback to _ITEM_FALLBACK_WEIGHTS_G

Then final = per_100g × portion_g / 100 as always.

User's exact regression checklist (see the message that motivated this file):
  Egg carton (per_100g 143/12.2/1.3/9.9, serving 104g = 2 eggs):
    "4 eggs"      → 208g → 297/25.4/2.7/20.6
    "2 eggs"      → 104g → 149/12.7/1.4/10.3
    "1 serving"   → 104g → 149/12.7/1.4/10.3
    "150 grams"   → 150g → 215/18.3/2.0/14.9
  Yogurt (per_100g 62/9.5/3.4/0.2, serving 160g):
    "1 serving"   → 160g → 99/15.2/5.4/0.3
    "200 grams"   → 200g → 124/19.0/6.8/0.4
  Meat pack (per_100g 171/26.5/0/6.9, serving 100g):
    "2 servings"  → 200g → 342/53/0/13.8
"""
import os
import sys
import json
import uuid
import base64
import struct
import zlib
import pytest
from httpx import AsyncClient, ASGITransport
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
import server  # noqa: E402
from server import app, resolve_portion_g  # noqa: E402

_sync_client = MongoClient(os.environ["MONGO_URL"])
_sync_db = _sync_client[os.environ.get("DB_NAME", "test_database")]


# ─── Helpers ──────────────────────────────────────────────────────────────

def _tiny_png_b64() -> str:
    def chunk(t, data):
        L = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(t + data) & 0xFFFFFFFF)
        return L + t + data + crc
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 20, 20, 8, 2, 0, 0, 0))
    raw = b""
    for _ in range(20):
        raw += b"\x00" + b"\xff\x00\x00" * 20
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return base64.b64encode(sig + ihdr + idat + iend).decode()


TEST_IMAGE = _tiny_png_b64()


def _mock_factory(*responses):
    payloads = [json.dumps(r) if isinstance(r, dict) else r for r in responses]
    calls = {"i": 0}
    async def _mock(system_message, user_message, temperature=0.7,
                   max_tokens=2500, image_base64=None, image_base64_2=None):
        idx = min(calls["i"], len(payloads) - 1)
        calls["i"] += 1
        return payloads[idx]
    _mock.calls = calls
    return _mock


@pytest.fixture
def paid_user():
    uid = f"TEST_fix9_{uuid.uuid4().hex[:8]}"
    _sync_db.profiles.insert_one({
        "id": uid,
        "email": f"{uid}@test.local",
        "name": "Fix9 Test User",
        "subscription_status": "monthly",
        "weight": 80, "height": 180, "age": 30,
        "gender": "male", "activity_level": "moderate", "goal": "maintenance",
    })
    yield uid
    _sync_db.profiles.delete_one({"id": uid})
    _sync_db.food_logs.delete_many({"user_id": uid})


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ─── Pure-function tests for resolve_portion_g ────────────────────────────

class TestResolvePortionG:
    """Direct unit tests on the pure resolver — no HTTP round trip."""

    def test_grams_direct(self):
        g, src, _ = resolve_portion_g(200, "grams", 104, 2, "egg", None)
        assert g == 200 and src == "grams"

    def test_grams_singular_alias(self):
        for u in ("g", "gram", "grams", "gm", "gms", "ml", "milliliters"):
            g, src, _ = resolve_portion_g(100, u, 50, None, None, None)
            assert g == 100 and src == "grams", f"unit={u}"

    def test_servings_scales_by_label(self):
        g, src, _ = resolve_portion_g(2, "servings", 160, None, None, None)
        assert g == 320 and src == "servings"

    def test_servings_no_label_returns_none(self):
        g, src, _ = resolve_portion_g(2, "servings", None, None, None, None)
        assert g is None and src == "servings_no_label"

    def test_count_label_wins_over_fallback(self):
        # User's exact scenario: 4 eggs on a "2 eggs per serving, 104g" label
        # Label per-unit = 104/2 = 52g. Fallback table has egg=58g. Label wins.
        g, src, dbg = resolve_portion_g(4, "count", 104, 2, "egg", None)
        assert g == 208.0, f"expected 208g, got {g}"
        assert src == "count_label"
        assert dbg["per_unit_g"] == 52.0

    def test_count_2_eggs(self):
        g, src, _ = resolve_portion_g(2, "count", 104, 2, "egg", None)
        assert g == 104.0
        assert src == "count_label"

    def test_count_fallback_when_no_units_per_serving(self):
        # Label lacks units_per_serving → fall back to _ITEM_FALLBACK_WEIGHTS_G
        g, src, dbg = resolve_portion_g(3, "egg", None, None, "egg", None)
        assert g == 3 * 58  # fallback egg = 58g
        assert src == "count_fallback"
        assert dbg["fallback_per_unit_g"] == 58

    def test_count_unresolved_when_unknown_unit(self):
        g, src, _ = resolve_portion_g(3, "count", None, None, "mystery_widget", None)
        assert g is None and src == "unresolved"

    def test_legacy_portion_g_when_no_amount(self):
        g, src, _ = resolve_portion_g(None, None, 104, 2, "egg", legacy_portion_g=250)
        assert g == 250.0 and src == "legacy"

    def test_amount_wins_over_legacy(self):
        # New API takes precedence over legacy portion_g if both provided
        g, src, _ = resolve_portion_g(4, "count", 104, 2, "egg", legacy_portion_g=999)
        assert g == 208.0 and src == "count_label"

    def test_none_when_nothing_given(self):
        g, src, _ = resolve_portion_g(None, None, 104, 2, "egg", None)
        assert g is None and src == "none"


# ─── End-to-end HTTP tests — user's regression checklist ─────────────────

EGG_CARTON_LABEL = {
    "food_name": "Free Range Eggs",
    "serving_size": "104g (2 eggs)",
    "serving_size_g": 104,
    "units_per_serving": 2,
    "unit_name": "egg",
    "per_100g": {"calories": 143, "protein": 12.2, "carbs": 1.3, "fats": 9.9},
    "calories": 149, "protein": 12.7, "carbs": 1.4, "fats": 10.3,
    "confidence": "high", "energy_source": "label",
}

YOGURT_LABEL = {
    "food_name": "Greek Yogurt Plain",
    "serving_size": "160g",
    "serving_size_g": 160,
    "units_per_serving": None,
    "unit_name": None,
    "per_100g": {"calories": 62, "protein": 9.5, "carbs": 3.4, "fats": 0.2},
    "calories": 99, "protein": 15.2, "carbs": 5.4, "fats": 0.3,
    "confidence": "high", "energy_source": "label",
}

MEAT_LABEL = {
    "food_name": "Extra Lean Beef Mince 5%",
    "serving_size": "100g",
    "serving_size_g": 100,
    "units_per_serving": None,
    "unit_name": None,
    "per_100g": {"calories": 171, "protein": 26.5, "carbs": 0.0, "fats": 6.9},
    "calories": 171, "protein": 26.5, "carbs": 0.0, "fats": 6.9,
    "confidence": "high", "energy_source": "label",
}


@pytest.mark.asyncio
@pytest.mark.parametrize("amount,unit,exp_g,exp_cal,exp_p,exp_c,exp_f", [
    # User's exact regression checklist for the egg carton
    (4, "count",    208, 297, 25.4, 2.7, 20.6),
    (2, "count",    104, 149, 12.7, 1.4, 10.3),
    (1, "servings", 104, 149, 12.7, 1.4, 10.3),
    (150, "grams",  150, 215, 18.3, 2.0, 14.9),
])
async def test_egg_carton_all_portion_shapes(client, paid_user, monkeypatch,
                                              amount, unit, exp_g, exp_cal, exp_p, exp_c, exp_f):
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(EGG_CARTON_LABEL))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "breakfast",
        "portion_amount": amount, "portion_unit": unit,
        "preview": True,
    })
    assert r.status_code == 200, r.text[:300]
    b = r.json()
    assert b["portion_g_applied"] == exp_g, f"portion_g mismatch: got {b['portion_g_applied']}, expected {exp_g}"
    assert abs(b["calories"] - exp_cal) <= 2, f"cal: got {b['calories']}, expected ~{exp_cal}"
    assert abs(b["protein"] - exp_p) <= 0.3, f"protein: got {b['protein']}, expected ~{exp_p}"
    assert abs(b["carbs"]   - exp_c) <= 0.3, f"carbs: got {b['carbs']}, expected ~{exp_c}"
    assert abs(b["fats"]    - exp_f) <= 0.3, f"fats: got {b['fats']}, expected ~{exp_f}"
    # Envelope surfaces label reference points to the UI
    assert b["label_serving_size_g"] == 104
    assert b["label_units_per_serving"] == 2
    assert b["label_unit_name"] == "egg"


@pytest.mark.asyncio
@pytest.mark.parametrize("amount,unit,exp_g,exp_cal,exp_p,exp_c,exp_f", [
    (1, "servings", 160,  99, 15.2, 5.4, 0.3),
    (200, "grams",  200, 124, 19.0, 6.8, 0.4),
])
async def test_yogurt_all_portion_shapes(client, paid_user, monkeypatch,
                                          amount, unit, exp_g, exp_cal, exp_p, exp_c, exp_f):
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(YOGURT_LABEL))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "snack",
        "portion_amount": amount, "portion_unit": unit,
        "preview": True,
    })
    assert r.status_code == 200, r.text[:300]
    b = r.json()
    assert b["portion_g_applied"] == exp_g
    assert abs(b["calories"] - exp_cal) <= 2
    assert abs(b["protein"] - exp_p) <= 0.3
    assert abs(b["carbs"]   - exp_c) <= 0.3
    assert abs(b["fats"]    - exp_f) <= 0.3


@pytest.mark.asyncio
async def test_meat_two_servings(client, paid_user, monkeypatch):
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(MEAT_LABEL))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "dinner",
        "portion_amount": 2, "portion_unit": "servings",
        "preview": True,
    })
    assert r.status_code == 200, r.text[:300]
    b = r.json()
    assert b["portion_g_applied"] == 200
    assert abs(b["calories"] - 342) <= 3, f"cal off: {b['calories']}"
    assert abs(b["protein"] - 53.0) <= 0.5
    assert abs(b["carbs"]  - 0.0) <= 0.3
    assert abs(b["fats"]   - 13.8) <= 0.5


# ─── Regression: the user's original egg bug ──────────────────────────────

@pytest.mark.asyncio
async def test_regression_4_eggs_not_halved(client, paid_user, monkeypatch):
    """Before Fix 9: '4 eggs' with a '2 eggs per serving, 104g' label was
    silently interpreted as one serving (104g) instead of two servings (208g),
    returning EXACTLY half the correct calories."""
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(EGG_CARTON_LABEL))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "breakfast",
        "portion_amount": 4, "portion_unit": "count",
        "preview": True,
    })
    assert r.status_code == 200
    b = r.json()
    # Before fix: 149 cal (half). After fix: 297 cal (correct).
    assert b["calories"] >= 290, (
        f"REGRESSION: '4 eggs' returned {b['calories']} cal — should be ~297. "
        "Portion count is not being converted to grams via the label."
    )
    assert b["portion_g_applied"] == 208


# ─── Fail-visible when the user gives count/servings but label is missing info ──

@pytest.mark.asyncio
async def test_count_without_label_units_uses_fallback(client, paid_user, monkeypatch):
    """If the label doesn't state units_per_serving, but the unit is a known
    countable (egg, slice, etc.), fall back to _ITEM_FALLBACK_WEIGHTS_G."""
    bare_egg_label = {
        **EGG_CARTON_LABEL,
        "serving_size_g": None,
        "units_per_serving": None,
        "unit_name": "egg",
    }
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(bare_egg_label))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "breakfast",
        "portion_amount": 3, "portion_unit": "egg",  # user explicitly says eggs
        "preview": True,
    })
    assert r.status_code == 200, r.text[:300]
    b = r.json()
    assert b["portion_g_applied"] == 3 * 58  # fallback egg = 58g
    assert b["portion_source"] == "count_fallback"


@pytest.mark.asyncio
async def test_servings_without_serving_size_fails_visibly(client, paid_user, monkeypatch):
    """User says '2 servings' but the label has no serving_size_g → 422."""
    no_serving_label = {**YOGURT_LABEL, "serving_size_g": None, "serving_size": "N/A"}
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(no_serving_label))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "snack",
        "portion_amount": 2, "portion_unit": "servings",
        "preview": True,
    })
    assert r.status_code == 422
    detail = r.json().get("detail", {})
    assert detail.get("error") == "portion_unresolvable"


# ─── Backward compatibility: legacy portion_g still works ────────────────

@pytest.mark.asyncio
async def test_legacy_portion_g_still_works(client, paid_user, monkeypatch):
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(YOGURT_LABEL))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "snack",
        "portion_g": 200,  # legacy path
        "preview": True,
    })
    assert r.status_code == 200
    b = r.json()
    assert b["portion_g_applied"] == 200
    assert b["portion_source"] == "legacy"
    assert 118 <= b["calories"] <= 130



# ─── Natural-language `portion_text` end-to-end ─────────────────────────

class TestParsePortionText:
    """Direct unit tests on the free-text parser."""

    def test_basic_number_and_unit(self):
        from server import parse_portion_text as p
        assert p("200 grams") == (200.0, "grams")
        assert p("200g") == (200.0, "grams")
        assert p("200 g") == (200.0, "grams")
        assert p("4 eggs") == (4.0, "egg")
        assert p("4 egg") == (4.0, "egg")
        assert p("1 slice") == (1.0, "slice")
        assert p("3 slices") == (3.0, "slice")
        assert p("2 servings") == (2.0, "servings")
        assert p("1 serving") == (1.0, "servings")

    def test_word_numbers(self):
        from server import parse_portion_text as p
        assert p("one serving") == (1.0, "servings")
        assert p("two eggs") == (2.0, "egg")
        assert p("half a serving") == (0.5, "servings")
        assert p("an egg") == (1.0, "egg")
        assert p("a serving") == (1.0, "servings")

    def test_unit_conversions(self):
        from server import parse_portion_text as p
        assert p("1 kg") == (1000.0, "grams")
        assert p("2 kg") == (2000.0, "grams")
        assert p("250 ml") == (250.0, "grams")  # 1:1 for label scaling
        assert p("1 l") == (1000.0, "grams")
        # ounces / pounds
        amt, unit = p("1 oz")
        assert unit == "grams" and abs(amt - 28.35) < 0.1
        amt, unit = p("1 lb")
        assert unit == "grams" and abs(amt - 453.6) < 0.5

    def test_bare_number_defaults_to_grams(self):
        from server import parse_portion_text as p
        assert p("200") == (200.0, "grams")
        assert p("150.5") == (150.5, "grams")

    def test_of_x_suffix_stripped(self):
        from server import parse_portion_text as p
        assert p("3 slices of bread") == (3.0, "slice")
        assert p("2 cups of rice") == (2.0, "cup")

    def test_empty_or_gibberish(self):
        from server import parse_portion_text as p
        assert p("") == (None, None)
        assert p("gibberish") == (None, None)
        assert p("no numbers here") == (None, None)

    def test_zero_or_negative_rejected(self):
        from server import parse_portion_text as p
        assert p("0 grams") == (None, None)


# ─── User's exact regression: "4 eggs" via portion_text ──────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("text,exp_g,exp_cal,exp_p,exp_c,exp_f", [
    ("4 eggs",       208, 297, 25.4, 2.7, 20.6),
    ("2 eggs",       104, 149, 12.7, 1.4, 10.3),
    ("1 egg",         52,  74,  6.3, 0.7,  5.1),  # 104/2 = 52g per egg
    ("2 servings",   208, 297, 25.4, 2.7, 20.6),  # 2 × 104g
    ("1 serving",    104, 149, 12.7, 1.4, 10.3),
    ("150 grams",    150, 215, 18.3, 2.0, 14.9),
    ("150g",         150, 215, 18.3, 2.0, 14.9),
    ("half a serving", 52, 74,  6.3, 0.7,  5.1),
    ("two eggs",     104, 149, 12.7, 1.4, 10.3),
    ("four eggs",    208, 297, 25.4, 2.7, 20.6),
])
async def test_egg_carton_portion_text(client, paid_user, monkeypatch,
                                        text, exp_g, exp_cal, exp_p, exp_c, exp_f):
    """User writes free-text portion in the description box. Backend parses
    and resolves via the label. '4 eggs' and '2 servings' MUST return the
    same numbers on this label (2 eggs / serving)."""
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(EGG_CARTON_LABEL))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "breakfast",
        "portion_text": text,
        "preview": True,
    })
    assert r.status_code == 200, r.text[:300]
    b = r.json()
    assert b["portion_g_applied"] == exp_g, (
        f"'{text}' → portion_g={b['portion_g_applied']}, expected {exp_g}"
    )
    assert abs(b["calories"] - exp_cal) <= 2, f"'{text}' cal off: {b['calories']} vs {exp_cal}"
    assert abs(b["protein"] - exp_p) <= 0.3, f"'{text}' protein off: {b['protein']} vs {exp_p}"
    assert abs(b["carbs"]   - exp_c) <= 0.3
    assert abs(b["fats"]    - exp_f) <= 0.3


@pytest.mark.asyncio
async def test_4_eggs_equals_2_servings(client, paid_user, monkeypatch):
    """User's explicit requirement: '4 eggs' and '2 servings' must yield the
    IDENTICAL result on a 2-eggs-per-serving carton."""
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(EGG_CARTON_LABEL, EGG_CARTON_LABEL))
    r1 = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "breakfast",
        "portion_text": "4 eggs", "preview": True,
    })
    r2 = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "breakfast",
        "portion_text": "2 servings", "preview": True,
    })
    assert r1.status_code == 200 and r2.status_code == 200
    a, b = r1.json(), r2.json()
    assert a["portion_g_applied"] == b["portion_g_applied"] == 208, (
        f"'4 eggs' ({a['portion_g_applied']}g) must equal '2 servings' ({b['portion_g_applied']}g) = 208g"
    )
    assert a["calories"] == b["calories"]
    assert a["protein"]  == b["protein"]
    assert a["carbs"]    == b["carbs"]
    assert a["fats"]     == b["fats"]


@pytest.mark.asyncio
@pytest.mark.parametrize("text,exp_g,exp_cal", [
    ("1 serving", 160,  99),
    ("2 servings", 320, 198),
    ("200 grams", 200, 124),
    ("200g", 200, 124),
])
async def test_yogurt_portion_text(client, paid_user, monkeypatch, text, exp_g, exp_cal):
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(YOGURT_LABEL))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "snack",
        "portion_text": text, "preview": True,
    })
    assert r.status_code == 200, r.text[:300]
    b = r.json()
    assert b["portion_g_applied"] == exp_g
    assert abs(b["calories"] - exp_cal) <= 2


@pytest.mark.asyncio
async def test_meat_two_servings_via_text(client, paid_user, monkeypatch):
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(MEAT_LABEL))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "dinner",
        "portion_text": "2 servings", "preview": True,
    })
    assert r.status_code == 200
    b = r.json()
    assert b["portion_g_applied"] == 200
    assert abs(b["calories"] - 342) <= 3


@pytest.mark.asyncio
async def test_gibberish_portion_text_fails_visibly(client, paid_user, monkeypatch):
    """Non-parseable text → 422 portion_unresolvable with a friendly message."""
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(EGG_CARTON_LABEL))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "breakfast",
        "portion_text": "banana pancake", "preview": True,
    })
    assert r.status_code == 422
    d = r.json().get("detail", {})
    assert d.get("error") == "portion_unresolvable"
    assert "portion" in d.get("message", "").lower() or "description" in d.get("message", "").lower()


@pytest.mark.asyncio
async def test_empty_portion_text_falls_to_best_effort(client, paid_user, monkeypatch):
    """No portion text → 200 with best-effort per-serving values (no 422)."""
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(EGG_CARTON_LABEL))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "breakfast",
        "portion_text": "", "preview": True,
    })
    assert r.status_code == 200




# ─── User's real-world regression: composite dish with "chicken" in name ──

@pytest.mark.asyncio
async def test_chicken_and_bacon_macaroni_records_label_correctly(client, paid_user, monkeypatch):
    """User's REAL bug from the field: scanning a "Chicken & Bacon Macaroni"
    ready meal returned API error 422 even though the AI read the label
    correctly. Root cause: _lookup_reference substring-matched "chicken" →
    returned plain chicken breast (165/31/0/3.6), and any composite dish
    with pasta has 14.9g carbs vs 0g in chicken breast → 1490% divergence →
    false hallucination flag → composite_reject → 422.

    Fix: when the label read passes physical plausibility (Atwater within
    30%, no macro over 100g/100g), we TRUST it and skip the reference
    check entirely. Reference cross-check only runs on already-suspect data.
    """
    macaroni = {
        "food_name": "Chicken & Bacon Macaroni",
        "serving_size": "350g",
        "serving_size_g": 350,
        "units_per_serving": None,
        "unit_name": None,
        "per_100g": {"calories": 149, "protein": 13.1, "carbs": 14.9, "fats": 3.9},
        "calories": 522, "protein": 45.8, "carbs": 52.2, "fats": 13.6,
        "confidence": "high", "energy_source": "label",
    }
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(macaroni))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "lunch",
        "portion_text": "1 serving",  # user's exact input
        "preview": True,
    })
    assert r.status_code == 200, f"REGRESSION: composite dish rejected. {r.text[:400]}"
    b = r.json()
    assert b["hallucination_fallback"] is False, "must NOT have swapped in chicken breast"
    assert b["per_100g_source"] == "label"
    # 149cal/100g × 350g = 521 cal (label-honored)
    assert 510 <= b["calories"] <= 535, f"cal off: {b['calories']}"
    assert 44 <= b["protein"] <= 48, f"protein was reading 108g under old bug: {b['protein']}"
    assert 50 <= b["carbs"] <= 55, f"carbs must not be 0 (chicken-breast substitution): {b['carbs']}"
    assert 12 <= b["fats"] <= 15


@pytest.mark.asyncio
async def test_free_range_eggs_bad_read_still_falls_back_safely(client, paid_user, monkeypatch):
    """When the AI hallucinates a WILDLY WRONG calorie value on eggs
    (e.g. 596cal/100g), the physical-plausibility check fires (Atwater
    mismatch), we retry, and if the retry still fails, fall back to the
    eggs reference (since "Free Range Eggs" contains the safe token "eggs")."""
    bad = {
        "food_name": "Free Range Eggs",
        "serving_size": "104g (2 eggs)",
        "serving_size_g": 104,
        "units_per_serving": 2,
        "unit_name": "egg",
        # 596cal but 12.1P/1.3C/9.9F → derived only ~143cal → 76% Atwater gap → IMPLAUSIBLE
        "per_100g": {"calories": 596, "protein": 12.1, "carbs": 1.3, "fats": 9.9},
        "calories": 620, "protein": 12.7, "carbs": 1.4, "fats": 10.3,
        "confidence": "high", "energy_source": "label",
    }
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(bad, bad, bad))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "breakfast",
        "portion_text": "4 eggs",
        "preview": True,
    })
    # Either the retry produced a plausible read (200), or we fell back to
    # eggs reference values (200 with per_100g_source == "reference_fallback"),
    # or we honestly failed (422). All three are acceptable — none silently
    # writes 596cal/100g to the log.
    if r.status_code == 200:
        b = r.json()
        # Whatever route we took, the final per-100g must be plausible
        cal_per_g = b["calories"] / max(b["portion_g_applied"] or 1, 1)
        assert cal_per_g < 5.0, f"still reporting an impossible {cal_per_g:.1f} cal/g"
    else:
        assert r.status_code == 422

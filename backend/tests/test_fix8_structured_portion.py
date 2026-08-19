"""Backend tests for Fix 8 — STRUCTURED PORTION + CODE-OWNED ARITHMETIC.

Covers architectural changes to /api/food/analyze:
  1. Code owns portion arithmetic when portion_g > 0
  2. Hallucination detection + retry + reference fallback
  3. Per-100g derivation from per-serving + serving_g
  4. Fail visibly (422) when per_100g cannot be established
  5. Fail visibly (422) on confidence: "low"
  6. No-portion best-effort path preserved
  7. Preview envelope (label_per_100g, portion_g_applied, per_100g_source, hallucination_fallback)
  8. Subscription gate (403 for free users)
  9. Structured logging on hallucination events
 10. Determinism — 5x run of happy path yields identical result

All Anthropic calls are stubbed via monkeypatch on server.call_claude_sonnet.
No network / real LLM API is hit.
"""
import os
import sys
import json
import uuid
import base64
import struct
import zlib
import asyncio
import logging
import pytest
from httpx import AsyncClient, ASGITransport
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
import server  # noqa: E402
from server import app  # noqa: E402

# Use a sync pymongo client bound to no loop for setup/teardown (Motor is
# tied to the loop that first touched it and pytest-asyncio spins loops in
# ways that break Motor's global executor).
_sync_client = MongoClient(os.environ["MONGO_URL"])
_sync_db = _sync_client[os.environ.get("DB_NAME", "test_database")]


# ─── Helpers ──────────────────────────────────────────────────────────────

def _tiny_png_b64() -> str:
    """Minimal valid PNG (>100 bytes base64) — passes /food/analyze image guard."""
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
    """Return an async mock producing the given JSON dict responses in order.
    Extra calls after the list is exhausted return the last response."""
    payloads = [json.dumps(r) if isinstance(r, dict) else r for r in responses]
    calls = {"i": 0, "history": []}

    async def _mock(system_message, user_message, temperature=0.7,
                   max_tokens=2500, image_base64=None, image_base64_2=None):
        idx = min(calls["i"], len(payloads) - 1)
        calls["i"] += 1
        calls["history"].append({"user_message": user_message})
        return payloads[idx]

    _mock.calls = calls
    return _mock


# ─── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def paid_user():
    """Seed a paid subscriber; teardown after test."""
    uid = f"TEST_fix8_{uuid.uuid4().hex[:8]}"
    _sync_db.profiles.insert_one({
        "id": uid,
        "email": f"{uid}@test.local",
        "name": "Fix8 Test User",
        "subscription_status": "monthly",
        "weight": 80, "height": 180, "age": 30,
        "gender": "male", "activity_level": "moderate", "goal": "maintenance",
    })
    yield uid
    _sync_db.profiles.delete_one({"id": uid})
    _sync_db.food_logs.delete_many({"user_id": uid})


@pytest.fixture
def free_user():
    uid = f"TEST_fix8_free_{uuid.uuid4().hex[:8]}"
    _sync_db.profiles.insert_one({
        "id": uid,
        "email": f"{uid}@test.local",
        "name": "Free User",
        "subscription_status": "free",
        "weight": 80, "height": 180, "age": 30,
        "gender": "male", "activity_level": "moderate", "goal": "maintenance",
    })
    yield uid
    _sync_db.profiles.delete_one({"id": uid})


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ─── 1. Subscription gate ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_subscription_gate_free_user_gets_403(client, free_user, monkeypatch):
    called = {"n": 0}
    async def _boom(*a, **kw):
        called["n"] += 1
        return "{}"
    monkeypatch.setattr(server, "call_claude_sonnet", _boom)

    r = await client.post("/api/food/analyze", json={
        "user_id": free_user, "image_base64": TEST_IMAGE,
        "meal_type": "snack", "portion_g": 200,
    })
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:200]}"
    assert called["n"] == 0, "gate must fire BEFORE calling the LLM"


# ─── 2. YOGURT hallucination scenario (user's real bug) ───────────────────

@pytest.mark.asyncio
async def test_yogurt_hallucination_falls_back_to_reference(client, paid_user, monkeypatch, caplog):
    """User's REAL yogurt bug: model returns invented 31g P/100g.

    IMPORTANT — this test currently FAILS because `_lookup_reference` picks the
    wrong reference ("protein powder" 400/80/10/3.3) for the food name
    "High Protein Yogurt" (substring match: 'protein' beats 'yogurt' by length
    despite being semantically wrong). The hallucination guard then sees
    max_div=90% (<100% threshold) and does NOT fall back. The model's bad
    138 cal/100g × 2 = 276cal is returned as-is.

    This documents the residual architectural gap flagged to the main agent.
    Once _lookup_reference is fixed to prefer 'yogurt' over 'protein' for this
    string, the guard will fire and calories should end up around 118 (=59×2).
    """
    bad = {
        "food_name": "High Protein Yogurt",
        "serving_size": "1 serving (100g)",
        "per_100g": {"calories": 138, "protein": 31, "carbs": 1, "fats": 1},
        "calories": 138, "protein": 31, "carbs": 1, "fats": 1,
        "confidence": "high", "energy_source": "label",
    }
    mock = _mock_factory(bad, bad, bad)
    monkeypatch.setattr(server, "call_claude_sonnet", mock)

    with caplog.at_level(logging.WARNING):
        r = await client.post("/api/food/analyze", json={
            "user_id": paid_user, "image_base64": TEST_IMAGE,
            "meal_type": "snack", "portion_g": 200, "preview": True,
        })
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:300]}"
    body = r.json()
    # Should be reference × 2 = ~118 / 20 / 8 / 0.8 ONCE bug is fixed.
    # Assertion left as spec — will fail until _lookup_reference is corrected.
    assert 110 <= body["calories"] <= 130, (
        f"cal off: {body['calories']} — reference lookup picked wrong food "
        "('protein' instead of 'yogurt' for 'High Protein Yogurt'). "
        "See RCA in test_reports/iteration_47.json."
    )
    assert 18 <= body["protein"] <= 22, f"protein off: {body['protein']}"
    assert body["hallucination_fallback"] is True
    assert body["per_100g_source"] == "reference_fallback"

    log_txt = " ".join(rec.getMessage() for rec in caplog.records)
    assert "[nutrition-guard]" in log_txt
    assert "hallucination_detected" in log_txt
    assert "hallucination_fallback_to_reference" in log_txt


# ─── 3. YOGURT happy path — correct per-100g values ──────────────────────

@pytest.mark.asyncio
async def test_yogurt_happy_path_correct_per100g(client, paid_user, monkeypatch):
    """Correct per-100g yogurt values. Expected: 62×2=124cal, 9.5×2=19P, 3.4×2=6.8C, 0.2×2=0.4F."""
    good = {
        "food_name": "Greek Yogurt Plain",
        "serving_size": "160g",
        "per_100g": {"calories": 62, "protein": 9.5, "carbs": 3.4, "fats": 0.2},
        "calories": 99, "protein": 15.2, "carbs": 5.4, "fats": 0.3,
        "confidence": "high", "energy_source": "label",
    }
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(good))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "snack", "portion_g": 200, "preview": True,
    })
    assert r.status_code == 200, r.text[:300]
    b = r.json()
    # Label-transcribed energy is now honored (Option A). Yogurt uses food-specific
    # Atwater factors so 62 kcal/100g stays as-is (P*4+C*4+F*9 = 53 is only a rough
    # anchor, not ground truth). At 200g: 124cal / 19P / 6.8C / 0.4F.
    assert 118 <= b["calories"] <= 130, f"cal off: {b['calories']}"
    assert abs(b["protein"] - 19.0) < 0.5
    assert abs(b["carbs"] - 6.8) < 0.5
    assert abs(b["fats"] - 0.4) < 0.1
    assert b["hallucination_fallback"] is False
    assert b["per_100g_source"] == "label"
    assert b["portion_g_applied"] == 200
    assert b["label_per_100g"]["protein"] == 9.5


# ─── 4. Code owns arithmetic — bad top-level totals ignored ───────────────

@pytest.mark.asyncio
async def test_code_owns_arithmetic_ignores_wrong_top_level_totals(client, paid_user, monkeypatch):
    payload = {
        "food_name": "Greek Yogurt",
        "serving_size": "1 serving (100g)",
        "per_100g": {"calories": 62, "protein": 9.5, "carbs": 3.4, "fats": 0.2},
        "calories": 500, "protein": 50, "carbs": 40, "fats": 20,  # WRONG
        "confidence": "high", "energy_source": "label",
    }
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(payload))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "snack", "portion_g": 200, "preview": True,
    })
    assert r.status_code == 200, r.text[:300]
    b = r.json()
    # Label-honored: 62 cal/100g × 2 = 124cal (Option A preserves label energy).
    assert 118 <= b["calories"] <= 130, f"code should scale per_100g×2 (label honored), got {b['calories']}"
    assert b["calories"] != 500


# ─── 5. Derive per-100g from per-serving + serving_g ─────────────────────

@pytest.mark.asyncio
async def test_derive_per100g_from_per_serving(client, paid_user, monkeypatch):
    """Model omits per_100g block but gives serving_size='160g' with per-serving totals.
    App derives per_100g and scales × 2."""
    payload = {
        "food_name": "High Protein Yogurt",
        "serving_size": "160g",
        "calories": 93, "protein": 15.2, "carbs": 5.4, "fats": 0.3,
        "confidence": "high", "energy_source": "label",
    }
    # Note: greek yogurt reference is 59/10/4/0.4 per-100g. Derived would be
    # 58.1/9.5/3.375/0.1875 — this is within ~100% of ref so may or may not trigger halluc.
    # Actual: derived cal=58.1 vs ref 59 → 1.5% off. Fine.
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(payload))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "snack", "portion_g": 200, "preview": True,
    })
    assert r.status_code == 200, r.text[:300]
    b = r.json()
    assert b["per_100g_source"] in ("derived_from_serving", "retry_derived"), b["per_100g_source"]
    # Derived per-100g × 2 = 116.25 cal, 19P, 6.75C, 0.375F
    assert 110 <= b["calories"] <= 122, f"cal off: {b['calories']}"
    assert 18.5 <= b["protein"] <= 20, f"protein off: {b['protein']}"
    assert 6 <= b["carbs"] <= 8, f"carbs off: {b['carbs']}"
    assert b["portion_g_applied"] == 200


# ─── 6. Fail visibly — no per_100g establishable ─────────────────────────

@pytest.mark.asyncio
async def test_fail_visibly_when_no_per100g_and_non_gram_serving(client, paid_user, monkeypatch):
    payload = {
        "food_name": "Mystery Dish",
        "serving_size": "1 serving",  # no grams, no cup — cannot derive
        "calories": 200, "protein": 5, "carbs": 20, "fats": 8,
        "confidence": "high", "energy_source": "derived",
    }
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(payload))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "snack", "portion_g": 200, "preview": True,
    })
    assert r.status_code == 422, f"expected 422 label_unreadable, got {r.status_code}: {r.text[:300]}"
    detail = r.json().get("detail", {})
    assert detail.get("error") == "label_unreadable"
    assert "label" in detail.get("message", "").lower()


# ─── 7. Fail visibly on confidence=low ───────────────────────────────────

@pytest.mark.asyncio
async def test_fail_visibly_on_low_confidence(client, paid_user, monkeypatch):
    payload = {
        "food_name": "Blurry Food",
        "serving_size": "100g",
        "per_100g": {"calories": 100, "protein": 5, "carbs": 10, "fats": 3},
        "calories": 100, "protein": 5, "carbs": 10, "fats": 3,
        "confidence": "low", "energy_source": "label",
    }
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(payload))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "snack", "portion_g": 200, "preview": True,
    })
    assert r.status_code == 422
    detail = r.json().get("detail", {})
    assert detail.get("error") == "label_unreadable"


# ─── 8. No-portion best-effort path preserved ────────────────────────────

@pytest.mark.asyncio
async def test_no_portion_best_effort_path(client, paid_user, monkeypatch):
    payload = {
        "food_name": "Greek Yogurt Plain",
        "serving_size": "160g",
        "per_100g": {"calories": 62, "protein": 9.5, "carbs": 3.4, "fats": 0.2},
        "calories": 99, "protein": 15.2, "carbs": 5.4, "fats": 0.3,
        "confidence": "high", "energy_source": "label",
    }
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(payload))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "snack", "preview": True,
    })
    assert r.status_code == 200, r.text[:300]
    b = r.json()
    # Best-effort: model top-level values used (or Fix-7 corrected). Values should be near per-serving 99cal.
    assert 85 <= b["calories"] <= 110, f"best-effort cal off: {b['calories']}"
    # envelope keys still present
    assert "label_per_100g" in b
    assert "per_100g_source" in b
    assert "hallucination_fallback" in b


# ─── 9. Preview envelope present on every success ────────────────────────

@pytest.mark.asyncio
async def test_preview_envelope_keys_present(client, paid_user, monkeypatch):
    payload = {
        "food_name": "Greek Yogurt",
        "serving_size": "100g",
        "per_100g": {"calories": 62, "protein": 9.5, "carbs": 3.4, "fats": 0.2},
        "calories": 62, "protein": 9.5, "carbs": 3.4, "fats": 0.2,
        "confidence": "high", "energy_source": "label",
    }
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(payload))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "snack", "portion_g": 100, "preview": True,
    })
    assert r.status_code == 200
    b = r.json()
    for k in ("label_per_100g", "portion_g_applied", "per_100g_source", "hallucination_fallback"):
        assert k in b, f"missing envelope key: {k}"
    # FoodEntry fields still present for downstream compat
    for k in ("food_name", "calories", "protein", "carbs", "fats", "serving_size"):
        assert k in b


# ─── 10. Determinism — 5x same input → same output (5 archetypes) ────────

# NOTE: Yogurt labels use food-specific Atwater factors — the printed 62 cal/100g
# does NOT equal P*4+C*4+F*9 (which is 53.4). Under Option A (label energy is
# ground truth), Fix 1's calorie reconciliation is skipped when energy_source is
# "label" and gap < 30%, so the 62 kcal/100g value flows through untouched.
# At 200g the user gets the label-honored 124 kcal (not the 4/4/9-derived 107).
ARCHETYPES = [
    # (name, per_100g, portion_g, expected_cal, expected_p)
    ("yogurt_100g", {"calories": 62, "protein": 9.5, "carbs": 3.4, "fats": 0.2}, 100, 62, 9.5),
    ("yogurt_180g", {"calories": 62, "protein": 9.5, "carbs": 3.4, "fats": 0.2}, 180, 112, 17.1),
    ("yogurt_200g", {"calories": 62, "protein": 9.5, "carbs": 3.4, "fats": 0.2}, 200, 124, 19.0),
    ("beef_mince_200g", {"calories": 171, "protein": 26.5, "carbs": 0, "fats": 6.9}, 200, 342, 53.0),
    ("egg_232g", {"calories": 143, "protein": 12.6, "carbs": 1.1, "fats": 9.5}, 232, 332, 29.2),
    ("milk_250ml", {"calories": 35, "protein": 3.4, "carbs": 4.9, "fats": 0.1}, 250, 88, 8.5),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("name,per100,portion,exp_cal,exp_p", ARCHETYPES)
async def test_archetype_determinism_5x(client, paid_user, monkeypatch,
                                        name, per100, portion, exp_cal, exp_p):
    payload = {
        "food_name": name.replace("_", " ").title(),
        "serving_size": f"{portion}g",
        "per_100g": per100,
        "calories": int(per100["calories"] * portion / 100),
        "protein": per100["protein"] * portion / 100,
        "carbs":   per100["carbs"]   * portion / 100,
        "fats":    per100["fats"]    * portion / 100,
        "confidence": "high", "energy_source": "label",
    }
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(payload))
    results = []
    for _ in range(5):
        r = await client.post("/api/food/analyze", json={
            "user_id": paid_user, "image_base64": TEST_IMAGE,
            "meal_type": "snack", "portion_g": portion, "preview": True,
        })
        assert r.status_code == 200, f"[{name}] status {r.status_code}: {r.text[:200]}"
        b = r.json()
        results.append((b["calories"], round(b["protein"], 2), round(b["carbs"], 2), round(b["fats"], 2)))
    # All 5 identical (determinism)
    assert len(set(results)) == 1, f"[{name}] non-deterministic: {results}"
    cal, p, c, f = results[0]
    assert abs(cal - exp_cal) <= 3, f"[{name}] cal {cal} vs expected ~{exp_cal}"
    assert abs(p - exp_p) <= 0.5, f"[{name}] protein {p} vs expected ~{exp_p}"


# ─── 11. Hallucination retry succeeds on 2nd try ─────────────────────────

@pytest.mark.asyncio
async def test_hallucination_retry_succeeds(client, paid_user, monkeypatch):
    """First call: bad values. Retry with reference anchor: good values.
    Must use retry values, not fallback to reference."""
    bad = {
        "food_name": "Greek Yogurt",
        "serving_size": "100g",
        "per_100g": {"calories": 138, "protein": 31, "carbs": 1, "fats": 1},
        "calories": 138, "protein": 31, "carbs": 1, "fats": 1,
        "confidence": "high", "energy_source": "label",
    }
    good = {
        "food_name": "Greek Yogurt",
        "serving_size": "100g",
        "per_100g": {"calories": 60, "protein": 10, "carbs": 4, "fats": 0.4},
        "calories": 60, "protein": 10, "carbs": 4, "fats": 0.4,
        "confidence": "high", "energy_source": "label",
    }
    # Call 1: initial vision. May also do consistency retry. Let's give 2 bad then good.
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(bad, bad, good))
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "snack", "portion_g": 200, "preview": True,
    })
    assert r.status_code == 200, r.text[:300]
    b = r.json()
    # After successful hallucination retry: 60 × 2 = 120 cal, 10 × 2 = 20 P
    assert b["hallucination_fallback"] is False
    assert b["per_100g_source"] in ("retry_label", "retry_derived"), b["per_100g_source"]
    assert 115 <= b["calories"] <= 125
    assert 19 <= b["protein"] <= 21


# ─── 12. preview=False persists to DB, preview=True does not ─────────────

@pytest.mark.asyncio
async def test_preview_true_does_not_insert(client, paid_user, monkeypatch):
    payload = {
        "food_name": "Greek Yogurt",
        "serving_size": "100g",
        "per_100g": {"calories": 62, "protein": 9.5, "carbs": 3.4, "fats": 0.2},
        "calories": 62, "protein": 9.5, "carbs": 3.4, "fats": 0.2,
        "confidence": "high", "energy_source": "label",
    }
    monkeypatch.setattr(server, "call_claude_sonnet", _mock_factory(payload))
    before = _sync_db.food_logs.count_documents({"user_id": paid_user})
    r = await client.post("/api/food/analyze", json={
        "user_id": paid_user, "image_base64": TEST_IMAGE,
        "meal_type": "snack", "portion_g": 100, "preview": True,
    })
    assert r.status_code == 200
    after = _sync_db.food_logs.count_documents({"user_id": paid_user})
    assert after == before, f"preview=True must not insert, before={before} after={after}"

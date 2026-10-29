"""
Body analyser: a daily fair-use limit, no assumed time period, the AI's answer
checked before it is shown, friendly errors — and every photo sent to the AI
shrunk to the size it reads (Snap and labels too).
"""
import asyncio
import base64
import io
from datetime import datetime, timedelta

import pytest
from PIL import Image

import server


def _jpeg(w, h):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (120, 90, 60)).save(buf, format="JPEG", quality=95)
    return base64.b64encode(buf.getvalue()).decode()


def test_big_photo_shrunk_small_photo_untouched():
    big = _jpeg(4032, 3024)
    out = Image.open(io.BytesIO(base64.b64decode(server._fit_image(big))))
    assert max(out.size) == 1568 and out.size == (1568, 1176)
    small = _jpeg(800, 600)
    assert server._fit_image(small) == small
    assert server._fit_image("not an image") == "not an image"


@pytest.mark.parametrize("raw, score", [(8, 8), ("8/10", 8), (12, 10), (-2, 0), ("7.6", 8), (None, 0)])
def test_ai_answer_checked(raw, score):
    d = server._clean_body_analysis({"estimated_progress_score": raw, "analysis_confidence": "Medium-high",
                                     "visible_changes": "Leaner waist", "recommendations": ["Sleep", 3, ""]})
    assert d["estimated_progress_score"] == score
    assert d["analysis_confidence"] == "high"
    assert d["visible_changes"] == ["Leaner waist"] and d["recommendations"] == ["Sleep"]
    assert d["estimated_body_fat_before"] == "Not estimated"


class Coll:
    def __init__(self):
        self.docs = []

    async def count_documents(self, q):
        since = q["created_at"]["$gte"]
        return len([d for d in self.docs if d["user_id"] == q["user_id"] and d["created_at"] >= since])

    async def insert_one(self, d):
        self.docs.append(d)

    async def find_one(self, q):
        return None


class DB:
    def __init__(self):
        self.body_usage, self.body_analyses, self.profiles = Coll(), Coll(), Coll()


@pytest.fixture
def body(monkeypatch):
    db = DB()
    seen = {}

    async def ok(_):
        return {"has_access": True}

    async def ai(**kw):
        seen.update(kw)
        return '{"overall_assessment": "Leaner.", "estimated_progress_score": "7/10", "analysis_confidence": "medium"}'
    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server, "check_subscription_access", ok)
    monkeypatch.setattr(server, "call_claude_sonnet", ai)
    return db, seen


def _req(period=""):
    return server.BodyAnalysisRequest(user_id="u", before_image_base64="a", after_image_base64="b", time_period=period)


def test_no_dates_no_assumed_period(body):
    db, seen = body
    r = asyncio.run(server.analyze_body_progress(_req()))
    assert "NOT GIVEN" in seen["system_message"] and "3 months" not in seen["system_message"]
    assert "not given" in seen["user_message"]
    assert r["analysis"]["estimated_progress_score"] == 7
    assert db.body_analyses.docs[0]["time_period"] == "Not given"
    asyncio.run(server.analyze_body_progress(_req("12 weeks")))
    assert "12 weeks" in seen["system_message"]


def test_daily_limit(body):
    db, _ = body
    for _ in range(server.BODY_DAILY_LIMIT):
        db.body_usage.docs.append({"user_id": "u", "created_at": datetime.utcnow() - timedelta(hours=1)})
    with pytest.raises(server.HTTPException) as e:
        asyncio.run(server.analyze_body_progress(_req()))
    assert e.value.status_code == 429 and e.value.detail["error"] == "daily_limit"


def test_friendly_error(body, monkeypatch):
    async def broken(**kw):
        raise RuntimeError("socket timeout at 10.0.0.3")
    monkeypatch.setattr(server, "call_claude_sonnet", broken)
    with pytest.raises(server.HTTPException) as e:
        asyncio.run(server.analyze_body_progress(_req()))
    assert "socket" not in str(e.value.detail) and "try again" in e.value.detail

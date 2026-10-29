"""
Admin 'Reset limits': clears a member's usage counters (this month's program /
meal plan generations, today's Snap and body analyses) so they can generate
again. Their programs and meal plans are kept; every reset is recorded.
"""
import asyncio
import re
from datetime import datetime, timedelta

import pytest

import server


class Res:
    def __init__(self, n):
        self.deleted_count = n


class Coll:
    def __init__(self, docs=None):
        self.docs = docs or []

    async def find_one(self, q):
        rx = q.get("email", {}).get("$regex")
        return next((d for d in self.docs if rx and re.match(rx, d["email"], re.I)), None)

    async def delete_many(self, q):
        keep, n = [], 0
        for d in self.docs:
            if d["user_id"] == q["user_id"] and d["created_at"] >= q["created_at"]["$gte"]:
                n += 1
            else:
                keep.append(d)
        self.docs = keep
        return Res(n)

    async def insert_one(self, d):
        self.docs.append(d)


@pytest.fixture
def db(monkeypatch):
    now = datetime.utcnow()
    last_month = now.replace(day=1) - timedelta(days=2)
    ev = lambda when: {"user_id": "u1", "created_at": when}
    d = type("DB", (), {})()
    d.profiles = Coll([{"id": "u1", "email": "Member@Example.com"}])
    d.generation_events = Coll([ev(now), ev(now), ev(now), ev(last_month)])
    d.meal_generation_events = Coll([ev(now)] * 4)
    d.snap_usage = Coll([ev(now - timedelta(hours=1))] * 15)
    d.body_usage = Coll([ev(now - timedelta(hours=1))] * 3)
    d.workouts = Coll([{"user_id": "u1", "created_at": now}])
    d.admin_actions = Coll()
    monkeypatch.setattr(server, "db", d)
    monkeypatch.setenv("ADMIN_EMAILS", "boss@interfitai.com")
    return d


def req(what="all", admin="boss@interfitai.com", email="member@example.com"):
    return server.ResetLimitsRequest(admin_email=admin, user_email=email, what=what)


def test_only_admins(db):
    with pytest.raises(server.HTTPException) as e:
        asyncio.run(server.reset_user_limits(req(admin="someone@else.com")))
    assert e.value.status_code == 403


def test_unknown_member(db):
    with pytest.raises(server.HTTPException) as e:
        asyncio.run(server.reset_user_limits(req(email="nobody@example.com")))
    assert e.value.status_code == 404


def test_reset_programs_only_this_month(db):
    r = asyncio.run(server.reset_user_limits(req("programs")))
    assert r["cleared"] == {"programs": 3}
    assert len(db.generation_events.docs) == 1          # last month's stays (history)
    assert len(db.meal_generation_events.docs) == 4      # untouched
    assert len(db.workouts.docs) == 1                    # their programs are kept


def test_reset_everything_and_logged(db):
    r = asyncio.run(server.reset_user_limits(req("all")))
    assert r["cleared"] == {"programs": 3, "meal_plans": 4, "snap_photos": 15, "body_analyses": 3}
    log = db.admin_actions.docs[0]
    assert log["action"] == "reset_limits" and log["admin_email"] == "boss@interfitai.com"
    assert log["user_email"] == "member@example.com"

"""
Tests for Spec 2 — Monthly program generation quota.

Covers:
  - Under-limit: generation succeeds and event is recorded
  - At-limit: 4th generation returns 403 generation_limit
  - Admin bypass: admin email is never blocked
  - Exercise edits don't consume quota (PATCH /workout/{id}/exercise)
  - GET /workouts/generation-quota/{user_id} returns correct counts
"""
import pytest
import httpx
import uuid
from datetime import datetime

BASE_URL = "http://localhost:8001/api"
ADMIN_EMAIL = "sebastianrush5@gmail.com"

GENERATE_PAYLOAD = {
    "goal": "build_muscle",
    "fitness_level": "intermediate",
    "days_per_week": 4,
    "duration_minutes": 45,
    "equipment": ["barbell", "dumbbell"],
    "focus_areas": ["chest", "back"],
    "preferred_split": "push_pull_legs",
}


def new_user():
    uid = f"test_quota_{uuid.uuid4().hex[:8]}"
    email = f"{uid}@test.com"
    return uid, email


async def create_profile(client, user_id, email):
    await client.put(f"{BASE_URL}/profile/{user_id}", json={
        "name": "Quota Tester",
        "email": email,
        "goal": "build_muscle",
        "age": 28,
        "weight": 80,
        "height": 178,
    })


async def generate(client, user_id):
    return await client.post(
        f"{BASE_URL}/workouts/generate",
        json={"user_id": user_id, **GENERATE_PAYLOAD},
        timeout=120,
    )


# ── Under-limit: first 3 generations succeed ─────────────────────────────────

@pytest.mark.asyncio
async def test_under_limit_success():
    """First generation for a new user succeeds (used=0, limit=3)."""
    async with httpx.AsyncClient(timeout=120) as client:
        uid, email = new_user()
        await create_profile(client, uid, email)

        r = await generate(client, uid)
        assert r.status_code == 200, r.text

        # Quota should now show used=1
        q = await client.get(f"{BASE_URL}/workouts/generation-quota/{uid}")
        assert q.status_code == 200
        data = q.json()
        assert data["used"] == 1
        assert data["limit"] == 3
        assert data["remaining"] == 2
        assert data["is_admin"] is False


@pytest.mark.asyncio
async def test_three_generations_allowed():
    """Three generations all succeed."""
    async with httpx.AsyncClient(timeout=360) as client:
        uid, email = new_user()
        await create_profile(client, uid, email)

        for i in range(3):
            r = await generate(client, uid)
            assert r.status_code == 200, f"Generation {i+1} failed: {r.text}"

        q = await client.get(f"{BASE_URL}/workouts/generation-quota/{uid}")
        assert q.json()["used"] == 3
        assert q.json()["remaining"] == 0


# ── At-limit: 4th generation is blocked ───────────────────────────────────────

@pytest.mark.asyncio
async def test_at_limit_returns_403():
    """4th generation returns 403 with generation_limit error."""
    async with httpx.AsyncClient(timeout=480) as client:
        uid, email = new_user()
        await create_profile(client, uid, email)

        for _ in range(3):
            r = await generate(client, uid)
            assert r.status_code == 200

        r4 = await generate(client, uid)
        assert r4.status_code == 403
        detail = r4.json().get("detail", {})
        assert detail.get("error") == "generation_limit"
        assert "reset_date" in detail
        assert detail.get("used") == 3
        assert detail.get("limit") == 3
        assert "consistency beats" in detail.get("message", "").lower() or "reset" in detail.get("message", "").lower()


# ── Admin bypass ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_bypass_no_limit():
    """Admin email is never blocked, even after 3 generations."""
    async with httpx.AsyncClient(timeout=480) as client:
        uid = f"test_admin_{uuid.uuid4().hex[:8]}"
        await create_profile(client, uid, ADMIN_EMAIL)

        # Admin should succeed regardless of count
        for i in range(4):
            r = await generate(client, uid)
            assert r.status_code == 200, f"Admin generation {i+1} blocked: {r.text}"

        q = await client.get(f"{BASE_URL}/workouts/generation-quota/{uid}")
        assert q.json()["is_admin"] is True
        assert q.json()["limit"] is None


# ── Editing doesn't consume quota ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_exercise_edit_does_not_consume_quota():
    """Editing an exercise via PATCH does not increment generation_events."""
    async with httpx.AsyncClient(timeout=120) as client:
        uid, email = new_user()
        await create_profile(client, uid, email)

        # Generate once
        r = await generate(client, uid)
        assert r.status_code == 200
        workout_id = r.json()["id"]

        # Quota is 1 after generation
        q_before = await client.get(f"{BASE_URL}/workouts/generation-quota/{uid}")
        used_before = q_before.json()["used"]
        assert used_before == 1

        # Edit an exercise (PATCH)
        patch_r = await client.patch(f"{BASE_URL}/workout/{workout_id}/exercise", json={
            "day_index": 0,
            "exercise_index": 0,
            "sets": 4,
        })
        assert patch_r.status_code == 200

        # Quota should still be 1
        q_after = await client.get(f"{BASE_URL}/workouts/generation-quota/{uid}")
        assert q_after.json()["used"] == used_before, "Exercise edit must not consume quota"


# ── Quota endpoint ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_quota_endpoint_fresh_user():
    """New user has used=0, remaining=3."""
    async with httpx.AsyncClient(timeout=30) as client:
        uid, email = new_user()
        await create_profile(client, uid, email)

        q = await client.get(f"{BASE_URL}/workouts/generation-quota/{uid}")
        assert q.status_code == 200
        data = q.json()
        assert data["used"] == 0
        assert data["remaining"] == 3
        assert data["is_admin"] is False
        assert "reset_date" in data

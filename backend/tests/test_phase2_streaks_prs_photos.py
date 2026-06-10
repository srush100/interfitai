"""
Phase 2 tests — Streaks, Personal Records, Photos
Tests for:
  - GET /api/workout/stats/{user_id}
  - PR detection in POST /api/workout/{workout_id}/session/complete
  - POST /api/workout/session/{session_id}/photo
  - GET /api/workout/personal-records/{user_id}
"""
import pytest
import httpx
import asyncio
import uuid
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8001/api"

# ── Helpers ────────────────────────────────────────────────────────────────────

def make_user_id():
    return f"test_user_{uuid.uuid4().hex[:8]}"

def make_workout_id():
    return f"test_workout_{uuid.uuid4().hex[:8]}"

async def create_test_profile(client: httpx.AsyncClient, user_id: str):
    await client.put(f"{BASE_URL}/profile/{user_id}", json={
        "name": "Phase2 Tester",
        "email": f"{user_id}@test.com",
        "goal": "build_muscle",
        "age": 28,
        "weight": 80,
        "height": 178,
    })

async def create_test_workout(client: httpx.AsyncClient, user_id: str, workout_id: str):
    """Insert a minimal workout document into the DB."""
    # Use generate endpoint to create a real workout
    r = await client.post(f"{BASE_URL}/workouts/generate", json={
        "user_id": user_id,
        "goal": "build_muscle",
        "fitness_level": "intermediate",
        "days_per_week": 4,
        "duration_minutes": 45,
        "equipment": ["barbell", "dumbbell"],
        "focus_areas": ["chest", "back"],
    })
    assert r.status_code == 200, f"Workout gen failed: {r.text}"
    return r.json()["id"]

async def complete_session(
    client: httpx.AsyncClient,
    workout_id: str,
    user_id: str,
    exercises: list,
    day_index: int = 0,
):
    r = await client.post(f"{BASE_URL}/workout/{workout_id}/session/complete", json={
        "user_id": user_id,
        "day_index": day_index,
        "day_focus": "push",
        "duration_minutes": 45,
        "completed_exercises": exercises,
    })
    assert r.status_code == 200, f"Complete failed: {r.text}"
    return r.json()

def bench_exercise(weight: float, reps: int, completed: bool = True):
    return {
        "exercise_name": "Bench Press",
        "muscle_groups": ["chest"],
        "sets": [{"set_number": 1, "weight": weight, "reps": reps, "completed": completed}],
    }

# ── Stats + Streak Tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stats_no_sessions():
    """Empty stats for a user with no sessions."""
    async with httpx.AsyncClient(timeout=30) as client:
        user_id = make_user_id()
        r = await client.get(f"{BASE_URL}/workout/stats/{user_id}")
        assert r.status_code == 200
        d = r.json()
        assert d["current_streak"] == 0
        assert d["best_streak"] == 0
        assert d["sessions_this_week"] == 0
        assert d["total_sessions"] == 0
        assert d["weekly_target"] == 4  # default

@pytest.mark.asyncio
async def test_stats_single_session_today():
    """One session today → streak = 1."""
    async with httpx.AsyncClient(timeout=60) as client:
        user_id = make_user_id()
        await create_test_profile(client, user_id)
        wid = await create_test_workout(client, user_id, make_workout_id())
        await complete_session(client, wid, user_id, [bench_exercise(80, 10)])

        r = await client.get(f"{BASE_URL}/workout/stats/{user_id}")
        assert r.status_code == 200
        d = r.json()
        assert d["current_streak"] >= 1
        assert d["total_sessions"] == 1
        assert d["sessions_this_week"] >= 1

@pytest.mark.asyncio
async def test_stats_weekly_target_from_program():
    """weekly_target pulled from the user's latest workout program."""
    async with httpx.AsyncClient(timeout=60) as client:
        user_id = make_user_id()
        await create_test_profile(client, user_id)
        # Generate a 5-day/week program
        r = await client.post(f"{BASE_URL}/workouts/generate", json={
            "user_id": user_id,
            "goal": "build_muscle",
            "fitness_level": "intermediate",
            "days_per_week": 5,
            "duration_minutes": 45,
            "equipment": ["barbell"],
            "focus_areas": ["chest"],
        })
        assert r.status_code == 200

        stats = await client.get(f"{BASE_URL}/workout/stats/{user_id}")
        assert stats.json()["weekly_target"] == 5

# ── PR Detection Tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pr_detection_weight():
    """Second session with higher weight → weight PR returned."""
    async with httpx.AsyncClient(timeout=60) as client:
        user_id = make_user_id()
        await create_test_profile(client, user_id)
        wid = await create_test_workout(client, user_id, make_workout_id())

        # First session — 80 kg × 10
        await complete_session(client, wid, user_id, [bench_exercise(80, 10)])

        # Second session — 85 kg × 8 (weight PR)
        result = await complete_session(client, wid, user_id, [bench_exercise(85, 8)])
        prs = result.get("personal_records", [])
        assert len(prs) == 1
        assert prs[0]["exercise_name"] == "Bench Press"
        assert prs[0]["type"] == "weight"
        assert prs[0]["new_value"] == 85.0
        assert prs[0]["previous_value"] == 80.0

@pytest.mark.asyncio
async def test_pr_detection_reps():
    """Same weight but more reps → reps PR."""
    async with httpx.AsyncClient(timeout=60) as client:
        user_id = make_user_id()
        await create_test_profile(client, user_id)
        wid = await create_test_workout(client, user_id, make_workout_id())

        await complete_session(client, wid, user_id, [bench_exercise(80, 10)])
        result = await complete_session(client, wid, user_id, [bench_exercise(80, 12)])
        prs = result.get("personal_records", [])
        assert len(prs) == 1
        assert prs[0]["type"] == "reps"
        assert prs[0]["new_value"] == 12
        assert prs[0]["previous_value"] == 10

@pytest.mark.asyncio
async def test_no_pr_lower_weight():
    """Lower weight → no PR."""
    async with httpx.AsyncClient(timeout=60) as client:
        user_id = make_user_id()
        await create_test_profile(client, user_id)
        wid = await create_test_workout(client, user_id, make_workout_id())

        await complete_session(client, wid, user_id, [bench_exercise(80, 10)])
        result = await complete_session(client, wid, user_id, [bench_exercise(75, 10)])
        assert result.get("personal_records", []) == []

@pytest.mark.asyncio
async def test_first_session_no_pr():
    """First-ever session for an exercise → no PR (nothing to beat)."""
    async with httpx.AsyncClient(timeout=60) as client:
        user_id = make_user_id()
        await create_test_profile(client, user_id)
        wid = await create_test_workout(client, user_id, make_workout_id())

        result = await complete_session(client, wid, user_id, [bench_exercise(80, 10)])
        # No prior sessions, so no PR
        assert result.get("personal_records", []) == []

@pytest.mark.asyncio
async def test_multiple_prs_in_one_session():
    """Multiple exercises with PRs in the same session."""
    async with httpx.AsyncClient(timeout=60) as client:
        user_id = make_user_id()
        await create_test_profile(client, user_id)
        wid = await create_test_workout(client, user_id, make_workout_id())

        squat = {
            "exercise_name": "Squat",
            "muscle_groups": ["legs"],
            "sets": [{"set_number": 1, "weight": 100, "reps": 5, "completed": True}],
        }
        # First session
        await complete_session(client, wid, user_id, [bench_exercise(80, 10), squat])
        # Second session — both are PRs
        squat2 = {
            "exercise_name": "Squat",
            "muscle_groups": ["legs"],
            "sets": [{"set_number": 1, "weight": 110, "reps": 5, "completed": True}],
        }
        result = await complete_session(client, wid, user_id, [bench_exercise(85, 8), squat2])
        prs = result.get("personal_records", [])
        assert len(prs) == 2

# ── Photo Tests ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_session_photo():
    """Add a photo to a completed session."""
    async with httpx.AsyncClient(timeout=60) as client:
        user_id = make_user_id()
        await create_test_profile(client, user_id)
        wid = await create_test_workout(client, user_id, make_workout_id())

        session = await complete_session(client, wid, user_id, [bench_exercise(80, 10)])
        session_id = session["id"]

        r = await client.post(f"{BASE_URL}/workout/session/{session_id}/photo", json={
            "photo_base64": "aGVsbG8gd29ybGQ="  # base64("hello world")
        })
        assert r.status_code == 200
        assert r.json()["session_id"] == session_id

@pytest.mark.asyncio
async def test_add_photo_not_found():
    """Photo endpoint returns 404 for unknown session_id."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/workout/session/nonexistent-id/photo", json={
            "photo_base64": "aGVsbG8="
        })
        assert r.status_code == 404

@pytest.mark.asyncio
async def test_update_session_photo():
    """Updating a photo replaces the old one."""
    async with httpx.AsyncClient(timeout=60) as client:
        user_id = make_user_id()
        await create_test_profile(client, user_id)
        wid = await create_test_workout(client, user_id, make_workout_id())
        session = await complete_session(client, wid, user_id, [bench_exercise(80, 10)])
        session_id = session["id"]

        await client.post(f"{BASE_URL}/workout/session/{session_id}/photo", json={"photo_base64": "Zmlyc3Q="})
        r = await client.post(f"{BASE_URL}/workout/session/{session_id}/photo", json={"photo_base64": "c2Vjb25k"})
        assert r.status_code == 200

# ── Personal Records Endpoint ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_personal_records_endpoint():
    """GET /personal-records returns all-time bests per exercise."""
    async with httpx.AsyncClient(timeout=60) as client:
        user_id = make_user_id()
        await create_test_profile(client, user_id)
        wid = await create_test_workout(client, user_id, make_workout_id())

        await complete_session(client, wid, user_id, [bench_exercise(80, 10)])
        await complete_session(client, wid, user_id, [bench_exercise(85, 8)])

        r = await client.get(f"{BASE_URL}/workout/personal-records/{user_id}")
        assert r.status_code == 200
        records = r.json()
        bench_record = next((rec for rec in records if rec["exercise_name"] == "Bench Press"), None)
        assert bench_record is not None
        assert bench_record["best_weight"] == 85.0

@pytest.mark.asyncio
async def test_personal_records_empty():
    """New user → empty records list."""
    async with httpx.AsyncClient(timeout=30) as client:
        user_id = make_user_id()
        r = await client.get(f"{BASE_URL}/workout/personal-records/{user_id}")
        assert r.status_code == 200
        assert r.json() == []

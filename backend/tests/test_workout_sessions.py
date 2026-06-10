"""
Workout Session Tracking Tests - Phase 1
Tests for:
- POST /api/workout/{workout_id}/session/complete
- GET /api/workout/sessions/{user_id}
- GET /api/workout/{workout_id}/last-session?day_index=N
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')

# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def api():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def test_user_id():
    return "TEST_session_user_phase1"

@pytest.fixture(scope="module")
def test_workout(api):
    """Use an existing workout from the database for session tests"""
    # Use the known existing workout ID in the test DB
    EXISTING_WORKOUT_ID = "3da77f8d-557b-4dc4-9af8-612492855da2"
    resp = api.get(f"{BASE_URL}/api/workout/{EXISTING_WORKOUT_ID}", timeout=15)
    if resp.status_code != 200:
        pytest.skip(f"Could not load workout {EXISTING_WORKOUT_ID}: {resp.status_code}")
    return resp.json()

def make_session_payload(user_id: str) -> dict:
    """Helper: build a valid CompleteSessionRequest payload"""
    return {
        "user_id": user_id,
        "day_index": 0,
        "day_focus": "Chest & Triceps",
        "duration_minutes": 45,
        "completed_exercises": [
            {
                "exercise_name": "Dumbbell Bench Press",
                "muscle_groups": ["chest"],
                "sets": [
                    {"set_number": 1, "weight": 30.0, "reps": 10, "completed": True},
                    {"set_number": 2, "weight": 30.0, "reps": 10, "completed": True},
                    {"set_number": 3, "weight": 32.5, "reps": 8, "completed": True},
                ]
            },
            {
                "exercise_name": "Incline Dumbbell Press",
                "muscle_groups": ["chest", "shoulders"],
                "sets": [
                    {"set_number": 1, "weight": 25.0, "reps": 12, "completed": True},
                    {"set_number": 2, "weight": 25.0, "reps": 10, "completed": False},
                ]
            }
        ],
    }

# ─── Backend Health ────────────────────────────────────────────────────────────

class TestHealth:
    """Ensure backend is reachable"""

    def test_health_check(self, api):
        resp = api.get(f"{BASE_URL}/api/health", timeout=10)
        assert resp.status_code == 200, f"Health check failed: {resp.text}"
        print("PASS: Backend health check OK")

# ─── POST /api/workout/{id}/session/complete ─────────────────────────────────

class TestCompleteSession:
    """Tests for completing a workout session"""

    def test_complete_session_returns_200(self, api, test_workout, test_user_id):
        """POST session/complete returns 200 with session data"""
        wid = test_workout["id"]
        payload = make_session_payload(test_user_id)
        resp = api.post(f"{BASE_URL}/api/workout/{wid}/session/complete", json=payload, timeout=15)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "id" in data, "Response missing 'id' field"
        assert "total_volume" in data, "Response missing 'total_volume' field"
        assert "date" in data, "Response missing 'date' field"
        print(f"PASS: complete_session returns 200, id={data['id']}")

    def test_complete_session_total_volume_correct(self, api, test_workout, test_user_id):
        """total_volume = weight × reps for completed sets only"""
        wid = test_workout["id"]
        payload = {
            "user_id": test_user_id,
            "day_index": 0,
            "day_focus": "Test",
            "duration_minutes": 30,
            "completed_exercises": [
                {
                    "exercise_name": "Squat",
                    "muscle_groups": ["legs"],
                    "sets": [
                        {"set_number": 1, "weight": 100.0, "reps": 5, "completed": True},   # 500
                        {"set_number": 2, "weight": 100.0, "reps": 5, "completed": True},   # 500
                        {"set_number": 3, "weight": 90.0, "reps": 5, "completed": False},   # 0 (not completed)
                    ]
                }
            ],
        }
        resp = api.post(f"{BASE_URL}/api/workout/{wid}/session/complete", json=payload, timeout=15)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        expected_volume = 1000.0  # 100*5 + 100*5 only (third set not completed)
        assert data["total_volume"] == expected_volume, \
            f"Volume incorrect: expected {expected_volume}, got {data['total_volume']}"
        print(f"PASS: total_volume correctly computed as {data['total_volume']}")

    def test_complete_session_zero_volume_when_no_weight(self, api, test_workout, test_user_id):
        """Sets without weight should contribute 0 to total_volume"""
        wid = test_workout["id"]
        payload = {
            "user_id": test_user_id,
            "day_index": 1,
            "day_focus": "Bodyweight",
            "completed_exercises": [
                {
                    "exercise_name": "Push-Up",
                    "muscle_groups": ["chest"],
                    "sets": [
                        {"set_number": 1, "weight": None, "reps": 15, "completed": True},
                        {"set_number": 2, "weight": None, "reps": 12, "completed": True},
                    ]
                }
            ],
        }
        resp = api.post(f"{BASE_URL}/api/workout/{wid}/session/complete", json=payload, timeout=15)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["total_volume"] == 0.0, \
            f"Expected 0 volume for no-weight exercises, got {data['total_volume']}"
        print(f"PASS: Zero volume for bodyweight exercises")

    def test_complete_session_creates_new_document(self, api, test_workout, test_user_id):
        """Each call creates a NEW document (no overwriting)"""
        wid = test_workout["id"]
        payload = make_session_payload(test_user_id)

        resp1 = api.post(f"{BASE_URL}/api/workout/{wid}/session/complete", json=payload, timeout=15)
        resp2 = api.post(f"{BASE_URL}/api/workout/{wid}/session/complete", json=payload, timeout=15)

        assert resp1.status_code == 200, f"First call failed: {resp1.status_code}"
        assert resp2.status_code == 200, f"Second call failed: {resp2.status_code}"

        id1 = resp1.json().get("id")
        id2 = resp2.json().get("id")
        assert id1 != id2, f"Both calls returned same id={id1}. Sessions are being overwritten!"
        print(f"PASS: Two sessions created with distinct ids: {id1} vs {id2}")

    def test_complete_session_invalid_workout_returns_404(self, api, test_user_id):
        """Non-existent workout_id returns 404"""
        resp = api.post(
            f"{BASE_URL}/api/workout/nonexistent-workout-id/session/complete",
            json=make_session_payload(test_user_id),
            timeout=15,
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        print("PASS: 404 returned for invalid workout_id")

# ─── GET /api/workout/sessions/{user_id} ─────────────────────────────────────

class TestGetUserSessions:
    """Tests for listing user sessions"""

    def test_get_sessions_returns_array(self, api, test_workout, test_user_id):
        """GET sessions/{user_id} returns an array"""
        resp = api.get(f"{BASE_URL}/api/workout/sessions/{test_user_id}", timeout=15)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASS: get_sessions returns list with {len(data)} sessions")

    def test_get_sessions_sorted_desc_by_date(self, api, test_workout, test_user_id):
        """Sessions are sorted by date descending (most recent first)"""
        # Ensure at least 2 sessions exist (created by earlier tests)
        resp = api.get(f"{BASE_URL}/api/workout/sessions/{test_user_id}", timeout=15)
        assert resp.status_code == 200
        sessions = resp.json()
        if len(sessions) < 2:
            pytest.skip("Not enough sessions to verify sort order")
        dates = [s["date"] for s in sessions]
        assert dates == sorted(dates, reverse=True), \
            f"Sessions not sorted desc: {dates}"
        print("PASS: Sessions sorted by date descending")

    def test_get_sessions_limit_param(self, api, test_workout, test_user_id):
        """?limit= param limits the number of returned sessions"""
        resp = api.get(f"{BASE_URL}/api/workout/sessions/{test_user_id}?limit=2", timeout=15)
        assert resp.status_code == 200
        sessions = resp.json()
        assert len(sessions) <= 2, f"Expected ≤2 sessions, got {len(sessions)}"
        print(f"PASS: limit=2 returned {len(sessions)} sessions")

    def test_get_sessions_workout_id_filter(self, api, test_workout, test_user_id):
        """?workout_id= filters by specific workout"""
        wid = test_workout["id"]
        resp = api.get(
            f"{BASE_URL}/api/workout/sessions/{test_user_id}?workout_id={wid}",
            timeout=15,
        )
        assert resp.status_code == 200
        sessions = resp.json()
        assert isinstance(sessions, list), "Expected list"
        for s in sessions:
            assert s["workout_id"] == wid, f"Session has wrong workout_id: {s['workout_id']}"
        print(f"PASS: workout_id filter returns {len(sessions)} sessions, all matching")

    def test_get_sessions_empty_for_unknown_user(self, api):
        """Unknown user_id returns empty list"""
        resp = api.get(f"{BASE_URL}/api/workout/sessions/unknown-user-xyz-000", timeout=15)
        assert resp.status_code == 200
        assert resp.json() == [], f"Expected empty list, got {resp.json()}"
        print("PASS: Unknown user returns empty array")

    def test_get_sessions_multiple_sessions_reverse_chron(self, api, test_workout, test_user_id):
        """After multiple completions, sessions appear in reverse chronological order"""
        wid = test_workout["id"]
        payload = make_session_payload(test_user_id)

        # Complete workout twice more
        resp1 = api.post(f"{BASE_URL}/api/workout/{wid}/session/complete", json=payload, timeout=15)
        resp2 = api.post(f"{BASE_URL}/api/workout/{wid}/session/complete", json=payload, timeout=15)
        assert resp1.status_code == 200 and resp2.status_code == 200

        # Fetch and check ordering
        resp = api.get(f"{BASE_URL}/api/workout/sessions/{test_user_id}", timeout=15)
        sessions = resp.json()
        assert len(sessions) >= 2, f"Expected ≥2 sessions, got {len(sessions)}"
        dates = [s["date"] for s in sessions]
        assert dates == sorted(dates, reverse=True), "Sessions not in reverse chron order"
        print(f"PASS: {len(sessions)} sessions in reverse chronological order")

# ─── GET /api/workout/{id}/last-session ──────────────────────────────────────

class TestLastSession:
    """Tests for last session endpoint"""

    def test_last_session_returns_null_when_none(self, api, test_user_id):
        """Returns null when no session exists for that workout+day combination"""
        fake_wid = f"test-nonexistent-{uuid.uuid4().hex[:8]}"
        resp = api.get(f"{BASE_URL}/api/workout/{fake_wid}/last-session?day_index=0", timeout=15)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data is None, f"Expected null, got: {data}"
        print("PASS: last-session returns null when no session exists")

    def test_last_session_returns_session_when_exists(self, api, test_workout, test_user_id):
        """Returns the most recent session when one exists"""
        wid = test_workout["id"]
        payload = make_session_payload(test_user_id)

        # Post a session so we know one exists
        post_resp = api.post(f"{BASE_URL}/api/workout/{wid}/session/complete", json=payload, timeout=15)
        assert post_resp.status_code == 200, f"Failed to create session: {post_resp.text}"

        # Now fetch last session
        resp = api.get(f"{BASE_URL}/api/workout/{wid}/last-session?day_index=0", timeout=15)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data is not None, "Expected a session object, got null"
        assert data["workout_id"] == wid
        assert data["day_index"] == 0
        assert "completed_exercises" in data
        assert "_id" not in data, "MongoDB _id should not be in response"
        print(f"PASS: last-session returns session for workout {wid} day 0")

    def test_last_session_day_index_filter(self, api, test_workout, test_user_id):
        """day_index=1 returns None if no session for day 1, even if day 0 has sessions"""
        wid = test_workout["id"]
        # Post a day=0 session
        payload = make_session_payload(test_user_id)  # day_index=0
        api.post(f"{BASE_URL}/api/workout/{wid}/session/complete", json=payload, timeout=15)

        # Check day_index=99 (unlikely to exist)
        resp = api.get(f"{BASE_URL}/api/workout/{wid}/last-session?day_index=99", timeout=15)
        assert resp.status_code == 200
        data = resp.json()
        assert data is None, f"Expected null for day_index=99, got {data}"
        print("PASS: last-session correctly filters by day_index")

    def test_last_session_returns_most_recent(self, api, test_workout, test_user_id):
        """Returns the most recent session (not the first)"""
        wid = test_workout["id"]

        # Post two sessions with different volumes to differentiate
        payload1 = {
            "user_id": test_user_id,
            "day_index": 0,
            "day_focus": "Day Zero",
            "completed_exercises": [
                {"exercise_name": "Curl", "muscle_groups": ["biceps"],
                 "sets": [{"set_number": 1, "weight": 10.0, "reps": 10, "completed": True}]}
            ]
        }
        payload2 = {
            "user_id": test_user_id,
            "day_index": 0,
            "day_focus": "Day Zero Updated",
            "completed_exercises": [
                {"exercise_name": "Curl", "muscle_groups": ["biceps"],
                 "sets": [{"set_number": 1, "weight": 20.0, "reps": 10, "completed": True}]}
            ]
        }
        api.post(f"{BASE_URL}/api/workout/{wid}/session/complete", json=payload1, timeout=15)
        api.post(f"{BASE_URL}/api/workout/{wid}/session/complete", json=payload2, timeout=15)

        resp = api.get(f"{BASE_URL}/api/workout/{wid}/last-session?day_index=0", timeout=15)
        data = resp.json()
        assert data is not None, "Expected session, got null"
        # The most recent session should have total_volume = 200 (20*10)
        assert data["total_volume"] == 200.0, \
            f"Expected most recent session (volume=200), got volume={data['total_volume']}"
        print(f"PASS: last-session returns most recent session (volume={data['total_volume']})")

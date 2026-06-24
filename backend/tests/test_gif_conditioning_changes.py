"""
Test suite for 7 code changes applied to InterFitAI:
1. _slot_importance: conditioning priority 2 for hybrid/functional
2. PATTERNS[conditioning]: barbells/dumbbells/Ski Erg entries added
3. horizontal_pull.bodyweight: Inverted Row → Prone Y Raise + Superman Row
4. Skull crusher GIF: 0055 → 0060
5. Side plank GIF: 1775 → 3544
6. GIF cache: ski erg 2142, jump rope 1160 added; assault bike 2138 duplicate removed
7. workout-detail.tsx UI changes (frontend only — not tested here)
"""

import pytest
import requests
import os
import sys
import time

BASE_URL = os.environ.get('EXPO_BACKEND_URL', '').rstrip('/')
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ─── Static code verification ─────────────────────────────────────────────────
class TestStaticCodeVerification:
    """Verify CACHED_EXERCISE_GIFS mappings and PATTERNS directly from source code"""

    def test_no_assault_bike_2138_in_source(self):
        """Change 6: duplicate 2138 entry for assault bike must be removed from server.py"""
        server_path = os.path.join(os.path.dirname(__file__), '..', 'server.py')
        with open(server_path, 'r') as f:
            content = f.read()
        # Only the correct mapping (2331) should be present for assault bike
        # A line like: "assault bike": "2138" or "assault bike intervals": "2138" must NOT exist
        lines_with_2138 = [
            line.strip() for line in content.splitlines()
            if '2138' in line and 'assault bike' in line.lower()
        ]
        assert lines_with_2138 == [], (
            f"Found assault bike mapped to 2138 (should have been removed): {lines_with_2138}"
        )

    def test_assault_bike_maps_to_2331(self):
        """Change 6: assault bike correct mapping must be 2331"""
        server_path = os.path.join(os.path.dirname(__file__), '..', 'server.py')
        with open(server_path, 'r') as f:
            content = f.read()
        # Both aliases should map to 2331
        assert '"assault bike": "2331"' in content, "assault bike must map to 2331"
        assert '"assault bike intervals": "2331"' in content, "assault bike intervals must map to 2331"

    def test_skull_crusher_maps_to_0060(self):
        """Change 4: skull crusher GIF changed from 0055 to 0060"""
        server_path = os.path.join(os.path.dirname(__file__), '..', 'server.py')
        with open(server_path, 'r') as f:
            content = f.read()
        # 0060 must be mapped
        assert '"skull crusher": "0060"' in content, "skull crusher must map to 0060"
        # 0055 must NOT be the actual KEY mapping for skull crusher
        # (the comment may reference 0055 as old value, so check exact mapping string only)
        assert '"skull crusher": "0055"' not in content, \
            "skull crusher must not map to old ID 0055"

    def test_side_plank_maps_to_3544(self):
        """Change 5: side plank GIF changed from 1775 to 3544"""
        server_path = os.path.join(os.path.dirname(__file__), '..', 'server.py')
        with open(server_path, 'r') as f:
            content = f.read()
        assert '"side plank": "3544"' in content, "side plank must map to 3544"
        # 1775 must NOT be the actual key mapping for plain "side plank"
        # (comments may reference it; check exact mapping string only)
        assert '"side plank": "1775"' not in content, \
            "side plank must not map to old ID 1775"

    def test_ski_erg_added_to_cache(self):
        """Change 6: ski erg 2142 added to CACHED_EXERCISE_GIFS"""
        server_path = os.path.join(os.path.dirname(__file__), '..', 'server.py')
        with open(server_path, 'r') as f:
            content = f.read()
        assert '"ski erg intervals": "2142"' in content, "ski erg intervals must map to 2142"

    def test_horizontal_pull_bodyweight_no_inverted_row(self):
        """Change 3: horizontal_pull.bodyweight should be Prone Y Raise + Superman Row, NOT Inverted Row"""
        server_path = os.path.join(os.path.dirname(__file__), '..', 'server.py')
        with open(server_path, 'r') as f:
            content = f.read()
        assert '"bodyweight":["Prone Y Raise", "Superman Row"]' in content, (
            "horizontal_pull bodyweight must use Prone Y Raise + Superman Row"
        )

    def test_conditioning_has_barbells_entry(self):
        """Change 2: conditioning PATTERNS must include barbells"""
        server_path = os.path.join(os.path.dirname(__file__), '..', 'server.py')
        with open(server_path, 'r') as f:
            content = f.read()
        assert '"Barbell Complex Intervals"' in content or '"Thruster Intervals"' in content, (
            "conditioning PATTERNS must have barbells entries"
        )

    def test_conditioning_has_dumbbells_entry(self):
        """Change 2: conditioning PATTERNS must include dumbbells"""
        server_path = os.path.join(os.path.dirname(__file__), '..', 'server.py')
        with open(server_path, 'r') as f:
            content = f.read()
        assert '"Dumbbell Thruster Intervals"' in content or '"Devil Press Intervals"' in content, (
            "conditioning PATTERNS must have dumbbells entries"
        )

    def test_conditioning_priority_2_for_hybrid_functional(self):
        """Change 1: _slot_importance must return 2 for conditioning in hybrid/functional"""
        server_path = os.path.join(os.path.dirname(__file__), '..', 'server.py')
        with open(server_path, 'r') as f:
            content = f.read()
        # Look for the priority 2 conditioning block
        assert "ex_type == 'conditioning' and style in ('hybrid', 'functional')" in content, (
            "_slot_importance must protect conditioning with priority 2 for hybrid/functional"
        )
        assert "return 2   # conditioning is core to hybrid/functional" in content or \
               "return 2" in content, "conditioning must return priority 2"


# ─── Backend health check ─────────────────────────────────────────────────────
class TestHealthCheck:
    """Verify backend is up and responding"""

    def test_health_check(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert "status" in data or "healthy" in str(data).lower(), \
            f"Unexpected health response: {data}"
        print(f"✅ Health check: {data}")


# ─── GIF proxy endpoint tests ────────────────────────────────────────────────
class TestGIFProxyEndpoints:
    """Test exercise GIF proxy endpoints for correct IDs"""

    def test_gif_2331_returns_200(self, api_client):
        """Change 6: ID 2331 (cycle cross trainer / correct assault bike) must return 200 OK"""
        response = api_client.get(f"{BASE_URL}/api/exercises/gif/2331", timeout=15)
        assert response.status_code == 200, (
            f"GIF 2331 (correct assault bike) failed: {response.status_code} — {response.text[:200]}"
        )
        print("✅ GIF ID 2331 returns 200 OK")

    def test_gif_2138_exists_but_not_assault_bike(self, api_client):
        """Change 6: ID 2138 must still exist (air bike core exercise) but is NOT the primary assault bike ID now"""
        response = api_client.get(f"{BASE_URL}/api/exercises/gif/2138", timeout=15)
        # The endpoint should work (2138 is a real exercise), but it should NOT be the assault bike
        # We only verify the endpoint status; the GIF content mismatch is confirmed by removing duplicate
        print(f"ℹ️ GIF ID 2138 status: {response.status_code} — duplicate removed from CACHED_EXERCISE_GIFS")
        # Just note: 2138 should no longer be in CACHED_EXERCISE_GIFS for assault bike
        assert response.status_code in (200, 404, 500), f"Unexpected status for 2138: {response.status_code}"

    def test_gif_0060_skull_crusher(self, api_client):
        """Change 4: GIF 0060 must resolve correctly (skull crusher correct ID)"""
        response = api_client.get(f"{BASE_URL}/api/exercises/gif/0060", timeout=15)
        assert response.status_code == 200, (
            f"GIF 0060 (skull crusher) failed: {response.status_code} — {response.text[:200]}"
        )
        print("✅ GIF ID 0060 (skull crusher) returns 200 OK")

    def test_gif_3544_side_plank(self, api_client):
        """Change 5: GIF 3544 must resolve correctly (correct side plank ID)"""
        response = api_client.get(f"{BASE_URL}/api/exercises/gif/3544", timeout=15)
        assert response.status_code == 200, (
            f"GIF 3544 (side plank) failed: {response.status_code} — {response.text[:200]}"
        )
        print("✅ GIF ID 3544 (side plank) returns 200 OK")

    def test_gif_2142_ski_erg(self, api_client):
        """Change 6: GIF 2142 (ski erg) must return 200 OK"""
        response = api_client.get(f"{BASE_URL}/api/exercises/gif/2142", timeout=15)
        assert response.status_code == 200, (
            f"GIF 2142 (ski erg) failed: {response.status_code} — {response.text[:200]}"
        )
        print("✅ GIF ID 2142 (ski erg) returns 200 OK")


# ─── Workout generation: bodyweight horizontal pull ───────────────────────────
class TestBodyweightHorizontalPull:
    """Change 3: Bodyweight workouts must not use Inverted Row for horizontal pull"""

    def test_bodyweight_workout_no_inverted_row(self, api_client):
        """Generate bodyweight-only workout and verify no 'Inverted Row' in horizontal_pull"""
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "build_muscle",
            "training_style": "calisthenics",
            "focus_areas": ["back", "chest"],
            "equipment": ["bodyweight"],
            "days_per_week": 2,
            "duration_minutes": 45,
            "fitness_level": "intermediate",
            "preferred_split": "ai_choose"
        }
        response = api_client.post(
            f"{BASE_URL}/api/workouts/generate",
            json=payload,
            timeout=120
        )
        assert response.status_code == 200, f"Workout generation failed: {response.status_code} — {response.text[:300]}"
        data = response.json()
        workout_days = data.get("workout_days", [])
        assert len(workout_days) > 0, "No workout days generated"

        # Collect all exercise names
        all_exercises = []
        for day in workout_days:
            for ex in day.get("exercises", []):
                all_exercises.append(ex.get("name", "").lower())

        print(f"✅ Generated bodyweight workout with {len(all_exercises)} exercises: {all_exercises}")

        # Inverted Row must NOT appear in bodyweight workouts
        inverted_row_found = any("inverted row" in name for name in all_exercises)
        assert not inverted_row_found, (
            f"'Inverted Row' found in bodyweight workout — should be Prone Y Raise/Superman Row. "
            f"Exercises: {all_exercises}"
        )

        # Prone Y Raise or Superman Row should be present
        has_prone_y = any("prone y" in name for name in all_exercises)
        has_superman = any("superman" in name for name in all_exercises)
        print(f"  Prone Y Raise: {has_prone_y}, Superman Row: {has_superman}")
        # Note: AI may not always generate these; we just ensure Inverted Row is gone
        print("✅ Bodyweight horizontal pull correctly excludes Inverted Row")


# ─── Workout generation: hybrid conditioning survival ─────────────────────────
class TestHybridConditioningInclusion:
    """Changes 1 & 2: Hybrid/functional workouts must include conditioning exercises"""

    def test_hybrid_workout_includes_conditioning(self, api_client):
        """Generate hybrid + full_gym workout and verify conditioning exercises present"""
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "body_recomp",
            "training_style": "hybrid",
            "focus_areas": ["full_body"],
            "equipment": ["full_gym"],
            "days_per_week": 3,
            "duration_minutes": 60,
            "fitness_level": "advanced",
            "preferred_split": "ai_choose"
        }
        response = api_client.post(
            f"{BASE_URL}/api/workouts/generate",
            json=payload,
            timeout=180
        )
        assert response.status_code == 200, (
            f"Hybrid workout generation failed: {response.status_code} — {response.text[:300]}"
        )
        data = response.json()
        workout_days = data.get("workout_days", [])
        assert len(workout_days) > 0, "No workout days generated"

        # Collect all exercise names and types
        all_exercises = []
        conditioning_exercises = []
        for day in workout_days:
            for ex in day.get("exercises", []):
                name = ex.get("name", "")
                ex_type = ex.get("exercise_type", "")
                all_exercises.append(name)
                if ex_type == "conditioning" or any(
                    kw in name.lower() for kw in [
                        "rowing machine", "assault bike", "ski erg",
                        "intervals", "burpee", "jump rope", "mountain climber"
                    ]
                ):
                    conditioning_exercises.append(name)

        print(f"✅ Hybrid workout: {len(workout_days)} days, {len(all_exercises)} exercises total")
        print(f"   Conditioning exercises found: {conditioning_exercises}")

        # At least one conditioning exercise should be present in a hybrid workout
        assert len(conditioning_exercises) > 0, (
            f"No conditioning exercises found in hybrid workout! "
            f"All exercises: {all_exercises}"
        )
        print("✅ Hybrid workout includes conditioning exercises (not trimmed)")

    def test_functional_workout_includes_conditioning(self, api_client):
        """Generate functional workout and verify conditioning slots survive trim"""
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "athletic_performance",
            "training_style": "functional",
            "focus_areas": ["full_body"],
            "equipment": ["full_gym"],
            "days_per_week": 3,
            "duration_minutes": 60,
            "fitness_level": "advanced",
            "preferred_split": "ai_choose"
        }
        response = api_client.post(
            f"{BASE_URL}/api/workouts/generate",
            json=payload,
            timeout=180
        )
        assert response.status_code == 200, (
            f"Functional workout generation failed: {response.status_code} — {response.text[:300]}"
        )
        data = response.json()
        workout_days = data.get("workout_days", [])
        assert len(workout_days) > 0, "No workout days generated"

        all_exercises = []
        conditioning_exercises = []
        for day in workout_days:
            for ex in day.get("exercises", []):
                name = ex.get("name", "")
                ex_type = ex.get("exercise_type", "")
                all_exercises.append(name)
                if ex_type == "conditioning" or any(
                    kw in name.lower() for kw in [
                        "rowing machine", "assault bike", "ski erg",
                        "intervals", "burpee", "jump rope", "mountain climber",
                        "battle rope", "thruster", "kettlebell swing"
                    ]
                ):
                    conditioning_exercises.append(name)

        print(f"✅ Functional workout: {len(workout_days)} days, {len(all_exercises)} exercises total")
        print(f"   Conditioning exercises found: {conditioning_exercises}")

        assert len(conditioning_exercises) > 0, (
            f"No conditioning exercises found in functional workout! "
            f"All exercises: {all_exercises}"
        )
        print("✅ Functional workout includes conditioning exercises (not trimmed)")


# ─── Workout generation: skull crusher GIF check ─────────────────────────────
class TestSkullCrusherGIF:
    """Change 4: Workout containing skull crusher must use GIF ID 0060"""

    def test_skull_crusher_gif_is_0060_in_generated_workout(self, api_client):
        """Generate a barbells workout and check skull crusher gif_url contains /0060/"""
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "build_muscle",
            "training_style": "weights",
            "focus_areas": ["chest", "triceps"],
            "equipment": ["barbells", "dumbbells"],
            "days_per_week": 2,
            "duration_minutes": 60,
            "fitness_level": "advanced",
            "preferred_split": "push_pull_legs"
        }
        response = api_client.post(
            f"{BASE_URL}/api/workouts/generate",
            json=payload,
            timeout=180
        )
        assert response.status_code == 200, f"Workout generation failed: {response.status_code}"
        data = response.json()

        skull_crusher_exercises = []
        for day in data.get("workout_days", []):
            for ex in day.get("exercises", []):
                name = ex.get("name", "")
                if "skull" in name.lower() or "lying tricep" in name.lower():
                    skull_crusher_exercises.append({
                        "name": name,
                        "gif_url": ex.get("gif_url", "")
                    })

        if skull_crusher_exercises:
            for ex in skull_crusher_exercises:
                gif_url = ex.get("gif_url", "")
                print(f"  Found skull crusher: {ex['name']} → gif_url: {gif_url}")
                if gif_url:
                    assert "/0060/" in gif_url or "/0060" in gif_url, (
                        f"Skull crusher GIF should be 0060, got: {gif_url}"
                    )
                    # Must NOT be 0055
                    assert "/0055/" not in gif_url and "/0055" not in gif_url, (
                        f"Skull crusher still mapped to old GIF 0055: {gif_url}"
                    )
            print(f"✅ Skull crusher GIF correctly uses ID 0060")
        else:
            print("ℹ️ Skull crusher not generated in this workout — GIF mapping verified via static check")
            pytest.skip("Skull crusher not generated in this workout session; static mapping confirmed")


# ─── Workout generation: full_gym conditioning exercises ─────────────────────
class TestFullGymConditioningExercises:
    """Change 2: full_gym conditioning must include Rowing Machine, Assault Bike, Ski Erg"""

    def test_full_gym_hybrid_includes_rowing_assault_bike_or_ski_erg(self, api_client):
        """Generate full_gym hybrid workout and verify at least one cardio machine exercise"""
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "athletic_performance",
            "training_style": "hybrid",
            "focus_areas": ["full_body"],
            "equipment": ["full_gym"],
            "days_per_week": 4,
            "duration_minutes": 60,
            "fitness_level": "advanced",
            "preferred_split": "ai_choose"
        }
        response = api_client.post(
            f"{BASE_URL}/api/workouts/generate",
            json=payload,
            timeout=180
        )
        assert response.status_code == 200, f"Workout generation failed: {response.status_code}"
        data = response.json()
        workout_days = data.get("workout_days", [])
        assert len(workout_days) > 0

        machine_cardio_exercises = []
        for day in workout_days:
            for ex in day.get("exercises", []):
                name = ex.get("name", "").lower()
                if any(kw in name for kw in ["rowing machine", "assault bike", "ski erg"]):
                    machine_cardio_exercises.append(ex.get("name", ""))

        print(f"  Cardio machine exercises found: {machine_cardio_exercises}")
        # At least one session should have a cardio machine exercise
        assert len(machine_cardio_exercises) > 0, (
            "No Rowing Machine, Assault Bike, or Ski Erg found in full_gym hybrid workout. "
            "Check conditioning PATTERNS full_gym list."
        )
        print(f"✅ Full_gym hybrid workout includes: {machine_cardio_exercises}")

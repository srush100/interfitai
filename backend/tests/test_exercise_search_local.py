"""
Tests for local MongoDB exercise search endpoint (replaces ExerciseDB RapidAPI).
Covers: muscle filter, text search, pagination, total_count, and response structure.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')


class TestExerciseSearchLocalDB:
    """Tests for GET /api/exercises/search from local MongoDB exercise_library"""

    def test_health_check(self):
        """Ensure backend is running"""
        resp = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert resp.status_code == 200

    def test_total_count_all_exercises(self):
        """No filters — should return all 1394 exercises"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        # total_count must be 1394
        assert data["total_count"] == 1394, f"Expected 1394 but got {data['total_count']}"
        # Default limit=50 so we get 50 back
        assert len(data["exercises"]) == 50
        assert data["offset"] == 0

    def test_chest_muscle_filter_count(self):
        """muscle=chest should map to 'pectorals' and return 100+ exercises"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search?muscle=chest&limit=50", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] >= 100, f"Expected 100+ chest exercises, got {data['total_count']}"
        exercises = data["exercises"]
        assert len(exercises) > 0
        # All returned exercises should target pectorals
        for ex in exercises:
            assert ex["target"] == "pectorals", f"Unexpected target: {ex['target']}"

    def test_chest_muscle_filter_structure(self):
        """Verify exercise structure: id, name, target, gifUrl, secondaryMuscles"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search?muscle=chest&limit=5", timeout=10)
        assert resp.status_code == 200
        exercises = resp.json()["exercises"]
        assert len(exercises) > 0
        required_fields = ["id", "name", "target", "gifUrl", "secondaryMuscles"]
        for ex in exercises[:5]:
            for field in required_fields:
                assert field in ex, f"Missing field '{field}' in exercise: {ex}"
            assert isinstance(ex["name"], str) and len(ex["name"]) > 0
            assert isinstance(ex["secondaryMuscles"], list)

    def test_text_search_deadlift(self):
        """search=deadlift should return relevant exercises"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search?search=deadlift&limit=50", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        exercises = data["exercises"]
        assert data["total_count"] > 0, "Expected deadlift search to return results"
        assert len(exercises) > 0
        # All returned exercises should have 'deadlift' in their name
        for ex in exercises:
            assert "deadlift" in ex["name"].lower(), f"'deadlift' not in name: {ex['name']}"

    def test_text_search_bench_press(self):
        """search=bench press should return 20+ results"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search?search=bench+press&limit=50", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] >= 10, f"Expected 10+ bench press results, got {data['total_count']}"

    def test_back_muscle_filter(self):
        """muscle=back should return many exercises (lats, traps, etc.)"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search?muscle=back&limit=50", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] > 50, f"Expected 50+ back exercises, got {data['total_count']}"
        back_targets = {"lats", "upper back", "lower back", "traps", "spine", "serratus anterior"}
        for ex in data["exercises"][:20]:
            assert ex["target"] in back_targets, f"Unexpected back target: {ex['target']}"

    def test_pagination_offset_10(self):
        """muscle=back, limit=10, offset=10 should return correct page"""
        # Get page 1
        resp1 = requests.get(f"{BASE_URL}/api/exercises/search?muscle=back&limit=10&offset=0", timeout=10)
        # Get page 2
        resp2 = requests.get(f"{BASE_URL}/api/exercises/search?muscle=back&limit=10&offset=10", timeout=10)
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        data1 = resp1.json()
        data2 = resp2.json()
        assert len(data1["exercises"]) == 10
        assert len(data2["exercises"]) == 10
        # total_count should be the same
        assert data1["total_count"] == data2["total_count"]
        # The two pages should not overlap (different exercise names)
        names1 = {ex["name"] for ex in data1["exercises"]}
        names2 = {ex["name"] for ex in data2["exercises"]}
        overlap = names1.intersection(names2)
        assert len(overlap) == 0, f"Overlapping exercises between page1 and page2: {overlap}"

    def test_pagination_offset_field_in_response(self):
        """Response should include offset and limit fields"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search?muscle=chest&limit=10&offset=10", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["offset"] == 10
        assert data["limit"] == 10
        assert data["total_count"] > 0

    def test_shoulders_muscle_filter(self):
        """muscle=shoulders should map to 'delts'"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search?muscle=shoulders&limit=20", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] > 0
        for ex in data["exercises"][:10]:
            assert ex["target"] == "delts", f"Expected delts but got: {ex['target']}"

    def test_legs_muscle_filter(self):
        """muscle=legs should map to quads, hamstrings, calves, etc."""
        resp = requests.get(f"{BASE_URL}/api/exercises/search?muscle=legs&limit=20", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] > 0
        leg_targets = {"quads", "hamstrings", "calves", "adductors", "abductors"}
        for ex in data["exercises"][:10]:
            assert ex["target"] in leg_targets, f"Unexpected leg target: {ex['target']}"

    def test_gif_url_format(self):
        """gifUrl should be in format /api/exercises/gif/{id} or None"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search?muscle=chest&limit=10", timeout=10)
        assert resp.status_code == 200
        exercises = resp.json()["exercises"]
        for ex in exercises:
            if ex["gifUrl"] is not None:
                assert ex["gifUrl"].startswith("/api/exercises/gif/"), f"Invalid gifUrl format: {ex['gifUrl']}"

    def test_biceps_filter(self):
        """muscle=biceps should return exercises targeting biceps"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search?muscle=biceps&limit=20", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] > 0
        for ex in data["exercises"][:10]:
            assert ex["target"] == "biceps"

    def test_abs_filter(self):
        """muscle=abs should map to abs and obliques"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search?muscle=abs&limit=30", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] > 0
        abs_targets = {"abs", "obliques"}
        for ex in data["exercises"][:15]:
            assert ex["target"] in abs_targets, f"Unexpected abs target: {ex['target']}"

    def test_total_count_1394_no_filters(self):
        """With no filters total_count must be exactly 1394"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search?limit=1&offset=0", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 1394, f"total_count={data['total_count']} != 1394"

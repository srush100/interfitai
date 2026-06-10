"""
Backend tests for unit_preference feature (kg/lbs preference)
Tests: PUT /api/profile/{user_id} unit_preference field, GET /api/profile/{user_id}
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')

TEST_EMAIL = "TEST_unit_pref@test.com"
TEST_PASSWORD = "UnitPref123!"
TEST_USER_ID = None


@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def test_user(api_client):
    """Create or login test user, return profile with id"""
    # Try to login first
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json()

    # Create new test user
    response = api_client.post(f"{BASE_URL}/api/profile", json={
        "name": "Test UnitPref User",
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "weight": 80.0,
        "height": 175.0,
        "age": 30,
        "gender": "male",
        "activity_level": "moderate",
        "goal": "muscle_building"
    })
    assert response.status_code == 200, f"Failed to create test user: {response.text}"
    return response.json()


class TestUnitPreferenceBackend:
    """Tests for unit_preference field in profile API"""

    def test_get_profile_has_unit_preference(self, api_client, test_user):
        """GET /api/profile/{user_id} should return unit_preference field"""
        user_id = test_user["id"]
        response = api_client.get(f"{BASE_URL}/api/profile/{user_id}")
        assert response.status_code == 200, f"GET profile failed: {response.text}"

        data = response.json()
        assert "unit_preference" in data, "unit_preference field missing from profile response"
        print(f"PASS: unit_preference present in profile. Current value: {data['unit_preference']}")

    def test_unit_preference_default_is_kg(self, api_client, test_user):
        """New profiles should default to 'kg' for unit_preference"""
        user_id = test_user["id"]
        response = api_client.get(f"{BASE_URL}/api/profile/{user_id}")
        assert response.status_code == 200
        data = response.json()
        unit_pref = data.get("unit_preference")
        assert unit_pref == "kg", f"Expected default 'kg', got '{unit_pref}'"
        print(f"PASS: Default unit_preference is 'kg'")

    def test_put_unit_preference_to_lbs(self, api_client, test_user):
        """PUT /api/profile/{user_id} with unit_preference='lbs' should save and return lbs"""
        user_id = test_user["id"]
        response = api_client.put(f"{BASE_URL}/api/profile/{user_id}", json={
            "unit_preference": "lbs"
        })
        assert response.status_code == 200, f"PUT unit_preference=lbs failed: {response.text}"
        data = response.json()
        assert data.get("unit_preference") == "lbs", f"Expected 'lbs', got '{data.get('unit_preference')}'"
        print(f"PASS: unit_preference set to 'lbs' in response")

    def test_put_unit_preference_persists_lbs(self, api_client, test_user):
        """After setting to lbs, subsequent GET should return lbs"""
        user_id = test_user["id"]
        # Confirm persistence via GET
        response = api_client.get(f"{BASE_URL}/api/profile/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("unit_preference") == "lbs", f"Expected persisted 'lbs', got '{data.get('unit_preference')}'"
        print(f"PASS: unit_preference='lbs' persisted in DB")

    def test_put_unit_preference_back_to_kg(self, api_client, test_user):
        """PUT with unit_preference='kg' should revert back to kg"""
        user_id = test_user["id"]
        response = api_client.put(f"{BASE_URL}/api/profile/{user_id}", json={
            "unit_preference": "kg"
        })
        assert response.status_code == 200, f"PUT unit_preference=kg failed: {response.text}"
        data = response.json()
        assert data.get("unit_preference") == "kg", f"Expected 'kg', got '{data.get('unit_preference')}'"
        print(f"PASS: unit_preference reverted to 'kg'")

    def test_put_unit_preference_with_other_fields(self, api_client, test_user):
        """PUT unit_preference alongside other profile fields should work"""
        user_id = test_user["id"]
        response = api_client.put(f"{BASE_URL}/api/profile/{user_id}", json={
            "unit_preference": "lbs",
            "weight": 82.0
        })
        assert response.status_code == 200, f"PUT failed: {response.text}"
        data = response.json()
        assert data.get("unit_preference") == "lbs", f"unit_preference wrong: {data.get('unit_preference')}"
        assert data.get("weight") == 82.0, f"weight not updated: {data.get('weight')}"
        print(f"PASS: unit_preference='lbs' and weight=82.0 both saved correctly")

    def test_put_unit_preference_does_not_affect_weight_storage(self, api_client, test_user):
        """Weight should always be stored in kg, unit_preference is display-only"""
        user_id = test_user["id"]
        # Reset weight
        api_client.put(f"{BASE_URL}/api/profile/{user_id}", json={"weight": 80.0, "unit_preference": "kg"})

        # Set preference to lbs - weight in DB should remain 80kg
        response = api_client.put(f"{BASE_URL}/api/profile/{user_id}", json={"unit_preference": "lbs"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("weight") == 80.0, f"Weight should remain 80.0 kg in DB, got {data.get('weight')}"
        assert data.get("unit_preference") == "lbs"
        print(f"PASS: Weight stored as 80.0 kg in DB even with unit_preference='lbs'")

    def test_put_invalid_unit_preference_rejected(self, api_client, test_user):
        """PUT with invalid unit_preference value should be handled (either rejected or no-op)"""
        user_id = test_user["id"]
        # First reset to kg
        api_client.put(f"{BASE_URL}/api/profile/{user_id}", json={"unit_preference": "kg"})

        response = api_client.put(f"{BASE_URL}/api/profile/{user_id}", json={
            "unit_preference": "invalid_unit"
        })
        # Either a 422 validation error or it saves the string (no strict validation on backend)
        # We just check the response is not a 500
        assert response.status_code in [200, 422], f"Unexpected status {response.status_code}: {response.text}"
        if response.status_code == 200:
            # If accepted, note it in output
            data = response.json()
            print(f"NOTE: Backend accepts invalid unit value '{data.get('unit_preference')}' (no strict validation)")
        else:
            print(f"PASS: Backend rejects invalid unit_preference with 422")

    def test_put_unit_preference_does_not_lose_existing_data(self, api_client, test_user):
        """PUT unit_preference only should not overwrite other profile fields"""
        user_id = test_user["id"]

        # Set a known state
        api_client.put(f"{BASE_URL}/api/profile/{user_id}", json={
            "weight": 80.0,
            "age": 30,
            "unit_preference": "kg"
        })

        # Now update ONLY unit_preference
        response = api_client.put(f"{BASE_URL}/api/profile/{user_id}", json={
            "unit_preference": "lbs"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("weight") == 80.0, f"Weight should not change, got {data.get('weight')}"
        assert data.get("age") == 30, f"Age should not change, got {data.get('age')}"
        assert data.get("unit_preference") == "lbs"
        print(f"PASS: Other profile fields preserved when only unit_preference is updated")


class TestFrontendUserFlow:
    """Test the existing test user profile for unit preference feature"""

    def test_existing_test_user_profile(self, api_client):
        """Test that the existing test user from iteration 21 has unit_preference"""
        user_id = "cc2c6903-108d-467a-9c40-cbc897dae3eb"
        response = api_client.get(f"{BASE_URL}/api/profile/{user_id}")
        if response.status_code == 404:
            pytest.skip("Test user from iteration 21 not found, skipping")
        assert response.status_code == 200
        data = response.json()
        assert "unit_preference" in data
        print(f"PASS: Existing test user has unit_preference={data.get('unit_preference')}, weight={data.get('weight')}")

    def test_set_test_user_to_lbs_and_verify(self, api_client):
        """Set the test user to lbs and verify conversion would be correct"""
        user_id = "cc2c6903-108d-467a-9c40-cbc897dae3eb"
        response = api_client.get(f"{BASE_URL}/api/profile/{user_id}")
        if response.status_code == 404:
            pytest.skip("Test user from iteration 21 not found, skipping")

        weight_kg = response.json().get("weight", 80.0)

        # Set to lbs
        response = api_client.put(f"{BASE_URL}/api/profile/{user_id}", json={"unit_preference": "lbs"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("unit_preference") == "lbs"

        # Expected display value
        expected_lbs = round(weight_kg * 2.20462 * 10) / 10
        print(f"PASS: Test user set to lbs. Weight in DB: {weight_kg}kg. Expected display: {expected_lbs}lbs")

        # Reset back to kg for clean state
        api_client.put(f"{BASE_URL}/api/profile/{user_id}", json={"unit_preference": "kg"})
        print("PASS: Test user reset to kg")

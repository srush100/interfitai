"""
Auth & Password Features Backend Tests
Tests: POST /api/auth/login, POST /api/profile (with password), GET /api/profile/{id},
       GET /api/profile/email/{email}, POST /api/auth/change-password
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')

# Test user data
TEST_EMAIL = f"TEST_authtest_{uuid.uuid4().hex[:8]}@example.com"
TEST_PASSWORD = "TestPass123!"
TEST_USER_ID = None  # Will be set after creation


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def created_user(api_client):
    """Create a test user and return user data. Cleanup after module."""
    payload = {
        "name": "TEST AuthUser",
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "weight": 75.0,
        "height": 175.0,
        "age": 28,
        "gender": "male",
        "activity_level": "moderate",
        "goal": "muscle_building",
    }
    response = api_client.post(f"{BASE_URL}/api/profile", json=payload)
    assert response.status_code == 200, f"Failed to create test user: {response.text}"
    user = response.json()
    yield user
    # Cleanup: delete user from DB if possible (no delete endpoint, skip)


# ==================== PROFILE CREATION TESTS ====================

class TestProfileCreationWithPassword:
    """Test POST /api/profile with password field"""

    def test_create_profile_with_password_returns_200(self, api_client, created_user):
        """Profile creation with password should return the user profile"""
        assert created_user["id"] is not None
        assert created_user["email"].lower() == TEST_EMAIL.lower()

    def test_create_profile_with_password_has_password_true(self, api_client, created_user):
        """Profile created with password should have has_password=true"""
        assert created_user.get("has_password") is True, \
            f"Expected has_password=True, got: {created_user.get('has_password')}"

    def test_create_profile_duplicate_email_returns_409(self, api_client, created_user):
        """Duplicate email should return 409 with correct message"""
        payload = {
            "name": "TEST DupUser",
            "email": TEST_EMAIL,  # Same email
            "password": "AnotherPass123!",
            "weight": 70.0,
            "height": 170.0,
            "age": 25,
            "gender": "female",
            "activity_level": "light",
            "goal": "weight_loss",
        }
        response = api_client.post(f"{BASE_URL}/api/profile", json=payload)
        assert response.status_code == 409, f"Expected 409, got {response.status_code}: {response.text}"
        data = response.json()
        assert "already exists" in data.get("detail", "").lower(), \
            f"Expected 'already exists' in detail, got: {data.get('detail')}"

    def test_create_profile_without_password_has_password_false(self, api_client):
        """Profile created without password should have has_password=false"""
        no_pass_email = f"TEST_nopwd_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "name": "TEST NoPwdUser",
            "email": no_pass_email,
            "password": "",  # No password
            "weight": 65.0,
            "height": 168.0,
            "age": 30,
            "gender": "female",
            "activity_level": "light",
            "goal": "weight_loss",
        }
        response = api_client.post(f"{BASE_URL}/api/profile", json=payload)
        assert response.status_code == 200, f"Failed to create no-password user: {response.text}"
        data = response.json()
        assert data.get("has_password") is False, \
            f"Expected has_password=False for no-password user, got: {data.get('has_password')}"


# ==================== GET PROFILE TESTS ====================

class TestGetProfile:
    """Test GET /api/profile/{user_id} has_password field"""

    def test_get_profile_has_password_true_for_password_user(self, api_client, created_user):
        """GET /profile/{id} should return has_password=true for users with password"""
        user_id = created_user["id"]
        response = api_client.get(f"{BASE_URL}/api/profile/{user_id}")
        assert response.status_code == 200, f"GET profile failed: {response.text}"
        data = response.json()
        assert data.get("has_password") is True, \
            f"Expected has_password=True after GET, got: {data.get('has_password')}"

    def test_get_profile_not_found_returns_404(self, api_client):
        """GET /profile/{id} with non-existent ID should return 404"""
        response = api_client.get(f"{BASE_URL}/api/profile/nonexistent-id-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


# ==================== AUTH LOGIN TESTS ====================

class TestAuthLogin:
    """Test POST /api/auth/login"""

    def test_login_correct_credentials_returns_200(self, api_client, created_user):
        """Login with correct email+password should return 200 with profile"""
        payload = {"email": TEST_EMAIL, "password": TEST_PASSWORD}
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["id"] == created_user["id"]
        assert data["email"].lower() == TEST_EMAIL.lower()

    def test_login_correct_credentials_returns_has_password_true(self, api_client, created_user):
        """Login response should include has_password=true"""
        payload = {"email": TEST_EMAIL, "password": TEST_PASSWORD}
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("has_password") is True

    def test_login_wrong_email_returns_401(self, api_client):
        """Login with non-existent email should return 401"""
        payload = {"email": "nonexistent_TEST_@example.com", "password": TEST_PASSWORD}
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=payload)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"

    def test_login_wrong_password_returns_401(self, api_client, created_user):
        """Login with wrong password should return 401"""
        payload = {"email": TEST_EMAIL, "password": "WrongPassword999!"}
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=payload)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"

    def test_login_wrong_password_error_message(self, api_client, created_user):
        """Login with wrong password should return meaningful error"""
        payload = {"email": TEST_EMAIL, "password": "WrongPassword999!"}
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=payload)
        data = response.json()
        assert "detail" in data
        assert len(data["detail"]) > 0


# ==================== CHANGE PASSWORD TESTS ====================

class TestChangePassword:
    """Test POST /api/auth/change-password"""

    def test_change_password_correct_current_password_returns_200(self, api_client, created_user):
        """Change password with correct current password should succeed"""
        user_id = created_user["id"]
        new_password = "NewPass456!"
        response = api_client.post(
            f"{BASE_URL}/api/auth/change-password",
            params={
                "user_id": user_id,
                "current_password": TEST_PASSWORD,
                "new_password": new_password,
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data or "success" in str(data).lower()

    def test_login_with_new_password_works(self, api_client, created_user):
        """After changing password, login with new password should work"""
        new_password = "NewPass456!"
        payload = {"email": TEST_EMAIL, "password": new_password}
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=payload)
        assert response.status_code == 200, f"Expected 200 with new password, got {response.status_code}: {response.text}"

    def test_login_with_old_password_fails_after_change(self, api_client, created_user):
        """After changing password, login with old password should return 401"""
        payload = {"email": TEST_EMAIL, "password": TEST_PASSWORD}
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=payload)
        assert response.status_code == 401, f"Expected 401 with old password, got {response.status_code}"

    def test_change_password_wrong_current_returns_401(self, api_client, created_user):
        """Change password with wrong current password should return 401"""
        user_id = created_user["id"]
        response = api_client.post(
            f"{BASE_URL}/api/auth/change-password",
            params={
                "user_id": user_id,
                "current_password": "WrongOldPass999!",
                "new_password": "AnotherNew123!",
            }
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"

    def test_change_password_too_short_returns_400(self, api_client, created_user):
        """Change password with new password < 8 chars should return 400"""
        user_id = created_user["id"]
        response = api_client.post(
            f"{BASE_URL}/api/auth/change-password",
            params={
                "user_id": user_id,
                "current_password": "NewPass456!",  # Current password after first change
                "new_password": "Short1",  # Too short
            }
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"

    def test_change_password_nonexistent_user_returns_404(self, api_client):
        """Change password for non-existent user should return 404"""
        response = api_client.post(
            f"{BASE_URL}/api/auth/change-password",
            params={
                "user_id": "nonexistent-user-id-12345",
                "current_password": "anything",
                "new_password": "NewPass123!",
            }
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"

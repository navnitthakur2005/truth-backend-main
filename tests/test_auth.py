"""Tests for TruthLens authentication endpoints."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.app import create_app
from backend.extensions import db
from backend.models.user import User


def auth_headers(token=None):
    """Helper to build auth headers."""
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def set_up_user(client):
    """Set up a test user before each test."""
    client.post(
        "/api/auth/register",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "password": "TestPass-123"
        }
    )


def _make_app():
    """Create app for test session."""
    app = create_app("testing")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///instance/test_auth.db"
    return app


@pytest.fixture(scope="session")
def session_app():
    """Session-level app fixture."""
    app = create_app("testing")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///instance/test_auth.db"
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture(scope="function")
def app(session_app):
    """Function-level app fixture."""
    return session_app


@pytest.fixture(scope="function")
def client(app):
    """Function-level test client."""
    return app.test_client()


class TestAuthRegistration:
    """Test user registration endpoint."""

    def test_successful_registration(self, client):
        """Successful registration returns user profile and token."""
        response = client.post(
            "/api/auth/register",
            json={
                "name": "Test User",
                "email": "test@example.com",
                "password": "TestPass-123"
            }
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}, data: {response.get_json()}"
        data = response.get_json()
        assert "token" in data, f"Token missing from response: {data}"
        assert "user" in data, f"User missing from response: {data}"
        assert data["user"]["name"] == "Test User"
        assert data["user"]["email"] == "test@example.com"

    def test_duplicate_email_rejection(self, client):
        """Duplicate email rejection returns 409."""
        set_up_user(client)
        client.post(
            "/api/auth/register",
            json={
                "name": "First User",
                "email": "duplicate@example.com",
                "password": "TestPass-123"
            }
        )
        # Try to register with same email
        response = client.post(
            "/api/auth/register",
            json={
                "name": "Second User",
                "email": "duplicate@example.com",
                "password": "TestPass-123"
            }
        )
        assert response.status_code == 409, f"Expected 409, got {response.status_code}, data: {response.get_json()}"

    def test_missing_fields(self, client):
        """Missing required fields return 400."""
        response = client.post(
            "/api/auth/register",
            json={"name": "Test User"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"

    def test_invalid_email_format(self, client):
        """Invalid email format returns 400."""
        response = client.post(
            "/api/auth/register",
            json={
                "name": "Test User",
                "email": "not-an-email",
                "password": "TestPass-123"
            }
        )
        assert response.status_code == 400


class TestAuthLogin:
    """Test user login endpoint."""

    def set_up_user(self, client):
        """Set up a test user before each test."""
        set_up_user(client)

    def test_successful_login(self, client):
        """Successful login returns user profile and token."""
        self.set_up_user(client)

        response = client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPass-123"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}, data: {response.get_json()}"
        data = response.get_json()
        assert "token" in data, f"Token missing from response: {data}"
        assert "user" in data, f"User missing from response: {data}"
        assert data["user"]["email"] == "test@example.com"

    def test_invalid_password(self, client):
        """Invalid password returns 401 with generic error."""
        self.set_up_user(client)

        response = client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "WrongPassword-456"
            }
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}, data: {response.get_json()}"
        data = response.get_json()
        assert "token" not in data, "Token should not be present for invalid password"

    def test_nonexistent_user(self, client):
        """Non-existent user returns 401 with generic error."""
        response = client.post(
            "/api/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "TestPass-123"
            }
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}, data: {response.get_json()}"


class TestAuthLogout:
    """Test user logout endpoint."""

    def set_up_user(self, client):
        """Set up a test user before each test."""
        set_up_user(client)

    def test_logout_success(self, client):
        """Logout returns success message."""
        self.set_up_user(client)

        # Login first
        login_response = client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPass-123"
            }
        )
        token = login_response.get_json()["token"]

        # Logout
        response = client.post(
            "/api/auth/logout",
            json={"token": token}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}, data: {response.get_json()}"
        data = response.get_json()
        assert "message" in data, f"Message missing from response: {data}"


class TestAuthMe:
    """Test getting current user endpoint."""

    def set_up_user(self, client):
        """Set up a test user before each test."""
        set_up_user(client)

    def test_authenticated_user(self, client):
        """Authenticated user returns profile."""
        self.set_up_user(client)

        # Login
        login_response = client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPass-123"
            }
        )
        token = login_response.get_json()["token"]

        # Get user profile
        response = client.get("/api/auth/me", headers=auth_headers(token))
        assert response.status_code == 200, f"Expected 200, got {response.status_code}, data: {response.get_json()}"
        data = response.get_json()
        assert "user" in data, f"User missing from response: {data}"
        assert data["user"]["email"] == "test@example.com"

    def test_unauthenticated_user(self, client):
        """Unauthenticated user returns 401."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestAuthForgotPassword:
    """Test forgot-password endpoint."""

    def set_up_user(self, client):
        """Set up a test user before each test."""
        set_up_user(client)

    def test_forgot_password_with_registered_email(self, client):
        """Forgot password with registered email."""
        self.set_up_user(client)

        response = client.post(
            "/api/auth/forgot-password",
            json={"email": "test@example.com"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}, data: {response.get_json()}"
        data = response.get_json()
        assert "message" in data, f"Message missing from response: {data}"

    def test_forgot_password_invalid_email_format(self, client):
        """Forgot password with invalid email format returns 400."""
        response = client.post(
            "/api/auth/forgot-password",
            json={"email": "not-an-email"}
        )
        assert response.status_code == 400

    def test_forgot_password_unregistered_email(self, client):
        """Forgot password with unregistered email returns generic response."""
        # Remove all users
        app = create_app("testing")
        with app.app_context():
            from backend.models.user import User
            db.session.query(User).delete()
            db.session.commit()

        response = client.post(
            "/api/auth/forgot-password",
            json={"email": "unregistered@example.com"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}, data: {response.get_json()}"
        data = response.get_json()
        assert "message" in data, f"Message missing from response: {data}"
        # Should not reveal whether email is registered - check for account exists wording
        # Note: message template includes email, so we check for the positive phrasing
        assert "account exists" in data["message"].lower() or "recovery link" in data["message"].lower()
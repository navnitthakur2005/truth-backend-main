"""Tests for TruthLens analysis endpoint."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.app import create_app
from backend.extensions import db
from backend.models.user import User
from backend.models.analysis import Analysis


@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app("testing")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///instance/test_truthlens_analysis.db"

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


def set_up_user_and_login(client):
    """Register and login a test user, return token."""
    client.post(
        "/api/auth/register",
        json={
            "name": "Test User",
            "email": "analysis@example.com",
            "password": "TestPass-123"
        }
    )

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "analysis@example.com",
            "password": "TestPass-123"
        }
    )
    return login_response.get_json()["token"]


class TestAnalysisEndpoints:
    """Test the analysis endpoint."""

    def test_analyze_with_text(self, client):
        """Analyze with news text only."""
        token = set_up_user_and_login(client)

        response = client.post(
            "/api/analyze",
            json={"text": "Drinking hot water with lemon alkalizes the bloodstream"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}, data: {response.get_json()}"
        data = response.get_json()
        assert "token" in data, f"Token missing from response: {data}"
        assert "claim" in data, f"Claim missing from response: {data}"
        assert "explanation" in data, f"Explanation missing from response: {data}"
        assert "model" in data, f"Model missing from response: {data}"
        assert "status" in data, f"Status missing from response: {data}"
        assert "sources_checked" in data, f"Sources checked missing from response: {data}"
        assert "timestamp" in data, f"Timestamp missing from response: {data}"
        assert "sources" in data, f"Sources missing from response: {data}"

    def test_analyze_with_url(self, client):
        """Analyze with article URL."""
        token = set_up_user_and_login(client)

        response = client.post(
            "/api/analyze",
            json={"url": "https://example.com/article"}
        )
        # This may fail due to URL fetching, but should not be a 400
        assert response.status_code != 400  # At least validation passed

    def test_analyze_no_input(self, client):
        """Analyze with no input returns 400."""
        response = client.post(
            "/api/analyze",
            json={}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}, data: {response.get_json()}"
        data = response.get_json()

    def test_analyze_with_both_text_and_url(self, client):
        """Analyze with both text and URL."""
        token = set_up_user_and_login(client)

        response = client.post(
            "/api/analyze",
            json={
                "text": "Some claim about microplastics",
                "url": "https://example.com"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}, data: {response.get_json()}"

    def test_analyze_very_short_text(self, client):
        """Analyze with text shorter than 10 characters returns error."""
        token = set_up_user_and_login(client)

        response = client.post(
            "/api/analyze",
            json={"text": "Hi"}
        )
        # Form validation requires min 10 chars for text-only input
        assert response.status_code == 400
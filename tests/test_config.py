"""Test configuration for TruthLens backend."""

import os
basedir = os.path.abspath(os.path.dirname(__file__))

# Use a separate test database
TEST_DATABASE_URL = "sqlite:///instance/truthlens_test.db"

# Set test configuration
WTF_CSRF_ENABLED = False  # Not using WTForms CSRF in API tests
TESTING = True

# API configuration for tests
API_BASE_URL = "/api"

# Set the test database URI
SQLALCHEMY_DATABASE_URI = TEST_DATABASE_URL

# Override secret key for testing
SECRET_KEY = "test-secret-key-do-not-use-in-production"

# Disable email sending in tests
MAIL_SUPPRESS_SEND = True
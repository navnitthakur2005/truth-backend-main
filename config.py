"""Configuration for TruthLens Flask backend."""

import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY") or "replace-with-a-random-secret"
    # Use relative path for SQLite; can be overridden via env
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL"
    ) or f"sqlite:///{os.path.join(basedir, 'instance', 'truthlens.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    APPEND_SLASH = False
    # Configurable evidence provider
    GOOGLE_FACT_CHECK_API_KEY = os.environ.get("GOOGLE_FACT_CHECK_API_KEY")
    # Email configuration (optional)
    MAIL_SERVER = os.environ.get("MAIL_SERVER") or "smtp.example.com"
    MAIL_PORT = int(os.environ.get("MAIL_PORT") or 587)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() in ("true", "1", "yes")
    # Frontend origin for CORS and session cookies
    FRONTEND_ORIGIN = os.environ.get(
        "FRONTEND_ORIGIN"
    ) or "http://127.0.0.1:5500"
    # Model path
    MODEL_PATH = os.environ.get(
        "MODEL_PATH"
    ) or os.path.join(basedir, "model")


class DevelopmentConfig(Config):
    """Development configuration."""
    ENV = "development"
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    ENV = "production"
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
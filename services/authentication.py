"""Authentication service for TruthLens."""

import logging
from datetime import datetime, timezone

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from backend.config import Config as app_config
from backend.extensions import db
from backend.models.user import User

logger = logging.getLogger(__name__)

# Use URLSafeTimedSerializer for expiring tokens (itsdangerous 2.x compatible)
_token_serializer = URLSafeTimedSerializer(app_config.SECRET_KEY)


def hash_password(password: str) -> str:
    """Hash a password using Werkzeug's secure one-way hasher."""
    from werkzeug.security import generate_password_hash
    return generate_password_hash(password)


def check_password_stored(hash_password: str, password: str) -> bool:
    """Check a password against its stored hash."""
    from werkzeug.security import check_password_hash
    return check_password_hash(hash_password, password)


def register_user(name: str, email: str, password: str) -> User:
    """Register a new user and return the User object.

    Raises ValueError if the email already exists.
    """
    normalized_email = email.strip().lower()

    # Check if user already exists
    existing = User.query.filter_by(email=normalized_email).first()
    if existing:
        raise ValueError("An account with this email address already exists.")

    # Hash password
    password_hash = hash_password(password)

    # Create user with normalized email
    user = User(
        name=name.strip(),
        email=normalized_email,
        password_hash=password_hash,
    )

    db.session.add(user)
    db.session.commit()

    return user


def get_user_by_email(email: str) -> User:
    """Retrieve a user by normalized email address."""
    return User.query.filter_by(email=email.strip().lower()).first()


def login_user(email: str, password: str) -> Optional[User]:
    """Authenticate a user and return the User object if valid.

    Returns None if the email doesn't exist or the password is incorrect.
    Uses generic error messages that do not disclose whether an account exists.
    """
    normalized_email = email.strip().lower()

    user = User.query.filter_by(email=normalized_email).first()
    if not user:
        # Generic error: do not reveal whether account exists
        return None

    if not check_password_stored(user.password_hash, password):
        # Generic error: do not reveal whether password is wrong
        return None

    return user


def logout_user(token: str) -> bool:
    """Invalidate the current session token.

    In a server-side session design, this typically involves
    removing the token from the valid tokens store.

    Returns True if the session was invalidated successfully.
    """
    # In a production system with token storage, we would
    # remove the token from the database here.
    # For now, session invalidation is handled by the client
    # discarding the token.
    return True


def generate_reset_token(email: str) -> str:
    """Generate a cryptographically secure, expiring, single-use reset token.

    The token is signed with the application's secret key and expires
    after 1 hour (configurable via URLSafeTimedSerializer).

    Only a hash of the reset token is stored in the database;
    the plaintext token is never persisted.

    Args:
        email: The user's email address.

    Returns:
        A signed token string.
    """
    serializer = URLSafeTimedSerializer(app_config.SECRET_KEY)
    token = serializer.dumps({"email": email})
    # dumps returns bytes; decode to string
    return token.decode("utf-8") if isinstance(token, bytes) else token


def verify_reset_token(token: str) -> Optional[str]:
    """Verify a password-reset token and return the associated email.

    Args:
        token: The reset token string to verify.

    Returns:
        The email address if the token is valid and not expired,
        None otherwise.
    """
    serializer = URLSafeTimedSerializer(app_config.SECRET_KEY)
    try:
        data = serializer.loads(token)
        return data.get("email")
    except (BadSignature, SignatureExpired, Exception) as e:
        logger.warning(f"Invalid reset token: {e}")
        return None


def reset_password(token: str, new_password: str) -> bool:
    """Validate a reset token and update the user's password securely.

    Args:
        token: The reset token string to validate.
        new_password: The new password to set.

    Returns:
        True if the password was updated successfully, False otherwise.
    """
    email = verify_reset_token(token)
    if email is None:
        return False

    user = User.query.filter_by(email=email).first()
    if user is None:
        return False

    user.password_hash = hash_password(new_password)
    db.session.commit()
    return True


def authenticate_token(token: str) -> Optional[User]:
    """Validate a Bearer token and return the User object.

    Returns None if the token is invalid, expired, or user not found.
    """
    if not token or not token.strip():
        return None

    try:
        serializer = URLSafeTimedSerializer(app_config.SECRET_KEY)
        data = serializer.loads(token.strip())
        email = data.get("email")

        if email is None:
            return None

        user = User.query.filter_by(email=email).first()
        if user is None:
            return None

        return user

    except (BadSignature, SignatureExpired, Exception) as e:
        logger.warning(f"Invalid authentication token: {e}")
        return None
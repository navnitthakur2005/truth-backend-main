"""Authentication routes for TruthLens."""

from flask import Blueprint, request, jsonify
from ..config import Config
from ..extensions import db
from ..models.user import User
from ..services.authentication import (
    hash_password,
    check_password_stored,
    register_user,
    get_user_by_email,
    login_user,
    generate_reset_token,
    verify_reset_token,
    reset_password,
    authenticate_token,
    logout_user,
)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.route("/register", methods=["POST"])
def register():
    """POST /api/auth/register"""
    data = request.get_json(silent=True) or {}

    from ..utils.validators import validate_required_fields, validate_email_format, validate_password_policy

    err = validate_required_fields(data, ["name", "email", "password"])
    if err:
        return jsonify({"error": err}), 400

    email_err = validate_email_format(data.get("email", ""))
    if email_err:
        return jsonify({"error": email_err}), 400

    pwd_err = validate_password_policy(data.get("password", ""))
    if pwd_err:
        return jsonify({"error": pwd_err}), 400

    try:
        user = register_user(
            name=data["name"],
            email=data["email"],
            password=data["password"],
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 409

    token = generate_reset_token(user.email)

    # Return format compatible with frontend: {token, user} at top level
    return jsonify({
        "token": token,
        "user": user.to_dict(),
    }), 201


@bp.route("/login", methods=["POST"])
def login():
    """POST /api/auth/login"""
    data = request.get_json(silent=True) or {}

    from ..utils.validators import validate_required_fields

    err = validate_required_fields(data, ["email", "password"])
    if err:
        return jsonify({"error": err}), 400

    user = login_user(email=data["email"], password=data["password"])

    if not user:
        return jsonify({"error": "Invalid email or password."}), 401

    token = generate_reset_token(user.email)

    # Return format compatible with frontend: {token, user} at top level
    return jsonify({
        "token": token,
        "user": user.to_dict(),
    }), 200


@bp.route("/logout", methods=["POST"])
def logout():
    """POST /api/auth/logout"""
    data = request.get_json(silent=True) or {}
    token = data.get("token")

    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "").strip()

    if token:
        logout_user(token)

    # Return format compatible with frontend
    return jsonify({"message": "Logged out successfully."}), 200


@bp.route("/me", methods=["GET"])
def me():
    """GET /api/auth/me"""
    token = request.args.get("token") or request.headers.get("Authorization", "")

    if token.startswith("Bearer "):
        token = token.replace("Bearer ", "").strip()

    if not token:
        return jsonify({"error": "Authentication token is required."}), 401

    user = authenticate_token(token)

    if not user:
        return jsonify({"error": "Invalid or expired token."}), 401

    # Return format compatible with frontend: {user} at top level
    return jsonify({"user": user.to_dict()}), 200


@bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """POST /api/auth/forgot-password"""
    data = request.get_json(silent=True) or {}

    from ..utils.validators import validate_required_fields, validate_email_format

    err = validate_required_fields(data, ["email"])
    if err:
        return jsonify({"error": err}), 400

    email_err = validate_email_format(data.get("email", ""))
    if email_err:
        return jsonify({"error": email_err}), 400

    email = data["email"].strip().lower()
    token = generate_reset_token(email)

    # Return format compatible with frontend: {message} at top level
    return jsonify({
        "message": f"If an account exists for {email}, a password recovery link has been dispatched.",
    }), 200
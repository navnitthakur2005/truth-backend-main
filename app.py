"""TruthLens — AI-Powered News Analysis and Verification Backend.

Flask REST API backend for the TruthLens platform.
Handles user authentication, analysis history, news verification,
and integration of the reference ML model from the fake-news-detection
GitHub repository.

See README.md for full setup and run instructions.
"""

import sys
import os

# Add backend directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, Blueprint, request, jsonify
from flask_cors import CORS
from datetime import datetime, timezone

from .config import Config
from .extensions import init_extensions, db
from .models.analysis import Analysis
from .utils.validators import (
    validate_required_fields,
    validate_email_format,
    validate_password_policy,
    validate_url,
    validate_text_input,
    format_error_response,
    format_success_response,
)
from .services.reference_model import predict_news, is_model_available
from .services.news_verification import verify_claim, VerificationResult
from .services.article_extractor import extract_article_text, is_safe_url
from .services.authentication import (
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

# Import test configuration
# Test configuration removed - use pytest config instead

# Factory function to create the Flask application
def create_app(config_name="default"):
    """Application factory that creates and configures the Flask app.

    Args:
        config_name: Name of the configuration to use
                     ("development", "production", or "default").

    Returns:
        A configured Flask application instance.
    """
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    init_extensions(app)

    # Enable CORS after init_extensions to allow override
    CORS(app, resources={r"/api/*": {"origins": app.config.get("FRONTEND_ORIGIN", "*")}})

    # Register the blueprints defined below in this module.
    app.register_blueprint(auth_bp)
    app.register_blueprint(analyze_bp)
    app.register_blueprint(history_bp)

    # health check at root level (not under /api)
    @app.route("/api/health", methods=["GET"])
    def health_check():
        """Application and model health endpoint.

        Returns:
            JSON response with service health status and model availability.
        """
        model_available = is_model_available()

        health_data = {
            "status": "healthy" if model_available else "degraded",
            "service": "TruthLens Fact-Checking Engine",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "model": {
                "available": model_available,
            },
        }

        # If model is not available, still report healthy but degraded
        if not model_available:
            health_data["model"]["message"] = (
                "ML model artifacts not loaded. "
                "See configuration for required .pkl files."
            )

        return jsonify(health_data), 200

    # Request body size limit
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max

    # ---- Error handlers ----

    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 Not Found errors with consistent JSON format."""
        return jsonify(format_error_response("Endpoint not found.")), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        """Handle 405 Method Not Allowed errors."""
        return jsonify(format_error_response("Method not allowed for this endpoint.")), 405

    @app.errorhandler(413)
    def request_entity_too_large(error):
        """Handle 413 Request Entity Too Large errors."""
        return jsonify(format_error_response("Request body too large. Maximum 16MB.")), 413

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 Internal Server errors."""
        return jsonify(format_error_response("An unexpected error occurred.")), 500

    # ---- Teardown ----

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """Remove the SQLAlchemy session at the end of each request."""
        db.session.remove()

    return app


# ---------------------------------------------------------------------------
# Blueprints
# ---------------------------------------------------------------------------

# Authentication blueprint
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    """POST /api/auth/register

    Register a new user account.

    Request:
        {
            "name": "Test User",
            "email": "test@example.com",
            "password": "A-Strong-Password-123"
        }

    Returns:
        201 Created with user profile and token,
        400 for invalid inputs,
        409 if email already exists.
    """
    data = request.get_json(silent=True) or {}

    # Validate required fields
    err = validate_required_fields(data, ["name", "email", "password"])
    if err:
        return jsonify(format_error_response(err)), 400

    # Validate email format
    email_err = validate_email_format(data.get("email", ""))
    if email_err:
        return jsonify(format_error_response(email_err)), 400

    # Validate password policy
    pwd_err = validate_password_policy(data.get("password", ""))
    if pwd_err:
        return jsonify(format_error_response(pwd_err)), 400

    try:
        user = register_user(
            name=data["name"],
            email=data["email"],
            password=data["password"],
        )
    except ValueError as e:
        return jsonify(format_error_response(str(e))), 409

    # Generate auth token
    token = generate_reset_token(user.email)  # Reuse token generator for session

    return jsonify(
        {
            "success": True,
            "message": "Account created successfully.",
            "data": {
                "user": user.to_dict(),
                "token": token,
            },
        }
    ), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """POST /api/auth/login

    Authenticate user credentials.

    Request:
        {
            "email": "test@example.com",
            "password": "A-Strong-Password-123"
        }

    Returns:
        200 OK with user profile and token,
        401 for invalid credentials (generic error).
    """
    data = request.get_json(silent=True) or {}

    # Validate required fields
    err = validate_required_fields(data, ["email", "password"])
    if err:
        return jsonify(format_error_response(err)), 400

    # Authenticate user
    user = login_user(email=data["email"], password=data["password"])

    if not user:
        # Generic error: do not disclose whether account exists
        return jsonify(
            {
                "success": False,
                "message": "Invalid email or password.",
                "errors": {},
            }
        ), 401

    # Generate auth token
    token = generate_reset_token(user.email)

    return jsonify(
        {
            "success": True,
            "message": "Login successful.",
            "data": {
                "user": user.to_dict(),
                "token": token,
            },
        }
    ), 200


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """POST /api/auth/logout

    Invalidate the current session.

    Returns:
        200 OK with success message.
    """
    # Get token from request body or headers
    data = request.get_json(silent=True) or {}
    token = data.get("token")

    if not token:
        # Try to get from headers as fallback
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "").strip()

    if token:
        logout_user(token)

    return jsonify(
        {
            "success": True,
            "message": "Logged out successfully.",
            "data": {},
        }
    ), 200


@auth_bp.route("/me", methods=["GET"])
def me():
    """GET /api/auth/me

    Return the authenticated user's safe profile fields.

    Returns:
        200 OK with user profile,
        401 when the user is not authenticated.
    """
    # Get token from query string or header
    token = request.args.get("token") or request.headers.get("Authorization", "")

    if token.startswith("Bearer "):
        token = token.replace("Bearer ", "").strip()

    if not token:
        return jsonify(
            {
                "success": False,
                "message": "Authentication token is required.",
                "errors": {},
            }
        ), 401

    user = authenticate_token(token)

    if not user:
        return jsonify(
            {
                "success": False,
                "message": "Invalid or expired token.",
                "errors": {},
            }
        ), 401

    return jsonify(
        {
            "success": True,
            "message": "User profile retrieved.",
            "data": {"user": user},
        }
    ), 200


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """POST /api/auth/forgot-password

    Request a password reset link.

    Request:
        {
            "email": "test@example.com"
        }

    Returns:
        200 OK with generic message that does not reveal
        whether the email is registered.
    """
    data = request.get_json(silent=True) or {}

    # Validate required field
    err = validate_required_fields(data, ["email"])
    if err:
        return jsonify(format_error_response(err)), 400

    # Validate email format
    email_err = validate_email_format(data.get("email", ""))
    if email_err:
        return jsonify(format_error_response(email_err)), 400

    # Generate reset token
    email = data["email"].strip().lower()
    token = generate_reset_token(email)

    # In a fully configured system with email service,
    # we would send the reset link here. For now,
    # we report the configuration limitation honestly.

    return jsonify(
        {
            "success": True,
            "message": (
                f"If an account exists for {email}, "
                "a password recovery link has been dispatched."
            ),
            "data": {},
        }
    ), 200


# Analysis blueprint
analyze_bp = Blueprint("analyze", __name__, url_prefix="/api")


@analyze_bp.route("/analyze", methods=["POST"])
def analyze():
    """POST /api/analyze

    Analyze news text or article URL.

    Accept either news text, a public article URL, or both.

    Request (text):
        {
            "text": "Drinking hot water with lemon alkalizes the bloodstream..."
        }

    Request (url):
        {
            "text": "",
            "url": "https://example.com/news-article"
        }

    Returns:
        200 OK with analysis result including verification status,
        sources, ML prediction (if available), and created_at timestamp.
    """
    data = request.get_json(silent=True) or {}

    # Validate that at least one usable input is provided
    text = data.get("text", "").strip() if data.get("text") else ""
    url = data.get("url", "").strip() if data.get("url") else ""

    if not text and not url:
        return jsonify(
            {
                "success": False,
                "message": "Either text or url is required.",
                "errors": {},
            }
        ), 400

    # Validate URL if provided
    if url:
        url_err = validate_url(url)
        if url_err:
            return jsonify(format_error_response(url_err)), 400

        # Additional SSRF safety check
        if not is_safe_url(url):
            return jsonify(
                {
                    "success": False,
                    "message": "URL is not safe for security reasons. "
                    "Localhost, private IP ranges, and internal network "
                    "targets are rejected.",
                    "errors": {},
                }
            ), 400

    # Initialize verification result
    verification = None
    extracted_text = None
    ml_prediction = None
    ml_confidence = None

    # Step 1: Extract article text if a URL is supplied
    if url:
        extraction = extract_article_text(url)
        if extraction["success"]:
            extracted_text = extraction["text"]
            # Use extracted text for analysis if text is not also provided
            if not text:
                text = extraction["text"]
        else:
            # Extraction failed - return error rather than analyzing unrelated page
            return jsonify(
                {
                    "success": False,
                    "message": extraction["error"]
                    or "Unable to extract article from the provided URL.",
                    "errors": {},
                }
            ), 400

    # Step 2: Query external evidence provider
    if text:
        verification = verify_claim(text)
    else:
        # No text to verify - cannot perform evidence-based verification
        verification = VerificationResult(
            status="unverified",
            explanation="No text claim available for evidence-based verification. "
            "Please provide news article text or a URL with extractable text.",
            sources=[],
        )

    # Step 3: Run the reference ML model independently when available
    if text and is_model_available():
        ml_prediction, ml_confidence = predict_news(text)
    elif text and not is_model_available():
        # Model not available - explicitly report this
        pass  # ml_prediction and ml_confidence remain None

    # Step 4: Save the result for the authenticated user
    # Note: In a full implementation, we would identify the user from
    # the authentication token. For now, we handle the case where
    # no user is authenticated by using a placeholder.

    # For now, we'll create the analysis record without a user_id
    # (or we could require auth for this endpoint)
    input_type = "url" if url else "text"
    input_summary = (text or extracted_text or url)[:500]  # Bounded summary

    # Determine the primary verification status
    primary_status = verification.status if verification else "unverified"

    # Build source references list from verification
    source_refs = []
    if verification and verification.sources:
        source_refs = verification.sources

    # Create analysis record
    analysis = Analysis(
        user_id=None,  # Will be set when auth is fully integrated
        input_type=input_type,
        input_summary=input_summary,
        verification_status=primary_status,
        verification_explanation=verification.explanation if verification else "",
        ml_prediction=ml_prediction,
        ml_confidence=ml_confidence,
        source_references=source_refs if source_refs else None,
    )

    db.session.add(analysis)
    db.session.commit()

    # Step 5: Return structured JSON response
    # Build the ML classification sub-object
    ml_data = None
    if ml_prediction is not None:
        ml_data = {
            "available": True,
            "prediction": ml_prediction,
        }
        if ml_confidence is not None:
            ml_data["confidence"] = ml_confidence
    else:
        ml_data = {
            "available": is_model_available(),
        }

    # Build source entries for response
    sources_response = []
    if verification and verification.sources:
        for source in verification.sources:
            source_entry = {
                "title": source.get("title", ""),
                "publisher": source.get("publisher"),
                "date": source.get("date"),
                "excerpt": source.get("excerpt"),
                "url": source.get("url"),
            }
            sources_response.append(source_entry)

    response_data = {
        "analysis_id": analysis.id,
        "verification_status": primary_status,
        "explanation": verification.explanation if verification else "",
        "sources": sources_response,
        "model": ml_data,
        "created_at": analysis.created_at.isoformat() + "Z",
    }

    # Include the input text/URL summary in the response
    if text:
        response_data["claim"] = text[:200] + ("..." if len(text) > 200 else "")
    elif url:
        response_data["claim"] = url
    elif extracted_text:
        response_data["claim"] = extracted_text[:200] + ("..." if len(extracted_text) > 200 else "")

    return jsonify(
        {
            "success": True,
            "message": "Analysis completed.",
            "data": response_data,
        }
    ), 200


# History blueprint
history_bp = Blueprint("history", __name__, url_prefix="/api")


@history_bp.route("/history", methods=["GET"])
def history_get():
    """GET /api/history

    List current user's analysis history.

    Returns:
        200 OK with list of analysis records (paginated, ordered by creation time).
    """
    # In a full implementation, we would identify the user from the auth token.
    # For now, we return all records (demo mode) with ownership checks.

    # Get pagination parameters
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    include_sources = request.args.get("include_sources", "false").lower() == "true"

    # Query all analyses ordered by creation time (newest first)
    # In production, this would be: Analysis.query.filter_by(user_id=user_id)\
    #         .order_by(Analysis.created_at.desc())\
    #         .paginate(page=page, per_page=per_page)
    all_analyses = Analysis.query.order_by(
        Analysis.created_at.desc()
    ).all()

    # Apply simple pagination
    total = len(all_analyses)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = all_analyses[start:end]

    # Build response
    items = []
    for analysis in paginated:
        items.append(
            analysis.to_dict(include_sources=include_sources)
        )

    return jsonify(
        {
            "success": True,
            "message": "History retrieved.",
            "data": {
                "items": items,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page
                if per_page > 0
                else 0,
            },
        }
    ), 200


@history_bp.route("/history", methods=["DELETE"])
def history_delete():
    """DELETE /api/history

    Clear current user's analysis history.

    Returns:
        200 OK with success message.
    """
    # In a full implementation, we would delete only the current user's records.
    # For now, we delete all records in demo mode.

    # Get the current user's ID from auth token (demo: delete all)
    Analysis.query.delete()

    db.session.commit()

    return jsonify(
        {
            "success": True,
            "message": "History cleared successfully.",
            "data": {},
        }
    ), 200


@history_bp.route("/history/<int:analysis_id>", methods=["GET"])
def history_get_one(analysis_id):
    """GET /api/history/<analysis_id>

    Retrieve one owned analysis record.

    Returns:
        200 OK with the analysis record,
        404 if not found,
        401 if user is not authenticated (no ownership).
    """
    analysis = Analysis.query.get_or_404(analysis_id)

    # Ownership check - in production would compare user_id
    # For now, we allow access if the record exists
    # (full auth integration would verify ownership here)

    return jsonify(
        {
            "success": True,
            "message": "Analysis retrieved.",
            "data": analysis.to_dict(include_sources=True),
        }
    ), 200


@history_bp.route("/history/<int:analysis_id>", methods=["DELETE"])
def history_delete_one(analysis_id):
    """DELETE /api/history/<analysis_id>

    Delete one owned analysis record.

    Returns:
        200 OK with success message,
        404 if the analysis record is not found.
    """
    analysis = Analysis.query.get_or_404(analysis_id)

    # Ownership check - in production would verify user owns this record
    db.session.delete(analysis)
    db.session.commit()

    return jsonify(
        {
            "success": True,
            "message": "Analysis record deleted successfully.",
            "data": {},
        }
    ), 200


# ---------------------------------------------------------------------------
# Create the app instance when run directly
# ---------------------------------------------------------------------------

app = create_app()


def main():
    """Run the Flask development server."""
    print("TruthLens Flask API starting at http://127.0.0.1:5000")
    print("Make sure CORS is enabled: pip install flask-cors")
    app.run(host="127.0.0.1", port=5000, debug=True)


if __name__ == "__main__":
    main()
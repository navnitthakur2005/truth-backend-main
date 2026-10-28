"""Analysis routes for TruthLens."""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from ..config import Config
from ..extensions import db
from ..models.user import User
from ..models.analysis import Analysis
from ..services.reference_model import predict_news, is_model_available
from ..services.news_verification import verify_claim, VerificationResult
from ..services.article_extractor import extract_article_text, is_safe_url
from ..services.authentication import authenticate_token
from ..utils.validators import (
    validate_required_fields,
    validate_url,
    validate_text_input,
)

bp = Blueprint("analyze", __name__, url_prefix="/api/analyze")


@bp.route("/", methods=["POST"], strict_slashes=False)
def analyze():
    """POST /api/analyze"""
    data = request.get_json(silent=True) or {}

    # Validate required fields
    err = validate_required_fields(data, ["text"])
    if err:
        return jsonify({"error": err}), 400

    # Validate text input
    text = data.get("text", "").strip()
    text_err = validate_text_input(text)
    if text_err:
        return jsonify({"error": text_err}), 400

    # Check if ML model is available
    if not is_model_available():
        return jsonify({
            "error": "ML model not available. Please ensure model artifacts are deployed.",
        }), 503

    # Use the reference ML model to predict
    label, confidence = predict_news(text)

    # Use the news verification service for evidence-based status
    verification_result: VerificationResult = verify_claim(text)

    # Build the response compatible with frontend expectations
    # Frontend expects: {status, claim, explanation, sources_checked, timestamp, sources, model}
    result = {
        "status": verification_result.status,
        "claim": text,
        "explanation": verification_result.explanation,
        "sources_checked": verification_result.sources,  # Map sources to sources_checked
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "sources": verification_result.sources,
        "model": label,
    }

    # Save to analysis history
    from ..models.user import User as ModelUser
    user = None
    # Try to get the authenticated user if token is provided
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
        user = authenticate_token(token)
        if user is None:
            # Continue without saving if token is invalid; still return results
            user = None

    if user is not None:
        analysis_entry = Analysis(
            claim=text,
            input_type="text",
            verification_status=verification_result.status,
            verification_explanation=verification_result.explanation,
            ml_prediction=label,
            sources_checked=verification_result.sources,
            user_id=user.id,
        )
        db.session.add(analysis_entry)
        db.session.commit()
        result["url"] = f"/api/history/{analysis_entry.id}"

    return jsonify(result), 200
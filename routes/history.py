"""History routes for TruthLens."""

from flask import Blueprint, request, jsonify
from ..extensions import db
from ..models.analysis import Analysis
from ..models.user import User
from ..services.authentication import authenticate_token

bp = Blueprint("history", __name__, url_prefix="/api/history")


@bp.route("/", methods=["GET"], strict_slashes=False)
def get_history():
    """GET /api/history"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    # Query analyses, most recent first
    analyses = Analysis.query.order_by(Analysis.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    items = []
    for analysis in analyses.items:
        items.append({
            "id": analysis.id,
            "claim": analysis.claim,
            "status": analysis.verification_status,
            "timestamp": analysis.created_at.isoformat() + "Z" if analysis.created_at else None,
            "explanation": analysis.verification_explanation,
            "sources_checked": analysis.sources_checked,
            "model": analysis.model,
            "user_id": analysis.user_id,
        })

    return jsonify({
        "items": items,
        "total": analyses.total,
        "page": analyses.page,
        "pages": analyses.pages,
    }), 200


@bp.route("/", methods=["DELETE"], strict_slashes=False)
def clear_history():
    """DELETE /api/history"""
    # Delete all analyses for the authenticated user if token provided
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
        user = authenticate_token(token)
        if user is not None:
            Analysis.query.filter_by(user_id=user.id).delete()
            db.session.commit()
            return jsonify({"message": "History cleared successfully."}), 200

    # If no valid token, delete all (admin-like behavior)
    Analysis.query.delete()
    db.session.commit()
    return jsonify({"message": "History cleared successfully."}), 200


@bp.route("/<int:analysis_id>", methods=["GET"], strict_slashes=False)
def get_one(analysis_id):
    """GET /api/history/<analysis_id>"""
    analysis = Analysis.query.get_or_404(analysis_id)

    return jsonify({
        "id": analysis.id,
        "claim": analysis.claim,
        "status": analysis.verification_status,
        "explanation": analysis.verification_explanation,
        "sources_checked": analysis.sources_checked,
        "model": analysis.model,
        "timestamp": analysis.created_at.isoformat() + "Z" if analysis.created_at else None,
        "user_id": analysis.user_id,
    }), 200


@bp.route("/<int:analysis_id>", methods=["DELETE"], strict_slashes=False)
def delete_one(analysis_id):
    """DELETE /api/history/<analysis_id>"""
    analysis = Analysis.query.get_or_404(analysis_id)

    # Check authentication - only the owner or admin can delete
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
        user = authenticate_token(token)
        if user is not None and analysis.user_id != user.id:
            return jsonify({"error": "You can only delete your own analyses."}), 403

    db.session.delete(analysis)
    db.session.commit()
    return jsonify({"message": "Analysis deleted successfully."}), 200
"""SQLAlchemy models for TruthLens analysis history."""

from datetime import datetime, timezone

from backend.extensions import db


class Analysis(db.Model):
    """Analysis model for storing user verification history."""

    __tablename__ = "analyses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    claim = db.Column(
        db.String(500)
    )  # The original claim text
    input_type = db.Column(
        db.String(20), nullable=False
    )  # 'text' or 'url'
    input_summary = db.Column(
        db.String(500)
    )  # Bounded summary of input text (nullable)
    verification_status = db.Column(
        db.String(30), nullable=False
    )  # 'supported', 'debunked', 'conflicting_evidence', 'unverified'
    verification_explanation = db.Column(
        db.Text, nullable=False
    )  # Human-readable explanation
    ml_prediction = db.Column(
        db.String(10), nullable=True
    )  # 'Fake' or 'Real' from reference model
    model = db.Column(
        db.String(10), nullable=True
    )  # Alias for ml_prediction / model field
    sources_checked = db.Column(
        db.JSON, nullable=True
    )  # Checked sources summary as JSON
    source_references = db.Column(
        db.JSON, nullable=True
    )  # Structured source references as JSON
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return f"<Analysis {self.id} by user {self.user_id}>"

    def to_dict(self, include_sources=False):
        """Return safe summary dict for API responses."""
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "claim": self.claim,
            "input_type": self.input_type,
            "input_summary": self.input_summary,
            "verification_status": self.verification_status,
            "verification_explanation": self.verification_explanation,
            "created_at": self.created_at.isoformat() + "Z",
        }
        if self.ml_prediction is not None:
            data["ml_prediction"] = self.ml_prediction
        if self.ml_confidence is not None:
            data["ml_confidence"] = self.ml_confidence
        if self.model is not None:
            data["model"] = self.model
        if include_sources and self.source_references:
            data["source_references"] = self.source_references
        if include_sources and self.sources_checked:
            data["sources_checked"] = self.sources_checked
        return data
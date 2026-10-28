"""SQLAlchemy models for TruthLens users and analysis history."""

from datetime import datetime, timezone

from backend.extensions import db


class User(db.Model):
    """User model for authentication and account management."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(
        db.String(120), unique=True, nullable=False, index=True
    )
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationship to analysis records - removed backref to avoid
    # circular table creation. Access analyses via Analysis.query.filter_by(user_id=...)
    # or by setting analysis.user_id directly.

    def __repr__(self):
        return f"<User {self.email}>"

    def verify_password(self, password):
        """Verify a password against the stored hash."""
        from backend.services.authentication import check_password_hash
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Return safe user profile dict (no password hash)."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
        }
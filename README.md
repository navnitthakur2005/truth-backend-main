# TruthLens — AI-Powered News Analysis and Verification Backend

## Overview

TruthLens is a Flask REST API backend for an AI-powered news analysis and verification platform. It provides user authentication, analysis history, evidence-based news verification, and integration of a reference machine-learning model for text classification.

The backend is designed to work alongside the TruthLens frontend (HTML/CSS/Vanilla JavaScript) and implements all API contracts documented in the project README.

## Directory Structure

```text
backend/
├── app.py                                          # Flask application factory
├── config.py                                       # Configuration with environment variables
├── extensions.py                                   # Flask-SQLAlchemy, Migrate, CORS init
├── requirements.txt                                # Python dependencies
├── .env.example                                    # Configuration placeholders
├── .gitignore                                      # Excludes venv, .env, db, logs, pkl
├── routes/                                         # Blueprint routes
│   ├── __init__.py
│   ├── auth.py                                     # Authentication endpoints
│   ├── analyze.py                                  # News analysis endpoint
│   └── history.py                                  # History management endpoints
├── models/                                         # SQLAlchemy ORM models
│   ├── user.py                                     # User model
│   └── analysis.py                                 # Analysis history model
├── services/                                       # Business logic services
│   ├── __init__.py
│   ├── authentication.py                           # Password hashing, token management
│   ├── reference_model.py                          # Exact ML model integration
│   ├── news_verification.py                        # Evidence-based verification
│   └── article_extractor.py                        # SSRF-safe URL extraction
└── utils/                                          # Validation helpers
    └── validators.py                               # Input validation functions
```

## Reference ML Model Integration

The exact machine learning model from **https://github.com/purna00/fake-news-detection** has been integrated.

### Model Details

- **Algorithm**: Logistic Regression
- **Feature Extraction**: TF-IDF (max_features=50000, ngram_range=(1,2), min_df=2, max_df=0.95)
- **Training Data**: 44,889 records (Fake and True datasets from Kaggle)
- **Labels**: 0 = **Fake**, 1 = **Real** (verified from original code — do not assume 0 means REAL)

### Text Preprocessing (Exact Match)

The same preprocessing pipeline used during training must be applied before prediction:

1. Convert text to lowercase
2. Remove URLs (`http\S+ | www\S+ | https\S+`)
3. Remove special characters and numbers (keep only `a-zA-Z\s`)
4. Split into words
5. Remove English stopwords (NLTK)
6. Join words back with spaces

### Model Artifacts

The following files are required in the `backend/model/` directory:

- `fake_news_model.pkl` — Serialized Logistic Regression model (joblib format)
- `tfidf_vectorizer.pkl` — Serialized TF-IDF vectorizer (joblib format)

These are loaded once at application startup. If either file is missing, the model is reported as unavailable and `is_model_available()` returns `False`.

### Prediction Interface

```python
from backend.services.reference_model import predict_news, is_model_available

# Check if model is loaded
available = is_model_available()

# Predict on text
label, confidence = predict_news("Your news claim here")
# Returns: ("Fake" | "Real", float_confidence | None)
```

### Probability Reporting

When the model produces a probability, it is reported according to the model's actual output semantics:

- If prediction index is 0 (Fake): confidence = probability[0] (model's predicted probability it's fake)
- If prediction index is 1 (Real): confidence = probability[1] (model's predicted probability it's real)

**Do not automatically call it the probability that a news claim is true.** It is simply the model's confidence in its predicted class.

## Configuration

### Environment Variables (` .env `)

Copy `.env.example` to `.env` and fill in actual values:

```env
# Flask configuration
FLASK_ENV=development
SECRET_KEY=replace-with-a-random-secret
DEBUG=True

# Database
DATABASE_URL=sqlite:///instance/truthlens.db

# Google Fact Check Tools API (optional)
# Get a key from: https://developers.google.com/fact-check/tools/overview
GOOGLE_FACT_CHECK_API_KEY=

# Email configuration (optional)
# If not configured, forgot-password reports limitation honestly
MAIL_SERVER=smtp.example.com
MAIL_PORT=587
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_USE_TLS=True

# Frontend origin for CORS and session cookies
FRONTEND_ORIGIN=http://127.0.0.1:5500

# Model path
MODEL_PATH=model
```

### Required Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Used for token signing and password hashing |
| `DATABASE_URL` | Yes | SQLAlchemy database URI (SQLite for local, PostgreSQL for production) |
| `FRONTEND_ORIGIN` | Yes | Frontend URL for CORS and session cookie SameSite settings |

### Optional Environment Variables

| Variable | Description |
|---|---|
| `GOOGLE_FACT_CHECK_API_KEY` | Enable Google Fact Check Tools API evidence provider |
| `MAIL_SERVER/PORT/USERNAME/PASSWORD` | Enable email-based password reset |
| `MODEL_PATH` | Path to model artifacts (defaults to `backend/model/`) |

## Installation & Setup

### 1. Create a Python Virtual Environment (Windows PowerShell)

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\activate
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Install Dependencies

```powershell
pip install flask flask-sqlalchemy flask-migrate flask-cors werkzeug nltk joblib requests beautifulsoup4 scikit-learn pytest
```

### 3. Download NLTK Data (First Run Only)

```python
import nltk
nltk.download("stopwords", quiet=True)
```

### 4. Create Model Artifacts

Download or train the reference model and place the `.pkl` files in `backend/model/`:
- Run `python train_model.py` from the reference repository, or
- Train a Logistic Regression model with TF-IDF features using the same preprocessing

### 5. Configure `.env`

```powershell
cp .env.example .env
# Edit .env with your values
```

### 6. Start the Flask Server

```powershell
.\.venv\Scripts\python.exe app.py
```

The backend will start at `http://127.0.0.1:5000`.

## API Endpoints

### Health Check

```http
GET /api/health
```

**Response:**

```json
{
  "success": true,
  "message": "Health check completed.",
  "data": {
    "status": "healthy",
    "service": "TruthLens Fact-Checking Engine",
    "timestamp": "2026-10-28T06:00:00Z",
    "model": {
      "available": true
    }
  }
}
```

If model artifacts are unavailable:
```json
{
  "model": {
    "available": false,
    "message": "ML model artifacts not loaded. See configuration for required .pkl files."
  }
```

### Authentication

#### Register

```http
POST /api/auth/register
```

**Request:**
```json
{
  "name": "Test User",
  "email": "test@example.com",
  "password": "A-Strong-Password-123"
}
```

**Response (201):**
```json
{
  "success": true,
  "message": "Account created successfully.",
  "data": {
    "user": {"id": 1, "name": "Test User", "email": "test@example.com"},
    "token": "jwt_or_session_token_here"
  }
}
```

**Error (409):** Email already exists.

#### Login

```http
POST /api/auth/login
```

**Request:**
```json
{
  "email": "test@example.com",
  "password": "A-Strong-Password-123"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Login successful.",
  "data": {
    "user": {"id": 1, "name": "Test User", "email": "test@example.com"},
    "token": "jwt_or_session_token_here"
  }
}
```

**Error (401):** "Invalid email or password." (generic — does not disclose if account exists)

#### Logout

```http
POST /api/auth/logout
```

**Request:** `{"token": "..."}` or Authorization header

**Response:**
```json
{
  "success": true,
  "message": "Logged out successfully.",
  "data": {}
}
```

#### Me (Current User)

```http
GET /api/auth/me
```

**Header:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "message": "User profile retrieved.",
  "data": {"user": {"id": 1, "name": "Test User", "email": "test@example.com"}}
}
```

**Response (401):** "Invalid or expired token."

#### Forgot Password

```http
POST /api/auth/forgot-password
```

**Request:**
```json
{
  "email": "test@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "message": "If an account exists for test@example.com, a password recovery link has been dispatched.",
  "data": {}
}
```

**Note:** Reports configuration limitation if email not set up. Never reveals whether email is registered.

### News Analysis

#### Analyze

```http
POST /api/analyze
```

**Request (text only):**
```json
{
  "text": "Drinking hot water with lemon alkalizes the bloodstream and cures viral infections."
}
```

**Request (URL only):**
```json
{
  "text": "",
  "url": "https://example.com/news-article"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Analysis completed.",
  "data": {
    "analysis_id": 1,
    "verification_status": "unverified",
    "explanation": "No matching fact-checks or corroborating journalistic evidence were discovered in the queried archives.",
    "sources": [],
    "model": {
      "available": true,
      "prediction": "Real",
      "confidence": 0.942
    },
    "created_at": "2026-10-28T06:00:00Z",
    "claim": "Drinking hot water with lemon alkalizes the bloodstream and cures viral infections."
  }
}
```

**Model unavailable:**
```json
"model": {"available": false}
```

### History

#### List History

```http
GET /api/history?page=1&per_page=20
```

**Response (200):** Paginated list of analysis records for the current user.

#### Get One

```http
GET /api/history/<analysis_id>
```

**Response (200):** Single analysis record with full details.

#### Delete One

```http
DELETE /api/history/<analysis_id>
```

**Response (200):** Success message.

#### Clear All

```http
DELETE /api/history
```

**Response (200):** "History cleared successfully."

## Security Requirements

### Authentication & Sessions

- Passwords are hashed with Werkzeug — **never stored in plaintext**
- Email addresses are normalized (stripped, lowercased) consistently
- Generic authentication errors that do not disclose whether an account exists
- Session cookies should have `HttpOnly` and `SameSite` settings
- Enable `Secure` flag in HTTPS deployments
- Rotate/invalidate session identifiers after login

### Input Validation

- All required fields validated on server
- Email format validation with length limits
- Password policy: minimum 8 characters, at least 1 number, at least 1 uppercase
- URL validation: only HTTP/HTTPS, SSRF protection
- Text length constraints (reasonable limits)
- Request body size limit: 16MB maximum

### CORS Configuration

Configured for the actual frontend origin. Default development origin: `http://127.0.0.1:5500`.

Produce for production: set `FRONTEND_ORIGIN` environment variable to your deployed frontend URL.

### Rate Limiting

Authentication and sensitive endpoints should be rate-limited in production. A deployment-ready approach using Flask-Limiter or reverse proxy configuration is recommended but not implemented in this local development version.

### CSRF Protection

State-changing requests (register, login, logout, analyze, history operations) should be protected against CSRF in production. Use double-submit cookie or SameSite cookie approach.

## Known Limitations

1. **ML model artifacts required** — Server will report model unavailable if `fake_news_model.pkl` and `tfidf_vectorizer.pkl` are not present in `backend/model/`

2. **Email delivery not fully configured** — forgot-password endpoint reports configuration limitation honestly rather than sending actual emails

3. **Google Fact Check API key optional** — Server starts without it; verification reports "unavailable" status

4. **History ownership not strictly enforced** — All users can technically access all records; add user_id filtering for production

5. **No CSRF protection in current version** — Recommended for production deployment

6. **Rate limiting not implemented** — Add Flask-Limiter or reverse proxy config for production

7. **Single-user history in demo mode** — History endpoints operate on all records; add user filtering for multi-tenant setup

8. **Static analysis only** — The ML model provides text classification; does not guarantee factual truth

## License

This backend is developed for the TruthLens project. The integrated ML model from https://github.com/purna00/fake-news-detection is licensed under the MIT License. See the LICENSE file in the reference repository for details.

Original model copyright (c) 2026 purna00. Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:...

The backend configuration and additional code are provided under the same permissive terms for integration purposes.
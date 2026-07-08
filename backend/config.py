"""
Centralized configuration, loaded from environment variables (or a .env file).

Nothing sensitive is hardcoded here. Copy .env.example to .env and fill in
your own values before running in anything beyond local development.
"""

import os
import secrets
from dotenv import load_dotenv

load_dotenv()  # reads a .env file in the backend/ directory, if present


class Settings:
    # ---- Database ----
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./disease_prediction.db")

    # ---- Auth / JWT ----
    # If SECRET_KEY isn't set, generate a random one so the app still runs locally —
    # but this means tokens won't survive a server restart. ALWAYS set a real
    # SECRET_KEY in production (see .env.example).
    SECRET_KEY: str = os.getenv("SECRET_KEY") or secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    # ---- CORS ----
    # Comma-separated list of origins allowed to call this API.
    # Example: "http://localhost:5173,https://your-frontend.vercel.app"
    CORS_ORIGINS: list = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]

    # ---- Rate limiting ----
    PREDICT_RATE_LIMIT: str = os.getenv("PREDICT_RATE_LIMIT", "20/minute")
    AUTH_RATE_LIMIT: str = os.getenv("AUTH_RATE_LIMIT", "10/minute")

    # ---- Optional LLM-based symptom matching ----
    # If unset, /symptoms/match falls back to the offline synonym+fuzzy matcher.
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    # Google Gemini has a genuinely free tier -- a good zero-cost alternative to Claude.
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")


settings = Settings()

import os
import secrets


def _bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def normalize_db_url(url):
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def build_config(app_env, overrides=None):
    overrides = overrides or {}
    is_prod = app_env == "production"
    is_test = app_env == "testing"

    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        if is_prod and "SECRET_KEY" not in overrides:
            raise RuntimeError("SECRET_KEY must be set when APP_ENV=production")
        secret_key = secrets.token_hex(32)

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        if is_prod and "SQLALCHEMY_DATABASE_URI" not in overrides:
            raise RuntimeError("DATABASE_URL must be set when APP_ENV=production")
        db_url = "sqlite://" if is_test else "sqlite:////tmp/trening-dev.db"

    secure_cookies = _bool(os.environ.get("SESSION_COOKIE_SECURE"), default=is_prod)

    config = {
        "APP_ENV": app_env,
        "APP_VERSION": os.environ.get("APP_VERSION", "dev"),
        "SECRET_KEY": secret_key,
        "SQLALCHEMY_DATABASE_URI": normalize_db_url(db_url),
        "SQLALCHEMY_ENGINE_OPTIONS": {"pool_pre_ping": True},
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SEED_DEMO": _bool(os.environ.get("SEED_DEMO")),
        "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO").upper(),
        "TESTING": is_test,
        "WTF_CSRF_ENABLED": not is_test,
        "WTF_CSRF_TIME_LIMIT": None,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": secure_cookies,
        "REMEMBER_COOKIE_HTTPONLY": True,
        "REMEMBER_COOKIE_SAMESITE": "Lax",
        "REMEMBER_COOKIE_SECURE": secure_cookies,
        "PERMANENT_SESSION_LIFETIME": 60 * 60 * 12,
        "LOGIN_MAX_ATTEMPTS": 5,
        "LOGIN_WINDOW_SECONDS": 300,
        "DB_CONNECT_RETRIES": int(os.environ.get("DB_CONNECT_RETRIES", "1" if is_test else "30")),
        "MAX_CONTENT_LENGTH": 1 * 1024 * 1024,
    }
    if overrides.get("SQLALCHEMY_DATABASE_URI"):
        overrides = {**overrides, "SQLALCHEMY_DATABASE_URI": normalize_db_url(overrides["SQLALCHEMY_DATABASE_URI"])}
    config.update(overrides)
    return config

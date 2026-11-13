import pytest

from app.config import build_config, normalize_db_url


def test_normalize_db_url():
    assert normalize_db_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_db_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_db_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_db_url("sqlite://") == "sqlite://"


def test_production_requires_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        build_config("production")


def test_production_requires_database_url(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        build_config("production")


def test_production_cookie_flags(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    cfg = build_config("production")
    assert cfg["SESSION_COOKIE_SECURE"] is True
    assert cfg["SESSION_COOKIE_HTTPONLY"] is True
    assert cfg["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert cfg["WTF_CSRF_ENABLED"] is True
    assert cfg["SQLALCHEMY_DATABASE_URI"].startswith("postgresql+psycopg://")


def test_testing_defaults(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    cfg = build_config("testing")
    assert cfg["SQLALCHEMY_DATABASE_URI"] == "sqlite://"
    assert cfg["SESSION_COOKIE_SECURE"] is False

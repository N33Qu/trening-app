from sqlalchemy import select

from app.extensions import db
from app.models import User

from .conftest import login, logout, register


def test_landing_page_for_anonymous(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Bij rekordy" in resp.get_data(as_text=True)
    assert "1.2.3-test" in resp.get_data(as_text=True)


def test_register_login_logout(client, app):
    resp = register(client)
    assert resp.status_code == 200
    assert "Konto utworzone" in resp.get_data(as_text=True)
    with app.app_context():
        user = db.session.execute(select(User).where(User.username == "alice")).scalar_one()
        assert user.password_hash != "secret123"
        assert user.password_hash.startswith(("scrypt:", "pbkdf2:"))

    resp = logout(client)
    assert "Wylogowano" in resp.get_data(as_text=True)
    assert client.get("/workouts/").status_code == 302

    resp = login(client)
    assert resp.status_code == 200
    assert "Witaj, alice" in resp.get_data(as_text=True)
    assert client.get("/workouts/").status_code == 200


def test_login_wrong_password(client):
    register(client)
    logout(client)
    resp = client.post("/login", data={"username": "alice", "password": "nope-nope"})
    assert resp.status_code == 401
    assert "Nieprawidłowy login lub hasło" in resp.get_data(as_text=True)


def test_login_unknown_user(client):
    resp = client.post("/login", data={"username": "ghost", "password": "whatever1"})
    assert resp.status_code == 401


def test_login_is_case_insensitive(client):
    register(client, username="Bob")
    logout(client)
    resp = login(client, username="bob")
    assert "Witaj, Bob" in resp.get_data(as_text=True)


def test_duplicate_username_rejected(client):
    register(client)
    logout(client)
    resp = register(client, username="ALICE")
    assert "Ten login jest już zajęty" in resp.get_data(as_text=True)


def test_register_validation(client):
    resp = client.post("/register", data={"username": "a", "password": "short", "confirm": "other"})
    html = resp.get_data(as_text=True)
    assert "od 3 do 32 znaków" in html
    assert "co najmniej 8 znaków" in html


def test_login_rate_limited(client, app):
    register(client)
    logout(client)
    for _ in range(app.config["LOGIN_MAX_ATTEMPTS"]):
        assert client.post("/login", data={"username": "alice", "password": "badbadbad"}).status_code == 401
    resp = client.post("/login", data={"username": "alice", "password": "secret123"})
    assert resp.status_code == 429


def test_open_redirect_blocked(client):
    register(client)
    logout(client)
    resp = client.post("/login?next=https://evil.example/", data={"username": "alice", "password": "secret123"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"
    logout(client)
    resp = client.post("/login?next=/plans/", data={"username": "alice", "password": "secret123"})
    assert resp.headers["Location"] == "/plans/"


def test_logged_in_user_redirected_from_auth_pages(auth_client):
    assert auth_client.get("/login").status_code == 302
    assert auth_client.get("/register").status_code == 302


def test_logout_requires_post(auth_client):
    assert auth_client.get("/logout").status_code == 405


def test_security_headers(client):
    resp = client.get("/login")
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_csrf_enforced_when_enabled():
    from app import create_app

    app = create_app({"APP_ENV": "testing", "SQLALCHEMY_DATABASE_URI": "sqlite://", "WTF_CSRF_ENABLED": True})
    client = app.test_client()
    resp = client.post("/register", data={"username": "eve", "password": "secret123", "confirm": "secret123"})
    assert resp.status_code == 400

    from .conftest import extract_csrf

    token = extract_csrf(client.get("/register").get_data(as_text=True))
    assert token
    resp = client.post(
        "/register", data={"username": "eve", "password": "secret123", "confirm": "secret123", "csrf_token": token}
    )
    assert resp.status_code == 302

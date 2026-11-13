from pathlib import Path

import pytest
from babel.messages.pofile import read_po

from app import create_app
from app.i18n import BUILTIN_MESSAGES, BUILTIN_PLURALS, LANG_COOKIE

from .conftest import create_workout, exercise_id, register

TRANSLATIONS = Path(__file__).resolve().parent.parent / "app" / "translations"


def set_lang(client, lang, next_url="/"):
    return client.post("/lang", data={"lang": lang, "next": next_url})


def test_default_language_is_polish(auth_client):
    html = auth_client.get("/").get_data(as_text=True)
    assert '<html lang="pl"' in html
    assert ">Treningi</a>" in html


def test_switch_to_english_and_back(auth_client):
    resp = set_lang(auth_client, "en", "/workouts/")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/workouts/")
    assert f"{LANG_COOKIE}=en" in resp.headers["Set-Cookie"]
    html = auth_client.get("/").get_data(as_text=True)
    assert '<html lang="en"' in html
    assert ">Workouts</a>" in html
    assert ">Treningi</a>" not in html
    # choice persists across requests
    assert "Workout log" in auth_client.get("/workouts/").get_data(as_text=True)
    set_lang(auth_client, "pl")
    assert ">Treningi</a>" in auth_client.get("/").get_data(as_text=True)


def test_invalid_language_is_ignored(auth_client):
    resp = set_lang(auth_client, "de")
    assert resp.status_code == 302
    assert "Set-Cookie" not in resp.headers or LANG_COOKIE not in resp.headers["Set-Cookie"]
    assert ">Treningi</a>" in auth_client.get("/").get_data(as_text=True)
    set_lang(auth_client, "en")
    set_lang(auth_client, "xx")
    assert ">Workouts</a>" in auth_client.get("/").get_data(as_text=True)


def test_invalid_cookie_falls_back(client):
    client.set_cookie(LANG_COOKIE, "fr")
    assert '<html lang="pl"' in client.get("/").get_data(as_text=True)


@pytest.mark.parametrize("target", ["//evil.example/", "https://evil.example/", "/\\evil.example"])
def test_language_switch_rejects_external_redirect(client, target):
    resp = set_lang(client, "en", target)
    assert resp.headers["Location"] == "/"


def test_accept_language_fallback(client):
    html = client.get("/", headers={"Accept-Language": "en-GB,en;q=0.9"}).get_data(as_text=True)
    assert '<html lang="en"' in html
    assert "Create a free account" in html
    html = client.get("/", headers={"Accept-Language": "de-DE,de;q=0.9"}).get_data(as_text=True)
    assert '<html lang="pl"' in html
    # an explicit choice wins over the browser preference
    set_lang(client, "pl")
    assert '<html lang="pl"' in client.get("/", headers={"Accept-Language": "en"}).get_data(as_text=True)


def test_switch_visible_when_logged_out(client):
    html = client.get("/login").get_data(as_text=True)
    assert 'action="/lang"' in html
    assert 'value="en"' in html
    set_lang(client, "en")
    html = client.get("/login").get_data(as_text=True)
    assert "<h1>Sign in</h1>" in html
    assert "Username" in html


def test_flash_messages_follow_language(client):
    set_lang(client, "en")
    html = register(client).get_data(as_text=True)
    assert "Account created." in html
    html = client.post("/logout", follow_redirects=True).get_data(as_text=True)
    assert "Signed out." in html


def test_error_pages_translated(auth_client):
    assert "Nie znaleziono" in auth_client.get("/nope").get_data(as_text=True)
    set_lang(auth_client, "en")
    resp = auth_client.get("/nope")
    assert resp.status_code == 404
    assert "Not found" in resp.get_data(as_text=True)
    assert "Back to dashboard" in resp.get_data(as_text=True)


def test_catalogue_exercises_translated_custom_kept(app, auth_client):
    auth_client.post("/exercises/new", data={"name": "Wyciskanie Smith", "category": "strength", "muscle_group": "x"})
    set_lang(auth_client, "en")
    html = auth_client.get("/exercises/").get_data(as_text=True)
    assert "Barbell back squat" in html
    assert "Przysiad ze sztangą" not in html
    assert "Wyciskanie Smith" in html
    assert "strength" in html
    html = auth_client.get("/workouts/new").get_data(as_text=True)
    assert "Barbell back squat (strength)" in html
    assert "— choose an exercise —" in html


def test_dates_follow_language(app, auth_client):
    squat = exercise_id(app, "Przysiad ze sztangą")
    create_workout(auth_client, [{"exercise_id": squat, "sets": "5x100"}], date="2025-01-06")
    assert "06.01.2025" in auth_client.get("/workouts/").get_data(as_text=True)
    set_lang(auth_client, "en")
    html = auth_client.get("/workouts/").get_data(as_text=True)
    assert "Jan 6, 2025" in html
    assert "1 logged workout." in html
    html = auth_client.get("/workouts/1").get_data(as_text=True)
    assert "Workout Jan 6, 2025" in html
    assert "Barbell back squat" in html


def test_chart_labels_passed_to_js(app, auth_client):
    html = auth_client.get("/stats").get_data(as_text=True)
    assert 'id="chart-i18n"' in html
    assert '"workouts": "Treningi"' in html
    set_lang(auth_client, "en")
    html = auth_client.get("/stats").get_data(as_text=True)
    assert '"lang": "en"' in html
    assert '"workouts": "Workouts"' in html
    assert '"bodyWeight": "Body weight"' in html


def test_builtin_validation_messages_follow_language(auth_client):
    data = {"date": "2025-01-06", "weight_kg": "500"}
    html = auth_client.post("/body/new", data=data).get_data(as_text=True)
    assert "Liczba musi mieścić się w zakresie od 20 do 400." in html
    html = auth_client.post("/body/new", data={"date": "2025-01-06", "weight_kg": "abc"}).get_data(as_text=True)
    assert "Podaj liczbę." in html
    set_lang(auth_client, "en")
    html = auth_client.post("/body/new", data=data).get_data(as_text=True)
    assert "Number must be between 20 and 400." in html
    assert "Liczba musi" not in html
    html = auth_client.post("/body/new", data={"date": "2025-01-06"}).get_data(as_text=True)
    assert "Enter at least one measurement value." in html


def test_required_and_length_messages(client):
    html = client.post("/register", data={"username": "", "password": "", "confirm": ""}).get_data(as_text=True)
    assert "To pole jest wymagane." in html
    html = client.post("/login", data={"username": "x" * 40, "password": "p"}).get_data(as_text=True)
    assert "Pole może mieć najwyżej 32 znaki." in html
    set_lang(client, "en")
    html = client.post("/register", data={"username": "ab", "password": "secret123", "confirm": "other123"})
    html = html.get_data(as_text=True)
    assert "Username must be 3 to 32 characters long." in html
    assert "Passwords do not match." in html
    html = client.post("/login", data={"username": "", "password": ""}).get_data(as_text=True)
    assert "This field is required." in html


def test_custom_parser_messages_translated(app, auth_client):
    squat = exercise_id(app, "Przysiad ze sztangą")
    html = create_workout(auth_client, [{"exercise_id": squat, "sets": "abc"}]).get_data(as_text=True)
    assert "Nie rozumiem serii „abc”" in html
    set_lang(auth_client, "en")
    html = create_workout(auth_client, [{"exercise_id": squat, "sets": "abc"}]).get_data(as_text=True)
    assert "Cannot understand the set &#34;abc&#34;" in html or 'Cannot understand the set "abc"' in html


def test_csrf_errors_follow_language():
    app = create_app({"APP_ENV": "testing", "SQLALCHEMY_DATABASE_URI": "sqlite://", "WTF_CSRF_ENABLED": True})
    client = app.test_client()
    resp = client.post("/login", data={"username": "a", "password": "b"})
    assert resp.status_code == 400
    assert "Brak tokenu CSRF." in resp.get_data(as_text=True)
    client.set_cookie(LANG_COOKIE, "en")
    html = client.post("/login", data={"username": "a", "password": "b"}).get_data(as_text=True)
    assert "The CSRF token is missing." in html
    assert "Bad request" in html


def test_static_pages_translated(auth_client):
    set_lang(auth_client, "en")
    html = auth_client.get("/body/import").get_data(as_text=True)
    assert "Import from Apple Health" in html
    assert "coming soon" in html
    assert "<em>Profile → Export All Health Data</em>" in html
    html = auth_client.get("/records/").get_data(as_text=True)
    assert "Personal records" in html


def test_english_catalogue_complete():
    builtin = set(BUILTIN_MESSAGES) | {singular for singular, _ in BUILTIN_PLURALS}
    with open(TRANSLATIONS / "en" / "LC_MESSAGES" / "messages.po", "rb") as fh:
        catalog = read_po(fh)
    missing = []
    for message in catalog:
        if not message.id:
            continue
        key = message.id if isinstance(message.id, str) else message.id[0]
        translated = message.string if isinstance(message.string, str) else all(message.string)
        if not translated and key not in builtin:
            missing.append(key)
    assert missing == []
    assert (TRANSLATIONS / "en" / "LC_MESSAGES" / "messages.mo").exists()
    assert (TRANSLATIONS / "pl" / "LC_MESSAGES" / "messages.mo").exists()

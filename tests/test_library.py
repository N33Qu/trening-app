import re
from pathlib import Path

from sqlalchemy import create_engine, func, inspect, select, text

from app import create_app, library
from app.extensions import db
from app.models import Exercise, WorkoutEntry
from app.seed import seed_catalogue

from .conftest import create_workout, exercise_id, logout, register

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"


def set_lang(client, lang):
    client.post("/lang", data={"lang": lang, "next": "/"})


def _global_count():
    return db.session.execute(select(func.count(Exercise.id)).where(Exercise.user_id.is_(None))).scalar()


# --- data -------------------------------------------------------------------

def test_library_data_is_complete():
    entries = library.entries()
    assert 120 <= len(entries) <= 160
    slugs = [e.slug for e in entries]
    assert len(slugs) == len(set(slugs))
    for e in entries:
        d = e.data
        assert d["name_pl"] and d["name_en"]
        assert d["instructions_pl"] and d["instructions_en"]
        assert d["primary"] and set(d["primary"] + d["secondary"]) <= set(library.MUSCLE_LABELS)
        assert d["equipment"] in library.EQUIPMENT_LABELS
        assert d["level"] in library.LEVEL_LABELS
        assert d["category"] in ("strength", "cardio")
        for img in d["images"]:
            assert (STATIC / img).is_file(), img
    with_images = [e for e in entries if e.images]
    assert len(with_images) >= len(entries) - 2
    total = sum((STATIC / img).stat().st_size for e in entries for img in e.images)
    assert total < 15 * 1024 * 1024


def test_every_muscle_group_used_and_drawn(auth_client):
    used = {m for e in library.entries() for m in e.primary + e.secondary}
    assert used == set(library.MUSCLE_LABELS)
    html = auth_client.get("/exercises/barbell-squat").get_data(as_text=True)
    drawn = set(re.findall(r'data-muscle="([^"]+)"', html))
    assert drawn == set(library.MUSCLE_LABELS)


# --- seeding ----------------------------------------------------------------

def test_seed_catalogue_idempotent(app):
    with app.app_context():
        assert _global_count() == len(library.entries())
        assert seed_catalogue() == 0
        assert seed_catalogue() == 0
        squat = db.session.execute(select(Exercise).where(Exercise.slug == "barbell-squat")).scalar_one()
        assert squat.name == "Przysiad ze sztangą"
        assert squat.muscle_group == "quadriceps"


def test_seed_never_touches_user_exercises(auth_client, app):
    auth_client.post("/exercises/new", data={"name": "Moje martwe", "category": "cardio", "muscle_group": "plecy"})
    with app.app_context():
        assert seed_catalogue() == 0
        own = db.session.execute(select(Exercise).where(Exercise.user_id.is_not(None))).scalar_one()
        assert (own.name, own.category, own.muscle_group, own.slug) == ("Moje martwe", "cardio", "plecy", None)


def test_seed_repairs_changed_catalogue_rows(app):
    with app.app_context():
        squat = db.session.execute(select(Exercise).where(Exercise.slug == "barbell-squat")).scalar_one()
        squat.category = "cardio"
        db.session.delete(db.session.execute(select(Exercise).where(Exercise.slug == "plank")).scalar_one())
        db.session.commit()
        assert seed_catalogue() == 2
        assert db.session.get(Exercise, squat.id).category == "strength"
        assert _global_count() == len(library.entries())


OLD_SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(32) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL, created_at DATETIME NOT NULL);
CREATE TABLE exercises (id INTEGER NOT NULL, name VARCHAR(80) NOT NULL, category VARCHAR(16) NOT NULL,
    muscle_group VARCHAR(60), user_id INTEGER, PRIMARY KEY (id),
    CONSTRAINT uq_exercise_user_name UNIQUE (user_id, name),
    CONSTRAINT ck_exercise_category CHECK (category IN ('strength', 'cardio')),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE);
CREATE TABLE workouts (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    date DATE NOT NULL, plan_day_id INTEGER, notes VARCHAR(1000), created_at DATETIME NOT NULL);
CREATE TABLE workout_entries (id INTEGER PRIMARY KEY,
    workout_id INTEGER NOT NULL REFERENCES workouts (id) ON DELETE CASCADE,
    exercise_id INTEGER NOT NULL REFERENCES exercises (id) ON DELETE CASCADE,
    position INTEGER NOT NULL, distance_km FLOAT, duration_min FLOAT);
INSERT INTO users VALUES (1, 'olduser', 'x', '2025-01-01 00:00:00');
INSERT INTO exercises VALUES (1, 'Przysiad ze sztangą', 'strength', 'nogi', NULL);
INSERT INTO exercises VALUES (2, 'Bieganie', 'cardio', NULL, NULL);
INSERT INTO exercises VALUES (3, 'Pływanie', 'cardio', NULL, NULL);
INSERT INTO exercises VALUES (4, 'Farmer walk', 'strength', 'chwyt', 1);
INSERT INTO workouts VALUES (1, 1, '2025-01-06', NULL, NULL, '2025-01-06 00:00:00');
INSERT INTO workout_entries VALUES (1, 1, 1, 0, NULL, NULL);
INSERT INTO workout_entries VALUES (2, 1, 4, 1, NULL, NULL);
INSERT INTO workout_entries VALUES (3, 1, 2, 2, 5.0, 30.0);
"""


def test_upgrade_existing_database_with_old_schema(tmp_path):
    url = f"sqlite:///{tmp_path / 'old.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        for statement in OLD_SCHEMA.strip().split(";"):
            if statement.strip():
                conn.execute(text(statement))
    engine.dispose()

    app = create_app({"APP_ENV": "testing", "SQLALCHEMY_DATABASE_URI": url})
    with app.app_context():
        columns = {c["name"] for c in inspect(db.engine).get_columns("exercises")}
        assert "slug" in columns
        assert "uq_exercises_slug" in {i["name"] for i in inspect(db.engine).get_indexes("exercises")}
        assert db.session.get(Exercise, 1).slug == "barbell-squat"
        assert db.session.get(Exercise, 2).slug == "running-treadmill"
        assert db.session.get(Exercise, 3).slug == "swimming"
        own = db.session.get(Exercise, 4)
        assert (own.name, own.slug, own.muscle_group, own.user_id) == ("Farmer walk", None, "chwyt", 1)
        assert [e.exercise_id for e in db.session.execute(select(WorkoutEntry).order_by(WorkoutEntry.id)).scalars()] \
            == [1, 4, 2]
        assert _global_count() == len(library.entries())
        db.session.remove()
        db.engine.dispose()

    # A second start (another replica or a restart) changes nothing.
    app2 = create_app({"APP_ENV": "testing", "SQLALCHEMY_DATABASE_URI": url})
    with app2.app_context():
        assert seed_catalogue() == 0
        assert _global_count() == len(library.entries())
        db.session.remove()
        db.engine.dispose()


# --- library page -----------------------------------------------------------

def _card_names(html):
    return re.findall(r'<h2 class="exercise-name">([^<]+)</h2>', html)


def test_library_lists_and_paginates(auth_client):
    html = auth_client.get("/exercises/").get_data(as_text=True)
    assert f"{len(library.entries())} ćwiczeń" in html
    assert len(_card_names(html)) == 24
    assert 'loading="lazy"' in html
    assert "/static/exercises/" in html
    assert "Free Exercise DB" in html
    page2 = auth_client.get("/exercises/?page=2").get_data(as_text=True)
    assert set(_card_names(page2)).isdisjoint(_card_names(html))
    last = auth_client.get("/exercises/?page=999")
    assert last.status_code == 200
    assert 'aria-current="page">7<' in last.get_data(as_text=True)


def test_library_search_polish_and_english(auth_client):
    html = auth_client.get("/exercises/?q=przysiad+sztang").get_data(as_text=True)
    names = _card_names(html)
    assert "Przysiad ze sztangą" in names
    assert all("rzysiad" in n for n in names)
    html = auth_client.get("/exercises/?q=bench+press").get_data(as_text=True)
    assert "Wyciskanie sztangi leżąc" in _card_names(html)
    html = auth_client.get("/exercises/?q=zzzz-nic").get_data(as_text=True)
    assert "Brak ćwiczeń spełniających kryteria" in html


def test_library_filters(auth_client):
    html = auth_client.get("/exercises/?muscle=biceps&equipment=dumbbell").get_data(as_text=True)
    names = _card_names(html)
    assert "Uginanie ramion z hantlami" in names
    assert "Uginanie ramion ze sztangą" not in names
    by_name = {e.name: e for e in library.entries()}
    for n in names:
        entry = by_name[n]
        assert entry.equipment == "dumbbell"
        assert "biceps" in entry.primary + entry.secondary
    html = auth_client.get("/exercises/?muscle=hamstrings").get_data(as_text=True)
    first = by_name[_card_names(html)[0]]
    assert "hamstrings" in first.primary
    html = auth_client.get("/exercises/?level=expert").get_data(as_text=True)
    assert all(by_name[n].level == "expert" for n in _card_names(html))
    assert 'value="expert" selected' in html
    # Unknown values are ignored instead of failing.
    html = auth_client.get("/exercises/?muscle=wings&equipment=x&level=god").get_data(as_text=True)
    assert len(_card_names(html)) == 24


def test_library_requires_login(client):
    assert client.get("/exercises/").status_code == 302
    assert client.get("/exercises/barbell-squat").status_code == 302


def test_own_exercises_listed_with_placeholder_and_private(client, app):
    register(client, "alice")
    client.post("/exercises/new", data={"name": "Sekretne ćwiczenie", "category": "strength"})
    html = client.get("/exercises/").get_data(as_text=True)
    assert "Sekretne ćwiczenie" in html
    assert "thumb-placeholder" in html
    logout(client)
    register(client, "bob")
    assert "Sekretne ćwiczenie" not in client.get("/exercises/").get_data(as_text=True)
    assert "Sekretne ćwiczenie" not in client.get("/exercises/?q=sekretne").get_data(as_text=True)


def test_custom_exercise_cannot_reuse_library_name(auth_client):
    resp = auth_client.post("/exercises/new", data={"name": "barbell back squat", "category": "strength"})
    assert "już istnieje" in resp.get_data(as_text=True)


# --- detail page ------------------------------------------------------------

def test_detail_polish(auth_client):
    resp = auth_client.get("/exercises/barbell-squat")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "<h1>Przysiad ze sztangą</h1>" in html
    assert 'class="muscle-map"' in html
    assert 'class="m is-primary" data-muscle="quadriceps"' in html
    assert 'class="m is-secondary" data-muscle="glutes"' in html
    assert 'class="m" data-muscle="chest"' in html
    assert "/static/exercises/barbell-squat/0.webp" in html
    assert "/static/exercises/barbell-squat/1.webp" in html
    assert "Wykonanie" in html and "klatce do przysiadów" in html
    assert html.count('<li>', html.index('class="steps"')) >= 5
    assert "Nie masz jeszcze zapisanych serii" in html
    assert "<script>" not in html and " onclick=" not in html
    assert auth_client.get("/static/exercises/barbell-squat/0.webp").status_code == 200


def test_detail_english(auth_client):
    set_lang(auth_client, "en")
    html = auth_client.get("/exercises/one-arm-dumbbell-row").get_data(as_text=True)
    assert "<h1>One-Arm Dumbbell Row</h1>" in html
    assert "How to do it" in html
    assert "Choose a flat bench" in html
    assert "Muscles worked" in html and "middle back" in html
    assert "Add to workout" in html
    assert 'lang="en"' in html


def test_detail_unknown_slug_404(auth_client):
    assert auth_client.get("/exercises/no-such-exercise").status_code == 404


def test_detail_without_images_uses_placeholder(auth_client):
    html = auth_client.get("/exercises/swimming").get_data(as_text=True)
    assert "Pływanie" in html
    assert "thumb-placeholder" in html
    assert "movement-frames" not in html


def test_detail_shows_own_history_only(client, app):
    register(client, "alice")
    squat = exercise_id(app, "Przysiad ze sztangą")
    create_workout(client, [{"exercise_id": squat, "sets": "5x100, 3x110"}])
    html = client.get("/exercises/barbell-squat").get_data(as_text=True)
    assert "5×100" in html and "3×110" in html
    assert "110 kg" in html
    assert f"/stats?exercise={squat}" in html
    assert f"/records/exercise/{squat}" in html
    logout(client)
    register(client, "bob")
    html = client.get("/exercises/barbell-squat").get_data(as_text=True)
    assert "5×100" not in html
    assert "Nie masz jeszcze zapisanych serii" in html


def test_detail_cardio_history(auth_client, app):
    run = exercise_id(app, "Bieganie")
    create_workout(auth_client, [{"exercise_id": run, "distance_km": "5", "duration_min": "27"}])
    html = auth_client.get("/exercises/running-treadmill").get_data(as_text=True)
    assert "5 km · 27 min" in html
    assert "/records/exercise/" not in html


# --- workout form -----------------------------------------------------------

def test_add_to_workout_preselects_exercise(auth_client, app):
    squat = exercise_id(app, "Przysiad ze sztangą")
    html = auth_client.get("/exercises/barbell-squat").get_data(as_text=True)
    assert f"/workouts/new?exercise={squat}" in html
    html = auth_client.get(f"/workouts/new?exercise={squat}").get_data(as_text=True)
    first = html[html.index('id="entries-0-exercise_id"'):html.index('id="entries-1-exercise_id"')]
    assert f'<option selected value="{squat}">' in first
    assert "<optgroup" in first and 'label="Czworogłowe uda"' in first


def test_add_to_workout_ignores_foreign_exercise(client, app):
    register(client, "alice")
    client.post("/exercises/new", data={"name": "Sekretne ćwiczenie", "category": "strength"})
    with app.app_context():
        secret = db.session.execute(select(Exercise.id).where(Exercise.user_id.is_not(None))).scalar_one()
    logout(client)
    register(client, "bob")
    html = client.get(f"/workouts/new?exercise={secret}").get_data(as_text=True)
    assert f'value="{secret}"' not in html
    first = html.split('id="entries-0-exercise_id"')[1].split("</select>")[0]
    assert first.count("<option selected") == 1 and '<option selected value="0">' in first


def test_workout_picker_groups(auth_client):
    auth_client.post("/exercises/new", data={"name": "Własne X", "category": "strength"})
    html = auth_client.get("/workouts/new").get_data(as_text=True)
    select_html = html.split('id="entries-0-exercise_id"')[1].split("</select>")[0]
    groups = re.findall(r'<optgroup label="([^"]+)"', select_html)
    assert groups[0] == "Moje ćwiczenia"
    assert "Cardio" in groups and "Rozciąganie i mobilność" in groups
    assert select_html.count("<option") == len(library.entries()) + 2

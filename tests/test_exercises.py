from sqlalchemy import select

from app.extensions import db
from app.models import Exercise

from .conftest import create_workout


def test_catalogue_seeded(auth_client, app):
    assert "Przysiad ze sztangą" in auth_client.get("/exercises/?q=barbell+back+squat").get_data(as_text=True)
    assert "Bieganie" in auth_client.get("/exercises/?q=bieganie").get_data(as_text=True)
    with app.app_context():
        cats = set(db.session.execute(select(Exercise.category)).scalars())
        assert cats == {"strength", "cardio"}


def test_custom_exercise_crud(auth_client, app):
    assert auth_client.get("/exercises/new").status_code == 200
    resp = auth_client.post("/exercises/new", data={"name": "Kettlebell swing", "category": "strength",
                                                    "muscle_group": "pośladki"}, follow_redirects=True)
    assert "Dodano ćwiczenie" in resp.get_data(as_text=True)
    resp = auth_client.post("/exercises/new", data={"name": "kettlebell SWING", "category": "strength"})
    assert "już istnieje" in resp.get_data(as_text=True)
    resp = auth_client.post("/exercises/new", data={"name": "Martwy ciąg", "category": "strength"})
    assert "już istnieje" in resp.get_data(as_text=True)

    with app.app_context():
        ex = db.session.execute(select(Exercise).where(Exercise.name == "Kettlebell swing")).scalar_one()
        ex_id = ex.id
    assert auth_client.get(f"/exercises/{ex_id}/edit").status_code == 200
    resp = auth_client.post(f"/exercises/{ex_id}/edit", data={"name": "KB swing", "category": "cardio"},
                            follow_redirects=True)
    assert "KB swing" in resp.get_data(as_text=True)
    resp = auth_client.post(f"/exercises/{ex_id}/edit", data={"name": "Bieganie", "category": "cardio"})
    assert "już istnieje" in resp.get_data(as_text=True)

    create_workout(auth_client, [{"exercise_id": ex_id, "duration_min": "10"}])
    resp = auth_client.post(f"/exercises/{ex_id}/delete", follow_redirects=True)
    assert "Nie można usunąć" in resp.get_data(as_text=True)


def test_delete_unused_custom_exercise(auth_client, app):
    auth_client.post("/exercises/new", data={"name": "Do usunięcia", "category": "strength"})
    with app.app_context():
        ex_id = db.session.execute(select(Exercise.id).where(Exercise.name == "Do usunięcia")).scalar_one()
    resp = auth_client.post(f"/exercises/{ex_id}/delete", follow_redirects=True)
    assert "Usunięto ćwiczenie" in resp.get_data(as_text=True)


def test_global_exercise_cannot_be_edited(auth_client, app):
    with app.app_context():
        ex_id = db.session.execute(select(Exercise.id).where(Exercise.user_id.is_(None))).scalars().first()
    assert auth_client.get(f"/exercises/{ex_id}/edit").status_code == 404
    assert auth_client.post(f"/exercises/{ex_id}/delete").status_code == 404


def test_picker_data_requires_login(client):
    resp = client.get("/exercises/picker.json")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_picker_data_lists_own_first_with_both_languages(auth_client):
    auth_client.post("/exercises/new", data={"name": "Zzz moje ćwiczenie", "category": "strength"})
    resp = auth_client.get("/exercises/picker.json")
    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "private, no-cache"
    items = resp.get_json()
    assert len(items) > 800
    assert items[0]["name"] == "Zzz moje ćwiczenie" and items[0]["own"] is True
    squat = next(i for i in items if i["name"] == "Przysiad ze sztangą")
    assert "Barbell" in squat["alt"] and squat["thumb"].endswith(".webp")
    assert {"id", "name", "alt", "group", "order", "own", "thumb"} <= set(squat)
    ids = [i["id"] for i in items]
    assert len(ids) == len(set(ids))


def test_picker_data_hides_other_users_exercises(client):
    from .conftest import login, register
    register(client, "owner")
    client.post("/exercises/new", data={"name": "Sekret właściciela", "category": "strength"})
    client.post("/logout")
    register(client, "other")
    login(client, "other")
    names = {i["name"] for i in client.get("/exercises/picker.json").get_json()}
    assert "Sekret właściciela" not in names


def test_forms_expose_picker_hooks(auth_client):
    html = auth_client.get("/workouts/new").get_data(as_text=True)
    assert 'data-picker-url="/exercises/picker.json"' in html
    assert "<optgroup" in html

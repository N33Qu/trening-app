from sqlalchemy import select

from app.extensions import db
from app.models import Exercise

from .conftest import create_workout


def test_catalogue_seeded(auth_client, app):
    html = auth_client.get("/exercises/").get_data(as_text=True)
    assert "Przysiad ze sztangą" in html
    assert "Bieganie" in html
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

from sqlalchemy import select

from app.extensions import db
from app.models import Plan, PlanDay, PlanExercise

from .conftest import create_workout, exercise_id


def test_plan_crud(auth_client, app):
    resp = auth_client.post("/plans/new", data={"name": "FBW", "description": "Opis", "is_active": "y"},
                            follow_redirects=True)
    assert "Utworzono plan" in resp.get_data(as_text=True)
    with app.app_context():
        plan_id = db.session.execute(select(Plan.id)).scalar_one()

    resp = auth_client.post(f"/plans/{plan_id}/days", data={"weekday": "2", "name": "Śr – nogi"},
                            follow_redirects=True)
    assert "Śr – nogi" in resp.get_data(as_text=True)
    with app.app_context():
        day_id = db.session.execute(select(PlanDay.id)).scalar_one()

    squat = exercise_id(app, "Przysiad ze sztangą")
    resp = auth_client.post(f"/plans/days/{day_id}/exercises", data={
        "exercise_id": str(squat), "target_sets": "5", "target_reps": "5", "target_weight": "100"},
        follow_redirects=True)
    html = resp.get_data(as_text=True)
    assert "Przysiad ze sztangą" in html
    assert "5 × 5 × 100 kg" in html

    resp = auth_client.post(f"/plans/days/{day_id}/exercises", data={
        "exercise_id": str(squat), "target_sets": "0", "target_reps": "5"}, follow_redirects=True)
    assert "Popraw dane ćwiczenia" in resp.get_data(as_text=True)
    resp = auth_client.post(f"/plans/{plan_id}/days", data={"weekday": "2", "name": ""}, follow_redirects=True)
    assert "Popraw dane dnia" in resp.get_data(as_text=True)

    assert "FBW" in auth_client.get("/plans/").get_data(as_text=True)
    assert auth_client.get(f"/plans/{plan_id}/edit").status_code == 200
    resp = auth_client.post(f"/plans/{plan_id}/edit", data={"name": "FBW 2"}, follow_redirects=True)
    assert "FBW 2" in resp.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Plan, plan_id).is_active is False

    with app.app_context():
        item_id = db.session.execute(select(PlanExercise.id)).scalar_one()
    auth_client.post(f"/plans/exercises/{item_id}/delete")
    auth_client.post(f"/plans/days/{day_id}/delete")
    with app.app_context():
        assert db.session.execute(select(PlanDay)).first() is None
    auth_client.post(f"/plans/{plan_id}/delete")
    with app.app_context():
        assert db.session.execute(select(Plan)).first() is None
    assert auth_client.post("/plans/exercises/999/delete").status_code == 404


def test_plan_completion_on_dashboard(auth_client, app):
    from datetime import date, timedelta

    bench = exercise_id(app, "Wyciskanie sztangi leżąc")
    auth_client.post("/plans/new", data={"name": "Plan", "is_active": "y"})
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    auth_client.post("/plans/1/days", data={"weekday": str(today.weekday()), "name": "Dzień A"})
    auth_client.post("/plans/1/days", data={"weekday": "6", "name": "Dzień B"})
    html = auth_client.get("/").get_data(as_text=True)
    assert "0%" in html
    create_workout(auth_client, [{"exercise_id": bench, "sets": "5x50"}], date=monday.isoformat(), plan_day_id=1)
    html = auth_client.get("/").get_data(as_text=True)
    assert "50%" in html
    assert "1 z 2 dni" in html

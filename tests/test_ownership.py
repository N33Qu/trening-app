from sqlalchemy import select

from app.extensions import db
from app.models import BodyMeasurement, Exercise, Plan, Workout

from .conftest import create_workout, exercise_id, login, logout, register


def _setup_alice(client, app):
    register(client, "alice")
    bench = exercise_id(app, "Wyciskanie sztangi leżąc")
    create_workout(client, [{"exercise_id": bench, "sets": "5x80"}])
    client.post("/plans/new", data={"name": "Plan Alicji", "is_active": "y"})
    client.post("/plans/1/days", data={"weekday": "0", "name": "Pon"})
    client.post("/plans/days/1/exercises", data={
        "exercise_id": str(bench), "target_sets": "3", "target_reps": "5", "target_weight": "80"})
    client.post("/body/new", data={"date": "2025-01-01", "weight_kg": "70"})
    client.post("/exercises/new", data={"name": "Sekretne ćwiczenie", "category": "strength"})
    with app.app_context():
        ids = {
            "workout": db.session.execute(select(Workout.id)).scalar_one(),
            "plan": db.session.execute(select(Plan.id)).scalar_one(),
            "body": db.session.execute(select(BodyMeasurement.id)).scalar_one(),
            "exercise": db.session.execute(select(Exercise.id).where(Exercise.user_id.is_not(None))).scalar_one(),
        }
    logout(client)
    return ids


def test_user_b_cannot_access_user_a_objects(client, app):
    ids = _setup_alice(client, app)
    register(client, "bob")

    for url in [
        f"/workouts/{ids['workout']}",
        f"/workouts/{ids['workout']}/edit",
        f"/plans/{ids['plan']}",
        f"/plans/{ids['plan']}/edit",
        f"/body/{ids['body']}/edit",
        f"/exercises/{ids['exercise']}/edit",
        f"/records/exercise/{ids['exercise']}",
        "/workouts/new?plan_day=1",
    ]:
        assert client.get(url).status_code == 404, url

    for url in [
        f"/workouts/{ids['workout']}/delete",
        f"/workouts/{ids['workout']}/edit",
        f"/plans/{ids['plan']}/delete",
        f"/plans/{ids['plan']}/days",
        "/plans/days/1/delete",
        "/plans/days/1/exercises",
        "/plans/exercises/1/delete",
        f"/body/{ids['body']}/delete",
        f"/exercises/{ids['exercise']}/delete",
    ]:
        assert client.post(url, data={"weekday": "1", "name": "x"}).status_code == 404, url

    # Lists do not leak other user's data.
    assert "Plan Alicji" not in client.get("/plans/").get_data(as_text=True)
    assert "Sekretne ćwiczenie" not in client.get("/exercises/").get_data(as_text=True)
    assert "Sekretne ćwiczenie" not in client.get("/workouts/new").get_data(as_text=True)
    assert "Brak rekordów" in client.get("/records/").get_data(as_text=True)
    assert "Brak pomiarów" in client.get("/body/").get_data(as_text=True)

    # Bob cannot log a workout with Alice's custom exercise or plan day.
    resp = create_workout(client, [{"exercise_id": ids["exercise"], "sets": "5x5"}])
    assert "Not a valid choice" in resp.get_data(as_text=True) or resp.status_code == 200
    with app.app_context():
        assert db.session.execute(select(Workout).where(Workout.user_id == 2)).first() is None
    resp = create_workout(client, [{"exercise_id": exercise_id(app, "Martwy ciąg"), "sets": "5x5"}], plan_day_id=1)
    with app.app_context():
        assert db.session.execute(select(Workout).where(Workout.user_id == 2)).first() is None

    # Alice's data is untouched.
    logout(client)
    login(client, "alice")
    assert client.get(f"/workouts/{ids['workout']}").status_code == 200
    assert client.get(f"/plans/{ids['plan']}").status_code == 200


def test_anonymous_redirected_to_login(client):
    for url in ["/workouts/", "/plans/", "/body/", "/records/", "/stats", "/exercises/"]:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

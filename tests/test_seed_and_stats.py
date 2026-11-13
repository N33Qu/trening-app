from sqlalchemy import func, select

from app.extensions import db
from app.models import BodyMeasurement, Exercise, PersonalRecord, Plan, User, Workout
from app.seed import seed_catalogue, seed_demo

from .conftest import login


def _counts():
    return {
        "users": db.session.execute(select(func.count(User.id))).scalar(),
        "workouts": db.session.execute(select(func.count(Workout.id))).scalar(),
        "plans": db.session.execute(select(func.count(Plan.id))).scalar(),
        "records": db.session.execute(select(func.count(PersonalRecord.id))).scalar(),
        "body": db.session.execute(select(func.count(BodyMeasurement.id))).scalar(),
        "exercises": db.session.execute(select(func.count(Exercise.id))).scalar(),
    }


def test_seed_demo_idempotent(app):
    with app.app_context():
        assert seed_demo() is True
        first = _counts()
        assert first["users"] == 1
        assert first["workouts"] >= 20
        assert first["plans"] == 1
        assert first["records"] >= 5
        assert first["body"] >= 8
        assert seed_demo() is False
        assert seed_catalogue() == 0
        assert _counts() == first


def test_seed_demo_cli_idempotent(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["seed-demo"])
    assert result.exit_code == 0
    assert "Utworzono konto demo" in result.output
    with app.app_context():
        first = _counts()
    result = runner.invoke(args=["seed-demo"])
    assert result.exit_code == 0
    assert "już istnieje" in result.output
    with app.app_context():
        assert _counts() == first


def test_seed_demo_on_startup():
    from app import create_app

    app = create_app({"APP_ENV": "testing", "SQLALCHEMY_DATABASE_URI": "sqlite://", "SEED_DEMO": True})
    with app.app_context():
        assert db.session.execute(select(User).where(User.username == "demo")).scalar_one()


def test_demo_pages_render(app, client):
    with app.app_context():
        seed_demo()
    resp = login(client, "demo", "demo1234")
    assert "Witaj, demo" in resp.get_data(as_text=True)
    with app.app_context():
        squat = db.session.execute(select(Exercise.id).where(Exercise.name == "Przysiad ze sztangą")).scalar_one()
        run = db.session.execute(select(Exercise.id).where(Exercise.name == "Bieganie")).scalar_one()
        workout = db.session.execute(select(Workout.id)).scalars().first()
    pages = ["/", "/stats", f"/stats?exercise={squat}", f"/stats?exercise={run}", "/workouts/", "/workouts/?page=2",
             f"/workouts/{workout}", "/plans/", "/plans/1", "/records/", f"/records/exercise/{squat}", "/body/",
             "/exercises/", "/workouts/new", "/workouts/new?plan_day=1", "/body/import"]
    for url in pages:
        resp = client.get(url)
        assert resp.status_code == 200, url
    html = client.get(f"/stats?exercise={squat}").get_data(as_text=True)
    assert 'data-chart="progress"' in html
    assert '"e1rm"' in html
    html = client.get("/").get_data(as_text=True)
    assert "Realizacja planu" in html


def test_stats_empty_user(auth_client):
    html = auth_client.get("/stats").get_data(as_text=True)
    assert "Brak danych do wykresów" in html
    html = auth_client.get("/").get_data(as_text=True)
    assert "Nie masz jeszcze żadnych treningów" in html


def test_stats_helpers(app):
    from datetime import date

    from app.blueprints.stats import plan_completion, workouts_per_week

    with app.app_context():
        seed_demo(today=date(2025, 6, 18))
        uid = db.session.execute(select(User.id)).scalar_one()
        weekly = workouts_per_week(uid, today=date(2025, 6, 18))
        assert len(weekly["labels"]) == 12
        assert sum(weekly["values"]) > 15
        completion = plan_completion(uid, today=date(2025, 6, 18))
        assert completion["total"] == 3
        assert completion["done"] == 2
        assert completion["percent"] == 67

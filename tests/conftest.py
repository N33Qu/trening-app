import os
import re

import pytest

os.environ["APP_ENV"] = "testing"
os.environ.pop("PROMETHEUS_MULTIPROC_DIR", None)
os.environ.pop("DATABASE_URL", None)
os.environ.pop("SEED_DEMO", None)

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402


@pytest.fixture()
def app():
    app = create_app({"APP_ENV": "testing", "SQLALCHEMY_DATABASE_URI": "sqlite://", "APP_VERSION": "1.2.3-test"})
    from app.blueprints.auth import throttle

    throttle._failures.clear()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, username="alice", password="secret123"):
    return client.post(
        "/register",
        data={"username": username, "password": password, "confirm": password},
        follow_redirects=True,
    )


def login(client, username="alice", password="secret123"):
    return client.post("/login", data={"username": username, "password": password}, follow_redirects=True)


def logout(client):
    return client.post("/logout", follow_redirects=True)


@pytest.fixture()
def auth_client(client):
    register(client)
    return client


def exercise_id(app, name):
    from sqlalchemy import select

    from app.models import Exercise

    with app.app_context():
        return db.session.execute(select(Exercise.id).where(Exercise.name == name)).scalar_one()


def create_workout(client, entries, date="2025-01-06", plan_day_id=0, notes="", follow=True):
    data = {"date": date, "plan_day_id": str(plan_day_id), "notes": notes}
    for i, entry in enumerate(entries):
        data[f"entries-{i}-exercise_id"] = str(entry.get("exercise_id", 0))
        data[f"entries-{i}-sets"] = entry.get("sets", "")
        data[f"entries-{i}-distance_km"] = entry.get("distance_km", "")
        data[f"entries-{i}-duration_min"] = entry.get("duration_min", "")
    return client.post("/workouts/new", data=data, follow_redirects=follow)


def extract_csrf(html):
    match = re.search(r'name="csrf_token" type="hidden" value="([^"]+)"', html) or re.search(
        r'name="csrf_token" value="([^"]+)"', html
    )
    return match.group(1) if match else None

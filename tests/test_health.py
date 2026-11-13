from unittest.mock import patch

from sqlalchemy.exc import OperationalError

from .conftest import create_workout, exercise_id


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "version": "1.2.3-test"}


def test_readyz_ok(client):
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.get_json()["database"] == "up"


def test_readyz_db_down(client):
    from app.extensions import db

    def boom(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("down"))

    with patch.object(db.session, "execute", side_effect=boom):
        resp = client.get("/readyz")
    assert resp.status_code == 503
    assert resp.get_json()["status"] == "unavailable"


def test_metrics_endpoint(client):
    client.get("/healthz")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/plain")
    body = resp.get_data(as_text=True)
    assert "flask_http_request_duration_seconds" in body
    assert "flask_http_request_total" in body
    assert "trening_users_total 0.0" in body
    assert "trening_workouts_total 0.0" in body
    assert "trening_personal_records_total 0.0" in body
    assert "trening_db_up 1.0" in body


def test_metrics_count_business_data(auth_client, app):
    squat = exercise_id(app, "Przysiad ze sztangą")
    create_workout(auth_client, [{"exercise_id": squat, "sets": "5x100"}])
    body = auth_client.get("/metrics").get_data(as_text=True)
    assert "trening_users_total 1.0" in body
    assert "trening_workouts_total 1.0" in body
    assert "trening_personal_records_total 2.0" in body


def test_metrics_survive_db_failure(client):
    from app.extensions import db

    with patch.object(db.session, "execute", side_effect=OperationalError("x", {}, Exception("down"))):
        body = client.get("/metrics").get_data(as_text=True)
    assert "trening_db_up 0.0" in body


def test_unknown_page_404(client):
    resp = client.get("/nope")
    assert resp.status_code == 404
    assert "Nie znaleziono" in resp.get_data(as_text=True)

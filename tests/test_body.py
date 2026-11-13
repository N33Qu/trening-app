from sqlalchemy import select

from app.extensions import db
from app.models import BodyMeasurement


def test_body_measurement_crud(auth_client, app):
    assert auth_client.get("/body/new").status_code == 200
    resp = auth_client.post("/body/new", data={
        "date": "2025-03-01", "weight_kg": "82.4", "waist_cm": "88", "body_fat_pct": "18.5"},
        follow_redirects=True)
    html = resp.get_data(as_text=True)
    assert "Zapisano pomiar" in html
    assert "82.4" in html
    auth_client.post("/body/new", data={"date": "2025-03-08", "weight_kg": "81.9"})

    with app.app_context():
        rows = db.session.execute(select(BodyMeasurement).order_by(BodyMeasurement.date)).scalars().all()
        assert [r.weight_kg for r in rows] == [82.4, 81.9]
        assert rows[0].source == "manual"
        assert rows[0].waist_cm == 88
        mid = rows[0].id

    html = auth_client.get("/body/").get_data(as_text=True)
    assert "-0.5 kg" in html
    assert 'id="chart-data"' in html

    assert auth_client.get(f"/body/{mid}/edit").status_code == 200
    resp = auth_client.post(f"/body/{mid}/edit", data={"date": "2025-03-01", "weight_kg": "83", "waist_cm": ""},
                            follow_redirects=True)
    assert "Zapisano zmiany" in resp.get_data(as_text=True)
    with app.app_context():
        m = db.session.get(BodyMeasurement, mid)
        assert m.weight_kg == 83
        assert m.waist_cm is None

    auth_client.post(f"/body/{mid}/delete")
    with app.app_context():
        assert db.session.get(BodyMeasurement, mid) is None


def test_body_measurement_validation(auth_client):
    html = auth_client.post("/body/new", data={"date": "2025-03-01"}).get_data(as_text=True)
    assert "co najmniej jedną wartość" in html
    html = auth_client.post("/body/new", data={"date": "2025-03-01", "weight_kg": "5"}).get_data(as_text=True)
    assert "Zapisano pomiar" not in html


def test_import_placeholder(auth_client):
    html = auth_client.get("/body/import").get_data(as_text=True)
    assert "Apple Health" in html
    assert "planowana" in html

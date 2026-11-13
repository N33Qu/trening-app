from sqlalchemy import select

from app.extensions import db
from app.models import PR_E1RM, PR_MAX_WEIGHT, PersonalRecord, Workout

from .conftest import create_workout, exercise_id


def _records(app, kind=None):
    with app.app_context():
        q = select(PersonalRecord).order_by(PersonalRecord.id)
        if kind:
            q = q.where(PersonalRecord.kind == kind)
        return [(r.exercise.name, r.kind, r.value) for r in db.session.execute(q).scalars()]


def test_workout_crud(auth_client, app):
    bench = exercise_id(app, "Wyciskanie sztangi leżąc")
    run = exercise_id(app, "Bieganie")
    resp = create_workout(auth_client, [
        {"exercise_id": bench, "sets": "5x80, 5x80, 3x5x75"},
        {"exercise_id": run, "distance_km": "5.2", "duration_min": "28"},
    ], notes="Pierwszy trening")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Zapisano trening" in html
    assert "Pierwszy trening" in html
    assert "5.2 km" in html
    with app.app_context():
        w = db.session.execute(select(Workout)).scalar_one()
        assert len(w.entries) == 2
        assert len(w.entries[0].sets) == 5
        assert w.total_volume == 5 * 80 * 2 + 3 * 5 * 75
        wid = w.id

    assert auth_client.get("/workouts/").status_code == 200
    assert auth_client.get(f"/workouts/{wid}/edit").status_code == 200

    resp = auth_client.post(f"/workouts/{wid}/edit", data={
        "date": "2025-01-07", "plan_day_id": "0", "notes": "Zmienione",
        "entries-0-exercise_id": str(bench), "entries-0-sets": "3x90",
    }, follow_redirects=True)
    assert "Zapisano zmiany" in resp.get_data(as_text=True)
    with app.app_context():
        w = db.session.get(Workout, wid)
        assert w.notes == "Zmienione"
        assert len(w.entries) == 1

    resp = auth_client.post(f"/workouts/{wid}/delete", follow_redirects=True)
    assert "Usunięto trening" in resp.get_data(as_text=True)
    with app.app_context():
        assert db.session.execute(select(Workout)).first() is None
        assert db.session.execute(select(PersonalRecord)).first() is None


def test_workout_validation_errors(auth_client, app):
    bench = exercise_id(app, "Wyciskanie sztangi leżąc")
    run = exercise_id(app, "Bieganie")
    html = create_workout(auth_client, [{"exercise_id": bench, "sets": "abc"}]).get_data(as_text=True)
    assert "Nie rozumiem serii" in html
    html = create_workout(auth_client, [{"exercise_id": bench, "sets": ""}]).get_data(as_text=True)
    assert "Podaj serie" in html
    html = create_workout(auth_client, [{"exercise_id": run}]).get_data(as_text=True)
    assert "Podaj dystans lub czas" in html
    html = create_workout(auth_client, [{"exercise_id": 0, "sets": "5x5"}]).get_data(as_text=True)
    assert "Wybierz ćwiczenie" in html
    html = create_workout(auth_client, [{"exercise_id": 0}]).get_data(as_text=True)
    assert "co najmniej jedno ćwiczenie" in html
    html = create_workout(auth_client, [{"exercise_id": bench, "sets": "5x5"}], date="2999-01-01").get_data(
        as_text=True)
    assert "przyszłości" in html
    with app.app_context():
        assert db.session.execute(select(Workout)).first() is None


def test_personal_record_detection(auth_client, app):
    squat = exercise_id(app, "Przysiad ze sztangą")
    resp = create_workout(auth_client, [{"exercise_id": squat, "sets": "5x100, 5x100"}], date="2025-01-06")
    html = resp.get_data(as_text=True)
    assert html.count("Nowy rekord!") == 2
    assert _records(app) == [
        ("Przysiad ze sztangą", PR_MAX_WEIGHT, 100.0),
        ("Przysiad ze sztangą", PR_E1RM, 116.7),
    ]

    # Same weights -> no new record.
    html = create_workout(auth_client, [{"exercise_id": squat, "sets": "5x100"}], date="2025-01-08").get_data(
        as_text=True)
    assert "Nowy rekord!" not in html

    # Heavier single -> max weight PR, but e1RM 110 < 116.7 -> no e1RM PR.
    html = create_workout(auth_client, [{"exercise_id": squat, "sets": "1x110"}], date="2025-01-10").get_data(
        as_text=True)
    assert html.count("Nowy rekord!") == 1
    assert ("Przysiad ze sztangą", PR_MAX_WEIGHT, 110.0) in _records(app)

    # More reps at 105 -> e1RM PR only.
    html = create_workout(auth_client, [{"exercise_id": squat, "sets": "6x105"}], date="2025-01-13").get_data(
        as_text=True)
    assert html.count("Nowy rekord!") == 1
    assert _records(app, PR_E1RM)[-1] == ("Przysiad ze sztangą", PR_E1RM, 126.0)

    page = auth_client.get("/records/").get_data(as_text=True)
    assert "Przysiad ze sztangą" in page
    assert "126" in page
    assert auth_client.get(f"/records/exercise/{squat}").status_code == 200

    metrics = auth_client.get("/metrics").get_data(as_text=True)
    assert "trening_personal_records_total 4.0" in metrics


def test_bodyweight_and_cardio_do_not_create_records(auth_client, app):
    pullup = exercise_id(app, "Podciąganie na drążku")
    run = exercise_id(app, "Bieganie")
    create_workout(auth_client, [
        {"exercise_id": pullup, "sets": "10, 8, 8"},
        {"exercise_id": run, "distance_km": "5", "sets": ""},
    ])
    assert _records(app) == []


def test_editing_workout_does_not_duplicate_records(auth_client, app):
    bench = exercise_id(app, "Wyciskanie sztangi leżąc")
    create_workout(auth_client, [{"exercise_id": bench, "sets": "5x80"}])
    with app.app_context():
        wid = db.session.execute(select(Workout.id)).scalar_one()
    resp = auth_client.post(f"/workouts/{wid}/edit", data={
        "date": "2025-01-06", "plan_day_id": "0",
        "entries-0-exercise_id": str(bench), "entries-0-sets": "5x80",
    }, follow_redirects=True)
    assert "Nowy rekord!" not in resp.get_data(as_text=True)
    assert len(_records(app)) == 2


def test_new_workout_from_plan_day_prefills(auth_client, app):
    bench = exercise_id(app, "Wyciskanie sztangi leżąc")
    auth_client.post("/plans/new", data={"name": "Plan A", "is_active": "y"})
    auth_client.post("/plans/1/days", data={"weekday": "0", "name": "Pon – klatka"})
    auth_client.post("/plans/days/1/exercises", data={
        "exercise_id": str(bench), "target_sets": "5", "target_reps": "5", "target_weight": "80"})
    html = auth_client.get("/workouts/new?plan_day=1").get_data(as_text=True)
    assert 'value="5x5x80"' in html
    resp = create_workout(auth_client, [{"exercise_id": bench, "sets": "5x5x80"}], plan_day_id=1)
    assert "Pon – klatka" in resp.get_data(as_text=True)


def test_pagination(auth_client, app):
    bench = exercise_id(app, "Wyciskanie sztangi leżąc")
    for day in range(1, 18):
        create_workout(auth_client, [{"exercise_id": bench, "sets": "5x50"}], date=f"2025-02-{day:02d}", follow=False)
    page1 = auth_client.get("/workouts/").get_data(as_text=True)
    assert "Strona 1 z 2" in page1
    page2 = auth_client.get("/workouts/?page=2").get_data(as_text=True)
    assert "Strona 2 z 2" in page2


def test_running_pace_shown_as_minutes_and_seconds(auth_client, app):
    run = exercise_id(app, "Bieganie")
    resp = create_workout(auth_client, [{"exercise_id": run, "distance_km": "5", "duration_min": "27"}])
    html = resp.get_data(as_text=True)
    assert "5:24 min/km" in html
    assert "5.40 min/km" not in html


def test_set_chips_do_not_wrap_inside():
    from pathlib import Path

    css = (Path(__file__).resolve().parent.parent / "app" / "static" / "css" / "style.css").read_text()
    chip_rule = next(line for line in css.splitlines() if line.startswith(".set-chip {"))
    assert "white-space: nowrap" in chip_rule

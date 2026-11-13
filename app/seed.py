import logging
import random
from contextlib import contextmanager
from datetime import date, timedelta

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .i18n import N_
from .models import (
    CATEGORY_CARDIO,
    CATEGORY_STRENGTH,
    BodyMeasurement,
    Exercise,
    Plan,
    PlanDay,
    PlanExercise,
    User,
    Workout,
    WorkoutEntry,
    WorkoutSet,
)

log = logging.getLogger(__name__)

ADVISORY_LOCK_KEY = 72_810_001
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo1234"

CATALOGUE = [
    (N_("Przysiad ze sztangą"), CATEGORY_STRENGTH, N_("nogi")),
    (N_("Wyciskanie sztangi leżąc"), CATEGORY_STRENGTH, N_("klatka")),
    (N_("Martwy ciąg"), CATEGORY_STRENGTH, N_("plecy / nogi")),
    (N_("Wyciskanie żołnierskie"), CATEGORY_STRENGTH, N_("barki")),
    (N_("Podciąganie na drążku"), CATEGORY_STRENGTH, N_("plecy")),
    (N_("Wiosłowanie sztangą"), CATEGORY_STRENGTH, N_("plecy")),
    (N_("Wyciskanie hantli na skosie"), CATEGORY_STRENGTH, N_("klatka")),
    (N_("Pompki na poręczach (dipy)"), CATEGORY_STRENGTH, N_("klatka / triceps")),
    (N_("Rumuński martwy ciąg"), CATEGORY_STRENGTH, N_("dwugłowe uda")),
    (N_("Wykroki z hantlami"), CATEGORY_STRENGTH, N_("nogi")),
    (N_("Hip thrust"), CATEGORY_STRENGTH, N_("pośladki")),
    (N_("Uginanie ramion ze sztangą"), CATEGORY_STRENGTH, N_("biceps")),
    (N_("Prostowanie ramion na wyciągu"), CATEGORY_STRENGTH, N_("triceps")),
    (N_("Ściąganie drążka wyciągu"), CATEGORY_STRENGTH, N_("plecy")),
    (N_("Wznosy bokiem z hantlami"), CATEGORY_STRENGTH, N_("barki")),
    (N_("Pompki"), CATEGORY_STRENGTH, N_("klatka")),
    (N_("Bieganie"), CATEGORY_CARDIO, None),
    (N_("Rower"), CATEGORY_CARDIO, None),
    (N_("Ergometr wioślarski"), CATEGORY_CARDIO, None),
    (N_("Pływanie"), CATEGORY_CARDIO, None),
    (N_("Skakanka"), CATEGORY_CARDIO, None),
]


@contextmanager
def advisory_lock():
    """Serialize schema creation / seeding across replicas (PostgreSQL only)."""
    if db.engine.dialect.name != "postgresql":
        yield
        return
    with db.engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": ADVISORY_LOCK_KEY})
        conn.commit()
        try:
            yield
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": ADVISORY_LOCK_KEY})
            conn.commit()


def seed_catalogue():
    existing = set(
        db.session.execute(select(Exercise.name).where(Exercise.user_id.is_(None))).scalars()
    )
    added = 0
    for name, category, group in CATALOGUE:
        if name not in existing:
            db.session.add(Exercise(name=name, category=category, muscle_group=group, user_id=None))
            added += 1
    if added:
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
    return added


def _exercise(name):
    return db.session.execute(
        select(Exercise).where(Exercise.name == name, Exercise.user_id.is_(None))
    ).scalar_one()


def _round_plate(value):
    return round(value / 2.5) * 2.5


def seed_demo(today=None):
    """Create the demo account with ~8 weeks of data. Returns True if created."""
    from .services import detect_personal_records

    if db.session.execute(select(User).where(User.username == DEMO_USERNAME)).scalar_one_or_none():
        return False
    seed_catalogue()
    rng = random.Random(20251)
    today = today or date.today()

    try:
        user = User(username=DEMO_USERNAME)
        user.set_password(DEMO_PASSWORD)
        db.session.add(user)
        db.session.flush()

        squat = _exercise("Przysiad ze sztangą")
        bench = _exercise("Wyciskanie sztangi leżąc")
        deadlift = _exercise("Martwy ciąg")
        ohp = _exercise("Wyciskanie żołnierskie")
        pullup = _exercise("Podciąganie na drążku")
        row = _exercise("Wiosłowanie sztangą")
        dips = _exercise("Pompki na poręczach (dipy)")
        lunges = _exercise("Wykroki z hantlami")
        running = _exercise("Bieganie")

        custom = Exercise(name="Farmer walk", category=CATEGORY_STRENGTH, muscle_group="chwyt", user_id=user.id)
        db.session.add(custom)

        plan = Plan(
            user_id=user.id,
            name="Siła 3 dni (Push / Nogi / Pull)",
            description="Trzy treningi tygodniowo, progresja liniowa +2,5 kg na górę i +5 kg na dół.",
            is_active=True,
        )
        day_push = PlanDay(weekday=0, name="Pon – klatka i barki")
        day_legs = PlanDay(weekday=2, name="Śr – nogi")
        day_pull = PlanDay(weekday=4, name="Pt – plecy")
        plan.days = [day_push, day_legs, day_pull]
        db.session.add(plan)

        start = {"bench": 70.0, "ohp": 42.5, "dips": 0.0, "squat": 95.0, "lunges": 16.0,
                 "deadlift": 120.0, "row": 60.0, "pullup": 0.0}
        week_step = {"bench": 2.5, "ohp": 1.25, "squat": 5.0, "deadlift": 5.0, "row": 2.5, "lunges": 1.0}

        day_push.exercises = [
            PlanExercise(exercise=bench, target_sets=5, target_reps=5, target_weight=start["bench"] + 20, position=0),
            PlanExercise(exercise=ohp, target_sets=3, target_reps=8, target_weight=start["ohp"] + 10, position=1),
            PlanExercise(exercise=dips, target_sets=3, target_reps=10, target_weight=0, position=2),
        ]
        day_legs.exercises = [
            PlanExercise(exercise=squat, target_sets=5, target_reps=5, target_weight=start["squat"] + 40, position=0),
            PlanExercise(exercise=lunges, target_sets=3, target_reps=10, target_weight=24, position=1),
        ]
        day_pull.exercises = [
            PlanExercise(exercise=deadlift, target_sets=3, target_reps=5, target_weight=start["deadlift"] + 40,
                         position=0),
            PlanExercise(exercise=pullup, target_sets=4, target_reps=8, target_weight=0, position=1),
            PlanExercise(exercise=row, target_sets=4, target_reps=8, target_weight=start["row"] + 20, position=2),
        ]
        db.session.flush()

        monday = today - timedelta(days=today.weekday())
        first_monday = monday - timedelta(weeks=8)
        skipped = {(2, 4), (5, 2)}

        def entry(exercise, sets, position, distance=None, duration=None):
            e = WorkoutEntry(exercise=exercise, position=position, distance_km=distance, duration_min=duration)
            e.sets = [WorkoutSet(set_no=i + 1, reps=r, weight_kg=w) for i, (r, w) in enumerate(sets)]
            return e

        workouts = []
        for week in range(9):
            week_start = first_monday + timedelta(weeks=week)
            for weekday, day in ((0, day_push), (2, day_legs), (4, day_pull), (5, None)):
                wdate = week_start + timedelta(days=weekday)
                if wdate > today or (week, weekday) in skipped:
                    continue

                def w(key, _week=week):
                    jitter = rng.choice([0, 0, 0, 2.5, -2.5])
                    return _round_plate(start[key] + week_step.get(key, 0) * _week + jitter)

                if weekday == 0:
                    b = w("bench")
                    entries = [
                        entry(bench, [(5, b)] * 4 + [(rng.choice([4, 5, 6]), b)], 0),
                        entry(ohp, [(8, w("ohp"))] * 3, 1),
                        entry(dips, [(10 + week // 3, 0)] * 3, 2),
                    ]
                    notes = "Dobra technika, pauza na klatce." if week % 3 == 0 else None
                elif weekday == 2:
                    s = w("squat")
                    entries = [
                        entry(squat, [(5, s)] * 5, 0),
                        entry(lunges, [(10, start["lunges"] + week)] * 3, 1),
                    ]
                    notes = "Ciężko, ale wszystkie serie zaliczone." if week == 6 else None
                elif weekday == 4:
                    d = w("deadlift")
                    entries = [
                        entry(deadlift, [(5, d)] * 2 + [(rng.choice([3, 5]), d + 5)], 0),
                        entry(pullup, [(6 + week // 2, 0)] * 4, 1),
                        entry(row, [(8, w("row"))] * 4, 2),
                    ]
                    if week in (3, 7):
                        entries.append(entry(custom, [(1, 2 * 32)] * 3, 3))
                    notes = None
                else:
                    if week % 2:
                        continue
                    dist = round(5 + week * 0.4 + rng.uniform(-0.3, 0.3), 1)
                    entries = [entry(running, [], 0, distance=dist, duration=round(dist * rng.uniform(5.4, 6.0), 0))]
                    notes = "Spokojne wybieganie."
                wk = Workout(user_id=user.id, date=wdate, plan_day=day, notes=notes)
                wk.entries = entries
                db.session.add(wk)
                workouts.append(wk)

            bdate = week_start + timedelta(days=rng.choice([0, 1]))
            if bdate <= today:
                weight = round(84.0 - 0.35 * week + rng.uniform(-0.3, 0.3), 1)
                db.session.add(BodyMeasurement(
                    user_id=user.id,
                    date=bdate,
                    weight_kg=weight,
                    waist_cm=round(90 - 0.4 * week, 1) if week % 2 == 0 else None,
                    chest_cm=104.0 if week % 4 == 0 else None,
                    arm_cm=37.5 + (0.5 if week >= 4 else 0) if week % 4 == 0 else None,
                    thigh_cm=60.0 if week % 4 == 0 else None,
                    body_fat_pct=round(19.5 - 0.25 * week, 1) if week % 2 == 0 else None,
                    source="manual",
                ))

        db.session.flush()
        for wk in sorted(workouts, key=lambda x: x.date):
            detect_personal_records(wk, count_metric=False)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        log.info("demo account created concurrently by another instance")
        return False
    log.info("demo account created with %d workouts", len(workouts))
    return True

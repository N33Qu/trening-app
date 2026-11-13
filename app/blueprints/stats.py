from collections import Counter, OrderedDict
from datetime import date, timedelta

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func, select

from ..extensions import db
from ..models import (
    BodyMeasurement,
    Exercise,
    PersonalRecord,
    Plan,
    PlanDay,
    Workout,
    WorkoutEntry,
    WorkoutSet,
)
from ..services import epley, visible_exercise

bp = Blueprint("stats", __name__)

WEEKS = 12


def week_start(d):
    return d - timedelta(days=d.weekday())


def workouts_per_week(user_id, today=None, weeks=WEEKS):
    today = today or date.today()
    first = week_start(today) - timedelta(weeks=weeks - 1)
    dates = db.session.execute(
        select(Workout.date).where(Workout.user_id == user_id, Workout.date >= first)
    ).scalars().all()
    counts = Counter(week_start(d) for d in dates)
    labels, values = [], []
    for i in range(weeks):
        ws = first + timedelta(weeks=i)
        labels.append(ws.isoformat())
        values.append(counts.get(ws, 0))
    return {"labels": labels, "values": values}


def plan_completion(user_id, today=None):
    today = today or date.today()
    ws = week_start(today)
    we = ws + timedelta(days=6)
    days = db.session.execute(
        select(PlanDay).join(Plan).where(Plan.user_id == user_id, Plan.is_active.is_(True))
        .order_by(PlanDay.weekday, PlanDay.id)
    ).scalars().all()
    done_ids = set(db.session.execute(
        select(Workout.plan_day_id).where(
            Workout.user_id == user_id, Workout.date >= ws, Workout.date <= we, Workout.plan_day_id.is_not(None)
        )
    ).scalars())
    items = [{"day": d, "done": d.id in done_ids, "past": d.weekday < today.weekday()} for d in days]
    done = sum(1 for i in items if i["done"])
    percent = round(100 * done / len(items)) if items else None
    return {"items": items, "done": done, "total": len(items), "percent": percent, "start": ws, "end": we}


def body_weight_series(user_id):
    rows = db.session.execute(
        select(BodyMeasurement.date, BodyMeasurement.weight_kg)
        .where(BodyMeasurement.user_id == user_id, BodyMeasurement.weight_kg.is_not(None))
        .order_by(BodyMeasurement.date)
    ).all()
    return {"labels": [r.date.isoformat() for r in rows], "values": [r.weight_kg for r in rows]}


def exercise_progress(user_id, exercise):
    entries = db.session.execute(
        select(WorkoutEntry, Workout.date)
        .join(Workout)
        .where(Workout.user_id == user_id, WorkoutEntry.exercise_id == exercise.id)
        .order_by(Workout.date, Workout.id)
    ).all()
    per_day = OrderedDict()
    for entry, wdate in entries:
        slot = per_day.setdefault(wdate, {"max": 0.0, "e1rm": 0.0, "volume": 0.0, "distance": 0.0, "duration": 0.0})
        for s in entry.sets:
            slot["max"] = max(slot["max"], s.weight_kg or 0)
            slot["e1rm"] = max(slot["e1rm"], epley(s.weight_kg or 0, s.reps))
            slot["volume"] += s.reps * (s.weight_kg or 0)
        slot["distance"] += entry.distance_km or 0
        slot["duration"] += entry.duration_min or 0
    labels = [d.isoformat() for d in per_day]
    vals = list(per_day.values())
    return {
        "labels": labels,
        "max_weight": [round(v["max"], 2) for v in vals],
        "e1rm": [round(v["e1rm"], 1) for v in vals],
        "volume": [round(v["volume"]) for v in vals],
        "distance": [round(v["distance"], 2) for v in vals],
        "duration": [round(v["duration"], 1) for v in vals],
        "sessions": len(vals),
    }


def default_exercise(user_id, exercises):
    """Most logged exercise that has weight data; otherwise the most logged one."""
    weighted = set(db.session.execute(
        select(WorkoutEntry.exercise_id)
        .join(Workout, Workout.id == WorkoutEntry.workout_id)
        .join(WorkoutSet, WorkoutSet.entry_id == WorkoutEntry.id)
        .where(Workout.user_id == user_id, WorkoutSet.weight_kg > 0)
        .distinct()
    ).scalars())
    return next((e for e in exercises if e.id in weighted), exercises[0])


@bp.get("/")
def dashboard():
    if not current_user.is_authenticated:
        return render_template("landing.html")
    uid = current_user.id
    today = date.today()
    ws = week_start(today)
    total_workouts = db.session.execute(select(func.count(Workout.id)).where(Workout.user_id == uid)).scalar()
    week_workouts = db.session.execute(
        select(func.count(Workout.id)).where(Workout.user_id == uid, Workout.date >= ws)
    ).scalar()
    total_records = db.session.execute(
        select(func.count(PersonalRecord.id)).where(PersonalRecord.user_id == uid)
    ).scalar()
    last_body = db.session.execute(
        select(BodyMeasurement).where(BodyMeasurement.user_id == uid, BodyMeasurement.weight_kg.is_not(None))
        .order_by(BodyMeasurement.date.desc(), BodyMeasurement.id.desc()).limit(1)
    ).scalar_one_or_none()
    recent = db.session.execute(
        select(Workout).where(Workout.user_id == uid).order_by(Workout.date.desc(), Workout.id.desc()).limit(5)
    ).scalars().all()
    recent_records = db.session.execute(
        select(PersonalRecord).where(PersonalRecord.user_id == uid)
        .order_by(PersonalRecord.achieved_on.desc(), PersonalRecord.id.desc()).limit(5)
    ).scalars().all()
    charts = {"perWeek": workouts_per_week(uid, today), "bodyWeight": body_weight_series(uid)}
    return render_template(
        "dashboard.html",
        total_workouts=total_workouts,
        week_workouts=week_workouts,
        total_records=total_records,
        last_body=last_body,
        recent=recent,
        recent_records=recent_records,
        completion=plan_completion(uid, today),
        charts=charts,
    )


@bp.get("/stats")
@login_required
def index():
    uid = current_user.id
    used = db.session.execute(
        select(Exercise, func.count(WorkoutEntry.id).label("n"))
        .join(WorkoutEntry, WorkoutEntry.exercise_id == Exercise.id)
        .join(Workout, Workout.id == WorkoutEntry.workout_id)
        .where(Workout.user_id == uid)
        .group_by(Exercise.id)
        .order_by(func.count(WorkoutEntry.id).desc(), Exercise.name)
    ).all()
    exercises = [row[0] for row in used]
    selected = None
    requested = request.args.get("exercise", type=int)
    if requested:
        selected = visible_exercise(requested, uid)
    if selected is None and exercises:
        selected = default_exercise(uid, exercises)
    progress = exercise_progress(uid, selected) if selected else None
    charts = {
        "progress": progress,
        "cardio": bool(selected and selected.is_cardio),
        "perWeek": workouts_per_week(uid),
        "bodyWeight": body_weight_series(uid),
    }
    return render_template(
        "stats/index.html",
        exercises=sorted(exercises, key=lambda e: e.display_name.lower()),
        selected=selected,
        progress=progress,
        completion=plan_completion(uid),
        charts=charts,
    )

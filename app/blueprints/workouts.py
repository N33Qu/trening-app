from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_babel import gettext
from flask_login import current_user, login_required
from sqlalchemy import func, select

from ..extensions import db
from ..forms import DeleteForm, WorkoutForm
from ..models import PR_LABELS, PersonalRecord, Workout, WorkoutEntry, WorkoutSet
from ..services import (
    detect_personal_records,
    exercise_choices,
    owned_or_404,
    plan_day_or_404,
    user_plan_days,
)

bp = Blueprint("workouts", __name__, url_prefix="/workouts")

PER_PAGE = 15
EMPTY_ROWS = 3


def _blank_entry():
    return {"exercise_id": 0, "sets": "", "distance_km": None, "duration_min": None}


def _prepare(form):
    choices, exercises = exercise_choices(current_user.id)
    for sub in form.entries:
        sub.exercise_id.choices = [(0, gettext("— wybierz ćwiczenie —")), *choices]
    days = user_plan_days(current_user.id)
    form.plan_day_id.choices = [(0, gettext("— bez planu —"))] + [
        (d.id, f"{d.plan.name}: {d.name}") for d in days
    ]
    return exercises


def _apply(form, workout, exercises):
    """Validate entry rows and write them to the workout. Returns False on error."""
    rows = []
    ok = True
    for sub in form.entries:
        ex_id = sub.exercise_id.data or 0
        sets = getattr(sub.form, "parsed_sets", [])
        has_data = bool(sets) or sub.distance_km.data is not None or sub.duration_min.data is not None
        if ex_id == 0:
            if has_data:
                sub.exercise_id.errors.append(gettext("Wybierz ćwiczenie."))
                ok = False
            continue
        exercise = exercises.get(ex_id)
        if exercise is None:
            sub.exercise_id.errors.append(gettext("Nieznane ćwiczenie."))
            ok = False
            continue
        if exercise.is_cardio:
            if sub.distance_km.data is None and sub.duration_min.data is None and not sets:
                sub.distance_km.errors.append(gettext("Podaj dystans lub czas."))
                ok = False
                continue
        elif not sets:
            sub.sets.errors.append(gettext("Podaj serie, np. 5x100."))
            ok = False
            continue
        rows.append((exercise, sets, sub.distance_km.data, sub.duration_min.data))
    if ok and not rows:
        form.entries[0].exercise_id.errors.append(gettext("Dodaj co najmniej jedno ćwiczenie."))
        ok = False
    if not ok:
        return False

    plan_day_id = form.plan_day_id.data or None
    if plan_day_id:
        plan_day_or_404(plan_day_id)
    workout.date = form.date.data
    workout.plan_day_id = plan_day_id
    workout.notes = form.notes.data or None
    workout.entries.clear()
    db.session.flush()
    for pos, (exercise, sets, distance, duration) in enumerate(rows):
        entry = WorkoutEntry(
            exercise_id=exercise.id,
            exercise=exercise,
            position=pos,
            distance_km=float(distance) if distance is not None else None,
            duration_min=float(duration) if duration is not None else None,
        )
        entry.sets = [WorkoutSet(set_no=i + 1, reps=r, weight_kg=w) for i, (r, w) in enumerate(sets)]
        workout.entries.append(entry)
    return True


def _flash_records(records):
    for rec in records:
        flash(gettext("Nowy rekord! %(exercise)s – %(kind)s: %(value)s kg", exercise=rec.exercise_name,
                      kind=PR_LABELS[rec.kind], value=f"{rec.value:g}"), "record")


def _form_page(form, title, workout=None):
    _, exercises = exercise_choices(current_user.id)
    cardio_ids = {e.id for e in exercises.values() if e.is_cardio}
    return render_template("workouts/form.html", form=form, title=title, workout=workout, cardio_ids=cardio_ids)


@bp.get("/")
@login_required
def index():
    page = max(request.args.get("page", 1, type=int), 1)
    total = db.session.execute(
        select(func.count(Workout.id)).where(Workout.user_id == current_user.id)
    ).scalar()
    workouts = db.session.execute(
        select(Workout)
        .where(Workout.user_id == current_user.id)
        .order_by(Workout.date.desc(), Workout.id.desc())
        .limit(PER_PAGE)
        .offset((page - 1) * PER_PAGE)
    ).scalars().all()
    pr_counts = dict(db.session.execute(
        select(PersonalRecord.workout_id, func.count(PersonalRecord.id))
        .where(PersonalRecord.user_id == current_user.id, PersonalRecord.workout_id.in_([w.id for w in workouts]))
        .group_by(PersonalRecord.workout_id)
    ).all())
    pages = max((total + PER_PAGE - 1) // PER_PAGE, 1)
    return render_template("workouts/list.html", workouts=workouts, page=page, pages=pages,
                           total=total, pr_counts=pr_counts)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "GET":
        data = {"date": date.today(), "plan_day_id": 0, "entries": []}
        day_id = request.args.get("plan_day", type=int)
        if day_id:
            day = plan_day_or_404(day_id)
            data["plan_day_id"] = day.id
            for pe in day.exercises:
                weight = f"{pe.target_weight:g}" if pe.target_weight else "0"
                sets = "" if pe.exercise.is_cardio else f"{pe.target_sets}x{pe.target_reps}x{weight}"
                data["entries"].append({**_blank_entry(), "exercise_id": pe.exercise_id, "sets": sets})
        data["entries"].extend([_blank_entry()] * EMPTY_ROWS)
        form = WorkoutForm(data=data)
    else:
        form = WorkoutForm()
    exercises = _prepare(form)
    if form.validate_on_submit():
        workout = Workout(user_id=current_user.id, date=form.date.data)
        db.session.add(workout)
        if _apply(form, workout, exercises):
            db.session.flush()
            records = detect_personal_records(workout)
            db.session.commit()
            flash(gettext("Zapisano trening."), "success")
            _flash_records(records)
            return redirect(url_for("workouts.detail", workout_id=workout.id))
        db.session.rollback()
        exercises = _prepare(form)
    return _form_page(form, gettext("Nowy trening"))


@bp.get("/<int:workout_id>")
@login_required
def detail(workout_id):
    workout = owned_or_404(Workout, workout_id)
    records = db.session.execute(
        select(PersonalRecord).where(PersonalRecord.workout_id == workout.id)
    ).scalars().all()
    return render_template("workouts/detail.html", workout=workout, records=records, delete_form=DeleteForm())


@bp.route("/<int:workout_id>/edit", methods=["GET", "POST"])
@login_required
def edit(workout_id):
    workout = owned_or_404(Workout, workout_id)
    if request.method == "GET":
        entries = [
            {
                "exercise_id": e.exercise_id,
                "sets": e.sets_text,
                "distance_km": e.distance_km,
                "duration_min": e.duration_min,
            }
            for e in workout.entries
        ] + [_blank_entry()]
        form = WorkoutForm(data={"date": workout.date, "plan_day_id": workout.plan_day_id or 0,
                                 "notes": workout.notes, "entries": entries})
    else:
        form = WorkoutForm()
    exercises = _prepare(form)
    if form.validate_on_submit():
        if _apply(form, workout, exercises):
            db.session.flush()
            records = detect_personal_records(workout)
            db.session.commit()
            flash(gettext("Zapisano zmiany."), "success")
            _flash_records(records)
            return redirect(url_for("workouts.detail", workout_id=workout.id))
        db.session.rollback()
        exercises = _prepare(form)
    return _form_page(form, gettext("Edytuj trening"), workout=workout)


@bp.post("/<int:workout_id>/delete")
@login_required
def delete(workout_id):
    workout = owned_or_404(Workout, workout_id)
    if DeleteForm().validate_on_submit():
        db.session.delete(workout)
        db.session.commit()
        flash(gettext("Usunięto trening."), "info")
    return redirect(url_for("workouts.index"))

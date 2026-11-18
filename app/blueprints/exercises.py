from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_babel import gettext
from flask_login import current_user, login_required
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .. import library
from ..extensions import db
from ..forms import DeleteForm, ExerciseForm
from ..models import PR_E1RM, PR_MAX_WEIGHT, Exercise, PersonalRecord, PlanExercise, Workout, WorkoutEntry
from ..services import owned_or_404, visible_exercises_query

bp = Blueprint("exercises", __name__, url_prefix="/exercises")


def _name_taken(name, exclude_id=None):
    q = select(Exercise.id).where(
        func.lower(Exercise.name) == name.lower(),
        (Exercise.user_id == current_user.id) | Exercise.user_id.is_(None),
    )
    if exclude_id:
        q = q.where(Exercise.id != exclude_id)
    lowered = name.lower()
    if any(lowered in (e.data["name_pl"].lower(), e.data["name_en"].lower()) for e in library.entries()):
        return True
    return db.session.execute(q).first() is not None


PER_PAGE = 24


def _filters():
    args = request.args
    return {
        "q": args.get("q", "").strip()[:80],
        "muscle": args.get("muscle", "") if args.get("muscle") in library.MUSCLE_LABELS else "",
        "equipment": args.get("equipment", "") if args.get("equipment") in library.EQUIPMENT_LABELS else "",
        "level": args.get("level", "") if args.get("level") in library.LEVEL_LABELS else "",
    }


def _matches(exercise, f):
    entry = exercise.library
    if f["q"]:
        haystack = entry.search_text if entry else exercise.name.lower()
        if not all(word in haystack or word in exercise.display_name.lower() for word in f["q"].lower().split()):
            return False
    if entry is None:
        return not (f["muscle"] or f["equipment"] or f["level"])
    if f["muscle"] and f["muscle"] not in entry.primary and f["muscle"] not in entry.secondary:
        return False
    if f["equipment"] and entry.equipment != f["equipment"]:
        return False
    return not (f["level"] and entry.level != f["level"])


@bp.get("/")
@login_required
def index():
    f = _filters()
    exercises = db.session.execute(visible_exercises_query(current_user.id)).scalars().all()
    catalogue = [e for e in exercises if e.is_global and _matches(e, f)]
    if f["muscle"]:
        # Exercises where the muscle is a prime mover first.
        catalogue.sort(key=lambda e: (f["muscle"] not in (e.library.primary if e.library else ()),
                                      e.display_name.lower()))
    else:
        catalogue.sort(key=lambda e: e.display_name.lower())
    own = [e for e in exercises if not e.is_global and _matches(e, f)]
    own.sort(key=lambda e: e.name.lower())

    total = len(catalogue)
    pages = max((total + PER_PAGE - 1) // PER_PAGE, 1)
    page = min(max(request.args.get("page", 1, type=int), 1), pages)
    active = {k: v for k, v in f.items() if v}
    return render_template(
        "exercises/list.html",
        exercises=catalogue[(page - 1) * PER_PAGE: page * PER_PAGE],
        own_exercises=own,
        total=total,
        page=page,
        pages=pages,
        filters=f,
        active_filters=active,
        muscles=[(m, library.MUSCLE_LABELS[m]) for m in library.MUSCLE_ORDER],
        equipment=list(library.EQUIPMENT_LABELS.items()),
        levels=list(library.LEVEL_LABELS.items()),
        delete_form=DeleteForm(),
    )


@bp.get("/<slug>")
@login_required
def detail(slug):
    exercise = db.session.execute(
        select(Exercise).where(Exercise.slug == slug, Exercise.user_id.is_(None))
    ).scalar_one_or_none()
    if exercise is None or exercise.library is None:
        abort(404)
    history = db.session.execute(
        select(WorkoutEntry, Workout.date)
        .join(Workout, Workout.id == WorkoutEntry.workout_id)
        .where(Workout.user_id == current_user.id, WorkoutEntry.exercise_id == exercise.id)
        .order_by(Workout.date.desc(), Workout.id.desc())
        .limit(5)
    ).all()
    sessions = db.session.execute(
        select(func.count(WorkoutEntry.id))
        .join(Workout, Workout.id == WorkoutEntry.workout_id)
        .where(Workout.user_id == current_user.id, WorkoutEntry.exercise_id == exercise.id)
    ).scalar()
    best = {}
    for kind in (PR_MAX_WEIGHT, PR_E1RM):
        best[kind] = db.session.execute(
            select(PersonalRecord)
            .where(PersonalRecord.user_id == current_user.id, PersonalRecord.exercise_id == exercise.id,
                   PersonalRecord.kind == kind)
            .order_by(PersonalRecord.value.desc(), PersonalRecord.achieved_on.desc())
            .limit(1)
        ).scalar_one_or_none()
    return render_template(
        "exercises/detail.html",
        exercise=exercise,
        entry=exercise.library,
        history=history,
        sessions=sessions,
        best=best,
        PR_MAX_WEIGHT=PR_MAX_WEIGHT,
        PR_E1RM=PR_E1RM,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = ExerciseForm()
    if form.validate_on_submit():
        if _name_taken(form.name.data):
            form.name.errors.append(gettext("Ćwiczenie o tej nazwie już istnieje."))
        else:
            db.session.add(Exercise(
                name=form.name.data, category=form.category.data,
                muscle_group=form.muscle_group.data or None, user_id=current_user.id,
            ))
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                form.name.errors.append(gettext("Ćwiczenie o tej nazwie już istnieje."))
                return render_template("exercises/form.html", form=form, title=gettext("Nowe ćwiczenie"))
            flash(gettext("Dodano ćwiczenie."), "success")
            return redirect(url_for("exercises.index"))
    return render_template("exercises/form.html", form=form, title=gettext("Nowe ćwiczenie"))


@bp.route("/<int:exercise_id>/edit", methods=["GET", "POST"])
@login_required
def edit(exercise_id):
    exercise = owned_or_404(Exercise, exercise_id)
    form = ExerciseForm(obj=exercise)
    if form.validate_on_submit():
        if _name_taken(form.name.data, exclude_id=exercise.id):
            form.name.errors.append(gettext("Ćwiczenie o tej nazwie już istnieje."))
        else:
            exercise.name = form.name.data
            exercise.category = form.category.data
            exercise.muscle_group = form.muscle_group.data or None
            db.session.commit()
            flash(gettext("Zapisano zmiany."), "success")
            return redirect(url_for("exercises.index"))
    return render_template("exercises/form.html", form=form, title=gettext("Edytuj ćwiczenie"))


@bp.post("/<int:exercise_id>/delete")
@login_required
def delete(exercise_id):
    exercise = owned_or_404(Exercise, exercise_id)
    if not DeleteForm().validate_on_submit():
        flash(gettext("Nieprawidłowe żądanie."), "error")
        return redirect(url_for("exercises.index"))
    used = db.session.execute(
        select(WorkoutEntry.id).where(WorkoutEntry.exercise_id == exercise.id).limit(1)
    ).first() or db.session.execute(
        select(PlanExercise.id).where(PlanExercise.exercise_id == exercise.id).limit(1)
    ).first()
    if used:
        flash(gettext("Nie można usunąć ćwiczenia używanego w treningach lub planach."), "error")
        return redirect(url_for("exercises.index"))
    db.session.delete(exercise)
    db.session.commit()
    flash(gettext("Usunięto ćwiczenie."), "info")
    return redirect(url_for("exercises.index"))

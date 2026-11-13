from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..forms import DeleteForm, ExerciseForm
from ..models import Exercise, PlanExercise, WorkoutEntry
from ..services import owned_or_404, visible_exercises_query

bp = Blueprint("exercises", __name__, url_prefix="/exercises")


def _name_taken(name, exclude_id=None):
    q = select(Exercise.id).where(
        func.lower(Exercise.name) == name.lower(),
        (Exercise.user_id == current_user.id) | Exercise.user_id.is_(None),
    )
    if exclude_id:
        q = q.where(Exercise.id != exclude_id)
    return db.session.execute(q).first() is not None


@bp.get("/")
@login_required
def index():
    exercises = db.session.execute(visible_exercises_query(current_user.id)).scalars().all()
    return render_template(
        "exercises/list.html",
        global_exercises=[e for e in exercises if e.is_global],
        own_exercises=[e for e in exercises if not e.is_global],
        delete_form=DeleteForm(),
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = ExerciseForm()
    if form.validate_on_submit():
        if _name_taken(form.name.data):
            form.name.errors.append("Ćwiczenie o tej nazwie już istnieje.")
        else:
            db.session.add(Exercise(
                name=form.name.data, category=form.category.data,
                muscle_group=form.muscle_group.data or None, user_id=current_user.id,
            ))
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                form.name.errors.append("Ćwiczenie o tej nazwie już istnieje.")
                return render_template("exercises/form.html", form=form, title="Nowe ćwiczenie")
            flash("Dodano ćwiczenie.", "success")
            return redirect(url_for("exercises.index"))
    return render_template("exercises/form.html", form=form, title="Nowe ćwiczenie")


@bp.route("/<int:exercise_id>/edit", methods=["GET", "POST"])
@login_required
def edit(exercise_id):
    exercise = owned_or_404(Exercise, exercise_id)
    form = ExerciseForm(obj=exercise)
    if form.validate_on_submit():
        if _name_taken(form.name.data, exclude_id=exercise.id):
            form.name.errors.append("Ćwiczenie o tej nazwie już istnieje.")
        else:
            exercise.name = form.name.data
            exercise.category = form.category.data
            exercise.muscle_group = form.muscle_group.data or None
            db.session.commit()
            flash("Zapisano zmiany.", "success")
            return redirect(url_for("exercises.index"))
    return render_template("exercises/form.html", form=form, title="Edytuj ćwiczenie")


@bp.post("/<int:exercise_id>/delete")
@login_required
def delete(exercise_id):
    exercise = owned_or_404(Exercise, exercise_id)
    if not DeleteForm().validate_on_submit():
        flash("Nieprawidłowe żądanie.", "error")
        return redirect(url_for("exercises.index"))
    used = db.session.execute(
        select(WorkoutEntry.id).where(WorkoutEntry.exercise_id == exercise.id).limit(1)
    ).first() or db.session.execute(
        select(PlanExercise.id).where(PlanExercise.exercise_id == exercise.id).limit(1)
    ).first()
    if used:
        flash("Nie można usunąć ćwiczenia używanego w treningach lub planach.", "error")
        return redirect(url_for("exercises.index"))
    db.session.delete(exercise)
    db.session.commit()
    flash("Usunięto ćwiczenie.", "info")
    return redirect(url_for("exercises.index"))

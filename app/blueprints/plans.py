from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_babel import gettext
from flask_login import current_user, login_required
from sqlalchemy import select

from ..extensions import db
from ..forms import DeleteForm, PlanDayForm, PlanExerciseForm, PlanForm
from ..models import Plan, PlanDay, PlanExercise
from ..services import exercise_choices, owned_or_404, plan_day_or_404, visible_exercise

bp = Blueprint("plans", __name__, url_prefix="/plans")


def _exercise_form():
    form = PlanExerciseForm()
    form.exercise_id.choices, _ = exercise_choices(current_user.id)
    return form


@bp.get("/")
@login_required
def index():
    plans = db.session.execute(
        select(Plan).where(Plan.user_id == current_user.id).order_by(Plan.is_active.desc(), Plan.created_at.desc())
    ).scalars().all()
    return render_template("plans/list.html", plans=plans)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = PlanForm()
    if form.validate_on_submit():
        plan = Plan(user_id=current_user.id, name=form.name.data,
                    description=form.description.data or None, is_active=form.is_active.data)
        db.session.add(plan)
        db.session.commit()
        flash(gettext("Utworzono plan. Dodaj dni treningowe."), "success")
        return redirect(url_for("plans.detail", plan_id=plan.id))
    return render_template("plans/form.html", form=form, title=gettext("Nowy plan"))


@bp.get("/<int:plan_id>")
@login_required
def detail(plan_id):
    plan = owned_or_404(Plan, plan_id)
    return render_template(
        "plans/detail.html",
        plan=plan,
        day_form=PlanDayForm(),
        exercise_form=_exercise_form(),
        delete_form=DeleteForm(),
    )


@bp.route("/<int:plan_id>/edit", methods=["GET", "POST"])
@login_required
def edit(plan_id):
    plan = owned_or_404(Plan, plan_id)
    form = PlanForm(obj=plan)
    if form.validate_on_submit():
        plan.name = form.name.data
        plan.description = form.description.data or None
        plan.is_active = form.is_active.data
        db.session.commit()
        flash(gettext("Zapisano plan."), "success")
        return redirect(url_for("plans.detail", plan_id=plan.id))
    return render_template("plans/form.html", form=form, title=gettext("Edytuj plan"), plan=plan)


@bp.post("/<int:plan_id>/delete")
@login_required
def delete(plan_id):
    plan = owned_or_404(Plan, plan_id)
    if DeleteForm().validate_on_submit():
        db.session.delete(plan)
        db.session.commit()
        flash(gettext("Usunięto plan."), "info")
    return redirect(url_for("plans.index"))


@bp.post("/<int:plan_id>/days")
@login_required
def add_day(plan_id):
    plan = owned_or_404(Plan, plan_id)
    form = PlanDayForm()
    if form.validate_on_submit():
        plan.days.append(PlanDay(weekday=form.weekday.data, name=form.name.data))
        db.session.commit()
        flash(gettext("Dodano dzień treningowy."), "success")
    else:
        flash(gettext("Popraw dane dnia treningowego."), "error")
    return redirect(url_for("plans.detail", plan_id=plan.id))


@bp.post("/days/<int:day_id>/delete")
@login_required
def delete_day(day_id):
    day = plan_day_or_404(day_id)
    plan_id = day.plan_id
    if DeleteForm().validate_on_submit():
        db.session.delete(day)
        db.session.commit()
        flash(gettext("Usunięto dzień."), "info")
    return redirect(url_for("plans.detail", plan_id=plan_id))


@bp.post("/days/<int:day_id>/exercises")
@login_required
def add_exercise(day_id):
    day = plan_day_or_404(day_id)
    form = _exercise_form()
    if form.validate_on_submit():
        exercise = visible_exercise(form.exercise_id.data, current_user.id)
        if exercise is None:
            flash(gettext("Nieznane ćwiczenie."), "error")
        else:
            day.exercises.append(PlanExercise(
                exercise_id=exercise.id,
                target_sets=form.target_sets.data,
                target_reps=form.target_reps.data,
                target_weight=float(form.target_weight.data) if form.target_weight.data is not None else None,
                position=len(day.exercises),
            ))
            db.session.commit()
            flash(gettext("Dodano ćwiczenie do dnia."), "success")
    else:
        flash(gettext("Popraw dane ćwiczenia (serie 1–20, powtórzenia 1–100)."), "error")
    return redirect(url_for("plans.detail", plan_id=day.plan_id))


@bp.post("/exercises/<int:item_id>/delete")
@login_required
def delete_exercise(item_id):
    item = db.session.get(PlanExercise, item_id)
    if item is None:
        abort(404)
    day = plan_day_or_404(item.plan_day_id)
    if DeleteForm().validate_on_submit():
        db.session.delete(item)
        db.session.commit()
        flash(gettext("Usunięto ćwiczenie z planu."), "info")
    return redirect(url_for("plans.detail", plan_id=day.plan_id))

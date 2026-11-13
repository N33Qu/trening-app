from flask import Blueprint, flash, redirect, render_template, url_for
from flask_babel import gettext
from flask_login import current_user, login_required
from sqlalchemy import select

from ..extensions import db
from ..forms import BodyMeasurementForm, DeleteForm
from ..models import SOURCE_MANUAL, BodyMeasurement
from ..services import owned_or_404

bp = Blueprint("body", __name__, url_prefix="/body")

FIELDS = ("weight_kg", "body_fat_pct", "waist_cm", "chest_cm", "arm_cm", "thigh_cm")


def _fill(measurement, form):
    measurement.date = form.date.data
    for name in FIELDS:
        value = getattr(form, name).data
        setattr(measurement, name, float(value) if value is not None else None)
    measurement.notes = form.notes.data or None


@bp.get("/")
@login_required
def index():
    rows = db.session.execute(
        select(BodyMeasurement)
        .where(BodyMeasurement.user_id == current_user.id)
        .order_by(BodyMeasurement.date.desc(), BodyMeasurement.id.desc())
    ).scalars().all()
    weights = [r for r in reversed(rows) if r.weight_kg is not None]
    chart = {
        "labels": [r.date.isoformat() for r in weights],
        "weight": [r.weight_kg for r in weights],
    }
    change = round(weights[-1].weight_kg - weights[0].weight_kg, 1) if len(weights) >= 2 else None
    charts = {"bodyWeight": {"labels": chart["labels"], "values": chart["weight"]}}
    return render_template("body/list.html", rows=rows, chart=chart, charts=charts, change=change,
                           delete_form=DeleteForm())


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = BodyMeasurementForm()
    if form.validate_on_submit():
        m = BodyMeasurement(user_id=current_user.id, source=SOURCE_MANUAL)
        _fill(m, form)
        db.session.add(m)
        db.session.commit()
        flash(gettext("Zapisano pomiar."), "success")
        return redirect(url_for("body.index"))
    return render_template("body/form.html", form=form, title=gettext("Nowy pomiar"))


@bp.route("/<int:measurement_id>/edit", methods=["GET", "POST"])
@login_required
def edit(measurement_id):
    m = owned_or_404(BodyMeasurement, measurement_id)
    form = BodyMeasurementForm(obj=m)
    if form.validate_on_submit():
        _fill(m, form)
        db.session.commit()
        flash(gettext("Zapisano zmiany."), "success")
        return redirect(url_for("body.index"))
    return render_template("body/form.html", form=form, title=gettext("Edytuj pomiar"), measurement=m)


@bp.post("/<int:measurement_id>/delete")
@login_required
def delete(measurement_id):
    m = owned_or_404(BodyMeasurement, measurement_id)
    if DeleteForm().validate_on_submit():
        db.session.delete(m)
        db.session.commit()
        flash(gettext("Usunięto pomiar."), "info")
    return redirect(url_for("body.index"))


@bp.get("/import")
@login_required
def import_placeholder():
    return render_template("body/import.html")

from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required
from sqlalchemy import select

from ..extensions import db
from ..models import PR_E1RM, PR_MAX_WEIGHT, PersonalRecord
from ..services import visible_exercise

bp = Blueprint("records", __name__, url_prefix="/records")


@bp.get("/")
@login_required
def index():
    rows = db.session.execute(
        select(PersonalRecord)
        .where(PersonalRecord.user_id == current_user.id)
        .order_by(PersonalRecord.achieved_on, PersonalRecord.id)
    ).scalars().all()
    best = {}
    for pr in rows:
        slot = best.setdefault(
            pr.exercise_id, {"exercise": pr.exercise, PR_MAX_WEIGHT: None, PR_E1RM: None, "count": 0}
        )
        slot["count"] += 1
        current = slot[pr.kind]
        if current is None or pr.value >= current.value:
            slot[pr.kind] = pr
    summary = sorted(best.values(), key=lambda s: s["exercise"].name)
    recent = list(reversed(rows))[:10]
    return render_template(
        "records/list.html", summary=summary, recent=recent, PR_MAX_WEIGHT=PR_MAX_WEIGHT, PR_E1RM=PR_E1RM
    )


@bp.get("/exercise/<int:exercise_id>")
@login_required
def history(exercise_id):
    exercise = visible_exercise(exercise_id, current_user.id)
    if exercise is None:
        abort(404)
    rows = db.session.execute(
        select(PersonalRecord)
        .where(PersonalRecord.user_id == current_user.id, PersonalRecord.exercise_id == exercise.id)
        .order_by(PersonalRecord.achieved_on.desc(), PersonalRecord.id.desc())
    ).scalars().all()
    return render_template("records/history.html", exercise=exercise, rows=rows)

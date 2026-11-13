import re
from dataclasses import dataclass

from flask import abort
from flask_babel import gettext
from flask_login import current_user
from sqlalchemy import func, or_, select

from .extensions import db
from .models import (
    PR_E1RM,
    PR_MAX_WEIGHT,
    Exercise,
    PersonalRecord,
    Plan,
    PlanDay,
    Workout,
)

MAX_SETS_PER_ENTRY = 50
_NUMBER = r"\d{1,4}(?:[.,]\d{1,3})?"
_SET_TOKEN = re.compile(
    rf"^(?P<a>{_NUMBER})(?:\s*[x×*@]\s*(?P<b>{_NUMBER}))?(?:\s*[x×*]\s*(?P<c>{_NUMBER}))?\s*(?:kg)?$",
    re.IGNORECASE,
)


def _int(value):
    if value is None or not re.fullmatch(r"\d+", value):
        raise SetsParseError(gettext("Liczba serii i powtórzeń musi być liczbą całkowitą."))
    return int(value)


class SetsParseError(ValueError):
    pass


def parse_sets(text):
    """Parse '5x100, 5x100, 3x5x80, 10' into [(reps, weight), ...].

    Formats: REPSxWEIGHT, SETSxREPSxWEIGHT, REPS (bodyweight, weight 0).
    """
    result = []
    if not text or not text.strip():
        return result
    # A comma directly followed by a digit is a decimal separator (22,5 kg).
    for raw in re.split(r";|\n|,(?!\d)|,\s+", text):
        token = raw.strip()
        if not token:
            continue
        match = _SET_TOKEN.match(token)
        if not match:
            raise SetsParseError(
                gettext("Nie rozumiem serii „%(token)s”. Użyj formatu np. 5x100 lub 3x5x80.", token=token)
            )
        a, b, c = match.group("a"), match.group("b"), match.group("c")
        if c is not None:
            count, reps, weight = _int(a), _int(b), c
        elif b is not None:
            count, reps, weight = 1, _int(a), b
        else:
            count, reps, weight = 1, _int(a), "0"
        weight = float(weight.replace(",", "."))
        if reps <= 0:
            raise SetsParseError(gettext("Liczba powtórzeń musi być większa od zera."))
        if count <= 0 or count > MAX_SETS_PER_ENTRY:
            raise SetsParseError(gettext("Nieprawidłowa liczba serii."))
        if reps > 500:
            raise SetsParseError(gettext("Nieprawidłowa liczba powtórzeń."))
        if weight > 1000:
            raise SetsParseError(gettext("Ciężar wygląda na nierealny (> 1000 kg)."))
        result.extend([(reps, weight)] * count)
        if len(result) > MAX_SETS_PER_ENTRY:
            raise SetsParseError(gettext("Maksymalnie %(num)d serii na ćwiczenie.", num=MAX_SETS_PER_ENTRY))
    return result


def format_pace(duration_min, distance_km):
    """Running pace as m:ss per km, e.g. 27 min / 5 km -> '5:24'."""
    if not duration_min or not distance_km or distance_km <= 0:
        return None
    seconds = round(duration_min * 60 / distance_km)
    return f"{seconds // 60}:{seconds % 60:02d}"


def epley(weight, reps):
    if reps <= 0 or weight <= 0:
        return 0.0
    if reps == 1:
        return float(weight)
    return round(weight * (1 + reps / 30.0), 1)


# --- ownership helpers -------------------------------------------------------

def owned_or_404(model, object_id):
    obj = db.session.execute(
        select(model).where(model.id == object_id, model.user_id == current_user.id)
    ).scalar_one_or_none()
    if obj is None:
        abort(404)
    return obj


def plan_day_or_404(day_id, user_id=None):
    user_id = user_id or current_user.id
    day = db.session.execute(
        select(PlanDay).join(Plan).where(PlanDay.id == day_id, Plan.user_id == user_id)
    ).scalar_one_or_none()
    if day is None:
        abort(404)
    return day


def visible_exercises_query(user_id):
    return (
        select(Exercise)
        .where(or_(Exercise.user_id.is_(None), Exercise.user_id == user_id))
        .order_by(Exercise.category.desc(), Exercise.name)
    )


def visible_exercise(exercise_id, user_id):
    return db.session.execute(
        select(Exercise).where(
            Exercise.id == exercise_id, or_(Exercise.user_id.is_(None), Exercise.user_id == user_id)
        )
    ).scalar_one_or_none()


def exercise_choices(user_id):
    exercises = db.session.execute(visible_exercises_query(user_id)).scalars().all()
    return [(e.id, f"{e.display_name} ({e.category_label})") for e in exercises], {e.id: e for e in exercises}


def user_plan_days(user_id):
    return db.session.execute(
        select(PlanDay).join(Plan).where(Plan.user_id == user_id).order_by(Plan.name, PlanDay.weekday)
    ).scalars().all()


# --- personal records --------------------------------------------------------

@dataclass
class NewRecord:
    exercise_name: str
    kind: str
    value: float


def _best_for_workout(workout):
    best = {}
    for entry in workout.entries:
        if entry.exercise.is_cardio:
            continue
        for s in entry.sets:
            if not s.weight_kg or s.weight_kg <= 0:
                continue
            cur = best.setdefault(entry.exercise_id, {})
            if s.weight_kg > cur.get(PR_MAX_WEIGHT, (0, 0, 0))[0]:
                cur[PR_MAX_WEIGHT] = (s.weight_kg, s.reps, s.weight_kg)
            e1rm = epley(s.weight_kg, s.reps)
            if e1rm > cur.get(PR_E1RM, (0, 0, 0))[0]:
                cur[PR_E1RM] = (e1rm, s.reps, s.weight_kg)
    return best


def detect_personal_records(workout, count_metric=True):
    """Recompute PRs contributed by a workout. Returns list of genuinely new records."""
    from .metrics import record_personal_records

    previous = {
        (pr.exercise_id, pr.kind): pr.value
        for pr in db.session.execute(
            select(PersonalRecord).where(PersonalRecord.workout_id == workout.id)
        ).scalars()
    }
    db.session.execute(
        PersonalRecord.__table__.delete().where(PersonalRecord.workout_id == workout.id)
    )

    new_records = []
    exercises = {e.exercise_id: e.exercise for e in workout.entries}
    for exercise_id, kinds in _best_for_workout(workout).items():
        for kind, (value, reps, weight) in kinds.items():
            prior_best = db.session.execute(
                select(func.max(PersonalRecord.value)).where(
                    PersonalRecord.user_id == workout.user_id,
                    PersonalRecord.exercise_id == exercise_id,
                    PersonalRecord.kind == kind,
                    or_(PersonalRecord.workout_id.is_(None), PersonalRecord.workout_id != workout.id),
                )
            ).scalar()
            if prior_best is not None and value <= prior_best:
                continue
            db.session.add(
                PersonalRecord(
                    user_id=workout.user_id,
                    exercise_id=exercise_id,
                    workout_id=workout.id,
                    kind=kind,
                    value=value,
                    reps=reps,
                    weight_kg=weight,
                    achieved_on=workout.date,
                )
            )
            old = previous.get((exercise_id, kind))
            if old is None or value > old:
                new_records.append(NewRecord(exercises[exercise_id].display_name, kind, value))

    if count_metric and new_records:
        record_personal_records(len(new_records))
    return new_records


def get_workout_or_404(workout_id):
    return owned_or_404(Workout, workout_id)

import datetime as dt
from datetime import UTC, datetime

from flask_babel import gettext, lazy_gettext
from flask_login import UserMixin
from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db

CATEGORY_STRENGTH = "strength"
CATEGORY_CARDIO = "cardio"
CATEGORY_LABELS = {CATEGORY_STRENGTH: lazy_gettext("siłowe"), CATEGORY_CARDIO: lazy_gettext("cardio")}

WEEKDAYS = [lazy_gettext("Poniedziałek"), lazy_gettext("Wtorek"), lazy_gettext("Środa"), lazy_gettext("Czwartek"),
            lazy_gettext("Piątek"), lazy_gettext("Sobota"), lazy_gettext("Niedziela")]
WEEKDAYS_SHORT = [lazy_gettext("Pon"), lazy_gettext("Wt"), lazy_gettext("Śr"), lazy_gettext("Czw"),
                  lazy_gettext("Pt"), lazy_gettext("Sob"), lazy_gettext("Nd")]

PR_MAX_WEIGHT = "max_weight"
PR_E1RM = "e1rm"
PR_LABELS = {PR_MAX_WEIGHT: lazy_gettext("Maksymalny ciężar"), PR_E1RM: lazy_gettext("Szacowany 1RM (Epley)")}

SOURCE_MANUAL = "manual"
SOURCE_APPLE_HEALTH = "apple_health"
SOURCE_LABELS = {SOURCE_MANUAL: lazy_gettext("ręcznie"), SOURCE_APPLE_HEALTH: "Apple Health"}


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Exercise(db.Model):
    __tablename__ = "exercises"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_exercise_user_name"),
        CheckConstraint("category IN ('strength', 'cardio')", name="ck_exercise_category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(16), default=CATEGORY_STRENGTH)
    muscle_group: Mapped[str | None] = mapped_column(String(60))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    @property
    def is_global(self):
        return self.user_id is None

    @property
    def is_cardio(self):
        return self.category == CATEGORY_CARDIO

    @property
    def display_name(self):
        """Catalogue exercises are translated; user-created ones are shown as typed."""
        return gettext(self.name) if self.is_global else self.name

    @property
    def display_muscle_group(self):
        if self.muscle_group and self.is_global:
            return gettext(self.muscle_group)
        return self.muscle_group

    @property
    def category_label(self):
        return CATEGORY_LABELS.get(self.category, self.category)


class Plan(db.Model):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    days: Mapped[list["PlanDay"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="PlanDay.weekday, PlanDay.id"
    )


class PlanDay(db.Model):
    __tablename__ = "plan_days"
    __table_args__ = (CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_plan_day_weekday"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column()
    name: Mapped[str] = mapped_column(String(100))

    plan: Mapped[Plan] = relationship(back_populates="days")
    exercises: Mapped[list["PlanExercise"]] = relationship(
        back_populates="day", cascade="all, delete-orphan", order_by="PlanExercise.position, PlanExercise.id"
    )

    @property
    def weekday_label(self):
        return WEEKDAYS[self.weekday]

    @property
    def weekday_short(self):
        return WEEKDAYS_SHORT[self.weekday]


class PlanExercise(db.Model):
    __tablename__ = "plan_exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_day_id: Mapped[int] = mapped_column(ForeignKey("plan_days.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"))
    target_sets: Mapped[int] = mapped_column(default=3)
    target_reps: Mapped[int] = mapped_column(default=8)
    target_weight: Mapped[float | None] = mapped_column()
    position: Mapped[int] = mapped_column(default=0)

    day: Mapped[PlanDay] = relationship(back_populates="exercises")
    exercise: Mapped[Exercise] = relationship()


class Workout(db.Model):
    __tablename__ = "workouts"
    __table_args__ = (Index("ix_workouts_user_date", "user_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    date: Mapped[dt.date] = mapped_column()
    plan_day_id: Mapped[int | None] = mapped_column(ForeignKey("plan_days.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    plan_day: Mapped[PlanDay | None] = relationship()
    entries: Mapped[list["WorkoutEntry"]] = relationship(
        back_populates="workout", cascade="all, delete-orphan", order_by="WorkoutEntry.position, WorkoutEntry.id"
    )

    @property
    def total_volume(self):
        return sum(s.reps * (s.weight_kg or 0) for e in self.entries for s in e.sets)

    @property
    def total_sets(self):
        return sum(len(e.sets) for e in self.entries)


class WorkoutEntry(db.Model):
    __tablename__ = "workout_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("workouts.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(default=0)
    distance_km: Mapped[float | None] = mapped_column()
    duration_min: Mapped[float | None] = mapped_column()

    workout: Mapped[Workout] = relationship(back_populates="entries")
    exercise: Mapped[Exercise] = relationship()
    sets: Mapped[list["WorkoutSet"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", order_by="WorkoutSet.set_no"
    )

    @property
    def sets_text(self):
        return ", ".join(f"{s.reps}x{_fmt(s.weight_kg)}" for s in self.sets)


class WorkoutSet(db.Model):
    __tablename__ = "workout_sets"
    __table_args__ = (CheckConstraint("reps > 0", name="ck_set_reps_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("workout_entries.id", ondelete="CASCADE"), index=True)
    set_no: Mapped[int] = mapped_column()
    reps: Mapped[int] = mapped_column()
    weight_kg: Mapped[float] = mapped_column(default=0.0)

    entry: Mapped[WorkoutEntry] = relationship(back_populates="sets")


class PersonalRecord(db.Model):
    __tablename__ = "personal_records"
    __table_args__ = (Index("ix_pr_user_exercise_kind", "user_id", "exercise_id", "kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"))
    workout_id: Mapped[int | None] = mapped_column(ForeignKey("workouts.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    value: Mapped[float] = mapped_column()
    reps: Mapped[int] = mapped_column()
    weight_kg: Mapped[float] = mapped_column()
    achieved_on: Mapped[dt.date] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    exercise: Mapped[Exercise] = relationship()

    @property
    def kind_label(self):
        return PR_LABELS.get(self.kind, self.kind)


class BodyMeasurement(db.Model):
    __tablename__ = "body_measurements"
    __table_args__ = (
        Index("ix_body_user_date", "user_id", "date"),
        UniqueConstraint("user_id", "source", "external_id", name="uq_body_import"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    date: Mapped[dt.date] = mapped_column()
    weight_kg: Mapped[float | None] = mapped_column()
    waist_cm: Mapped[float | None] = mapped_column()
    chest_cm: Mapped[float | None] = mapped_column()
    arm_cm: Mapped[float | None] = mapped_column()
    thigh_cm: Mapped[float | None] = mapped_column()
    body_fat_pct: Mapped[float | None] = mapped_column()
    notes: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(32), default=SOURCE_MANUAL)
    external_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    @property
    def source_label(self):
        return SOURCE_LABELS.get(self.source, self.source)


def _fmt(value):
    if value is None:
        return "0"
    return f"{value:g}"

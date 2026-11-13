from datetime import date

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    FieldList,
    Form,
    FormField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    EqualTo,
    InputRequired,
    Length,
    NumberRange,
    Optional,
    Regexp,
    ValidationError,
)

from .models import CATEGORY_LABELS, WEEKDAYS
from .services import SetsParseError, parse_sets


def _not_future(form, field):
    if field.data and field.data > date.today():
        raise ValidationError("Data nie może być z przyszłości.")


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class LoginForm(FlaskForm):
    username = StringField("Login", validators=[DataRequired(), Length(max=32)], filters=[_strip])
    password = PasswordField("Hasło", validators=[DataRequired(), Length(max=128)])
    remember = BooleanField("Zapamiętaj mnie")
    submit = SubmitField("Zaloguj")


class RegisterForm(FlaskForm):
    username = StringField(
        "Login",
        validators=[
            DataRequired(),
            Length(min=3, max=32, message="Login musi mieć od 3 do 32 znaków."),
            Regexp(r"^[A-Za-z0-9_.-]+$", message="Dozwolone znaki: litery, cyfry, _ . -"),
        ],
        filters=[_strip],
    )
    password = PasswordField(
        "Hasło", validators=[DataRequired(), Length(min=8, max=128, message="Hasło musi mieć co najmniej 8 znaków.")]
    )
    confirm = PasswordField(
        "Powtórz hasło", validators=[DataRequired(), EqualTo("password", message="Hasła nie są identyczne.")]
    )
    submit = SubmitField("Załóż konto")


class ExerciseForm(FlaskForm):
    name = StringField("Nazwa", validators=[DataRequired(), Length(max=80)], filters=[_strip])
    category = SelectField("Kategoria", choices=list(CATEGORY_LABELS.items()))
    muscle_group = StringField("Partia mięśniowa", validators=[Optional(), Length(max=60)], filters=[_strip])
    submit = SubmitField("Zapisz")


class PlanForm(FlaskForm):
    name = StringField("Nazwa planu", validators=[DataRequired(), Length(max=100)], filters=[_strip])
    description = TextAreaField("Opis", validators=[Optional(), Length(max=500)])
    is_active = BooleanField("Plan aktywny (liczony w realizacji tygodnia)", default=True)
    submit = SubmitField("Zapisz plan")


class PlanDayForm(FlaskForm):
    weekday = SelectField("Dzień tygodnia", choices=list(enumerate(WEEKDAYS)), coerce=int)
    name = StringField("Nazwa dnia", validators=[DataRequired(), Length(max=100)], filters=[_strip],
                       render_kw={"placeholder": "np. Pon – klatka"})
    submit = SubmitField("Dodaj dzień")


class PlanExerciseForm(FlaskForm):
    exercise_id = SelectField("Ćwiczenie", coerce=int, validators=[InputRequired()])
    target_sets = IntegerField("Serie", default=3, validators=[InputRequired(), NumberRange(1, 20)])
    target_reps = IntegerField("Powtórzenia", default=8, validators=[InputRequired(), NumberRange(1, 100)])
    target_weight = DecimalField("Ciężar (kg)", places=2, validators=[Optional(), NumberRange(0, 1000)])
    submit = SubmitField("Dodaj ćwiczenie")


class EntryForm(Form):
    exercise_id = SelectField("Ćwiczenie", coerce=int, validators=[Optional()])
    sets = StringField("Serie (powt. x kg)", validators=[Optional(), Length(max=500)],
                       render_kw={"placeholder": "np. 5x100, 5x100, 3x5x90"})
    distance_km = DecimalField("Dystans (km)", places=2, validators=[Optional(), NumberRange(0, 1000)])
    duration_min = DecimalField("Czas (min)", places=1, validators=[Optional(), NumberRange(0, 2000)])

    def validate_sets(self, field):
        try:
            self.parsed_sets = parse_sets(field.data)
        except SetsParseError as exc:
            raise ValidationError(str(exc)) from exc


class WorkoutForm(FlaskForm):
    date = DateField("Data", default=date.today, validators=[DataRequired(), _not_future])
    plan_day_id = SelectField("Dzień planu", coerce=int, validators=[Optional()])
    notes = TextAreaField("Notatki", validators=[Optional(), Length(max=1000)])
    entries = FieldList(FormField(EntryForm), min_entries=1, max_entries=30)
    submit = SubmitField("Zapisz trening")


class BodyMeasurementForm(FlaskForm):
    date = DateField("Data", default=date.today, validators=[DataRequired(), _not_future])
    weight_kg = DecimalField("Masa ciała (kg)", places=1, validators=[Optional(), NumberRange(20, 400)])
    body_fat_pct = DecimalField("Tkanka tłuszczowa (%)", places=1, validators=[Optional(), NumberRange(1, 75)])
    waist_cm = DecimalField("Talia (cm)", places=1, validators=[Optional(), NumberRange(20, 300)])
    chest_cm = DecimalField("Klatka (cm)", places=1, validators=[Optional(), NumberRange(20, 300)])
    arm_cm = DecimalField("Ramię (cm)", places=1, validators=[Optional(), NumberRange(5, 100)])
    thigh_cm = DecimalField("Udo (cm)", places=1, validators=[Optional(), NumberRange(10, 150)])
    notes = StringField("Notatka", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Zapisz pomiar")

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False
        values = [self.weight_kg.data, self.body_fat_pct.data, self.waist_cm.data,
                  self.chest_cm.data, self.arm_cm.data, self.thigh_cm.data]
        if all(v is None for v in values):
            self.weight_kg.errors.append("Podaj co najmniej jedną wartość pomiaru.")
            return False
        return True


class DeleteForm(FlaskForm):
    submit = SubmitField("Usuń")

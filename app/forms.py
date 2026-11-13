from datetime import date

from flask_babel import lazy_gettext as _l
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

from .i18n import form_translations
from .models import CATEGORY_LABELS, WEEKDAYS
from .services import SetsParseError, parse_sets


def _not_future(form, field):
    if field.data and field.data > date.today():
        raise ValidationError(_l("Data nie może być z przyszłości."))


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class _TranslatedMeta:
    def get_translations(self, form):
        return form_translations


class BaseForm(FlaskForm):
    class Meta(_TranslatedMeta):
        pass


class LoginForm(BaseForm):
    username = StringField(_l("Login"), validators=[DataRequired(), Length(max=32)], filters=[_strip])
    password = PasswordField(_l("Hasło"), validators=[DataRequired(), Length(max=128)])
    remember = BooleanField(_l("Zapamiętaj mnie"))
    submit = SubmitField(_l("Zaloguj"))


class RegisterForm(BaseForm):
    username = StringField(
        _l("Login"),
        validators=[
            DataRequired(),
            Length(min=3, max=32, message=_l("Login musi mieć od 3 do 32 znaków.")),
            Regexp(r"^[A-Za-z0-9_.-]+$", message=_l("Dozwolone znaki: litery, cyfry, _ . -")),
        ],
        filters=[_strip],
    )
    password = PasswordField(
        _l("Hasło"),
        validators=[DataRequired(), Length(min=8, max=128, message=_l("Hasło musi mieć co najmniej 8 znaków."))],
    )
    confirm = PasswordField(
        _l("Powtórz hasło"),
        validators=[DataRequired(), EqualTo("password", message=_l("Hasła nie są identyczne."))],
    )
    submit = SubmitField(_l("Załóż konto"))


class ExerciseForm(BaseForm):
    name = StringField(_l("Nazwa"), validators=[DataRequired(), Length(max=80)], filters=[_strip])
    category = SelectField(_l("Kategoria"), choices=list(CATEGORY_LABELS.items()))
    muscle_group = StringField(_l("Partia mięśniowa"), validators=[Optional(), Length(max=60)], filters=[_strip])
    submit = SubmitField(_l("Zapisz"))


class PlanForm(BaseForm):
    name = StringField(_l("Nazwa planu"), validators=[DataRequired(), Length(max=100)], filters=[_strip])
    description = TextAreaField(_l("Opis"), validators=[Optional(), Length(max=500)])
    is_active = BooleanField(_l("Plan aktywny (liczony w realizacji tygodnia)"), default=True)
    submit = SubmitField(_l("Zapisz plan"))


class PlanDayForm(BaseForm):
    weekday = SelectField(_l("Dzień tygodnia"), choices=list(enumerate(WEEKDAYS)), coerce=int)
    name = StringField(_l("Nazwa dnia"), validators=[DataRequired(), Length(max=100)], filters=[_strip],
                       render_kw={"placeholder": _l("np. Pon – klatka")})
    submit = SubmitField(_l("Dodaj dzień"))


class PlanExerciseForm(BaseForm):
    exercise_id = SelectField(_l("Ćwiczenie"), coerce=int, validators=[InputRequired()])
    target_sets = IntegerField(_l("Serie"), default=3, validators=[InputRequired(), NumberRange(1, 20)])
    target_reps = IntegerField(_l("Powtórzenia"), default=8, validators=[InputRequired(), NumberRange(1, 100)])
    target_weight = DecimalField(_l("Ciężar (kg)"), places=2, validators=[Optional(), NumberRange(0, 1000)])
    submit = SubmitField(_l("Dodaj ćwiczenie"))


class EntryForm(Form):
    class Meta(_TranslatedMeta):
        pass

    exercise_id = SelectField(_l("Ćwiczenie"), coerce=int, validators=[Optional()])
    sets = StringField(_l("Serie (powt. x kg)"), validators=[Optional(), Length(max=500)],
                       render_kw={"placeholder": _l("np. 5x100, 5x100, 3x5x90")})
    distance_km = DecimalField(_l("Dystans (km)"), places=2, validators=[Optional(), NumberRange(0, 1000)])
    duration_min = DecimalField(_l("Czas (min)"), places=1, validators=[Optional(), NumberRange(0, 2000)])

    def validate_sets(self, field):
        try:
            self.parsed_sets = parse_sets(field.data)
        except SetsParseError as exc:
            raise ValidationError(str(exc)) from exc


class WorkoutForm(BaseForm):
    date = DateField(_l("Data"), default=date.today, validators=[DataRequired(), _not_future])
    plan_day_id = SelectField(_l("Dzień planu"), coerce=int, validators=[Optional()])
    notes = TextAreaField(_l("Notatki"), validators=[Optional(), Length(max=1000)])
    entries = FieldList(FormField(EntryForm), min_entries=1, max_entries=30)
    submit = SubmitField(_l("Zapisz trening"))


class BodyMeasurementForm(BaseForm):
    date = DateField(_l("Data"), default=date.today, validators=[DataRequired(), _not_future])
    weight_kg = DecimalField(_l("Masa ciała (kg)"), places=1, validators=[Optional(), NumberRange(20, 400)])
    body_fat_pct = DecimalField(_l("Tkanka tłuszczowa (%)"), places=1, validators=[Optional(), NumberRange(1, 75)])
    waist_cm = DecimalField(_l("Talia (cm)"), places=1, validators=[Optional(), NumberRange(20, 300)])
    chest_cm = DecimalField(_l("Klatka (cm)"), places=1, validators=[Optional(), NumberRange(20, 300)])
    arm_cm = DecimalField(_l("Ramię (cm)"), places=1, validators=[Optional(), NumberRange(5, 100)])
    thigh_cm = DecimalField(_l("Udo (cm)"), places=1, validators=[Optional(), NumberRange(10, 150)])
    notes = StringField(_l("Notatka"), validators=[Optional(), Length(max=500)])
    submit = SubmitField(_l("Zapisz pomiar"))

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False
        values = [self.weight_kg.data, self.body_fat_pct.data, self.waist_cm.data,
                  self.chest_cm.data, self.arm_cm.data, self.thigh_cm.data]
        if all(v is None for v in values):
            self.weight_kg.errors.append(_l("Podaj co najmniej jedną wartość pomiaru."))
            return False
        return True


class DeleteForm(BaseForm):
    submit = SubmitField(_l("Usuń"))

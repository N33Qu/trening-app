from datetime import date

from flask import Blueprint, current_app, has_request_context, redirect, request, url_for
from flask_babel import format_date, get_locale, get_translations
from flask_wtf.i18n import translations as wtforms_translations

LANGUAGES = ("pl", "en")
DEFAULT_LANGUAGE = "pl"
LANG_COOKIE = "lang"
LANG_COOKIE_MAX_AGE = 365 * 24 * 60 * 60

bp = Blueprint("i18n", __name__)


def N_(message):
    """Mark a string for extraction without translating it."""
    return message


def N_plural(singular, plural):
    return singular, plural


# WTForms / Flask-WTF built-in messages translated in the app catalogue.
BUILTIN_MESSAGES = (
    N_("This field is required."),
    N_("Invalid input."),
    N_("Not a valid choice."),
    N_("Invalid Choice: could not coerce."),
    N_("Not a valid integer value."),
    N_("Not a valid decimal value."),
    N_("Not a valid float value."),
    N_("Not a valid date value."),
    N_("Field must be equal to %(other_name)s."),
    N_("Field must be between %(min)d and %(max)d characters long."),
    N_("Number must be at least %(min)s."),
    N_("Number must be at most %(max)s."),
    N_("Number must be between %(min)s and %(max)s."),
    N_("The CSRF token is missing."),
    N_("The CSRF session token is missing."),
    N_("The CSRF token has expired."),
    N_("The CSRF token is invalid."),
    N_("The CSRF tokens do not match."),
    N_("The referrer header is missing."),
    N_("The referrer does not match the host."),
)
BUILTIN_PLURALS = (
    N_plural("Field must be at least %(min)d character long.", "Field must be at least %(min)d characters long."),
    N_plural("Field cannot be longer than %(max)d character.", "Field cannot be longer than %(max)d characters."),
)


class FormTranslations:
    """WTForms translations: app catalogue first, then the WTForms catalogue."""

    def gettext(self, string):
        translated = get_translations().gettext(string)
        return translated if translated != string else wtforms_translations.gettext(string)

    def ngettext(self, singular, plural, n):
        translated = get_translations().ngettext(singular, plural, n)
        if translated not in (singular, plural):
            return translated
        return wtforms_translations.ngettext(singular, plural, n)


form_translations = FormTranslations()


def select_locale():
    if not has_request_context():
        return DEFAULT_LANGUAGE
    lang = request.cookies.get(LANG_COOKIE)
    if lang in LANGUAGES:
        return lang
    return request.accept_languages.best_match(LANGUAGES) or DEFAULT_LANGUAGE


def current_language():
    locale = get_locale()
    return locale.language if locale and locale.language in LANGUAGES else DEFAULT_LANGUAGE


def format_day(value):
    """Full date: 13.11.2026 (pl) or Nov 13, 2026 (en)."""
    if not isinstance(value, date):
        return value
    if current_language() == "pl":
        return value.strftime("%d.%m.%Y")
    return format_date(value, "MMM d, y")


def format_day_short(value):
    """Day and month: 13.11 (pl) or Nov 13 (en)."""
    if not isinstance(value, date):
        return value
    if current_language() == "pl":
        return value.strftime("%d.%m")
    return format_date(value, "MMM d")


def _safe_next(target):
    if not target or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return None
    return target


@bp.post("/lang")
def set_language():
    response = redirect(_safe_next(request.form.get("next")) or url_for("stats.dashboard"))
    lang = request.form.get("lang", "")
    if lang in LANGUAGES:
        response.set_cookie(
            LANG_COOKIE, lang, max_age=LANG_COOKIE_MAX_AGE, httponly=True, samesite="Lax",
            secure=current_app.config["SESSION_COOKIE_SECURE"],
        )
    return response

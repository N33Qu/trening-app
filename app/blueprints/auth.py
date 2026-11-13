import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlsplit

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_babel import gettext
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..forms import LoginForm, RegisterForm
from ..models import User

bp = Blueprint("auth", __name__)

# Dummy hash so that unknown usernames take as long as wrong passwords.
_DUMMY = User(username="_")
_DUMMY.set_password("timing-equaliser")


class LoginThrottle:
    """Per-process sliding window of failed logins keyed by client IP + username."""

    def __init__(self):
        self._failures = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key, window):
        now = time.monotonic()
        q = self._failures[key]
        while q and now - q[0] > window:
            q.popleft()
        return q

    def blocked(self, key, limit, window):
        with self._lock:
            return len(self._prune(key, window)) >= limit

    def fail(self, key, window):
        with self._lock:
            self._prune(key, window).append(time.monotonic())

    def reset(self, key):
        with self._lock:
            self._failures.pop(key, None)


throttle = LoginThrottle()


def _safe_next(target):
    if not target:
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not target.startswith("/") or target.startswith("//"):
        return None
    return target


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("stats.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        cfg = current_app.config
        key = f"{request.remote_addr}|{form.username.data.lower()}"
        if throttle.blocked(key, cfg["LOGIN_MAX_ATTEMPTS"], cfg["LOGIN_WINDOW_SECONDS"]):
            flash(gettext("Zbyt wiele nieudanych prób logowania. Spróbuj ponownie za kilka minut."), "error")
            return render_template("auth/login.html", form=form), 429
        user = db.session.execute(
            select(User).where(func.lower(User.username) == form.username.data.lower())
        ).scalar_one_or_none()
        if user is None:
            _DUMMY.check_password(form.password.data)
        if user is None or not user.check_password(form.password.data):
            throttle.fail(key, cfg["LOGIN_WINDOW_SECONDS"])
            current_app.logger.info("failed login for username=%r", form.username.data[:32])
            flash(gettext("Nieprawidłowy login lub hasło."), "error")
            return render_template("auth/login.html", form=form), 401
        throttle.reset(key)
        login_user(user, remember=form.remember.data)
        flash(gettext("Witaj, %(name)s!", name=user.username), "success")
        return redirect(_safe_next(request.args.get("next")) or url_for("stats.dashboard"))
    return render_template("auth/login.html", form=form)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("stats.dashboard"))
    form = RegisterForm()
    if form.validate_on_submit():
        exists = db.session.execute(
            select(User.id).where(func.lower(User.username) == form.username.data.lower())
        ).first()
        if exists:
            form.username.errors.append(gettext("Ten login jest już zajęty."))
        else:
            user = User(username=form.username.data)
            user.set_password(form.password.data)
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                form.username.errors.append(gettext("Ten login jest już zajęty."))
                return render_template("auth/register.html", form=form)
            login_user(user)
            flash(gettext("Konto utworzone. Zacznij od dodania planu lub pierwszego treningu!"), "success")
            return redirect(url_for("stats.dashboard"))
    return render_template("auth/register.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash(gettext("Wylogowano."), "info")
    return redirect(url_for("auth.login"))

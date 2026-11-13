import logging
import os
import secrets
import time

import click
from flask import Flask, g, render_template, request
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import build_config
from .extensions import csrf, db, login_manager
from .metrics import init_metrics
from .services import format_pace

log = logging.getLogger(__name__)


@event.listens_for(Engine, "connect")
def _sqlite_foreign_keys(dbapi_connection, connection_record):
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _configure_logging(level):
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    root.setLevel(getattr(logging, level, logging.INFO))


def create_app(config_overrides=None):
    app_env = (config_overrides or {}).get("APP_ENV") or os.environ.get("APP_ENV", "production")
    app = Flask(__name__)
    app.config.update(build_config(app_env, config_overrides))
    _configure_logging(app.config["LOG_LEVEL"])

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    init_metrics(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    from .blueprints import auth, body, exercises, health, plans, records, stats, workouts

    app.register_blueprint(health.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(stats.bp)
    app.register_blueprint(plans.bp)
    app.register_blueprint(workouts.bp)
    app.register_blueprint(exercises.bp)
    app.register_blueprint(records.bp)
    app.register_blueprint(body.bp)
    csrf.exempt(health.bp)

    _register_hooks(app)
    _register_cli(app)

    with app.app_context():
        bootstrap_database(app)

    return app


def _register_hooks(app):
    @app.before_request
    def _nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.after_request
    def _security_headers(response):
        nonce = getattr(g, "csp_nonce", "")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'",
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        if request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        if request.endpoint and not request.endpoint.startswith(("static", "health.")):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    app.add_template_filter(format_pace, "pace")

    @app.context_processor
    def _inject():
        return {
            "app_version": app.config["APP_VERSION"],
            "csp_nonce": getattr(g, "csp_nonce", ""),
        }

    @app.errorhandler(404)
    def _not_found(_e):
        return render_template("errors/error.html", code=404, title="Nie znaleziono",
                               message="Strona nie istnieje albo nie masz do niej dostępu."), 404

    @app.errorhandler(403)
    def _forbidden(_e):
        return render_template("errors/error.html", code=403, title="Brak dostępu",
                               message="Nie masz uprawnień do tej operacji."), 403

    @app.errorhandler(400)
    def _bad_request(_e):
        return render_template("errors/error.html", code=400, title="Nieprawidłowe żądanie",
                               message="Formularz wygasł lub zawiera błędy. Odśwież stronę i spróbuj ponownie."), 400

    @app.errorhandler(500)
    def _server_error(_e):
        db.session.rollback()
        return render_template("errors/error.html", code=500, title="Błąd serwera",
                               message="Coś poszło nie tak. Spróbuj ponownie za chwilę."), 500


def _register_cli(app):
    @app.cli.command("seed-demo")
    def seed_demo_command():
        """Create demo account (demo / demo1234) with sample data."""
        from .seed import advisory_lock, seed_catalogue, seed_demo

        with advisory_lock():
            seed_catalogue()
            created = seed_demo()
        click.echo("Utworzono konto demo." if created else "Konto demo już istnieje – pominięto.")


def bootstrap_database(app):
    from .seed import advisory_lock, seed_catalogue, seed_demo

    retries = max(1, app.config["DB_CONNECT_RETRIES"])
    for attempt in range(1, retries + 1):
        try:
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            break
        except Exception as exc:  # noqa: BLE001
            if attempt == retries:
                raise
            log.warning("database not reachable (attempt %d/%d): %s", attempt, retries, exc.__class__.__name__)
            time.sleep(2)

    with advisory_lock():
        db.create_all()
        seed_catalogue()
        if app.config["SEED_DEMO"]:
            seed_demo()
    db.session.remove()
    if db.engine.dialect.name != "sqlite":
        db.engine.dispose()

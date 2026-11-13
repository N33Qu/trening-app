from flask import Blueprint, Response, current_app, jsonify
from sqlalchemy import text

from ..extensions import db
from ..metrics import render_metrics

bp = Blueprint("health", __name__)


@bp.get("/healthz")
def healthz():
    return jsonify(status="ok", version=current_app.config["APP_VERSION"])


@bp.get("/readyz")
def readyz():
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db.session.rollback()
        current_app.logger.warning("readiness check failed: database unreachable")
        return jsonify(status="unavailable", database="down"), 503
    return jsonify(status="ready", database="up")


@bp.get("/metrics")
def metrics():
    payload, content_type = render_metrics()
    return Response(payload, content_type=content_type)

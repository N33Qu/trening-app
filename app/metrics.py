import logging
import os

from flask import current_app
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, generate_latest
from prometheus_client.core import GaugeMetricFamily
from prometheus_flask_exporter import PrometheusMetrics
from sqlalchemy import func, select

from .extensions import db

log = logging.getLogger(__name__)


def multiprocess_enabled():
    return bool(os.environ.get("PROMETHEUS_MULTIPROC_DIR"))


def init_metrics(app):
    registry = CollectorRegistry(auto_describe=True)
    PrometheusMetrics(
        app,
        path=None,
        registry=registry,
        group_by="url_rule",
        excluded_paths=["/metrics", "/static"],
        defaults_prefix="flask",
    )
    pr_counter = Counter(
        "trening_personal_records",
        "Number of new personal records detected when saving workouts",
        registry=registry,
    )
    app.extensions["trening_metrics"] = {"registry": registry, "pr_counter": pr_counter}


def record_personal_records(amount=1):
    current_app.extensions["trening_metrics"]["pr_counter"].inc(amount)


class BusinessCollector:
    """Gauges computed from the database at scrape time."""

    def collect(self):
        from .models import PersonalRecord, User, Workout

        users = GaugeMetricFamily("trening_users_total", "Registered user accounts")
        workouts = GaugeMetricFamily("trening_workouts_total", "Logged workouts")
        records = GaugeMetricFamily("trening_personal_records_stored", "Personal records stored in database")
        up = GaugeMetricFamily("trening_db_up", "1 if database query for business metrics succeeded")
        try:
            users.add_metric([], db.session.execute(select(func.count(User.id))).scalar() or 0)
            workouts.add_metric([], db.session.execute(select(func.count(Workout.id))).scalar() or 0)
            records.add_metric([], db.session.execute(select(func.count(PersonalRecord.id))).scalar() or 0)
            up.add_metric([], 1)
            yield users
            yield workouts
            yield records
        except Exception:  # noqa: BLE001 - metrics must never break scraping
            db.session.rollback()
            log.warning("business metrics query failed", exc_info=True)
            up.add_metric([], 0)
        yield up


def render_metrics():
    if multiprocess_enabled():
        from prometheus_client import multiprocess

        base = CollectorRegistry()
        multiprocess.MultiProcessCollector(base)
    else:
        base = current_app.extensions["trening_metrics"]["registry"]
    business = CollectorRegistry(auto_describe=False)
    business.register(BusinessCollector())
    payload = generate_latest(base) + generate_latest(business)
    return payload, CONTENT_TYPE_LATEST

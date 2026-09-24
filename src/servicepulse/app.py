import os
import sqlite3
import time
from functools import wraps
from pathlib import Path

from flask import Flask, Response, g, jsonify, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)

VALID_SEVERITIES = {"low", "medium", "high", "critical"}
VALID_STATUSES = {"open", "investigating", "resolved"}


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=os.getenv("SERVICEPULSE_DB", str(Path(app.instance_path) / "servicepulse.db")),
        API_KEY=os.getenv("SERVICEPULSE_API_KEY", "local-demo-key"),
        TESTING=False,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    registry = CollectorRegistry()
    request_count = Counter(
        "servicepulse_http_requests_total",
        "Total HTTP requests handled by ServicePulse",
        ["method", "endpoint", "status"],
        registry=registry,
    )
    request_latency = Histogram(
        "servicepulse_http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["endpoint"],
        registry=registry,
    )
    app.extensions["metrics_registry"] = registry

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
        return g.db

    def init_db():
        database = get_db()
        database.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                service TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        database.commit()

    @app.teardown_appcontext
    def close_db(_error=None):
        database = g.pop("db", None)
        if database is not None:
            database.close()

    def require_api_key(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if request.headers.get("X-API-Key") != app.config["API_KEY"]:
                return jsonify(error="A valid X-API-Key header is required"), 401
            return view(*args, **kwargs)

        return wrapped

    @app.before_request
    def start_timer():
        g.request_started = time.perf_counter()

    @app.after_request
    def record_metrics(response):
        endpoint = request.endpoint or "unknown"
        request_count.labels(request.method, endpoint, str(response.status_code)).inc()
        request_latency.labels(endpoint).observe(time.perf_counter() - g.request_started)
        return response

    @app.get("/health")
    def health():
        get_db().execute("SELECT 1").fetchone()
        return jsonify(service="servicepulse", status="healthy"), 200

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)

    @app.get("/api/incidents")
    def list_incidents():
        rows = get_db().execute(
            "SELECT id, title, service, severity, status, created_at, updated_at "
            "FROM incidents ORDER BY id DESC"
        ).fetchall()
        return jsonify([dict(row) for row in rows]), 200

    @app.post("/api/incidents")
    @require_api_key
    def create_incident():
        payload = request.get_json(silent=True) or {}
        error = validate_incident(payload)
        if error:
            return jsonify(error=error), 400
        database = get_db()
        cursor = database.execute(
            "INSERT INTO incidents (title, service, severity, status) VALUES (?, ?, ?, ?)",
            (
                payload["title"].strip(),
                payload["service"].strip(),
                payload["severity"],
                payload.get("status", "open"),
            ),
        )
        database.commit()
        row = database.execute(
            "SELECT id, title, service, severity, status, created_at, updated_at "
            "FROM incidents WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return jsonify(dict(row)), 201

    @app.patch("/api/incidents/<int:incident_id>")
    @require_api_key
    def update_incident(incident_id):
        payload = request.get_json(silent=True) or {}
        status = payload.get("status")
        if status not in VALID_STATUSES:
            return jsonify(error="status must be open, investigating, or resolved"), 400
        database = get_db()
        cursor = database.execute(
            "UPDATE incidents SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, incident_id),
        )
        database.commit()
        if cursor.rowcount == 0:
            return jsonify(error="incident not found"), 404
        row = database.execute(
            "SELECT id, title, service, severity, status, created_at, updated_at "
            "FROM incidents WHERE id = ?",
            (incident_id,),
        ).fetchone()
        return jsonify(dict(row)), 200

    with app.app_context():
        init_db()

    return app


def validate_incident(payload):
    title = payload.get("title")
    service = payload.get("service")
    severity = payload.get("severity")
    status = payload.get("status", "open")
    if not isinstance(title, str) or not title.strip():
        return "title is required"
    if not isinstance(service, str) or not service.strip():
        return "service is required"
    if severity not in VALID_SEVERITIES:
        return "severity must be low, medium, high, or critical"
    if status not in VALID_STATUSES:
        return "status must be open, investigating, or resolved"
    return None

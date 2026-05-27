from flask import Blueprint, jsonify, current_app
from app.extensions import db
from sqlalchemy import text

health_bp = Blueprint("health", __name__)


@health_bp.route("/healthcheck", methods=["GET"])
def healthcheck():
    """Liveness + readiness probe: checks the app and DB connectivity."""
    db_status = "ok"
    db_error = None

    try:
        db.session.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = "unavailable"
        db_error = str(exc)
        current_app.logger.error(
            "Healthcheck: database unreachable", extra={"error": db_error}
        )

    status_code = 200 if db_status == "ok" else 503
    payload = {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
    }
    if db_error:
        payload["database_error"] = db_error

    current_app.logger.debug("Healthcheck called", extra={"db_status": db_status})
    return jsonify(payload), status_code

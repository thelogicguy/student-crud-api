from flask import Flask, jsonify
from app.config import get_config
from app.extensions import db, migrate
from app.logger import setup_logger
from app.routes.health import health_bp
from app.routes.students import students_bp


def create_app(config=None):
    app = Flask(__name__)

    # ── Configuration ────────────────────────────────────────────────────────
    if config is None:
        cfg = get_config()
    else:
        cfg = config

    app.config.from_object(cfg)

    # ── Extensions ───────────────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)

    # ── Logging ──────────────────────────────────────────────────────────────
    setup_logger(app)

    # ── Blueprints ───────────────────────────────────────────────────────────
    app.register_blueprint(health_bp)
    app.register_blueprint(students_bp, url_prefix="/api/v1/students")

    # ── Root index ───────────────────────────────────────────────────────────
    # A 200 at "/" gives clients (and the DAST spider) a discoverable entry point
    # instead of a 404, and advertises the live endpoints.
    @app.route("/", methods=["GET"])
    def index():
        return jsonify(
            {
                "status": "ok",
                "service": "student-crud-api",
                "endpoints": {
                    "health": "/healthcheck",
                    "students": "/api/v1/students",
                },
            }
        ), 200

    # ── Security headers ───────────────────────────────────────────────────────
    # Applied to every response (including error handlers). Closes the baseline
    # DAST findings: Storable/Cacheable Content [10049], missing CSP [10038],
    # X-Content-Type-Options [10021], X-Frame-Options [10020], etc. This is a
    # JSON API that serves no browser-rendered content, so the policy is strict.
    @app.after_request
    def set_security_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        # Cross-Origin-Resource-Policy [ZAP 90004]: this API's responses should
        # never be embedded as a cross-origin resource.
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )
        # Werkzeug leaks its version in the Server header; drop the detail.
        response.headers["Server"] = "student-crud-api"
        return response

    # ── Error Handlers ───────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"status": "error", "message": "Route not found."}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"status": "error", "message": "Method not allowed."}), 405

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error("Unhandled exception", exc_info=True)
        return jsonify({"status": "error", "message": "Internal server error."}), 500

    # Import models so Flask-Migrate can detect them
    from app.models import Student  # noqa: F401

    app.logger.info("Application created", extra={"env": cfg.__class__.__name__})
    return app

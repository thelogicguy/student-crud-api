from flask import Flask, jsonify
from app.config import get_config, TestingConfig
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

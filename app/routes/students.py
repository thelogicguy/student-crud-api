from flask import Blueprint, jsonify, request, current_app
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.student import Student
from app.schemas.student import StudentCreateSchema, StudentUpdateSchema

students_bp = Blueprint("students", __name__)

_create_schema = StudentCreateSchema()
_update_schema = StudentUpdateSchema()


# ─── Helpers ────────────────────────────────────────────────────────────────

def _success(data, status=200):
    return jsonify({"status": "success", "data": data}), status


def _error(message, status=400, details=None):
    body = {"status": "error", "message": message}
    if details:
        body["details"] = details
    return jsonify(body), status


# ─── Routes ─────────────────────────────────────────────────────────────────

@students_bp.route("", methods=["POST"])
def create_student():
    """Add a new student."""
    payload = request.get_json(silent=True)
    if payload is None:
        current_app.logger.warning("create_student: invalid or missing JSON body")
        return _error("Request body must be valid JSON", 400)

    try:
        data = _create_schema.load(payload)
    except ValidationError as exc:
        current_app.logger.warning(
            "create_student: validation failed", extra={"errors": exc.messages}
        )
        return _error("Validation failed", 422, exc.messages)

    student = Student(**data)
    try:
        db.session.add(student)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        current_app.logger.warning(
            "create_student: duplicate email", extra={"email": data.get("email")}
        )
        return _error(f"A student with email '{data['email']}' already exists.", 409)

    current_app.logger.info(
        "create_student: student created", extra={"student_id": student.id}
    )
    return _success(student.to_dict(), 201)


@students_bp.route("", methods=["GET"])
def get_all_students():
    """Retrieve all students with optional pagination."""
    try:
        page = int(request.args.get("page", 1))
        per_page = min(int(request.args.get("per_page", 20)), 100)
    except ValueError:
        return _error("'page' and 'per_page' must be integers", 400)

    pagination = Student.query.order_by(Student.id).paginate(
        page=page, per_page=per_page, error_out=False
    )

    current_app.logger.info(
        "get_all_students",
        extra={"page": page, "per_page": per_page, "total": pagination.total},
    )
    return _success(
        {
            "students": [s.to_dict() for s in pagination.items],
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            },
        }
    )


@students_bp.route("/<int:student_id>", methods=["GET"])
def get_student(student_id):
    """Retrieve a single student by ID."""
    student = db.session.get(Student, student_id)
    if not student:
        current_app.logger.warning(
            "get_student: not found", extra={"student_id": student_id}
        )
        return _error(f"Student with id {student_id} not found.", 404)

    current_app.logger.info("get_student", extra={"student_id": student_id})
    return _success(student.to_dict())


@students_bp.route("/<int:student_id>", methods=["PUT"])
def update_student(student_id):
    """Update an existing student (partial update supported)."""
    student = db.session.get(Student, student_id)
    if not student:
        current_app.logger.warning(
            "update_student: not found", extra={"student_id": student_id}
        )
        return _error(f"Student with id {student_id} not found.", 404)

    payload = request.get_json(silent=True)
    if payload is None:
        return _error("Request body must be valid JSON", 400)

    try:
        data = _update_schema.load(payload)
    except ValidationError as exc:
        current_app.logger.warning(
            "update_student: validation failed", extra={"errors": exc.messages}
        )
        return _error("Validation failed", 422, exc.messages)

    if not data:
        return _error("No updatable fields provided.", 400)

    for field, value in data.items():
        setattr(student, field, value)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        current_app.logger.warning(
            "update_student: duplicate email", extra={"email": data.get("email")}
        )
        return _error(f"A student with email '{data['email']}' already exists.", 409)

    current_app.logger.info("update_student: updated", extra={"student_id": student_id})
    return _success(student.to_dict())


@students_bp.route("/<int:student_id>", methods=["DELETE"])
def delete_student(student_id):
    """Delete a student record."""
    student = db.session.get(Student, student_id)
    if not student:
        current_app.logger.warning(
            "delete_student: not found", extra={"student_id": student_id}
        )
        return _error(f"Student with id {student_id} not found.", 404)

    db.session.delete(student)
    db.session.commit()

    current_app.logger.info("delete_student: deleted", extra={"student_id": student_id})
    return jsonify({"status": "success", "message": f"Student {student_id} deleted."}), 200

from marshmallow import Schema, fields, validate, validates, ValidationError
import re


class StudentCreateSchema(Schema):
    first_name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=100),
        metadata={"description": "Student's first name"},
    )
    last_name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=100),
        metadata={"description": "Student's last name"},
    )
    email = fields.Email(
        required=True,
        validate=validate.Length(max=255),
        metadata={"description": "Student's unique email address"},
    )
    date_of_birth = fields.Date(
        required=True,
        format="%Y-%m-%d",
        metadata={"description": "Date of birth in YYYY-MM-DD format"},
    )
    grade = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.Length(max=10),
        metadata={"description": "Student's grade (e.g. '10', 'A', 'Grade 5')"},
    )

    @validates("first_name")
    def validate_first_name(self, value):
        if not value.strip():
            raise ValidationError("first_name cannot be blank.")

    @validates("last_name")
    def validate_last_name(self, value):
        if not value.strip():
            raise ValidationError("last_name cannot be blank.")


class StudentUpdateSchema(Schema):
    first_name = fields.Str(
        required=False,
        validate=validate.Length(min=1, max=100),
    )
    last_name = fields.Str(
        required=False,
        validate=validate.Length(min=1, max=100),
    )
    email = fields.Email(
        required=False,
        validate=validate.Length(max=255),
    )
    date_of_birth = fields.Date(
        required=False,
        format="%Y-%m-%d",
    )
    grade = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.Length(max=10),
    )
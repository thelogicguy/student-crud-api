import pytest
from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    """Create application for testing with an in-memory SQLite DB."""
    _app = create_app(config=TestingConfig())
    with _app.app_context():
        _db.create_all()
        yield _app
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    """Test client; each test gets a clean DB state."""
    with app.app_context():
        # Truncate all tables before each test
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()
    return app.test_client()


@pytest.fixture
def sample_student_payload():
    return {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
        "date_of_birth": "1815-12-10",
        "grade": "A",
    }


@pytest.fixture
def created_student(client, sample_student_payload):
    """Creates a student via the API and returns the response JSON."""
    resp = client.post(
        "/api/v1/students",
        json=sample_student_payload,
        content_type="application/json",
    )
    assert resp.status_code == 201
    return resp.get_json()["data"]

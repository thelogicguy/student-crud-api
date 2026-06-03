"""Unit tests for /api/v1/students endpoints."""


BASE = "/api/v1/students"


# ─── Healthcheck ─────────────────────────────────────────────────────────────

class TestHealthcheck:
    def test_healthcheck_returns_200(self, client):
        resp = client.get("/healthcheck")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["database"] == "ok"


# ─── Create Student ───────────────────────────────────────────────────────────

class TestCreateStudent:
    def test_create_student_success(self, client, sample_student_payload):
        resp = client.post(BASE, json=sample_student_payload)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "success"
        student = data["data"]
        assert student["first_name"] == "Ada"
        assert student["last_name"] == "Lovelace"
        assert student["email"] == "ada@example.com"
        assert student["grade"] == "A"
        assert student["id"] is not None
        assert student["created_at"] is not None

    def test_create_student_missing_required_field(self, client):
        resp = client.post(BASE, json={"first_name": "Ada"})
        assert resp.status_code == 422
        body = resp.get_json()
        assert body["status"] == "error"
        assert "details" in body

    def test_create_student_invalid_email(self, client):
        resp = client.post(
            BASE,
            json={
                "first_name": "Ada",
                "last_name": "Lovelace",
                "email": "not-an-email",
                "date_of_birth": "1815-12-10",
            },
        )
        assert resp.status_code == 422

    def test_create_student_duplicate_email(self, client, sample_student_payload):
        client.post(BASE, json=sample_student_payload)
        resp = client.post(BASE, json=sample_student_payload)
        assert resp.status_code == 409
        assert "already exists" in resp.get_json()["message"]

    def test_create_student_invalid_json(self, client):
        resp = client.post(BASE, data="not json", content_type="application/json")
        assert resp.status_code == 400

    def test_create_student_no_grade(self, client):
        payload = {
            "first_name": "Charles",
            "last_name": "Babbage",
            "email": "charles@example.com",
            "date_of_birth": "1791-12-26",
        }
        resp = client.post(BASE, json=payload)
        assert resp.status_code == 201
        assert resp.get_json()["data"]["grade"] is None

    def test_create_student_blank_first_name(self, client):
        payload = {
            "first_name": "   ",
            "last_name": "Lovelace",
            "email": "blank@example.com",
            "date_of_birth": "1815-12-10",
        }
        resp = client.post(BASE, json=payload)
        assert resp.status_code == 422


# ─── Get All Students ─────────────────────────────────────────────────────────

class TestGetAllStudents:
    def test_get_all_students_empty(self, client):
        resp = client.get(BASE)
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["students"] == []
        assert data["pagination"]["total"] == 0

    def test_get_all_students_with_data(self, client, created_student):
        resp = client.get(BASE)
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data["students"]) == 1
        assert data["pagination"]["total"] == 1

    def test_get_all_students_pagination(self, client):
        students = [
            {
                "first_name": f"Student{i}",
                "last_name": "Test",
                "email": f"student{i}@example.com",
                "date_of_birth": "2000-01-01",
            }
            for i in range(5)
        ]
        for s in students:
            client.post(BASE, json=s)

        resp = client.get(f"{BASE}?page=1&per_page=2")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data["students"]) == 2
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["pages"] == 3
        assert data["pagination"]["has_next"] is True

    def test_get_all_students_invalid_page(self, client):
        resp = client.get(f"{BASE}?page=abc")
        assert resp.status_code == 400


# ─── Get Student by ID ────────────────────────────────────────────────────────

class TestGetStudentById:
    def test_get_student_success(self, client, created_student):
        sid = created_student["id"]
        resp = client.get(f"{BASE}/{sid}")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["id"] == sid

    def test_get_student_not_found(self, client):
        resp = client.get(f"{BASE}/99999")
        assert resp.status_code == 404
        assert "not found" in resp.get_json()["message"]


# ─── Update Student ───────────────────────────────────────────────────────────

class TestUpdateStudent:
    def test_update_student_success(self, client, created_student):
        sid = created_student["id"]
        resp = client.put(f"{BASE}/{sid}", json={"grade": "A+"})
        assert resp.status_code == 200
        updated = resp.get_json()["data"]
        assert updated["grade"] == "A+"
        assert updated["first_name"] == "Ada"  # unchanged

    def test_update_student_email(self, client, created_student):
        sid = created_student["id"]
        resp = client.put(f"{BASE}/{sid}", json={"email": "new_ada@example.com"})
        assert resp.status_code == 200
        assert resp.get_json()["data"]["email"] == "new_ada@example.com"

    def test_update_student_not_found(self, client):
        resp = client.put(f"{BASE}/99999", json={"grade": "B"})
        assert resp.status_code == 404

    def test_update_student_duplicate_email(self, client):
        client.post(
            BASE,
            json={
                "first_name": "Alan",
                "last_name": "Turing",
                "email": "alan@example.com",
                "date_of_birth": "1912-06-23",
            },
        )
        r2 = client.post(
            BASE,
            json={
                "first_name": "Grace",
                "last_name": "Hopper",
                "email": "grace@example.com",
                "date_of_birth": "1906-12-09",
            },
        )
        sid2 = r2.get_json()["data"]["id"]
        resp = client.put(f"{BASE}/{sid2}", json={"email": "alan@example.com"})
        assert resp.status_code == 409

    def test_update_student_empty_body(self, client, created_student):
        sid = created_student["id"]
        resp = client.put(f"{BASE}/{sid}", json={})
        assert resp.status_code == 400

    def test_update_student_invalid_email(self, client, created_student):
        sid = created_student["id"]
        resp = client.put(f"{BASE}/{sid}", json={"email": "bad-email"})
        assert resp.status_code == 422


# ─── Delete Student ───────────────────────────────────────────────────────────

class TestDeleteStudent:
    def test_delete_student_success(self, client, created_student):
        sid = created_student["id"]
        resp = client.delete(f"{BASE}/{sid}")
        assert resp.status_code == 200
        assert "deleted" in resp.get_json()["message"]

        # Confirm it's gone
        resp2 = client.get(f"{BASE}/{sid}")
        assert resp2.status_code == 404

    def test_delete_student_not_found(self, client):
        resp = client.delete(f"{BASE}/99999")
        assert resp.status_code == 404


# ─── Error Handlers ───────────────────────────────────────────────────────────

class TestErrorHandlers:
    def test_404_unknown_route(self, client):
        resp = client.get("/api/v1/nonexistent")
        assert resp.status_code == 404

    def test_405_wrong_method(self, client):
        resp = client.patch(BASE)
        assert resp.status_code == 405

# Student CRUD REST API

A production-ready REST API for managing student records, built with **Python** and **Flask**. Supports full CRUD operations, API versioning, structured JSON logging, database migrations, and a `/healthcheck` endpoint.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [API Endpoints](#api-endpoints)
- [Local Setup](#local-setup)
- [Environment Variables](#environment-variables)
- [Database Migrations](#database-migrations)
- [Running Tests](#running-tests)
- [Postman Collection](#postman-collection)

---

## Tech Stack

| Layer       | Technology                         |
|-------------|-------------------------------------|
| Language    | Python 3.11+                        |
| Framework   | Flask 3.x                           |
| ORM         | Flask-SQLAlchemy + SQLAlchemy 2.x   |
| Migrations  | Flask-Migrate (Alembic)             |
| Validation  | Marshmallow                         |
| Logging     | python-json-logger (structured JSON)|
| Database    | PostgreSQL (SQLite for tests)       |
| WSGI Server | Gunicorn                            |
| Testing     | pytest + pytest-flask               |

---

## Project Structure

```
student-crud-api/
├── app/
│   ├── __init__.py          # Application factory
│   ├── config.py            # Environment-based config
│   ├── extensions.py        # SQLAlchemy, Migrate singletons
│   ├── logger.py            # Structured JSON logging setup
│   ├── models/
│   │   └── student.py       # Student SQLAlchemy model
│   ├── routes/
│   │   ├── health.py        # GET /healthcheck
│   │   └── students.py      # /api/v1/students CRUD routes
│   └── schemas/
│       └── student.py       # Marshmallow request schemas
├── migrations/              # Flask-Migrate / Alembic files
├── tests/
│   ├── conftest.py          # Pytest fixtures
│   └── test_students.py     # 24 unit tests across all endpoints
├── .env.example             # Environment variable template
├── .gitignore
├── docker-compose.yml       # Local PostgreSQL via Docker
├── Makefile                 # Developer shortcuts
├── postman_collection.json  # Importable Postman collection
├── requirements.txt         # Python dependencies
└── run.py                   # Application entry point
```

---

## API Endpoints

All student endpoints are versioned under `/api/v1/students`.

| Method   | Path                          | Description              |
|----------|-------------------------------|--------------------------|
| `GET`    | `/healthcheck`                | Liveness + DB probe      |
| `POST`   | `/api/v1/students`            | Create a new student     |
| `GET`    | `/api/v1/students`            | List all students (paginated) |
| `GET`    | `/api/v1/students/:id`        | Get a student by ID      |
| `PUT`    | `/api/v1/students/:id`        | Update a student (partial) |
| `DELETE` | `/api/v1/students/:id`        | Delete a student         |

### Student Object

```json
{
  "id": 1,
  "first_name": "Ada",
  "last_name": "Lovelace",
  "email": "ada@example.com",
  "date_of_birth": "1815-12-10",
  "grade": "A",
  "created_at": "2024-01-01T10:00:00+00:00",
  "updated_at": "2024-01-01T10:00:00+00:00"
}
```

### Pagination Query Parameters

`GET /api/v1/students?page=1&per_page=20`

| Parameter  | Default | Max  | Description          |
|------------|---------|------|----------------------|
| `page`     | `1`     | —    | Page number          |
| `per_page` | `20`    | `100`| Records per page     |

---

## Local Setup

### Prerequisites

- Python 3.11+
- Docker + Docker Compose
- `make`

### Step 1 – Clone the repository

```bash
git clone https://github.com/<your-username>/student-crud-api.git
cd student-crud-api
```

### Step 2 – Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### Step 3 – Install dependencies

```bash
make install
# or: pip install -r requirements.txt
```

### Step 4 – Configure environment variables

```bash
cp .env.example .env
# Edit .env with your database credentials
```

### Step 5 – Start PostgreSQL and the API via Docker

**Option A – Docker Compose (recommended)**

```bash
make docker-db-up
# Starts postgres:16 on localhost:5432
```

```bash
make docker-db-migrate
# Applies all Alembic migration scripts inside the API container
```

```bash
make docker-build
# Builds the REST API docker image
```

```bash
make docker-api-up
# Starts the API container after the DB is running and migrations are applied
```

> `make docker-api-up` already performs the correct order:
> 1. start the DB container
> 2. run DB migrations
> 3. start the API container

**Option B – Local PostgreSQL**

```sql
CREATE DATABASE student_db;
```
Then update `DATABASE_URL` in `.env` accordingly.

### Step 6 – Run database migrations (local dev)

```bash
make db-upgrade
# Applies all Alembic migration scripts
```

### Step 7 – Start the server

```bash
make dev       # Flask dev server with hot-reload (port 5000)
# or
make run       # Gunicorn production server
```

The API will be available at `http://localhost:5000`.

---

## Environment Variables

Copy `.env.example` to `.env` and set the following:

| Variable       | Required | Default       | Description                                   |
|----------------|----------|---------------|-----------------------------------------------|
| `DATABASE_URL` | ✅ Yes   | —             | PostgreSQL connection string                  |
| `FLASK_ENV`    | No       | `development` | `development`, `testing`, or `production`     |
| `FLASK_APP`    | No       | `run.py`      | Entry point for the `flask` CLI               |
| `SECRET_KEY`   | No       | (dev default) | Flask secret key — **change in production**   |
| `PORT`         | No       | `5000`        | Port for the server                           |
| `LOG_LEVEL`    | No       | `INFO`        | `DEBUG`, `INFO`, `WARNING`, `ERROR`           |

Example `DATABASE_URL`:
```
postgresql://postgres:postgres@localhost:5432/student_db
```

---

## Database Migrations

Flask-Migrate (Alembic) manages schema changes.

```bash
# First-time setup (already done if you cloned the repo)
make db-init

# Generate a migration after changing a model
make db-migrate msg="add phone_number to students"

# Apply pending migrations
make db-upgrade

# Roll back the last migration
make db-downgrade
```

---

## Running Tests

Tests use an **in-memory SQLite database** — no external services needed.

```bash
# Run all tests
make test

# Run with coverage report
make test-cov
```

Coverage report is written to `htmlcov/index.html`.

### Test Coverage

| Class                  | Tests |
|------------------------|-------|
| `TestHealthcheck`      | 1     |
| `TestCreateStudent`    | 7     |
| `TestGetAllStudents`   | 4     |
| `TestGetStudentById`   | 2     |
| `TestUpdateStudent`    | 6     |
| `TestDeleteStudent`    | 2     |
| `TestErrorHandlers`    | 2     |
| **Total**              | **24**|

---

## Postman Collection

Import `postman_collection.json` into Postman:

1. Open Postman → **Import** → select `postman_collection.json`
2. Set the `base_url` collection variable to `http://localhost:5000`
3. Use **Create Student** first — it auto-saves the `student_id` variable for subsequent requests

---

## Make Targets

```
make help          Show all available targets
make install       Install Python dependencies
make dev           Start Flask dev server (hot-reload)
make run           Start Gunicorn production server
make test          Run all unit tests
make test-cov      Run tests with HTML coverage report
make db-upgrade    Apply pending DB migrations
make db-migrate    Generate a new migration (use msg="description")
make db-downgrade  Revert the last migration
make docker-db-up  Start PostgreSQL via Docker Compose
make docker-db-migrate Apply DB migrations inside the API container
make docker-build  Build the REST API Docker image
make docker-api-up Start DB, run migrations, and start the API container
make docker-down   Stop Docker Compose services
make clean         Remove cache and coverage files
```

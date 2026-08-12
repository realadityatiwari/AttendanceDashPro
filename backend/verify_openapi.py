import json
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
response = client.get("/api/v1/openapi.json")
openapi_data = response.json()

paths = openapi_data.get("paths", {})
openapi_endpoints = set()
for path, methods in paths.items():
    for method in methods:
        openapi_endpoints.add(f"{method.upper()} {path}")

# Hardcode the ones from API_DESIGN.md
design_endpoints = {
    "GET /api/v1/student/me",
    "GET /api/v1/subjects",
    "GET /api/v1/timetable",
    "GET /api/v1/calendar/today",
    "GET /api/v1/calendar/{target_date}",
    "GET /api/v1/events",
    "GET /api/v1/attendance/summary/{subject_code}",
    "POST /api/v1/attendance",
    "GET /api/v1/quiz-eligibility/{subject_code}/{quiz_cycle}",
    "GET /api/v1/laboratory/{subject_code}/experiments",
    "GET /api/v1/laboratory/{subject_code}/records"
}

missing = design_endpoints - openapi_endpoints
extra = openapi_endpoints - design_endpoints - {"GET /api/v1/", "GET /api/v1/health"}

print("MISSING from OpenAPI:", missing)
print("EXTRA in OpenAPI:", extra)

import sys
import json
from fastapi.testclient import TestClient
from app.main import app
from app.api.dependencies.deps import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal

client = TestClient(app)

print("--- TESTING PUBLIC ENDPOINTS ---")
response = client.get("/")
print(f"GET / -> Status: {response.status_code}, Body: {response.json()}")

response = client.get("/health")
print(f"GET /health -> Status: {response.status_code}, Body: {response.json()}")

response = client.get("/api/v1/openapi.json")
print(f"GET /api/v1/openapi.json -> Status: {response.status_code}")

print("\n--- TESTING PROTECTED ENDPOINT WITHOUT AUTH ---")
response = client.get("/api/v1/student/me")
print(f"GET /api/v1/student/me -> Status: {response.status_code}, Body: {response.json()}")

print("\n--- TESTING PROTECTED ENDPOINT WITH DUMMY AUTH ---")
response = client.get("/api/v1/student/me", headers={"Authorization": "Bearer DUMMY_TOKEN"})
print(f"GET /api/v1/student/me (Auth) -> Status: {response.status_code}, Body: {response.json()}")

print("\n--- DONE ---")

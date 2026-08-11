from fastapi import FastAPI
from app.api.v1.router import api_router

app = FastAPI(
    title="AttendanceDash Pro API",
    description="Backend API for AttendanceDash Pro domain engines",
    version="1.0.0"
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "AttendanceDash Pro API is running"}

@app.get("/health")
def read_health():
    return {"status": "ok"}

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AttendanceDash Pro"
    API_V1_STR: str = "/api/v1"
    
    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3100", "http://127.0.0.1:3100"]
    
    # Database
    DATABASE_URI: str = "postgresql+asyncpg://postgres:postgres@localhost:55432/attendancedash"
    
    # Timezone Strategy
    INSTITUTION_TIMEZONE: str = "Asia/Kolkata"
    
    # JWT Authentication
    JWT_SECRET_KEY: str = "supersecret_development_key_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours; env-overridable for production

    # Security Headers
    SECURITY_HSTS_ENABLED: bool = False  # Enable only when HTTPS is guaranteed in production

    # Rate Limiting (in-process; for multi-process deployment use a distributed limiter)
    LOGIN_MAX_ATTEMPTS: int = 10
    LOGIN_WINDOW_SECONDS: int = 900       # 15 minutes
    REGISTER_MAX_ATTEMPTS: int = 5
    REGISTER_WINDOW_SECONDS: int = 3600   # 1 hour

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

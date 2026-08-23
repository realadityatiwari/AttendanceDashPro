from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

DEV_JWT_SECRET = "supersecret_development_key_change_in_production"

class Settings(BaseSettings):
    APP_ENV: str = "development"  # "development" | "production"
    PROJECT_NAME: str = "AttendanceDash Pro"
    API_V1_STR: str = "/api/v1"
    
    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3100", "http://127.0.0.1:3100"]
    
    # Database
    DATABASE_URI: str = "postgresql+asyncpg://postgres:postgres@localhost:55432/attendancedash"
    
    # Timezone Strategy
    INSTITUTION_TIMEZONE: str = "Asia/Kolkata"
    
    # JWT Authentication
    JWT_SECRET_KEY: str = DEV_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours; env-overridable for production

    # Security Headers
    SECURITY_HSTS_ENABLED: bool = False  # Enable only when HTTPS is guaranteed in production

    # Rate Limiting (in-process; for multi-process deployment use a distributed limiter)
    LOGIN_MAX_ATTEMPTS: int = 10
    LOGIN_WINDOW_SECONDS: int = 900       # 15 minutes
    REGISTER_MAX_ATTEMPTS: int = 5
    REGISTER_WINDOW_SECONDS: int = 3600   # 1 hour

    @model_validator(mode="after")
    def _validate_production_jwt_secret(self) -> "Settings":
        """Production guard: reject the known development default or an
        obviously unsafe JWT secret. The error message never prints the
        secret itself."""
        if self.APP_ENV == "production":
            if self.JWT_SECRET_KEY == DEV_JWT_SECRET:
                raise ValueError(
                    "JWT_SECRET_KEY cannot be the development default when "
                    "APP_ENV=production. Set a strong random secret via the "
                    "JWT_SECRET_KEY environment variable."
                )
            if len(self.JWT_SECRET_KEY) < 20:
                raise ValueError(
                    "JWT_SECRET_KEY must be at least 20 characters when "
                    "APP_ENV=production."
                )
        return self

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

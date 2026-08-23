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
    def _validate_production_config(self) -> "Settings":
        """Production guard (Phase 17 + 18B):
        - Reject the known development default or an obviously unsafe JWT secret.
        - Reject development database hosts (localhost/127.0.0.1/host.docker.internal).
        - Reject localhost CORS origins.
        The error messages never print secret values.
        """
        if self.APP_ENV != "production":
            return self
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
        for dev_host in ("localhost", "127.0.0.1", "host.docker.internal"):
            if dev_host in self.DATABASE_URI:
                raise ValueError(
                    "DATABASE_URI must not reference a development host "
                    f"({dev_host}) when APP_ENV=production. Use the production "
                    "database service hostname (e.g. postgres) or a managed "
                    "database endpoint."
                )
        for origin in self.BACKEND_CORS_ORIGINS:
            if "localhost" in origin or "127.0.0.1" in origin:
                raise ValueError(
                    "BACKEND_CORS_ORIGINS must not contain localhost origins "
                    "when APP_ENV=production."
                )
        return self

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

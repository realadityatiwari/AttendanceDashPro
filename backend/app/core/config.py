from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AttendanceDash Pro"
    API_V1_STR: str = "/api/v1"
    
    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3100", "http://127.0.0.1:3100"]
    
    # Database
    DATABASE_URI: str = "postgresql+asyncpg://postgres:postgres@localhost:55432/attendancedash"
    
    # Timezone Strategy
    # As per ADR/Migration notes, the institutional timezone is Asia/Kolkata
    INSTITUTION_TIMEZONE: str = "Asia/Kolkata"
    
    # JWT Authentication
    JWT_SECRET_KEY: str = "supersecret_development_key_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200 # 30 days

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

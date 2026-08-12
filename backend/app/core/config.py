from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AttendanceDash Pro"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URI: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/attendancedash"
    
    # Timezone Strategy
    # As per ADR/Migration notes, the institutional timezone is Asia/Kolkata
    INSTITUTION_TIMEZONE: str = "Asia/Kolkata"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

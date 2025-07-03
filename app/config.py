"""
 Application Configuration Module
 Handles all the environment variables and settings
"""
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, EmailStr, PostgresDsn, field_validator, ValidationInfo

class Settings(BaseSettings):
    """ Application Settings """
    # Application
    APP_NAME:str = "JRN Resume Builder"
    APP_VERSION:str = "1.0.0"
    API_V1_STR:str="/api/v1/resume"

    # Server
    HOST:str = "0.0.0.0"
    PORT:int = 8001
    WORKERS:int = 2

    # Security
    SECRET_KEY:str
    ALGORITHM:str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES:int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_MIN_LENGTH: int = 8

    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)


    # Database
    POSTGRES_SERVER:str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: str = "5432"
    DATABASE_URL: Optional[str] = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info: ValidationInfo) -> str:
        if isinstance(v, str):
            return v

        user = info.data["POSTGRES_USER"]
        password = info.data["POSTGRES_PASSWORD"]
        host = info.data.get("POSTGRES_SERVER", "localhost")
        port = info.data.get("POSTGRES_PORT", "5432")
        db = info.data["POSTGRES_DB"]

        # Ensure proper URL encoding of special characters in password
        from urllib.parse import quote_plus
        password = quote_plus(password)

        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"

    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_DB: int = 0
    
    # AI Services
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    AI_MODEL: str = "gpt-4"
    AI_MAX_TOKENS: int = 2000
    AI_TEMPERATURE: float = 0.7
    AI_TIMEOUT: int = 30

    # File Storage
    UPLOAD_DIR: str = "static/uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_FILE_TYPES: List[str] = [".pdf", ".docx", ".doc"]

    # Email
    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = None
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[EmailStr] = None
    EMAILS_FROM_NAME: Optional[str] = None
    
    @field_validator("EMAILS_FROM_NAME")
    def get_project_name(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if not v:
            return values["APP_NAME"]
        return v
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: List[str] = ["json"]
    CELERY_TIMEZONE: str = "UTC"

    # Monitoring
    SENTRY_DSN: Optional[str] = None
    ENABLE_METRICS: bool = True
    LOG_LEVEL: str = "INFO"
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60  # seconds
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # Resume Processing
    MAX_RESUME_VERSIONS: int = 10
    RESUME_ANALYSIS_CACHE_TTL: int = 3600  # 1 hour
    
    # Job Description Processing
    JOB_DESCRIPTION_MAX_LENGTH: int = 50000
    SKILLS_EXTRACTION_CACHE_TTL: int = 7200  # 2 hours
    
    # Templates
    DEFAULT_TEMPLATE_ID: int = 1
    TEMPLATE_CACHE_TTL: int = 86400  # 24 hours
    
    # Export Settings
    PDF_MAX_SIZE: int = 50 * 1024 * 1024  # 50MB
    EXPORT_TIMEOUT: int = 60  # seconds
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"

class DevelopmentSettings(Settings):
    """Development environment settings."""
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    WORKERS: int = 1


class ProductionSettings(Settings):
    """Production environment settings."""
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    WORKERS: int = 4
    
    # Enhanced security for production
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    RATE_LIMIT_REQUESTS: int = 60
    

class TestingSettings(Settings):
    """Testing environment settings."""
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    
    # Use test database
    POSTGRES_DB: str = "ai_resume_test"
    
    # Disable external services
    SENTRY_DSN: Optional[str] = None
    ENABLE_METRICS: bool = False
    
    # Faster testing
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 5
    PASSWORD_MIN_LENGTH: int = 4


@lru_cache()
def get_settings() -> Settings:
    """Get application settings based on environment."""
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    if env == "production":
        return ProductionSettings()
    elif env == "testing":
        return TestingSettings()
    else:
        return DevelopmentSettings()


# Global settings instance
settings = get_settings()

# Additional configuration constants
class Constants:
    """Application constants."""
    
    # User roles
    USER_ROLE_USER = "user"
    USER_ROLE_ADMIN = "admin"
    USER_ROLE_PREMIUM = "premium"
    
    # Resume sections
    RESUME_SECTIONS = [
        "personal_info",
        "summary",
        "experience",
        "education",
        "skills",
        "certifications",
        "projects",
        "achievements",
        "languages",
        "references"
    ]
    
    # File types
    SUPPORTED_MIME_TYPES = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/msword": ".doc"
    }
    
    # AI prompt types
    AI_PROMPT_TYPES = {
        "ANALYZE_RESUME": "analyze_resume",
        "ANALYZE_JOB": "analyze_job_description",
        "OPTIMIZE_RESUME": "optimize_resume",
        "EXTRACT_SKILLS": "extract_skills",
        "GENERATE_SUMMARY": "generate_summary",
        "ATS_OPTIMIZE": "ats_optimize"
    }
    
    # Export formats
    EXPORT_FORMATS = ["pdf", "docx", "json"]
    
    # Template categories
    TEMPLATE_CATEGORIES = [
        "modern",
        "classic",
        "creative",
        "technical",
        "executive",
        "academic",
        "entry_level"
    ]
    
    # Industries
    INDUSTRIES = [
        "technology",
        "finance",
        "healthcare",
        "education",
        "manufacturing",
        "retail",
        "consulting",
        "marketing",
        "sales",
        "human_resources",
        "operations",
        "legal",
        "design",
        "other"
    ]


# Export settings for easy import
__all__ = ["settings", "Settings", "Constants", "get_settings"]
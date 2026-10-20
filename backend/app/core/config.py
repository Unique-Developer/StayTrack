import os
from pathlib import Path

class Settings:
    PROJECT_NAME: str = "StayTrack"
    TAGLINE: str = "Daily Reports. Continuous Insights."
    API_V1_STR: str = "/api/v1"
    
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    STORAGE_DIR: Path = BASE_DIR / "storage" / "reports"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "staytrack-secret-encryption-key-for-jwt-and-sessions-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    DEFAULT_ADMIN_EMAIL: str = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@staytrack.local")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "StayTrack2026!")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'staytrack.db'}")
    
    # Motel Defaults
    DEFAULT_PROPERTY_NAME: str = "STUDIO 6 - STAFFORD, VA"
    DEFAULT_PROPERTY_CODE: str = "3756"
    DEFAULT_TIMEZONE: str = "America/New_York"
    
    # Analytics Defaults
    DEFAULT_ROLLING_WINDOW_DAYS: int = 30  # 30 distinct reporting dates
    DEFAULT_CONTINUOUS_STAY_DAYS: int = 30  # Mode A threshold
    DEFAULT_MIN_APPEARANCE_DAYS: int = 3    # Mode B threshold
    DEFAULT_DEPARTURE_CONVENTION: str = "checkin_plus_nights"  # check_in + nights
    RETENTION_DAYS: int = 365 * 7  # 7 years permanent default retention

    def ensure_directories(self):
        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.ensure_directories()

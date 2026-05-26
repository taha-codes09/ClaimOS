"""
Application Settings and Configuration
======================================
Centralized configuration using Pydantic Settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # ============================================================
    # API KEYS
    # ============================================================
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    
    # Pinecone
    pinecone_api_key: str = ""
    pinecone_environment: str = "us-east-1"
    pinecone_index_name: str = "insurance-claims-index"
    
    # Weather APIs
    noaa_api_key: Optional[str] = None
    tomorrow_io_api_key: str = ""
    weather_underground_api_key: Optional[str] = None
    
    # ISO ClaimSearch
    iso_claimsearch_api_key: Optional[str] = None
    
    # AWS S3
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    s3_bucket_name: Optional[str] = None
    
    # ============================================================
    # DATABASE
    # ============================================================
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "insurance_claims_db"
    database_user: str = "postgres"
    database_password: str = "postgres"
    
    @property
    def database_url(self) -> str:
        return f"postgresql://{self.database_user}:{self.database_password}@{self.database_host}:{self.database_port}/{self.database_name}"
    
    # ============================================================
    # APPLICATION
    # ============================================================
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    
    # Claim processing thresholds
    fast_track_threshold: float = 5000.0
    large_loss_threshold: float = 50000.0
    auto_approve_limit: float = 2500.0
    siu_referral_threshold: int = 60
    
    # OCR settings
    ocr_min_confidence: float = 85.0
    
    # Rate limits
    noaa_rate_limit: int = 1000
    pinecone_rate_limit: int = 10000
    
    # ============================================================
    # SECURITY
    # ============================================================
    secret_key: str = "change-this-secret-key-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:8080"
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    # ============================================================
    # LOGGING
    # ============================================================
    log_level: str = "INFO"
    log_format: str = "json"
    
    # ============================================================
    # INSURER PROFILE (Default)
    # ============================================================
    insurer_company_name: str = "Default Insurance Co"
    insurer_lines_of_business: str = "Auto,Property,Health,Liability"
    insurer_states_licensed: str = "TX,CA,NY,FL"
    
    @property
    def lines_of_business_list(self) -> List[str]:
        return [lob.strip() for lob in self.insurer_lines_of_business.split(",")]
    
    @property
    def states_licensed_list(self) -> List[str]:
        return [state.strip() for state in self.insurer_states_licensed.split(",")]
    
    # ============================================================
    # MODEL CONFIGURATION
    # ============================================================
    # Primary LLM for orchestration and complex reasoning
    orchestrator_model: str = "claude-3-5-sonnet-20241022"
    
    # Model for agents requiring strong pattern recognition
    pattern_recognition_model: str = "gpt-4o-2024-08-06"
    
    # Model for document understanding
    document_model: str = "claude-3-5-sonnet-20241022"
    
    # Model for quantitative tasks
    quantitative_model: str = "gpt-4o-2024-08-06"
    
    # Fallback model (for cost optimization)
    fallback_model: str = "gpt-4o-mini-2024-07-18"
    
    # ============================================================
    # HELPER METHODS
    # ============================================================
    
    def get_insurer_profile(self) -> dict:
        """Get default insurer profile for agent prompts."""
        return {
            "company_name": self.insurer_company_name,
            "lines_of_business": self.lines_of_business_list,
            "states_licensed": self.states_licensed_list,
            "fast_track_threshold": f"${self.fast_track_threshold:,.0f}",
            "large_loss_threshold": f"${self.large_loss_threshold:,.0f}",
            "auto_approve_limit": f"${self.auto_approve_limit:,.0f}",
            "fraud_siu_threshold": self.siu_referral_threshold,
            "erp_system": "Guidewire ClaimCenter"
        }
    
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"
    
    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Use this function to access settings throughout the application.
    """
    return Settings()


# Convenience export
settings = get_settings()

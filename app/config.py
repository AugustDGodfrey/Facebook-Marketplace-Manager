"""Application Configuration"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "sqlite:///./facebook_marketplace.db"

    # Facebook Credentials
    facebook_email: str = ""
    facebook_password: str = ""
    facebook_2fa_backup_code: str | None = None

    # AI Vision Provider
    vision_provider: str = "openai"  # "openai" or "anthropic"
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # LLM Provider
    llm_provider: str = "openai"  # "openai" or "anthropic"

    # Marketplace Scraping
    marketplace_search_interval_minutes: int = 15
    comparable_listings_count: int = 18
    image_compression_quality: int = 85
    image_max_width: int = 1200

    # Offer Settings
    offer_aggressiveness_multiplier: float = 1.0
    offer_min_floor_percentage: float = 40
    offer_absolute_minimum_dollars: float = 5
    condition_threshold_percentage: int = 50
    listing_age_motivated_days: int = 14

    # Messenger Automation
    messenger_daily_cap: int = 20
    messenger_delay_min_seconds: int = 30
    messenger_delay_max_seconds: int = 180
    human_review_queue_enabled: bool = True
    auto_send_enabled: bool = False

    # Message Generation
    message_tone: str = "casual"  # "casual" or "semi-formal"
    message_mention_comps: bool = True
    message_mention_condition: bool = True

    # Scheduler
    scheduler_enabled: bool = True
    scheduler_timezone: str = "America/New_York"

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/facebook_marketplace.log"
    log_max_bytes: int = 10485760  # 10MB
    log_backup_count: int = 5

    # Web App
    fast_api_host: str = "0.0.0.0"
    fast_api_port: int = 8000
    fast_api_reload: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def images_dir(self) -> Path:
        """Get images directory path."""
        return Path("app/images")

    @property
    def logs_dir(self) -> Path:
        """Get logs directory path."""
        return Path("logs")


settings = Settings()

"""Configuration settings for the Regulatory Classifier."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Keys
    gemini_api_key: str
    mistral_api_key: str
    openai_api_key: str
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    
    # File Storage
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 50
    
    # Model Configuration
    primary_llm_model: str = "gemini-2.5-flash"  # Updated to 2.5 Flash
    secondary_llm_model: str = "mistral-small-2503"  # Updated from deprecated mistral-small (Mistral Small 3.1)
    openai_moderation_model: str = "omni-moderation-latest"  # Updated per OpenAI API requirements
    
    # Processing Configuration
    enable_dual_llm_validation: bool = True
    min_confidence_threshold: float = 0.7
    legibility_threshold: float = 0.6
    
    # Auto-improvement settings (optional, with defaults)
    auto_improvement_feedback_threshold: int = 10
    auto_improvement_min_confidence: float = 0.75
    auto_improvement_enabled: bool = True
    auto_improvement_min_feedback: int = 5
    auto_improvement_check_interval: int = 300  # seconds
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore"  # Ignore extra fields from .env
    }


# Initialize settings
settings = Settings()

# Create upload directory if it doesn't exist
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)


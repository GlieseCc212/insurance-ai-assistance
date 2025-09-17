"""
Configuration settings for Insurance AI Assistant
"""
from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # Environment
    environment: str = "development"
    
    # API Keys
    google_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    
    # Database
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "insurance_ai"
    
    # ChromaDB
    chroma_db_path: str = "./chroma_db"
    
    # File Upload
    upload_dir: str = "./uploads"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_file_types: list = ["pdf", "docx", "doc", "txt"]
    
    # Email Settings
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    access_token_expire_minutes: int = 30
    
    # AI Model Settings
    embedding_model: str = "all-MiniLM-L6-v2"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
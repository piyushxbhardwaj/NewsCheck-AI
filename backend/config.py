import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Get root directory of the project
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    database_path: str = str(ROOT_DIR / "database" / "newscheck.db")
    
    # LLM Settings (supports OpenAI, Ollama, LM Studio, Groq, etc.)
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    
    # Search APIs
    tavily_api_key: str = ""
    
    # Cache Settings
    cache_expiry_hours: int = 24

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure the database directory exists
os.makedirs(os.path.dirname(settings.database_path), exist_ok=True)

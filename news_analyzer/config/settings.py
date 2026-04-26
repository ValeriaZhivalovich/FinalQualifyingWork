from pydantic import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения"""

    # Database
    database_url: str = "sqlite:///news_analyzer.db"

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "mistral:7b"

    # Telegram
    telegram_api_id: str = ""
    telegram_api_hash: str = ""

    # VK
    vk_access_token: str = ""

    # Scheduler
    fetch_interval_minutes: int = 30

    class Config:
        env_file = ".env"
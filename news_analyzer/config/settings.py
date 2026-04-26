from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения"""

    # Database
    database_url: str = "sqlite:///news_analyzer.db"

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "mistral:7b"

    # Telegram (для будущих коллекторов)
    telegram_api_id: str = ""
    telegram_api_hash: str = ""

    # VK (для будущих коллекторов)
    vk_access_token: str = ""

    # Scheduler
    fetch_interval_minutes: int = 30

    # UI
    ui_theme: str = "light"  # light/dark

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
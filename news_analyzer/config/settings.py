from pydantic_settings import BaseSettings


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
    telegram_phone: str = ""

    # VK
    vk_access_token: str = ""

    # Twitter/X
    twitter_username: str = ""
    twitter_password: str = ""
    twitter_email: str = ""

    # Reddit
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = ""

    # Scheduler
    fetch_interval_minutes: int = 30

    # UI
    ui_theme: str = "light"  # light/dark

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
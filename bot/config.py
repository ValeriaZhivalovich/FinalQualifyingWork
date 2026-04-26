import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bot settings
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    
    # API keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_KEY", "").strip()
    
    # API endpoints
    PERPLEXITY_API_URL: str = os.getenv("PERPLEXITY_API_URL", "")
    
    # Timeouts
    DEFAULT_TIMEOUT: float = 280.0  # Увеличено до 4.5 минут (чуть меньше серверного таймаута)
    EXTENDED_TIMEOUT: float = 280.0  # Увеличено до 4.5 минут
    IMAGE_TIMEOUT: float = 280.0  # Увеличено до 4.5 минут для обработки изображений  
    
    # Retry settings
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0
    RETRY_BACKOFF: float = 2.0
    
    # Rate limiting
    MIN_REQUEST_INTERVAL: float = 2.0
    
    # Context settings
    MAX_CONTEXT_SIZE: int = 3
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Message limits
    MAX_MESSAGE_LENGTH: int = 4096
    MAX_LOG_MESSAGE_LENGTH: int = 100
    
    # Ignore list
    IGNORED_USER_IDS: list[int] = []
    IGNORE_CHAT_ADMINS: bool = True
    
    # Service chat for admin notifications
    SERVICE_CHAT_ID: int = 0
    
    # Browser settings
    BROWSER_HEADLESS: bool = True
    BROWSER_PROFILE_DIR: str = "chrome_profile"
    PERPLEXITY_SPACE_ID: str = "crypto-asistant-T51ZY9NXQUunuH1GpXVkzg"  # ID вашего Space в Perplexity
    
    def __init__(self):
        # Browser settings from env
        self.BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "true").lower() in ("true", "1", "yes", "on")
        browser_profile_dir = os.getenv("BROWSER_PROFILE_DIR", "chrome_profile")
        self.BROWSER_PROFILE_DIR = browser_profile_dir
        self.PERPLEXITY_SPACE_ID = os.getenv("PERPLEXITY_SPACE_ID", "")
        
        ignored_ids_str = os.getenv("IGNORED_USER_IDS", "")
        if ignored_ids_str:
            try:
                self.IGNORED_USER_IDS = [int(uid.strip()) for uid in ignored_ids_str.split(",") if uid.strip()]
            except ValueError as e:
                print(f"Warning: Invalid IGNORED_USER_IDS format. Expected comma-separated integers. Error: {e}")
                print(f"Raw value: '{ignored_ids_str}'")
        
        ignore_admins_str = os.getenv("IGNORE_CHAT_ADMINS", "true").lower()
        self.IGNORE_CHAT_ADMINS = ignore_admins_str in ("true", "1", "yes", "on")
        
        # Load service chat ID
        service_chat_id_str = os.getenv("SERVICE_CHAT_ID", "0")
        try:
            self.SERVICE_CHAT_ID = int(service_chat_id_str)
        except ValueError as e:
            print(f"Warning: Invalid SERVICE_CHAT_ID format. Expected integer. Error: {e}")
            print(f"Raw value: '{service_chat_id_str}'")

config = Config()
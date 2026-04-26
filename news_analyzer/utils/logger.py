from loguru import logger
import sys
from pathlib import Path

# Настройка логирования
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

logger.remove()  # Удалить стандартный handler

# Лог в файл (основной)
logger.add(
    logs_dir / "app.log",
    rotation="10 MB",
    retention="1 week",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)

# Лог ошибок отдельно
logger.add(
    logs_dir / "errors.log",
    rotation="10 MB",
    retention="1 month",
    level="ERROR",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)

# Лог в консоль для разработки
logger.add(
    sys.stdout,
    level="INFO",
    format="{time:HH:mm:ss} | {level} | {message}"
)
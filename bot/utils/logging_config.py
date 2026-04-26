"""
Конфигурация логирования для бота
Минимум в консоли, подробности в файлах
"""
import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path

def setup_logging(log_level="INFO"):
    """Настройка логирования с минимальным выводом в консоль"""
    
    # Создаем директорию для логов
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Форматы логов
    console_format = '%(asctime)s - %(levelname)s - %(message)s'
    file_format = '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Ловим всё
    
    # Очищаем существующие обработчики
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 1. Консольный обработчик - ТОЛЬКО критические сообщения
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # Только WARNING и выше
    console_formatter = logging.Formatter(console_format, datefmt='%H:%M:%S')
    console_handler.setFormatter(console_formatter)
    
    # Фильтр для консоли - показываем только важные события
    class ImportantOnlyFilter(logging.Filter):
        def filter(self, record):
            # Показываем только критические сообщения о запуске/остановке
            important_messages = [
                "Бот запускается",
                "Бот запущен",
                "Бот останавливается",
                "Chrome браузер успешно запущен",
                "Chrome браузер остановлен",
                "Express сервер запущен",
                "Критическая ошибка",
                "CRITICAL",
                "ERROR"
            ]
            
            # Всегда показываем ERROR и CRITICAL
            if record.levelno >= logging.ERROR:
                return True
                
            # Для остальных - только если содержат важные фразы
            return any(msg in record.getMessage() for msg in important_messages)
    
    console_handler.addFilter(ImportantOnlyFilter())
    root_logger.addHandler(console_handler)
    
    # 2. Основной файловый обработчик - все логи
    main_log_file = log_dir / f"bot_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        main_log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, log_level))
    file_formatter = logging.Formatter(file_format)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # 3. Отдельный файл для ошибок
    error_log_file = log_dir / "errors.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_handler)
    
    # 4. Отдельный файл для отладки (если включен DEBUG)
    if log_level == "DEBUG":
        debug_log_file = log_dir / f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        debug_handler = logging.FileHandler(debug_log_file, encoding='utf-8')
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(file_formatter)
        root_logger.addHandler(debug_handler)
    
    # Настройка логгеров сторонних библиотек
    logging.getLogger('aiogram').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Специальный логгер для важных событий (всегда в консоль)
    important_logger = logging.getLogger('IMPORTANT')
    important_handler = logging.StreamHandler()
    important_handler.setLevel(logging.INFO)
    important_handler.setFormatter(logging.Formatter('🚀 %(message)s'))
    important_logger.addHandler(important_handler)
    important_logger.propagate = False
    
    return important_logger

def get_important_logger():
    """Получить логгер для важных сообщений"""
    return logging.getLogger('IMPORTANT')
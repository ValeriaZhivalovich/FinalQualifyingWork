"""
Модуль для управления режимом ответов (авто/мануал)
"""
import logging
from typing import Optional
import json
import os

logger = logging.getLogger(__name__)

class ResponseModeManager:
    """Менеджер режимов ответов"""
    
    def __init__(self):
        self.mode = "manual"  # По умолчанию режим с подтверждением
        self.mode_file = "response_mode.json"
        self.load_mode()
    
    def load_mode(self):
        """Загружает сохраненный режим из файла"""
        try:
            if os.path.exists(self.mode_file):
                with open(self.mode_file, 'r') as f:
                    data = json.load(f)
                    self.mode = data.get('mode', 'manual')
                    logger.info(f"Загружен режим: {self.mode}")
            else:
                logger.info("Файл режима не найден, используется режим по умолчанию: manual")
        except Exception as e:
            logger.error(f"Ошибка загрузки режима: {e}")
            self.mode = "manual"
    
    def save_mode(self):
        """Сохраняет текущий режим в файл"""
        try:
            with open(self.mode_file, 'w') as f:
                json.dump({'mode': self.mode}, f)
            logger.info(f"Режим сохранен: {self.mode}")
        except Exception as e:
            logger.error(f"Ошибка сохранения режима: {e}")
    
    def set_auto(self):
        """Включает автоматический режим (без подтверждения)"""
        self.mode = "auto"
        self.save_mode()
        logger.info("Включен автоматический режим (без подтверждения)")
        return True
    
    def set_manual(self):
        """Включает режим с подтверждением"""
        self.mode = "manual"
        self.save_mode()
        logger.info("Включен режим с подтверждением")
        return True
    
    def is_auto(self) -> bool:
        """Проверяет, включен ли автоматический режим"""
        return self.mode == "auto"
    
    def is_manual(self) -> bool:
        """Проверяет, включен ли режим с подтверждением"""
        return self.mode == "manual"
    
    def get_mode(self) -> str:
        """Возвращает текущий режим"""
        return self.mode
    
    def get_mode_description(self) -> str:
        """Возвращает описание текущего режима"""
        if self.mode == "auto":
            return "🚀 Автоматический режим (ответы отправляются сразу)"
        else:
            return "🔒 Режим с подтверждением (требуется одобрение)"

# Создаем глобальный экземпляр менеджера
response_mode_manager = ResponseModeManager()
from abc import ABC, abstractmethod
from ..models import CleanArticle, ProcessedArticle


class BaseAIAgent(ABC):
    """Абстрактный ИИ-агент"""

    @abstractmethod
    def process(self, clean_article: CleanArticle) -> ProcessedArticle:
        """Обработать статью и вернуть результат"""
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """Проверить доступность ИИ-бэкенда"""
        pass
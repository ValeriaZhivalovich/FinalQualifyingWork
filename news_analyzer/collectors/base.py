from abc import ABC, abstractmethod
from typing import List
from ..models import RawArticle


class BaseCollector(ABC):
    """Абстрактный базовый класс для всех коллекторов"""

    source_name: str  # "telegram" | "vk" | "rss" | "twitter"

    @abstractmethod
    def fetch(self) -> List[RawArticle]:
        """Получить сырые публикации из источника"""
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Проверить корректность конфигурации"""
        pass
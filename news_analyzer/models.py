from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class RawArticle:
    """Сырая публикация из источника (не хранится в БД)"""
    source: str  # 'telegram', 'vk', 'rss'
    source_id: str  # ID записи в источнике
    title: Optional[str]  # Заголовок (если есть)
    text: str  # Сырой текст публикации
    url: Optional[str]  # Ссылка на оригинал
    published_at: datetime  # Дата публикации
    raw_data: Dict[str, Any]  # Оригинальный ответ API


@dataclass
class CleanArticle:
    """Нормализованная публикация после NLP обработки"""
    source: str
    source_id: str
    title: Optional[str]
    text_clean: str  # Очищенный текст
    url: Optional[str]
    published_at: datetime
    language: str  # Определенный язык


@dataclass
class ProcessedArticle:
    """Обработанная публикация с ИИ"""
    source: str
    source_id: str
    title: Optional[str]
    text_clean: str
    summary: str  # Резюме от ИИ
    category: str  # Категория
    url: Optional[str]
    published_at: datetime
    text_hash: str  # SHA-256 для дедупликации
    ai_model: str  # Версия модели
import re
from typing import Optional
import langdetect
from ..models import RawArticle, CleanArticle


class NLPPreprocessor:
    """Обработка и нормализация текста"""

    def __init__(self):
        # TODO: Initialize NLTK, pymystem3, etc.
        pass

    def process(self, raw_article: RawArticle) -> CleanArticle:
        """Обработать сырую публикацию"""
        # Определение языка
        try:
            language = langdetect.detect(raw_article.text)
        except:
            language = 'unknown'

        # Очистка текста
        text_clean = self._clean_text(raw_article.text)

        # TODO: Токенизация, стоп-слова, лемматизация

        return CleanArticle(
            source=raw_article.source,
            source_id=raw_article.source_id,
            title=raw_article.title,
            text_clean=text_clean,
            url=raw_article.url,
            published_at=raw_article.published_at,
            language=language
        )

    def _clean_text(self, text: str) -> str:
        """Базовая очистка текста"""
        # Удаление HTML
        text = re.sub(r'<[^>]+>', '', text)
        # Удаление эмодзи и спецсимволов
        text = re.sub(r'[^\w\s]', '', text)
        # Нормализация пробелов
        text = re.sub(r'\s+', ' ', text).strip()
        # Нижний регистр
        return text.lower()
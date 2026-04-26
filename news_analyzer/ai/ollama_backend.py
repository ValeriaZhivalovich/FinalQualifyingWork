import hashlib
from .agent import BaseAIAgent
from ..models import CleanArticle, ProcessedArticle


class OllamaAgent(BaseAIAgent):
    """ИИ-агент на базе Ollama"""

    def __init__(self, model_name: str = "mistral:7b"):
        self.model_name = model_name
        # TODO: Initialize Ollama client

    def process(self, clean_article: CleanArticle) -> ProcessedArticle:
        """Обработать статью через Ollama"""
        # Генерация резюме
        summary = self._generate_summary(clean_article.text_clean)

        # Определение категории
        category = self._classify_category(clean_article.text_clean)

        # Хеш для дедупликации
        text_hash = hashlib.sha256(clean_article.text_clean.encode()).hexdigest()

        return ProcessedArticle(
            source=clean_article.source,
            source_id=clean_article.source_id,
            title=clean_article.title,
            text_clean=clean_article.text_clean,
            summary=summary,
            category=category,
            url=clean_article.url,
            published_at=clean_article.published_at,
            text_hash=text_hash,
            ai_model=self.model_name
        )

    def _generate_summary(self, text: str) -> str:
        """Сгенерировать резюме"""
        # TODO: Ollama API call
        prompt = f"Сократи следующую новость до 2-3 предложений на русском языке. Только суть. Текст: {text}"
        return "TODO: Summary from Ollama"

    def _classify_category(self, text: str) -> str:
        """Определить категорию"""
        # TODO: Ollama API call
        prompt = f"Определи одну категорию для новости из списка: политика, технологии, экономика, спорт, культура, прочее. Ответь одним словом. Текст: {text}"
        return "прочее"  # fallback

    def validate_connection(self) -> bool:
        """Проверить подключение к Ollama"""
        # TODO: Check if Ollama is running
        return True
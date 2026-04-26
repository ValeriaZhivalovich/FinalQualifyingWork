import hashlib
import requests
from typing import Optional
from .agent import BaseAIAgent
from ..models import CleanArticle, ProcessedArticle


class OllamaAgent(BaseAIAgent):
    """ИИ-агент на базе Ollama"""

    def __init__(self, host: str = "http://localhost:11434", model_name: str = "mistral:7b"):
        self.host = host.rstrip('/')
        self.model_name = model_name
        self.api_url = f"{self.host}/api/generate"

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
        prompt = f"Сократи следующую новость до 2-3 предложений на русском языке. Только суть, без лишних слов. Текст: {text}"

        try:
            response = self._call_ollama(prompt)
            if response:
                # Очищаем ответ от лишних символов
                summary = response.strip()
                return summary if summary else "Не удалось сгенерировать резюме"
            else:
                return "Ошибка генерации резюме"
        except Exception as e:
            print(f"Error generating summary: {e}")
            return "Ошибка генерации резюме"

    def _classify_category(self, text: str) -> str:
        """Определить категорию"""
        categories = ["политика", "технологии", "экономика", "спорт", "культура", "прочее"]
        categories_str = ", ".join(categories)

        prompt = f"Определи одну категорию для новости из списка: {categories_str}. Ответь только одним словом из списка. Текст: {text}"

        try:
            response = self._call_ollama(prompt)
            if response:
                # Нормализуем ответ
                category = response.strip().lower()
                if category in categories:
                    return category
                else:
                    return "прочее"  # fallback
            else:
                return "прочее"
        except Exception as e:
            print(f"Error classifying category: {e}")
            return "прочее"

    def _call_ollama(self, prompt: str) -> Optional[str]:
        """Вызов Ollama API"""
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Низкая температура для детерминированных ответов
                "num_predict": 100   # Ограничение длины ответа
            }
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=50)
            response.raise_for_status()
            data = response.json()
            return data.get('response', '').strip()
        except requests.exceptions.RequestException as e:
            print(f"Ollama API error: {e}")
            return None

    def validate_connection(self) -> bool:
        """Проверить подключение к Ollama"""
        try:
            # Проверяем доступность модели
            test_payload = {
                "model": self.model_name,
                "prompt": "test",
                "stream": False
            }
            response = requests.post(self.api_url, json=test_payload, timeout=50)
            return response.status_code == 200
        except:
            return False
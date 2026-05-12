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

    # Промпты для обработки новостей
    SUMMARY_PROMPT = """Проанализируй текст и дай краткую и досконально верно проверенную аннотацию (summary) до 15 слов, явно описывающую всю новость, не повторяя заголовок. В ответе пиши только аннотацию:
{text}
Аннотация:"""

    CATEGORY_PROMPT = """Определи одну категорию для новости из списка: 
{categories_str}. Ответь только одним словом из списка без дополнительных объяснений.
Текст: {text}"""

    TITLE_PROMPT = """Придумай короткий заголовок (до 8 слов) для текста ниже. В ответе напиши только заголовок:
{text}
Заголовок:"""

    def process(self, clean_article: CleanArticle) -> ProcessedArticle:
        title = clean_article.title or ""
        text = clean_article.text_clean or ""
        # Генерация заголовка, если его нет
        if not title and text:
            title = self._generate_title(text)
        if not title:
            title = "Без заголовка"
        # Убираем заголовок из начала text_clean, чтобы не дублировать
        if title and text.startswith(title):
            text = text[len(title):].strip(". ,;:!?\n\r\t ")
        input_text = f"{title}. {text}".strip(". ") if title and text else (title or text)
        summary = self._generate_summary(input_text)
        category = self._classify_category(input_text)
        text_hash = hashlib.sha256(clean_article.text_clean.encode()).hexdigest()

        return ProcessedArticle(
            source=clean_article.source,
            source_id=clean_article.source_id,
            title=title,
            text_clean=clean_article.text_clean,
            summary=summary,
            category=category,
            url=clean_article.url,
            published_at=clean_article.published_at,
            text_hash=text_hash,
            ai_model=self.model_name
        )

    def _generate_summary(self, text: str) -> str:
        prompt = self.SUMMARY_PROMPT.format(text=text)

        try:
            response = self._call_ollama(prompt)
            if response:
                summary = response.strip()
                for prefix in ["Summary:", "summary:", "Суть:", "Аннотация:", "Аннотация"]:
                    if summary.startswith(prefix):
                        summary = summary[len(prefix):].strip()
                return summary if summary else "Не удалось сгенерировать резюме"
            else:
                return "Ошибка генерации резюме"
        except Exception as e:
            print(f"Error generating summary: {e}")
            return "Ошибка генерации резюме"

    def _generate_title(self, text: str) -> str:
        prompt = self.TITLE_PROMPT.format(text=text)
        try:
            response = self._call_ollama(prompt)
            if response:
                title = response.strip()
                for prefix in ["Заголовок:", "Заголовок"]:
                    if title.startswith(prefix):
                        title = title[len(prefix):].strip()
                return title if title else "Без заголовка"
            return "Без заголовка"
        except Exception as e:
            print(f"Error generating title: {e}")
            return "Без заголовка"

    def _classify_category(self, text: str) -> str:
        """Определить категорию"""
        categories = ["политика", "технологии", "экономика", "спорт", "культура", "прочее"]
        categories_str = ", ".join(categories)

        prompt = self.CATEGORY_PROMPT.format(categories_str=categories_str, text=text)

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
                "temperature": 0.2,
                "num_predict": 128,
                "top_k": 40,
                "top_p": 0.9
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
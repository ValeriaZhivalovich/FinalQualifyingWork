import re
from typing import Optional
import langdetect
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from pymystem3 import Mystem
from ..models import RawArticle, CleanArticle


class NLPPreprocessor:
    """Обработка и нормализация текста"""

    def __init__(self):
        # Скачиваем необходимые ресурсы NLTK при первом запуске
        try:
            nltk.data.find('tokenizers/punkt_tab')
        except LookupError:
            print("Downloading NLTK punkt_tab...")
            nltk.download('punkt_tab')

        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            print("Downloading NLTK stopwords...")
            nltk.download('stopwords')

        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            print("Downloading NLTK punkt...")
            nltk.download('punkt')

        try:
            nltk.data.find('corpora/wordnet')
        except LookupError:
            print("Downloading NLTK wordnet...")
            nltk.download('wordnet')

        # Инициализируем лемматизаторы
        try:
            self.mystem = Mystem()
        except:
            print("Warning: pymystem3 not available, Russian lemmatization disabled")
            self.mystem = None

        try:
            self.lemmatizer_en = nltk.WordNetLemmatizer()
        except:
            print("Warning: NLTK WordNet not available")
            self.lemmatizer_en = None

        # Стоп-слова
        try:
            self.stop_words_ru = set(stopwords.words('russian'))
        except:
            print("Warning: Russian stopwords not available")
            self.stop_words_ru = set()

        try:
            self.stop_words_en = set(stopwords.words('english'))
        except:
            print("Warning: English stopwords not available")
            self.stop_words_en = set()

    def process(self, raw_article: RawArticle) -> CleanArticle:
        """Обработать сырую публикацию"""
        # Определение языка
        try:
            # Ограничиваем текст для определения языка (langdetect может зависать на длинных текстах)
            text_sample = raw_article.text[:1000] if len(raw_article.text) > 1000 else raw_article.text
            language = langdetect.detect(text_sample)
        except:
            language = 'unknown'

        # Очистка текста
        text_clean = self._clean_text(raw_article.text)

        # Токенизация
        tokens = self._tokenize(text_clean, language)

        # Удаление стоп-слов
        tokens = self._remove_stopwords(tokens, language)

        # Лемматизация
        tokens = self._lemmatize(tokens, language)

        # Собираем обратно в текст
        text_clean = ' '.join(tokens)

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
        # Удаление HTML-тегов
        text = re.sub(r'<[^>]+>', '', text)
        # Удаление эмодзи и спецсимволов (кроме букв, цифр, пробелов)
        text = re.sub(r'[^\w\s]', '', text)
        # Нормализация пробелов
        text = re.sub(r'\s+', ' ', text).strip()
        # Нижний регистр
        return text.lower()

    def _tokenize(self, text: str, language: str) -> list[str]:
        """Токенизация текста"""
        try:
            tokens = word_tokenize(text, language=language if language in ['english', 'russian'] else 'english')
        except:
            # Fallback на английскую токенизацию
            tokens = word_tokenize(text, language='english')
        return tokens

    def _remove_stopwords(self, tokens: list[str], language: str) -> list[str]:
        """Удаление стоп-слов"""
        if language == 'russian':
            stop_words = self.stop_words_ru
        elif language == 'english':
            stop_words = self.stop_words_en
        else:
            # Для других языков используем английские стоп-слова
            stop_words = self.stop_words_en

        return [token for token in tokens if token.lower() not in stop_words and len(token) > 1]

    def _lemmatize(self, tokens: list[str], language: str) -> list[str]:
        """Лемматизация"""
        if language == 'russian':
            # Используем pymystem3 для русского
            if self.mystem:
                try:
                    lemmas = self.mystem.lemmatize(' '.join(tokens))
                    return [lemma for lemma in lemmas if lemma.strip() and lemma != ' ']
                except:
                    pass
            return tokens
        elif language == 'english':
            # Используем NLTK для английского
            if self.lemmatizer_en:
                try:
                    return [self.lemmatizer_en.lemmatize(token) for token in tokens]
                except:
                    pass
            return tokens
        else:
            # Для других языков возвращаем как есть
            return tokens
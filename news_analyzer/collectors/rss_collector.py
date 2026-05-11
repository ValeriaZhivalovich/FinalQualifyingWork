from typing import List, Dict, Any, Optional
from datetime import datetime
from ..models import RawArticle
from .base import BaseCollector
import feedparser
import requests


class RSSCollector(BaseCollector):
    source_name = "rss"

    def __init__(self, feed_urls: List[str] | None = None, topic_keywords: List[str] | None = None,
                 max_age_days: Optional[int] = None, limit_per_feed: int = 50):
        # Список RSS-лент для парсинга
        self.feed_urls = feed_urls or [
            "https://ria.ru/export/rss2/archive/index.xml",  # РИА Новости
            "https://lenta.ru/rss",  # Lenta.ru
            "https://tass.ru/rss/v2.xml",  # ТАСС
            "https://www.interfax.ru/rss.asp",  # Интерфакс
        ]

        # Максимальное количество статей с одного фида (для ускорения)
        self.limit_per_feed = limit_per_feed

        # Ограничение по возрасту новости (в днях)
        # None - без ограничения, 1 - только за последний день, 7 - за неделю и т.д.
        self.max_age_days = max_age_days

        # Ключевые слова для фильтрации новостей по заданной тематике
        # None  - использовать список по умолчанию (Крым)
        # []    - без фильтрации (все новости)
        # [слова] - фильтровать по указанным словам
        if topic_keywords is None:
            self.topic_keywords = [
                # Основные названия
                "крым", "крыма", "крыму", "крымом", "крыме", "крымский", "крымская", "крымские",
                "севастополь", "севастополя", "севастополю", "севастополем", "севастополь",
                "керчь", "керчи", "керчью", "керчью", "керчи", "керченский", "керченская",
                "симферополь", "симферополя", "симферополю", "симферополем", "симферополе",
                "ялта", "ялты", "ялте", "ялту", "ялтой", "ялтинский", "ялтинская",
                "феодосия", "феодосии", "феодосией", "феодосию", "феодосии",
                "евпатория", "евпатории", "евпаторией", "евпаторию", "евпатории",

                # Дополнительные ключевые слова
                "крымчанин", "крымчане", "крымчан", "крымчанам",
                "крымский мост", "крымского моста",
                "аннексия", "аннекси", "аннексирован",
                "оккупация", "оккупирован", "оккупации",
                "полуостров", "полуострова", "полуостровом",
                "таврида", "тавриды", "тавриде"
            ]
        else:
            self.topic_keywords = topic_keywords

        # Ключевые слова для фильтрации новостей по Крыму
        self.crimea_keywords = [
            # Основные названия
            "крым", "крыма", "крыму", "крымом", "крыме", "крымский", "крымская", "крымские",
            "севастополь", "севастополя", "севастополю", "севастополем", "севастополе",
            "керчь", "керчи", "керчью", "керчью", "керчи", "керченский", "керченская",
            "симферополь", "симферополя", "симферополю", "симферополем", "симферополе",
            "ялта", "ялты", "ялте", "ялту", "ялтой", "ялтинский", "ялтинская",
            "феодосия", "феодосии", "феодосией", "феодосию", "феодосии",
            "евпатория", "евпатории", "евпаторией", "евпаторию", "евпатории",
        
            # Дополнительные ключевые слова
            "крымчанин", "крымчане", "крымчан", "крымчанам",
            "крымский мост", "крымского моста",
            "аннексия", "аннекси", "аннексирован",
            "оккупация", "оккупирован", "оккупации",
            "полуостров", "полуострова", "полуостровом",
            "таврида", "тавриды", "тавриде"
        ]





    def fetch(self) -> List[RawArticle]:
        """Спарсить все RSS-ленты и вернуть статьи"""
        articles: List[RawArticle] = []

        for feed_url in self.feed_urls:
            try:
                feed = feedparser.parse(feed_url)

                if not feed.entries:
                    print(f"No entries in feed: {feed_url}")
                    continue

                entries = feed.entries[:self.limit_per_feed]

                for entry in entries:
                    # Проверка по дате
                    published = self._parse_date(entry)
                    if self.max_age_days and published:
                        from datetime import datetime, timedelta
                        cutoff = datetime.now() - timedelta(days=self.max_age_days)
                        if published < cutoff:
                            continue

                    # Фильтрация по ключевым словам
                    title = entry.get('title', '')
                    summary = entry.get('summary', '')
                    text = f"{title} {summary}".strip()

                    if not self._matches_keywords(text):
                        continue

                    # Генерация source_id
                    link = entry.get('link', '')
                    source_id = link or entry.get('id', '') or title[:100]

                    article = RawArticle(
                        source=self.source_name,
                        source_id=source_id,
                        title=title or None,
                        text=text,
                        url=link or None,
                        published_at=published if published else datetime.now(),
                        raw_data=entry
                    )
                    articles.append(article)

            except Exception as e:
                print(f"Error parsing feed {feed_url}: {e}")

        print(f"RSSCollector fetched {len(articles)} articles")
        return articles

    def _parse_date(self, entry) -> datetime:
        """Разобрать дату публикации из RSS entry"""
        date_fields = ['published_parsed', 'updated_parsed']
        for field in date_fields:
            if field in entry and entry[field]:
                try:
                    return datetime(*entry[field][:6])
                except (TypeError, ValueError):
                    pass

        # Fallback: пробуем строковые поля
        for field in ['published', 'updated']:
            if field in entry and entry[field]:
                try:
                    from email.utils import parsedate_to_datetime
                    return parsedate_to_datetime(entry[field]).replace(tzinfo=None)
                except Exception:
                    pass
        return None

    def _matches_keywords(self, text: str) -> bool:
        """Проверить, содержит ли текст ключевые слова"""
        if not self.topic_keywords:
            return True
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in self.topic_keywords)

    def validate_config(self) -> bool:
        """Проверить конфигурацию RSS"""
        if not self.feed_urls:
            print("No RSS feed URLs configured")
            return False

        # Проверяем хотя бы один URL
        for url in self.feed_urls:
            if not url.startswith(('http://', 'https://')):
                print(f"Invalid RSS URL: {url}")
                return False

        return True

from typing import List, Dict, Any
from datetime import datetime
from ..models import RawArticle
from .base import BaseCollector
import feedparser
import requests


class RSSCollector(BaseCollector):
    source_name = "rss"

    def __init__(self, feed_urls: List[str] = None):
        # Список RSS-лент для парсинга
        self.feed_urls = feed_urls or [
            "https://ria.ru/export/rss2/archive/index.xml",  # РИА Новости
            "https://lenta.ru/rss",  # Lenta.ru
            "https://tass.ru/rss/v2.xml",  # ТАСС
            "https://www.interfax.ru/rss.asp",  # Интерфакс
        ]

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
        """Получить новости из RSS-лент"""
        articles = []
        total_filtered = 0

        for feed_url in self.feed_urls:
            try:
                print(f"Fetching RSS from: {feed_url}")
                # Добавляем timeout для предотвращения зависания
                response = requests.get(feed_url, timeout=10)
                print(f"Response status: {response.status_code}")
                feed = feedparser.parse(response.content)

                # Проверяем статус код ответа HTTP
                if response.status_code not in [200, 301, 302]:  # Allow redirects
                    print(f"Failed to fetch RSS from {feed_url}: HTTP {response.status_code}")
                    continue

                if not feed.entries:
                    print(f"No entries found in RSS from {feed_url}")
                    print(f"Feed bozo: {feed.get('bozo')}")
                    if feed.get('bozo_exception'):
                        print(f"Feed parsing error: {feed.get('bozo_exception')}")
                    continue

                print(f"Found {len(feed.entries)} entries in {feed_url}")

                for entry in feed.entries:
                    try:
                        article = self._parse_entry(entry, feed_url)
                        if article is not None:
                            articles.append(article)
                        else:
                            total_filtered += 1
                    except Exception as e:
                        print(f"Error parsing RSS entry from {feed_url}: {e}")
                        import traceback
                        traceback.print_exc()

            except Exception as e:
                print(f"Error fetching RSS feed {feed_url}: {e}")

        print(f"Total articles fetched: {len(articles)}, filtered out: {total_filtered}")
        return articles

    def _parse_entry(self, entry, feed_url: str) -> RawArticle | None:
        """Парсить одну запись из RSS"""
        # Извлечение заголовка
        title = getattr(entry, 'title', None)
        if title:
            title = title.strip()

        # Извлечение текста (описания)
        text = ""
        if hasattr(entry, 'description'):
            text = entry.description.strip()
        elif hasattr(entry, 'summary'):
            text = entry.summary.strip()

        # Если текста мало, попробуем content
        if hasattr(entry, 'content') and len(text) < 50:
            content = entry.content[0] if isinstance(entry.content, list) else entry.content
            if hasattr(content, 'value'):
                text = content.value.strip()

        # Извлечение ссылки
        url = getattr(entry, 'link', None)

        # Извлечение даты публикации
        published_at = datetime.now()  # fallback
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                published_at = datetime(*entry.published_parsed[:6])
            except:
                pass

        # Source ID - используем URL или guid
        source_id = getattr(entry, 'id', None) or getattr(entry, 'guid', None) or url
        if not source_id:
            # Fallback: хеш от заголовка и текста
            import hashlib
            source_id = hashlib.md5(f"{title}{text}".encode()).hexdigest()

        # Raw data для отладки
        raw_data = {
            'feed_url': feed_url,
            'entry': dict(entry)
        }

        # Фильтрация: только новости по Крыму
        content_to_check = f"{title or ''} {text or ''}".lower()

        has_crimea_keyword = any(keyword in content_to_check for keyword in self.crimea_keywords)

        if not has_crimea_keyword:
            return None  # Пропускаем новость, если она не касается Крыма

        return RawArticle(
            source=self.source_name,
            source_id=source_id,
            title=title,
            text=text,
            url=url,
            published_at=published_at,
            raw_data=raw_data
        )

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
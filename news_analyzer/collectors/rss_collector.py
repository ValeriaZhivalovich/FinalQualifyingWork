from typing import List
from .base import BaseCollector
from ..models import RawArticle


class RSSCollector(BaseCollector):
    source_name = "rss"

    def fetch(self) -> List[RawArticle]:
        # TODO: Implement RSS fetching using feedparser
        return []

    def validate_config(self) -> bool:
        # TODO: Validate RSS feed URLs
        return True
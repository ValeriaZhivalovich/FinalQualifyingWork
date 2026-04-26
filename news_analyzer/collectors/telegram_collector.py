from typing import List
from .base import BaseCollector
from ..models import RawArticle


class TelegramCollector(BaseCollector):
    source_name = "telegram"

    def fetch(self) -> List[RawArticle]:
        # TODO: Implement Telegram fetching using Telethon
        return []

    def validate_config(self) -> bool:
        # TODO: Validate Telegram API config
        return True
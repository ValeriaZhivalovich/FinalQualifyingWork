from typing import List, Optional
from datetime import datetime, timedelta
from ..models import RawArticle
from .base import BaseCollector
import asyncio


CRIMEA_KEYWORDS = [
    "крым", "крыма", "крыму", "крымом", "крыме", "крымский", "крымская", "крымские",
    "севастополь", "симферополь", "керчь", "керченский", "симферополе",
    "ялта", "ялты", "ялте", "ялтинский", "феодосия", "феодосии",
    "евпатория", "евпатории", "крымчанин", "крымчане",
    "крымский мост", "полуостров", "таврида",
    "аннексия", "аннексирован", "оккупация",
]


class TelegramPyrogramCollector(BaseCollector):
    source_name = "telegram_pyrogram"

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        phone: str,
        channels: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        max_age_hours: int = 48,
        limit_per_channel: int = 50,
    ):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.channels = channels or [
            "crimea24tv",
            "rian_crimea",
            "krymrealii",
            "crimeanews",
            "sevastopollive",
        ]
        self.keywords = keywords or CRIMEA_KEYWORDS
        self.max_age_hours = max_age_hours
        self.limit_per_channel = limit_per_channel

    def validate_config(self) -> bool:
        return bool(self.api_id) and bool(self.api_hash) and bool(self.phone)

    def _matches_keywords(self, text: str) -> bool:
        if not text:
            return False
        text_lower = text.lower()
        for kw in self.keywords:
            if kw in text_lower:
                return True
        return False

    def fetch(self) -> List[RawArticle]:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            articles = loop.run_until_complete(self._fetch_async())
            loop.close()
            return articles
        except Exception as e:
            print(f"[TelegramPyrogram] Error: {e}")
            return []

    async def _fetch_async(self) -> List[RawArticle]:
        try:
            from pyrogram import Client
            from pyrogram.errors import RPCError
        except ImportError:
            print("[TelegramPyrogram] pyrogram not installed")
            return []

        articles: List[RawArticle] = []
        app = Client(
            "session_pyrogram",
            api_id=self.api_id,
            api_hash=self.api_hash,
            phone_number=self.phone,
        )

        try:
            await app.start()
            cutoff = datetime.utcnow() - timedelta(hours=self.max_age_hours)

            for channel_username in self.channels:
                try:
                    async for message in app.get_chat_history(
                        channel_username,
                        limit=self.limit_per_channel,
                    ):
                        if not message.text:
                            continue
                        if message.date.replace(tzinfo=None) < cutoff:
                            break
                        if not self._matches_keywords(message.text):
                            continue

                        articles.append(RawArticle(
                            source=self.source_name,
                            source_id=f"pyro_{channel_username}_{message.id}",
                            title=None,
                            text=message.text,
                            url=f"https://t.me/{channel_username}/{message.id}",
                            published_at=message.date.replace(tzinfo=None),
                            raw_data={
                                "channel": channel_username,
                                "message_id": message.id,
                            },
                        ))
                except RPCError as e:
                    print(f"[TelegramPyrogram] Error in {channel_username}: {e}")

        except Exception as e:
            print(f"[TelegramPyrogram] Connection error: {e}")
        finally:
            await app.stop()

        return articles

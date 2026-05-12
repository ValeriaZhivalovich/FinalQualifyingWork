from typing import List, Optional
from datetime import datetime, timedelta
from ..models import RawArticle
from .base import BaseCollector
import asyncio
import re


CRIMEA_KEYWORDS = [
    "крым", "крыма", "крыму", "крымом", "крыме", "крымский", "крымская", "крымские",
    "севастополь", "севастополя", "севастополю", "севастополем", "севастополе",
    "керчь", "керчи", "керченский", "симферополь", "симферополя", "симферополе",
    "ялта", "ялты", "ялте", "ялтинский", "феодосия", "феодосии",
    "евпатория", "евпатории", "крымчанин", "крымчане",
    "крымский мост", "полуостров", "таврида",
    "аннексия", "аннексирован", "оккупация", "оккупирован",
]


class TelegramTelethonCollector(BaseCollector):
    source_name = "telegram_telethon"

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
            print(f"[TelegramTelethon] Error: {e}")
            return []

    async def _fetch_async(self) -> List[RawArticle]:
        try:
            from telethon import TelegramClient
            from telethon.errors import SessionPasswordNeededError
        except ImportError:
            print("[TelegramTelethon] telethon not installed")
            return []

        articles: List[RawArticle] = []
        client = TelegramClient("session_telethon", self.api_id, self.api_hash)

        try:
            await client.start(phone=self.phone)

            cutoff = datetime.utcnow() - timedelta(hours=self.max_age_hours)

            for channel_username in self.channels:
                try:
                    entity = await client.get_entity(channel_username)
                except Exception as e:
                    print(f"[TelegramTelethon] Cannot get entity {channel_username}: {e}")
                    continue

                async for message in client.iter_messages(
                    entity,
                    limit=self.limit_per_channel,
                    offset_date=cutoff,
                ):
                    if not message.text:
                        continue

                    if not self._matches_keywords(message.text):
                        continue

                    articles.append(RawArticle(
                        source=self.source_name,
                        source_id=f"tg_{channel_username}_{message.id}",
                        title=None,
                        text=message.text,
                        url=f"https://t.me/{channel_username}/{message.id}",
                        published_at=message.date.replace(tzinfo=None),
                        raw_data={
                            "channel": channel_username,
                            "message_id": message.id,
                            "views": getattr(message, "views", None),
                            "forwards": getattr(message, "forwards", None),
                        },
                    ))

        except SessionPasswordNeededError:
            print("[TelegramTelethon] 2FA password required")
        except Exception as e:
            print(f"[TelegramTelethon] Connection error: {e}")
        finally:
            await client.disconnect()

        return articles

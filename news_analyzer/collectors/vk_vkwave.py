from typing import List, Optional
from datetime import datetime, timedelta
from ..models import RawArticle
from .base import BaseCollector
import asyncio


CRIMEA_KEYWORDS = [
    "крым", "крыма", "крыму", "крымом", "крыме", "крымский", "крымская", "крымские",
    "севастополь", "симферополь", "керчь", "керченский",
    "ялта", "ялтинский", "феодосия", "евпатория",
    "крымчанин", "крымчане", "полуостров", "таврида",
    "аннексия", "оккупация",
]


class VkWaveCollector(BaseCollector):
    source_name = "vk_wave"

    def __init__(
        self,
        token: str,
        groups: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        max_age_hours: int = 48,
        limit_per_group: int = 30,
    ):
        self.token = token
        self.groups = groups or [
            "crimea24tv",
            "krymrealii",
            "crimeanews",
            "sevastopol_live",
        ]
        self.keywords = keywords or CRIMEA_KEYWORDS
        self.max_age_hours = max_age_hours
        self.limit_per_group = limit_per_group

    def validate_config(self) -> bool:
        return bool(self.token)

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
            print(f"[VkWave] Error: {e}")
            return []

    async def _fetch_async(self) -> List[RawArticle]:
        articles: List[RawArticle] = []
        try:
            from vkwave.api import API, Token
            from vkwave.api.methods import Wall
            from vkwave.client import AIOHTTPClient
        except ImportError:
            print("[VkWave] vkwave not installed")
            return []

        try:
            client = AIOHTTPClient()
            api = API(clients=client, tokens=Token(self.token))
            wall = Wall(api)

            cutoff_ts = (datetime.utcnow() - timedelta(hours=self.max_age_hours)).timestamp()

            for group_screen_name in self.groups:
                try:
                    group_resp = await api.groups.get_by_id(group_id=group_screen_name)
                    group_id = group_resp.response.items[0].id

                    posts_resp = await wall.get(
                        owner_id=-group_id,
                        count=self.limit_per_group,
                        v="5.131",
                    )
                except Exception as e:
                    print(f"[VkWave] Error with group {group_screen_name}: {e}")
                    continue

                for item in posts_resp.response.items:
                    text = getattr(item, "text", "")
                    if not text:
                        continue
                    if getattr(item, "date", 0) < cutoff_ts:
                        break
                    if not self._matches_keywords(text):
                        continue

                    published_at = datetime.fromtimestamp(item.date).replace(tzinfo=None)

                    articles.append(RawArticle(
                        source=self.source_name,
                        source_id=f"vkw_{item.owner_id}_{item.id}",
                        title=None,
                        text=text,
                        url=f"https://vk.com/{group_screen_name}?w=wall{item.owner_id}_{item.id}",
                        published_at=published_at,
                        raw_data={
                            "group": group_screen_name,
                            "post_id": item.id,
                            "likes": getattr(item.likes, "count", 0) if hasattr(item, "likes") else 0,
                            "comments": getattr(item.comments, "count", 0) if hasattr(item, "comments") else 0,
                            "reposts": getattr(item.reposts, "count", 0) if hasattr(item, "reposts") else 0,
                        },
                    ))

        except Exception as e:
            print(f"[VkWave] Error: {e}")

        return articles

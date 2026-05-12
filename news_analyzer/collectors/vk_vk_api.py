from typing import List, Optional
from datetime import datetime, timedelta, timezone
from ..models import RawArticle
from .base import BaseCollector


CRIMEA_KEYWORDS = [
    "крым", "крыма", "крыму", "крымом", "крыме", "крымский", "крымская", "крымские",
    "севастополь", "симферополь", "керчь", "керченский",
    "ялта", "ялтинский", "феодосия", "евпатория",
    "крымчанин", "крымчане", "полуостров", "таврида",
    "аннексия", "оккупация",
]

VK_CRIMEA_GROUPS = [
    "crimea24tv",
    "krymrealii",
    "crimeanews",
    "sevastopol_live",
]


class VkApiCollector(BaseCollector):
    source_name = "vk"

    def __init__(
        self,
        access_token: str,
        groups: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        max_age_hours: int = 48,
        limit_per_group: int = 30,
    ):
        self.access_token = access_token
        self.groups = groups or VK_CRIMEA_GROUPS
        self.keywords = keywords or CRIMEA_KEYWORDS
        self.max_age_hours = max_age_hours
        self.limit_per_group = limit_per_group

    def validate_config(self) -> bool:
        return bool(self.access_token)

    def _matches_keywords(self, text: str) -> bool:
        if not text:
            return False
        text_lower = text.lower()
        for kw in self.keywords:
            if kw in text_lower:
                return True
        return False

    def fetch(self) -> List[RawArticle]:
        articles: List[RawArticle] = []
        try:
            import vk_api
        except ImportError:
            print("[VkApi] vk_api not installed")
            return []

        try:
            vk_session = vk_api.VkApi(token=self.access_token)
            vk = vk_session.get_api()

            cutoff_ts = (datetime.utcnow() - timedelta(hours=self.max_age_hours)).timestamp()

            for group_screen_name in self.groups:
                try:
                    group = vk.groups.getById(group_id=group_screen_name)
                    if not group:
                        continue
                    group_id = group[0]["id"]

                    posts = vk.wall.get(
                        owner_id=-group_id,
                        count=self.limit_per_group,
                        v="5.131",
                    )
                except Exception as e:
                    print(f"[VkApi] Error getting group {group_screen_name}: {e}")
                    continue

                for item in posts.get("items", []):
                    text = item.get("text", "")
                    if not text:
                        continue
                    if item.get("date", 0) < cutoff_ts:
                        break
                    if not self._matches_keywords(text):
                        continue

                    published_at = datetime.fromtimestamp(item["date"], tz=timezone.utc).replace(tzinfo=None)

                    post_url = f"https://vk.com/{group_screen_name}?w=wall{item['owner_id']}_{item['id']}"
                    attachments = item.get("attachments", [])

                    articles.append(RawArticle(
                        source=self.source_name,
                        source_id=f"vk_{item['owner_id']}_{item['id']}",
                        title=None,
                        text=text,
                        url=post_url,
                        published_at=published_at,
                        raw_data={
                            "group": group_screen_name,
                            "post_id": item["id"],
                            "likes": item.get("likes", {}).get("count", 0),
                            "comments": item.get("comments", {}).get("count", 0),
                            "reposts": item.get("reposts", {}).get("count", 0),
                            "views": item.get("views", {}).get("count", 0),
                            "attachments": len(attachments),
                        },
                    ))

        except Exception as e:
            print(f"[VkApi] Error: {e}")

        return articles

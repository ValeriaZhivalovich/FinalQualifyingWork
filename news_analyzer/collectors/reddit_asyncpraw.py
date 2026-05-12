from typing import List, Optional
from datetime import datetime, timedelta
from ..models import RawArticle
from .base import BaseCollector
import asyncio


CRIMEA_KEYWORDS = [
    "крым", "крыма", "крыму", "крымом", "крыме", "крымский", "крымская", "крымские",
    "севастополь", "симферополь", "керчь", "керченский",
    "ялта", "ялтинский", "феодосия", "евпатория",
    "полуостров", "таврида", "аннексия", "оккупация",
    "Crimea", "crimea",
]


class RedditAsyncPRAWCollector(BaseCollector):
    source_name = "reddit_async"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        subreddits: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        max_age_hours: int = 48,
        limit_per_subreddit: int = 50,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.subreddits = subreddits or [
            "ukraine",
            "UkraineWarVideoReport",
            "worldnews",
            "europe",
            "geopolitics",
        ]
        self.keywords = keywords or CRIMEA_KEYWORDS
        self.max_age_hours = max_age_hours
        self.limit_per_subreddit = limit_per_subreddit

    def validate_config(self) -> bool:
        return bool(self.client_id) and bool(self.client_secret) and bool(self.user_agent)

    def _matches_keywords(self, text: str) -> bool:
        if not text:
            return False
        text_lower = text.lower()
        for kw in self.keywords:
            if kw.lower() in text_lower:
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
            print(f"[RedditAsyncPRAW] Error: {e}")
            return []

    async def _fetch_async(self) -> List[RawArticle]:
        articles: List[RawArticle] = []
        try:
            import asyncpraw
        except ImportError:
            print("[RedditAsyncPRAW] asyncpraw not installed")
            return []

        try:
            reddit = asyncpraw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent,
            )

            cutoff = datetime.utcnow() - timedelta(hours=self.max_age_hours)

            for subreddit_name in self.subreddits:
                try:
                    subreddit = await reddit.subreddit(subreddit_name)
                    async for submission in subreddit.new(limit=self.limit_per_subreddit):
                        published_at = datetime.fromtimestamp(submission.created_utc)
                        if published_at < cutoff:
                            break

                        combined_text = f"{submission.title} {submission.selftext or ''}"
                        if not self._matches_keywords(combined_text):
                            continue

                        articles.append(RawArticle(
                            source=self.source_name,
                            source_id=f"areddit_{submission.id}",
                            title=submission.title,
                            text=combined_text,
                            url=submission.url,
                            published_at=published_at,
                            raw_data={
                                "subreddit": subreddit_name,
                                "post_id": submission.id,
                                "author": str(submission.author),
                                "score": submission.score,
                                "num_comments": submission.num_comments,
                                "upvote_ratio": submission.upvote_ratio,
                            },
                        ))
                except Exception as e:
                    print(f"[RedditAsyncPRAW] Error in r/{subreddit_name}: {e}")

            await reddit.close()
        except Exception as e:
            print(f"[RedditAsyncPRAW] Error: {e}")

        return articles

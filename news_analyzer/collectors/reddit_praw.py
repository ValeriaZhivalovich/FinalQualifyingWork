from typing import List, Optional
from datetime import datetime, timedelta
from ..models import RawArticle
from .base import BaseCollector


CRIMEA_KEYWORDS = [
    "крым", "крыма", "крыму", "крымом", "крыме", "крымский", "крымская", "крымские",
    "севастополь", "симферополь", "керчь", "керченский",
    "ялта", "ялтинский", "феодосия", "евпатория",
    "полуостров", "таврида", "аннексия", "оккупация",
    "Crimea", "crimea",
]


CRIMEA_SUBREDDITS = [
    "ukraine",
    "UkraineWarVideoReport",
    "worldnews",
    "europe",
    "geopolitics",
]


class RedditPRAWCollector(BaseCollector):
    source_name = "reddit"

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
        self.subreddits = subreddits or CRIMEA_SUBREDDITS
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
        articles: List[RawArticle] = []
        try:
            import praw
        except ImportError:
            print("[RedditPRAW] praw not installed")
            return []

        try:
            reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent,
            )

            cutoff = datetime.utcnow() - timedelta(hours=self.max_age_hours)

            for subreddit_name in self.subreddits:
                try:
                    subreddit = reddit.subreddit(subreddit_name)
                    for submission in subreddit.new(limit=self.limit_per_subreddit):
                        published_at = datetime.fromtimestamp(submission.created_utc)
                        if published_at < cutoff:
                            break

                        combined_text = f"{submission.title} {submission.selftext or ''}"
                        if not self._matches_keywords(combined_text):
                            continue

                        articles.append(RawArticle(
                            source=self.source_name,
                            source_id=f"reddit_{submission.id}",
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
                    print(f"[RedditPRAW] Error in r/{subreddit_name}: {e}")

        except Exception as e:
            print(f"[RedditPRAW] Error: {e}")

        return articles

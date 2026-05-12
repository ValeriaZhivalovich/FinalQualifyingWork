from typing import List, Optional
from datetime import datetime, timedelta
from ..models import RawArticle
from .base import BaseCollector
import asyncio
from pathlib import Path


CRIMEA_KEYWORDS = [
    "крым", "крыма", "крыму", "крымом", "крыме", "крымский", "крымская", "крымские",
    "севастополь", "симферополь", "керчь", "керченский",
    "ялта", "ялтинский", "феодосия", "евпатория",
    "крымчанин", "крымчане", "полуостров", "таврида",
    "аннексия", "оккупация", "crimea", "Crimea",
]

TWITTER_QUERIES = [
    "Крым",
    "Севастополь",
    "Керчь",
    "крымский мост",
    "полуостров Крым",
]


class TwitterTwikitCollector(BaseCollector):
    source_name = "twitter_twikit"

    def __init__(
        self,
        username: str = "",
        password: str = "",
        email: str = "",
        queries: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        max_tweets: int = 20,
        max_age_hours: int = 48,
        lang: str = "ru",
    ):
        self.username = username.lstrip("@")
        self.password = password
        self.email = email
        self.queries = queries or TWITTER_QUERIES
        self.keywords = keywords or CRIMEA_KEYWORDS
        self.max_tweets = max_tweets
        self.max_age_hours = max_age_hours
        self.lang = lang
        self._cookies_file = Path("twikit_cookies.json")

    def validate_config(self) -> bool:
        return bool(self.username) and bool(self.password)

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
            print(f"[TwitterTwikit] Error: {e}")
            return []

    async def _fetch_async(self) -> List[RawArticle]:
        try:
            from twikit import Client
        except ImportError:
            print("[TwitterTwikit] twikit not installed")
            return []

        articles: List[RawArticle] = []
        client = Client(language=self.lang)

        try:
            if self._cookies_file.exists():
                client.load_cookies(str(self._cookies_file))
            else:
                if self.email:
                    await client.login(
                        auth_info_1=self.username,
                        auth_info_2=self.email,
                        password=self.password,
                    )
                else:
                    await client.login(
                        auth_info_1=self.username,
                        password=self.password,
                    )
                client.save_cookies(str(self._cookies_file))

            cutoff = datetime.utcnow() - timedelta(hours=self.max_age_hours)

            for query in self.queries:
                try:
                    tweets = await client.search_tweet(
                        query, product="Latest", count=self.max_tweets
                    )
                except Exception as e:
                    print(f"[TwitterTwikit] Search error for '{query}': {e}")
                    continue

                for tweet in tweets:
                    text = getattr(tweet, "text", None) or ""
                    if not self._matches_keywords(text):
                        continue

                    tweet_date = tweet.created_at
                    if isinstance(tweet_date, str):
                        try:
                            tweet_date = datetime.strptime(
                                tweet_date, "%a %b %d %H:%M:%S %z %Y"
                            ).replace(tzinfo=None)
                        except ValueError:
                            tweet_date = datetime.utcnow()
                    elif hasattr(tweet_date, "replace"):
                        tweet_date = tweet_date.replace(tzinfo=None)

                    user = getattr(tweet, "user", None)
                    screen_name = user.screen_name if user else "unknown"

                    articles.append(RawArticle(
                        source=self.source_name,
                        source_id=f"twikit_{tweet.id}",
                        title=None,
                        text=text,
                        url=f"https://twitter.com/i/web/status/{tweet.id}",
                        published_at=tweet_date,
                        raw_data={
                            "tweet_id": str(tweet.id),
                            "user": screen_name,
                            "favorite_count": getattr(tweet, "favorite_count", None),
                            "retweet_count": getattr(tweet, "retweet_count", None),
                        },
                    ))

        except Exception as e:
            print(f"[TwitterTwikit] Error: {e}")
        finally:
            if self._cookies_file.exists():
                try:
                    client.save_cookies(str(self._cookies_file))
                except Exception:
                    pass

        return articles

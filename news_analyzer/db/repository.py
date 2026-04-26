from sqlalchemy.orm import sessionmaker, Session
from typing import List, Optional
from ..models import ProcessedArticle
from .models import Article, Source


class DatabaseRepository:
    """Репозиторий для работы с базой данных"""

    def __init__(self, session_factory: sessionmaker):
        self.session_factory = session_factory

    def save_article(self, processed_article: ProcessedArticle) -> bool:
        """Сохранить обработанную статью (с дедупликацией)"""
        session: Session = self.session_factory()
        try:
            # Проверка на дубликат по text_hash
            existing = session.query(Article).filter_by(text_hash=processed_article.text_hash).first()
            if existing:
                return False  # Уже существует

            article = Article(
                source=processed_article.source,
                source_id=processed_article.source_id,
                title=processed_article.title,
                text_clean=processed_article.text_clean,
                summary=processed_article.summary,
                category=processed_article.category,
                url=processed_article.url,
                published_at=processed_article.published_at,
                processed_at=processed_article.published_at,  # TODO: use current time
                text_hash=processed_article.text_hash,
                ai_model=processed_article.ai_model
            )
            session.add(article)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_articles(self, limit: int = 50, offset: int = 0) -> List[Article]:
        """Получить список статей"""
        session: Session = self.session_factory()
        try:
            return session.query(Article).order_by(Article.published_at.desc()).limit(limit).offset(offset).all()
        finally:
            session.close()

    # TODO: Другие CRUD методы для Source
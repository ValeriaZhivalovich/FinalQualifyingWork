from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import desc, and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime
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
                print(f"Duplicate article skipped: {processed_article.title}")
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
                processed_at=datetime.now(),
                text_hash=processed_article.text_hash,
                ai_model=processed_article.ai_model
            )
            session.add(article)
            session.commit()
            print(f"Article saved: {processed_article.title}")
            return True
        except Exception as e:
            session.rollback()
            print(f"Error saving article {processed_article.title}: {e}")
            raise e
        finally:
            session.close()

    def get_articles(self, limit: int = 50, offset: int = 0,
                     category: Optional[str] = None,
                     source: Optional[str] = None,
                     search: Optional[str] = None) -> List[Article]:
        """Получить список статей с фильтрами"""
        session: Session = self.session_factory()
        try:
            query = session.query(Article)

            if category:
                query = query.filter(Article.category == category)

            if source:
                query = query.filter(Article.source == source)

            if search:
                # Поиск по заголовку и резюме
                search_filter = f"%{search}%"
                query = query.filter(
                    or_(
                        Article.title.like(search_filter),
                        Article.summary.like(search_filter)
                    )
                )

            return query.order_by(desc(Article.published_at)).limit(limit).offset(offset).all()
        finally:
            session.close()

    def get_article_by_id(self, article_id: int) -> Optional[Article]:
        """Получить статью по ID"""
        session: Session = self.session_factory()
        try:
            return session.query(Article).filter(Article.id == article_id).first()
        finally:
            session.close()

    def mark_as_read(self, article_id: int) -> bool:
        """Отметить статью как прочитанную"""
        session: Session = self.session_factory()
        try:
            article = session.query(Article).filter(Article.id == article_id).first()
            if article:
                article.is_read = True
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_categories(self) -> List[str]:
        """Получить список уникальных категорий"""
        session: Session = self.session_factory()
        try:
            result = session.query(Article.category).distinct().all()
            return [row[0] for row in result]
        finally:
            session.close()

    def get_sources(self) -> List[str]:
        """Получить список уникальных источников"""
        session: Session = self.session_factory()
        try:
            result = session.query(Article.source).distinct().all()
            return [row[0] for row in result]
        finally:
            session.close()

    # Методы для Source (настройки источников)
    def save_source(self, source: Source) -> int:
        """Сохранить источник"""
        session: Session = self.session_factory()
        try:
            session.add(source)
            session.commit()
            session.refresh(source)
            return source.id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_active_sources(self) -> List[Source]:
        """Получить активные источники"""
        session: Session = self.session_factory()
        try:
            return session.query(Source).filter(Source.is_active == True).all()
        finally:
            session.close()

    def update_source_last_fetch(self, source_id: int):
        """Обновить время последнего парсинга источника"""
        session: Session = self.session_factory()
        try:
            source = session.query(Source).filter(Source.id == source_id).first()
            if source:
                source.last_fetch = datetime.now()
                session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
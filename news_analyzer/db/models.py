from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Article(Base):
    """Основная таблица новостей"""
    __tablename__ = 'articles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False)  # telegram / vk / rss
    source_id = Column(String(255), nullable=False)
    title = Column(Text)
    text_clean = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)
    url = Column(Text)
    published_at = Column(DateTime, nullable=False)
    processed_at = Column(DateTime, nullable=False)
    text_hash = Column(String(64), nullable=False, unique=True)
    ai_model = Column(String(100), nullable=False)
    is_read = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint('source', 'source_id', name='unique_source_id'),
    )


class Source(Base):
    """Таблица настроенных источников"""
    __tablename__ = 'sources'

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(50), nullable=False)  # telegram / vk / rss
    name = Column(String(255), nullable=False)
    config = Column(Text, nullable=False)  # JSON string
    is_active = Column(Boolean, default=True)
    last_fetch = Column(DateTime)
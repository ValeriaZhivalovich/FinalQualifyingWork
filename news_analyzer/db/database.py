from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from .models import Base


def create_database_engine(database_url: str):
    """Создать SQLAlchemy engine"""
    if database_url.startswith('sqlite'):
        # Для SQLite отключаем пулинг для потокобезопасности
        engine = create_engine(
            database_url,
            connect_args={'check_same_thread': False},
            poolclass=StaticPool,
            echo=False  # В продакшене False
        )
    else:
        engine = create_engine(database_url, echo=False)

    return engine


def create_tables(engine):
    """Создать все таблицы"""
    Base.metadata.create_all(bind=engine)


def get_session_factory(engine) -> sessionmaker:
    """Получить фабрику сессий"""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session(session_factory: sessionmaker) -> Session:
    """Получить сессию БД (для использования в контекстах)"""
    return session_factory()
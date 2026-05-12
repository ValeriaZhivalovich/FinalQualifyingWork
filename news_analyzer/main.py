import sys
import os
import asyncio
from pathlib import Path
import argparse

# Windows: явно устанавливаем ProactorEventLoop для поддержки subprocess
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Добавить корневую директорию в путь для импортов
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Также добавить текущую директорию news_analyzer
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

import logging
from typing import List
from news_analyzer.config.settings import Settings
from news_analyzer.collectors.base import BaseCollector
from news_analyzer.db.database import create_database_engine, create_tables, get_session_factory
from news_analyzer.db.repository import DatabaseRepository
from news_analyzer.nlp.preprocessor import NLPPreprocessor
from news_analyzer.ai.ollama_backend import OllamaAgent
from news_analyzer.collectors.rss_collector import RSSCollector
from news_analyzer.collectors.telegram_telethon import TelegramTelethonCollector
from news_analyzer.collectors.telegram_pyrogram import TelegramPyrogramCollector
from news_analyzer.collectors.twitter_twikit import TwitterTwikitCollector
from news_analyzer.collectors.vk_vk_api import VkApiCollector
from news_analyzer.collectors.vk_vkwave import VkWaveCollector
from news_analyzer.collectors.reddit_praw import RedditPRAWCollector
from news_analyzer.collectors.reddit_asyncpraw import RedditAsyncPRAWCollector
from news_analyzer.pipeline.orchestrator import PipelineOrchestrator
from news_analyzer.ui.app import main as ui_main

logger = logging.getLogger(__name__)


def initialize_components(settings: Settings):
    """Инициализировать все компоненты приложения"""

    # Инициализация БД
    engine = create_database_engine(settings.database_url)
    create_tables(engine)
    session_factory = get_session_factory(engine)
    repository = DatabaseRepository(session_factory)

    # Инициализация NLP
    preprocessor = NLPPreprocessor()

    # Инициализация ИИ агента
    ai_agent = OllamaAgent(host=settings.ollama_host, model_name=settings.ollama_model)

    # Инициализация коллекторов
    collectors: List[BaseCollector] = [
        RSSCollector(),
    ]

    # Telegram (Telethon)
    if settings.telegram_api_id and settings.telegram_api_hash:
        collectors.append(TelegramTelethonCollector(
            api_id=int(settings.telegram_api_id) if settings.telegram_api_id.isdigit() else 0,
            api_hash=settings.telegram_api_hash,
            phone=settings.telegram_phone,
        ))

    # Telegram (Pyrogram)
    if settings.telegram_api_id and settings.telegram_api_hash:
        collectors.append(TelegramPyrogramCollector(
            api_id=int(settings.telegram_api_id) if settings.telegram_api_id.isdigit() else 0,
            api_hash=settings.telegram_api_hash,
            phone=settings.telegram_phone,
        ))

    # Twitter (Twikit) — требует логин/пароль
    if settings.twitter_username and settings.twitter_password:
        collectors.append(TwitterTwikitCollector(
            username=settings.twitter_username,
            password=settings.twitter_password,
            email=settings.twitter_email,
        ))

    # VK (vk_api)
    if settings.vk_access_token:
        collectors.append(VkApiCollector(access_token=settings.vk_access_token))

    # VK (vkwave)
    if settings.vk_access_token:
        collectors.append(VkWaveCollector(token=settings.vk_access_token))

    # Reddit (PRAW)
    if settings.reddit_client_id and settings.reddit_client_secret:
        collectors.append(RedditPRAWCollector(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent or "news_analyzer/1.0",
        ))

    # Reddit (asyncpraw)
    if settings.reddit_client_id and settings.reddit_client_secret:
        collectors.append(RedditAsyncPRAWCollector(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent or "news_analyzer/1.0",
        ))

    # Инициализация оркестратора
    orchestrator = PipelineOrchestrator(collectors, preprocessor, ai_agent, repository)

    return {
        'engine': engine,
        'session_factory': session_factory,
        'repository': repository,
        'preprocessor': preprocessor,
        'ai_agent': ai_agent,
        'collectors': collectors,
        'orchestrator': orchestrator
    }


def run_parsing_demo(orchestrator: PipelineOrchestrator):
    """Демонстрационный запуск парсинга"""
    logger.info("Starting parsing demo...")
    try:
        count = orchestrator.run_full_cycle()
        logger.info(f"Demo completed. Processed {count} articles.")
    except Exception as e:
        logger.error(f"Error during demo: {e}")


def main():
    """Главная функция приложения"""
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='News Analyzer')
    parser.add_argument('--headless', action='store_true', help='Run without GUI (for testing)')
    parser.add_argument('--skip-parsing', action='store_true', help='Skip initial parsing demo')
    args = parser.parse_args()

    logger.info("News Analyzer starting...")

    try:
        # Загрузка настроек
        settings = Settings()

        # Инициализация компонентов
        components = initialize_components(settings)

        logger.info("Components initialized successfully")

        # Проверка подключения к Ollama
        if not components['ai_agent'].validate_connection():
            logger.warning("Ollama connection not available. AI features will not work.")

        # Для демонстрации - запуск парсинга (если не отключено)
        if not args.skip_parsing:
            logger.info("Running initial parsing demo...")
            run_parsing_demo(components['orchestrator'])

        # Запуск UI (если не headless режим)
        if not args.headless:
            logger.info("Starting UI...")
            import flet as ft
            # Передаем orchestrator и repository в UI для возможности запуска парсинга и загрузки новостей
            def ui_main_with_components(page: ft.Page):
                from news_analyzer.ui.app import NewsAnalyzerApp
                app = NewsAnalyzerApp(
                    orchestrator=components['orchestrator'],
                    repository=components['repository']
                )
                app.main(page)

            ft.run(ui_main_with_components, view=ft.AppView.WEB_BROWSER)

            # Запуск планировщика с интервалом из настроек
            try:
                from news_analyzer.pipeline.scheduler import NewsScheduler
                scheduler = NewsScheduler(components['orchestrator'])
                scheduler.start(interval_minutes=settings.fetch_interval_minutes)
                components['scheduler'] = scheduler
                logger.info(f"Scheduler started with interval {settings.fetch_interval_minutes} min")
            except Exception as e:
                logger.warning(f"Failed to start scheduler: {e}")
        else:
            logger.info("Headless mode: skipping UI")

    except Exception as e:
        logger.error(f"Application error: {e}")
        raise


if __name__ == "__main__":
    main()
from typing import List, Optional, Callable
import logging
from datetime import datetime, timedelta
from ..collectors.base import BaseCollector
from ..nlp.preprocessor import NLPPreprocessor
from ..ai.agent import BaseAIAgent
from ..db.repository import DatabaseRepository
from ..models import RawArticle, CleanArticle, ProcessedArticle

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Оркестратор полного цикла обработки"""

    def __init__(self, collectors: List[BaseCollector], preprocessor: NLPPreprocessor,
                 ai_agent: BaseAIAgent, repository: DatabaseRepository):
        self.collectors = collectors
        self.preprocessor = preprocessor
        self.ai_agent = ai_agent
        self.repository = repository
        self._stop_requested = False

    def run_full_cycle(self) -> int:
        """Запустить полный цикл сбора и обработки"""
        total_processed = 0

        for collector in self.collectors:
            if not collector.validate_config():
                logger.warning(f"Invalid config for {collector.source_name}")
                continue

            try:
                raw_articles = collector.fetch()
                logger.info(f"Fetched {len(raw_articles)} articles from {collector.source_name}")

                for raw in raw_articles:
                    if self._stop_requested:
                        logger.info("Stop requested, halting processing")
                        break
                    try:
                        # Нормализация
                        clean = self.preprocessor.process(raw)

                        # ИИ обработка
                        processed = self.ai_agent.process(clean)

                        # Сохранение
                        try:
                            if self.repository.save_article(processed):
                                total_processed += 1
                                logger.debug(f"Processed and saved article: {processed.title}")
                            else:
                                logger.debug(f"Article already exists (duplicate): {raw.source_id}")
                        except Exception as e:
                            logger.error(f"Error saving article {processed.title}: {e}")

                    except Exception as e:
                        logger.error(f"Error processing article {raw.source_id}: {e}")

            except Exception as e:
                logger.error(f"Error fetching from {collector.source_name}: {e}")
            
            if self._stop_requested:
                break

        logger.info(f"Total articles processed: {total_processed}")
        return total_processed

    def run_stream_cycle(self, on_article_processed: Optional[Callable[[ProcessedArticle, bool], None]] = None,
                          on_article_skipped: Optional[Callable[[RawArticle, str], None]] = None,
                          on_step: Optional[Callable[[str], None]] = None,
                          max_articles: Optional[int] = None) -> int:
        """
        Запустить цикл сбора и обработки в потоковом режиме с оповещениями после каждой статьи.
        
        Args:
            on_article_processed: Колбек вызывается после обработки каждой статьи 
                                  (article, is_new -> True если сохранена, False если дубль)
            on_article_skipped: Колбек вызывается при пропуске статьи (raw_article, reason)
            on_step: Колбек для логирования шагов процесса (сообщение)
            max_articles: Максимальное количество статей для обработки (по умолчанию все)
        
        Returns:
            Количество новых обработанных статей
        """
        self._stop_requested = False
        total_processed = 0
        total_fetched = 0

        for collector in self.collectors:
            if self._stop_requested:
                break
            
            if not collector.validate_config():
                msg = f"Invalid config for {collector.source_name}"
                logger.warning(msg)
                if on_step:
                    on_step(msg)
                continue

            try:
                raw_articles = collector.fetch()
                total_fetched += len(raw_articles)
                msg = f"Fetched {len(raw_articles)} articles from {collector.source_name}"
                logger.info(msg)
                if on_step:
                    on_step(msg)

                for raw in raw_articles:
                    if self._stop_requested:
                        break
                    
                    if max_articles is not None and total_processed >= max_articles:
                        msg = f"Reached max articles limit ({max_articles})"
                        logger.info(msg)
                        if on_step:
                            on_step(msg)
                        self._stop_requested = True
                        break
                    
                    try:
                        # Нормализация
                        normalize_msg = f"Normalizing: {raw.title or 'No title'}"
                        logger.debug(normalize_msg)
                        if on_step:
                            on_step(normalize_msg)
                        
                        clean = self.preprocessor.process(raw)

                        # ИИ обработка
                        ai_msg = f"AI processing: {raw.title or 'No title'}"
                        logger.debug(ai_msg)
                        if on_step:
                            on_step(ai_msg)
                        
                        processed = self.ai_agent.process(clean)

                        # Сохранение
                        try:
                            if self.repository.save_article(processed):
                                total_processed += 1
                                msg = f"Saved: {processed.title}"
                                logger.info(msg)
                                if on_step:
                                    on_step(msg)
                                if on_article_processed:
                                    on_article_processed(processed, True)
                            else:
                                msg = f"Duplicate skipped: {raw.title or raw.source_id}"
                                logger.debug(msg)
                                if on_step:
                                    on_step(msg)
                                if on_article_skipped:
                                    on_article_skipped(raw, "duplicate")
                                if on_article_processed:
                                    # Передаем None как статью, чтобы показать что это дубль
                                    # или можно добавить специальный флаг
                                    pass
                        except Exception as e:
                            msg = f"Error saving article {processed.title}: {e}"
                            logger.error(msg)
                            if on_step:
                                on_step(msg)

                    except Exception as e:
                        msg = f"Error processing article {raw.source_id}: {e}"
                        logger.error(msg)
                        if on_step:
                            on_step(msg)

            except Exception as e:
                msg = f"Error fetching from {collector.source_name}: {e}"
                logger.error(msg)
                if on_step:
                    on_step(msg)

        msg = f"Stream cycle complete. Total processed: {total_processed}, Total fetched: {total_fetched}"
        logger.info(msg)
        if on_step:
            on_step(msg)
        return total_processed

    def stop_stream(self):
        """Остановить текущий потоковый цикл"""
        self._stop_requested = True

    def run_cycle_for_source(self, source_type: str, max_articles: Optional[int] = None,
                              on_article_processed: Optional[Callable[[ProcessedArticle, bool], None]] = None,
                              on_step: Optional[Callable[[str], None]] = None) -> int:
        """
        Запустить цикл только для указанного типа источника.
        
        Args:
            source_type: Тип источника (например, 'rss', 'telegram', 'vk')
            max_articles: Максимальное количество статей для обработки
            on_article_processed: Колбек после обработки статьи
            on_step: Колбек для шагов
        
        Returns:
            Количество новых обработанных статей
        """
        # Фильтруем коллекторы по типу источника
        target_collectors = [c for c in self.collectors if c.source_name == source_type]
        if not target_collectors:
            msg = f"No collectors found for source type: {source_type}"
            logger.warning(msg)
            if on_step:
                on_step(msg)
            return 0
        
        # Временно заменяем список коллекторов
        original_collectors = self.collectors
        self.collectors = target_collectors
        
        try:
            result = self.run_stream_cycle(
                on_article_processed=on_article_processed,
                on_step=on_step,
                max_articles=max_articles
            )
            return result
        finally:
            self.collectors = original_collectors
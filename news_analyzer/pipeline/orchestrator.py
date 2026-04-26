from typing import List
import logging
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

        logger.info(f"Total articles processed: {total_processed}")
        return total_processed
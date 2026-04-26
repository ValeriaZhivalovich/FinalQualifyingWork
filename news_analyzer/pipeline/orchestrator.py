from typing import List
from ..collectors.base import BaseCollector
from ..nlp.preprocessor import NLPPreprocessor
from ..ai.agent import BaseAIAgent
from ..db.repository import DatabaseRepository
from ..models import RawArticle, CleanArticle, ProcessedArticle


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
                print(f"Invalid config for {collector.source_name}")
                continue

            raw_articles = collector.fetch()
            print(f"Fetched {len(raw_articles)} articles from {collector.source_name}")

            for raw in raw_articles:
                try:
                    # Нормализация
                    clean = self.preprocessor.process(raw)

                    # ИИ обработка
                    processed = self.ai_agent.process(clean)

                    # Сохранение
                    if self.repository.save_article(processed):
                        total_processed += 1

                except Exception as e:
                    print(f"Error processing article {raw.source_id}: {e}")

        return total_processed
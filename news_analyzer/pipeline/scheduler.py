from apscheduler.schedulers.blocking import BlockingScheduler
from .orchestrator import PipelineOrchestrator


class NewsScheduler:
    """Планировщик для периодического запуска парсинга"""

    def __init__(self, orchestrator: PipelineOrchestrator):
        self.orchestrator = orchestrator
        self.scheduler = BlockingScheduler()

    def start(self, interval_minutes: int = 30):
        """Запустить планировщик"""
        self.scheduler.add_job(
            self._run_cycle,
            'interval',
            minutes=interval_minutes,
            id='news_fetch',
            name='Fetch and process news'
        )
        print(f"Scheduler started with {interval_minutes} minutes interval")
        self.scheduler.start()

    def _run_cycle(self):
        """Выполнить цикл обработки"""
        try:
            count = self.orchestrator.run_full_cycle()
            print(f"Processed {count} articles")
        except Exception as e:
            print(f"Error in scheduled cycle: {e}")

    def stop(self):
        """Остановить планировщик"""
        self.scheduler.shutdown()
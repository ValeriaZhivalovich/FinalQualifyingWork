from apscheduler.schedulers.background import BackgroundScheduler
from .orchestrator import PipelineOrchestrator


class NewsScheduler:
    """Планировщик для периодического запуска парсинга"""

    def __init__(self, orchestrator: PipelineOrchestrator):
        self.orchestrator = orchestrator
        self.scheduler = BackgroundScheduler()
        self._running = False

    def start(self, interval_minutes: int = 30):
        """Запустить планировщик"""
        if self._running:
            self.scheduler.resume()
            return
        self.scheduler.add_job(
            self._run_cycle,
            'interval',
            minutes=interval_minutes,
            id='news_fetch',
            name='Fetch and process news'
        )
        self.scheduler.start()
        self._running = True
        print(f"Scheduler started with {interval_minutes} minutes interval")

    def stop(self):
        """Остановить планировщик"""
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
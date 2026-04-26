import asyncio
import logging
import signal
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from .config import config
from .handlers import setup_routers
from .utils.service_notify import init_service_notifier, get_service_notifier
from .utils.pid_lock import PIDLock
# from .browser_manager import init_browser, stop_browser  # Отключено - используем расширение Chrome

# Настройка логирования
from .utils.logging_config import setup_logging, get_important_logger
from .config import config

# Настраиваем логирование с минимальным выводом в консоль
important_logger = setup_logging(config.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

async def on_startup() -> None:
    important_logger.info("Бот запускается...")
    logger.info(f"Загружено {len(config.IGNORED_USER_IDS)} игнорируемых ID: {config.IGNORED_USER_IDS}")
    
    # Браузер запускается через расширение Chrome в start_server.sh
    # Не нужно запускать отдельный браузер из бота
    logger.info("Используется браузер с расширением Chrome")
    important_logger.info("✅ Бот готов к работе с расширением Chrome")
    
    # Инициализируем сервисный нотификатор
    init_service_notifier(bot)
    service_notifier = get_service_notifier()
    if service_notifier:
        await service_notifier.notify_bot_started()
        
        # Уведомляем о текущем режиме работы
        from .utils.response_mode import response_mode_manager
        mode_description = response_mode_manager.get_mode_description()
        try:
            await bot.send_message(
                chat_id=config.SERVICE_CHAT_ID,
                text=f"ℹ️ <b>Текущий режим работы:</b>\n{mode_description}\n\n"
                     f"Используйте /mode для проверки режима\n"
                     f"Используйте /auto или /manual для переключения",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки информации о режиме: {e}")
    
async def on_shutdown() -> None:
    important_logger.info("Бот останавливается...")
    
    # Уведомляем об остановке бота
    service_notifier = get_service_notifier()
    if service_notifier:
        await service_notifier.notify_bot_stopped()
    
    # Останавливаем воркер очереди Perplexity если он запущен
    from .handlers.groups import perplexity_worker_task
    if perplexity_worker_task and not perplexity_worker_task.done():
        perplexity_worker_task.cancel()
        try:
            await perplexity_worker_task
        except asyncio.CancelledError:
            pass
        logger.info("Воркер очереди Perplexity остановлен")
    
    # Браузер управляется через start_server.sh, не нужно останавливать
    logger.info("Завершение работы бота")
    
    await bot.session.close()

async def main() -> None:
    # Подключаем роутеры
    dp.include_router(setup_routers())
    
    # Запускаем бота
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Polling режим
    logger.info("Запуск в режиме polling")
    important_logger.info("✅ Бот запущен и готов к работе")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        important_logger.error(f"❌ Критическая ошибка в polling: {e}")
        # Не вызываем raise, чтобы ошибка не пробросилась выше
        # Polling завершится, но процесс не упадет резко

# Глобальная переменная для PID lock
pid_lock = None

def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    important_logger.info(f"📡 Получен сигнал {signum}, завершаем работу...")
    if pid_lock:
        pid_lock.release()
    sys.exit(0)

if __name__ == "__main__":
    # Устанавливаем обработчики сигналов
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Создаем PID lock
    pid_lock = PIDLock("logs/bot.pid")
    
    # Проверяем, не запущен ли уже бот
    if not pid_lock.acquire():
        important_logger.error("❌ Бот уже запущен! Проверьте процессы или удалите logs/bot.pid")
        # Опционально: можем попробовать убить старый процесс
        if "--force" in sys.argv:
            important_logger.warning("⚠️ Принудительное завершение старого процесса...")
            if pid_lock.kill_existing():
                important_logger.info("✅ Старый процесс завершен")
                if not pid_lock.acquire():
                    important_logger.error("❌ Не удалось захватить блокировку после завершения старого процесса")
                    sys.exit(1)
            else:
                important_logger.error("❌ Не удалось завершить старый процесс")
                sys.exit(1)
        else:
            important_logger.info("💡 Используйте --force для принудительного перезапуска")
            sys.exit(1)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        important_logger.info("⏹ Остановка по Ctrl+C")
    except Exception as e:
        important_logger.error(f"❌ Бот упал с ошибкой: {e}")
        # НЕ вызываем raise - это предотвратит падение процесса
        # Бот завершится с кодом 1, но не крашнется
        sys.exit(1)
    finally:
        # Освобождаем PID lock при выходе
        if pid_lock:
            pid_lock.release()
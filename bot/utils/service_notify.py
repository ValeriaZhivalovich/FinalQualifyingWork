import logging
from typing import Optional
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from ..config import config

logger = logging.getLogger(__name__)


class ServiceNotifier:
    """Класс для отправки сервисных уведомлений в административный чат"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.service_chat_id = config.SERVICE_CHAT_ID
        self.enabled = self.service_chat_id != 0
        
        if not self.enabled:
            logger.info("ServiceNotifier отключен: SERVICE_CHAT_ID не установлен")
        else:
            logger.info(f"ServiceNotifier инициализирован для чата: {self.service_chat_id}")
    
    async def send_notification(self, message: str, parse_mode: str = "HTML") -> bool:
        """Отправляет уведомление в сервисный чат"""
        if not self.enabled:
            return False
            
        try:
            await self.bot.send_message(
                chat_id=self.service_chat_id,
                text=message,
                parse_mode=parse_mode,
                disable_web_page_preview=True
            )
            return True
        except TelegramAPIError as e:
            logger.error(f"Ошибка отправки в сервисный чат: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке в сервисный чат: {e}")
            return False
    
    async def notify_error(self, error_type: str, error_msg: str, context: Optional[str] = None):
        """Уведомляет об ошибке"""
        message = f"🚨 <b>Ошибка: {error_type}</b>\n\n"
        message += f"<code>{error_msg}</code>\n"
        
        if context:
            message += f"\n<b>Контекст:</b>\n{context}"
        
        await self.send_notification(message)
    
    async def notify_queue_status(self, queue_size: int, processing: bool = False):
        """Уведомляет о состоянии очереди"""
        status = "обрабатывается" if processing else "ожидает"
        emoji = "⚙️" if processing else "⏳"
        
        message = f"{emoji} <b>Состояние очереди:</b>\n"
        message += f"Размер очереди: {queue_size}\n"
        message += f"Статус: {status}"
        
        await self.send_notification(message)
    
    async def notify_request_start(self, chat_id: int, user_name: str, question: str, images: Optional[list] = None):
        """Уведомляет о начале обработки запроса"""
        # Обрезаем длинный вопрос
        question_preview = question[:200] + "..." if len(question) > 200 else question
        
        message = f"📥 <b>Новый запрос</b>\n\n"
        message += f"Чат: {chat_id}\n"
        message += f"Пользователь: {user_name}\n"
        message += f"Вопрос: <i>{question_preview}</i>"
        
        if images and len(images) > 0:
            message += f"\n\n🖼 <b>Вопрос содержит {len(images)} изображение(й)</b>"
        
        await self.send_notification(message)
        
        # Отправляем изображения отдельными сообщениями
        if images:
            import base64
            import io
            
            for idx, image_data in enumerate(images):
                try:
                    logger.info(f"Отправка изображения {idx + 1} из {len(images)}, размер: {len(image_data)} символов")
                    
                    # Убираем префикс data:image/jpeg;base64, если есть
                    if image_data.startswith('data:'):
                        logger.info("Убираем data: префикс")
                        image_data = image_data.split(',')[1]
                    
                    # Декодируем base64
                    image_bytes = base64.b64decode(image_data)
                    logger.info(f"Декодировано {len(image_bytes)} байт")
                    
                    # Создаем BytesIO объект
                    image_io = io.BytesIO(image_bytes)
                    image_io.seek(0)
                    
                    # Создаем InputFile из BytesIO
                    from aiogram.types import BufferedInputFile
                    input_file = BufferedInputFile(
                        file=image_bytes,
                        filename=f"image_{idx + 1}.jpg"
                    )
                    
                    # Отправляем изображение
                    await self.bot.send_photo(
                        chat_id=self.service_chat_id,
                        photo=input_file,
                        caption=f"Изображение {idx + 1} из {len(images)}"
                    )
                    logger.info(f"Изображение {idx + 1} успешно отправлено в сервисный чат")
                    
                except Exception as e:
                    logger.error(f"Ошибка при отправке изображения {idx + 1} в сервисный чат: {e}")
                    logger.error(f"Тип ошибки: {type(e).__name__}")
                    logger.error(f"Первые 100 символов изображения: {str(image_data)[:100]}...")
    
    async def notify_double_check_result(self, text: str, nano_result: bool, mini_result: bool):
        """Уведомляет о результатах двойной проверки"""
        text_preview = text[:100] + "..." if len(text) > 100 else text
        
        emoji = "✅" if nano_result and mini_result else "❌"
        message = f"{emoji} <b>Двойная проверка вопроса</b>\n\n"
        message += f"Текст: <i>{text_preview}</i>\n"
        message += f"GPT-4.1-nano: {'✅ Вопрос' if nano_result else '❌ Не вопрос'}\n"
        message += f"GPT-4.1-mini: {'✅ Вопрос' if mini_result else '❌ Не вопрос'}\n"
        message += f"Результат: {'Обработка' if nano_result and mini_result else 'Пропуск'}"
        
        await self.send_notification(message)
    
    async def notify_duplicate_skip(self, chat_id: int, user_name: str, question: str):
        """Уведомляет о пропуске повторного вопроса"""
        # Обрезаем длинный вопрос
        question_preview = question[:200] + "..." if len(question) > 200 else question
        
        message = f"🔁 <b>Пропуск повторного вопроса</b>\n\n"
        message += f"Чат: <code>{chat_id}</code>\n"
        message += f"Пользователь: {user_name}\n"
        message += f"Вопрос: <i>{question_preview}</i>\n"
        message += f"Причина: Идентичный вопрос был задан"
        
        await self.send_notification(message)
    
    async def notify_skip_response(self, chat_id: int, user_name: str, question: str, processing_time: float):
        """Уведомляет о пропуске вопроса (SKIP)"""
        # Обрезаем длинный вопрос
        question_preview = question[:200] + "..." if len(question) > 200 else question
        
        message = f"⏭️ <b>Вопрос пропущен (SKIP)</b>\n\n"
        message += f"Чат: {chat_id}\n"
        message += f"Пользователь: {user_name}\n"
        message += f"Вопрос: <i>{question_preview}</i>\n"
        message += f"Время обработки: {processing_time:.1f}с\n\n"
        
        await self.send_notification(message)
    
    async def notify_input_field_error(self, chat_id: int, user_name: str, question: str, processing_time: float):
        """Уведомляет о проблеме с полем ввода (технический SKIP)"""
        # Обрезаем длинный вопрос
        question_preview = question[:200] + "..." if len(question) > 200 else question
        
        message = f"⚠️ <b>Технический SKIP</b>\n\n"
        message += f"Чат: {chat_id}\n"
        message += f"Пользователь: {user_name}\n"
        message += f"Вопрос: <i>{question_preview}</i>\n"
        message += f"Время обработки: {processing_time:.1f}с\n\n"
        message += f"<i>Причина: Не удалось найти поле ввода в Perplexity Space</i>"
        
        await self.send_notification(message)
    
    async def notify_request_complete(self, chat_id: int, status: str, processing_time: float):
        """Уведомляет о завершении обработки запроса"""
        emoji = "✅" if status == "success" else "❌" if status == "error" else "⏭️"
        
        message = f"{emoji} <b>Запрос обработан</b>\n\n"
        message += f"Чат: {chat_id}\n"
        message += f"Статус: {status}\n"
        message += f"Время обработки: {processing_time:.1f}с"
        
        await self.send_notification(message)
    
    async def notify_bot_started(self):
        """Уведомляет о запуске бота"""
        message = "🤖 <b>Бот запущен (perplexity space)</b>\n\n"
        
        await self.send_notification(message)
    
    async def notify_bot_stopped(self):
        """Уведомляет об остановке бота"""
        await self.send_notification("🛑 <b>Бот остановлен</b>")


# Глобальный экземпляр для использования в других модулях
service_notifier: Optional[ServiceNotifier] = None


def init_service_notifier(bot: Bot) -> ServiceNotifier:
    """Инициализирует глобальный экземпляр ServiceNotifier"""
    global service_notifier
    service_notifier = ServiceNotifier(bot)
    return service_notifier


def get_service_notifier() -> Optional[ServiceNotifier]:
    """Возвращает глобальный экземпляр ServiceNotifier"""
    return service_notifier
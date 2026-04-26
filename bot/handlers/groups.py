from aiogram import Router, types, F
from aiogram.types import Message, PhotoSize
import logging
from collections import deque
from typing import Dict, List, Optional, Deque, Any, Set
import asyncio
import time
from datetime import datetime, timedelta
import base64
import io
from PIL import Image

from ..utils.gpt import is_question
from ..utils.perplexity import ask_perplexity_group
from ..config import config
from ..utils.service_notify import get_service_notifier
from ..utils.feedback import feedback_manager

router = Router()
logger = logging.getLogger(__name__)

print("✅ GROUPS.PY ЗАГРУЖЕН! Router создан.")  # Отладка

# Временно отключаем отладочный обработчик - он блокирует остальные!
# @router.message()
# async def debug_all_messages(message: Message) -> None:
#     """Отладочный обработчик для ВСЕХ сообщений"""
#     if message.chat.type in ["group", "supergroup"]:
#         print(f"🔵 DEBUG: Любое сообщение в группе!")
#         print(f"  - Chat type: {message.chat.type}")
#         print(f"  - Chat ID: {message.chat.id}")
#         print(f"  - Media group ID: {message.media_group_id}")
#         print(f"  - Has photo: {bool(message.photo)}")
#         print(f"  - Has caption: {bool(message.caption)}")
#         print(f"  - Caption: {message.caption[:50] if message.caption else None}")

# Настройки контекста
MAX_CONTEXT_SIZE = config.MAX_CONTEXT_SIZE

# Хранилище контекста для каждого чата
chat_contexts: Dict[int, Deque[Dict[str, Any]]] = {}

# Очередь запросов к Perplexity API
perplexity_queue: asyncio.Queue = asyncio.Queue()
perplexity_processing = False
perplexity_worker_task: Optional[asyncio.Task] = None

# Кеш администраторов чата (chat_id -> (admin_ids, last_update))
admin_cache: Dict[int, tuple[Set[int], datetime]] = {}
ADMIN_CACHE_TTL = timedelta(minutes=5)  # Обновляем кеш каждые 5 минут

# Кеш последних ответов бота для предотвращения повторов
# chat_id -> List[(question_hash, timestamp)]
recent_bot_responses: Dict[int, List[tuple[int, datetime]]] = {}
RESPONSE_CACHE_TTL = timedelta(minutes=10)  # Время жизни кеша ответов

# Кеш активных запросов для предотвращения дублирования
# request_id -> timestamp
active_requests: Dict[str, datetime] = {}
REQUEST_TTL = timedelta(minutes=5)  # Время жизни активного запроса

# Кеш для связи ответов бота с вопросами для фидбека
# (chat_id, message_id) -> (question, answer, context)
bot_messages_cache: Dict[tuple[int, int], tuple[str, str, Optional[str]]] = {}
MESSAGE_CACHE_TTL = timedelta(hours=24)  # Храним сутки для возможности получить фидбек

# Кеш для сбора медиагрупп (альбомов с несколькими фото)
# media_group_id -> {messages: List[Message], last_update: datetime}
media_groups_cache: Dict[str, Dict[str, Any]] = {}
MEDIA_GROUP_TTL = timedelta(seconds=5)  # Ждем 5 секунд для сбора всех фото альбома

def add_to_context(chat_contexts: Dict[int, Deque[Dict[str, Any]]], chat_id: int, message: Message) -> None:
    """Добавляет сообщение в контекст чата"""
    if chat_id not in chat_contexts:
        chat_contexts[chat_id] = deque(maxlen=MAX_CONTEXT_SIZE)
    
    # Сохраняем информацию о сообщении
    chat_contexts[chat_id].append({
        "user": message.from_user.full_name if message.from_user else "Unknown",
        "text": message.text or "",
        "message_id": message.message_id
    })

def get_chat_context(chat_contexts: Dict[int, Deque[Dict[str, Any]]], chat_id: int) -> List[Dict[str, Any]]:
    """Получает контекст чата (последние сообщения)"""
    if chat_id not in chat_contexts:
        return []
    
    return list(chat_contexts[chat_id])

async def is_chat_admin(message: Message, user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором чата"""
    chat_id = message.chat.id
    
    # Проверяем кеш
    if chat_id in admin_cache:
        admin_ids, last_update = admin_cache[chat_id]
        if datetime.now() - last_update < ADMIN_CACHE_TTL:
            return user_id in admin_ids
    
    # Обновляем кеш
    try:
        # Получаем список администраторов чата
        admins = await message.bot.get_chat_administrators(chat_id)
        admin_ids = {admin.user.id for admin in admins}
        admin_cache[chat_id] = (admin_ids, datetime.now())
        
        logger.debug(f"[{chat_id}] Обновлен список администраторов: {len(admin_ids)} админов")
        return user_id in admin_ids
    except Exception as e:
        logger.error(f"[{chat_id}] Ошибка при получении списка администраторов: {e}")
        return False

def is_direct_mention(message: Message) -> bool:
    """Проверяет, является ли сообщение прямым обращением к боту"""
    # Проверяем, есть ли упоминание бота в тексте
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                # Извлекаем упоминание из текста
                mention = message.text[entity.offset:entity.offset + entity.length]
                bot_info = message.bot._me
                if bot_info and bot_info.username and mention == f"@{bot_info.username}":
                    logger.debug(f"Обнаружено прямое упоминание бота: {mention}")
                    return True
    
    # Проверяем, является ли сообщение ответом на сообщение бота
    if message.reply_to_message:
        bot_info = message.bot._me
        if bot_info and message.reply_to_message.from_user and message.reply_to_message.from_user.id == bot_info.id:
            logger.debug("Обнаружен ответ на сообщение бота")
            return True
    
    return False

def _hash_question(question: str) -> int:
    """Создает хеш вопроса для проверки дубликатов"""
    # Нормализуем текст: убираем лишние пробелы, приводим к нижнему регистру
    normalized = " ".join(question.lower().split())
    return hash(normalized)

def is_recent_duplicate(chat_id: int, question: str) -> bool:
    """Проверяет, отвечал ли бот на похожий вопрос недавно"""
    if chat_id not in recent_bot_responses:
        return False
    
    question_hash = _hash_question(question)
    current_time = datetime.now()
    
    # Очищаем устаревшие записи
    recent_bot_responses[chat_id] = [
        (q_hash, timestamp) 
        for q_hash, timestamp in recent_bot_responses[chat_id]
        if current_time - timestamp < RESPONSE_CACHE_TTL
    ]
    
    # Проверяем наличие дубликата
    for q_hash, _ in recent_bot_responses[chat_id]:
        if q_hash == question_hash:
            return True
    
    return False

async def split_message(text: str, max_length: int = 4096) -> list:
    """Разбивает длинное сообщение на части с учетом HTML тегов и ссылок"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_text = text
    
    while current_text:
        if len(current_text) <= max_length:
            parts.append(current_text)
            break
        
        # Ищем безопасное место для разбивки
        # Приоритет 1: двойной перенос строки (конец абзаца)
        cut_point = current_text.rfind('\n\n', 0, max_length - 100)
        
        # Приоритет 2: одинарный перенос строки
        if cut_point == -1:
            cut_point = current_text.rfind('\n', 0, max_length - 100)
        
        # Приоритет 3: конец предложения
        if cut_point == -1:
            cut_point = current_text.rfind('. ', 0, max_length - 100)
            if cut_point != -1:
                cut_point += 1  # Включаем точку
        
        # Приоритет 4: запятая или другой разделитель
        if cut_point == -1:
            for sep in [', ', '; ', ' - ', ' — ']:
                cut_point = current_text.rfind(sep, 0, max_length - 100)
                if cut_point != -1:
                    cut_point += len(sep) - 1  # Оставляем разделитель
                    break
        
        # Если не нашли хорошее место, режем по пробелу
        if cut_point == -1:
            cut_point = current_text.rfind(' ', 0, max_length - 100)
        
        # В крайнем случае режем жестко
        if cut_point == -1:
            cut_point = max_length - 100
        
        # Проверяем, не разрываем ли мы HTML тег или ссылку
        part_to_check = current_text[:cut_point]
        
        # Подсчитываем незакрытые теги <a>
        open_links = part_to_check.count('<a href=') - part_to_check.count('</a>')
        
        # Если есть незакрытая ссылка, ищем её закрытие
        if open_links > 0:
            close_tag_pos = current_text.find('</a>', cut_point)
            if close_tag_pos != -1 and close_tag_pos - cut_point < 200:  # Если закрытие близко
                cut_point = close_tag_pos + 4  # Включаем закрывающий тег
        
        # Добавляем часть в список
        parts.append(current_text[:cut_point].rstrip())
        current_text = current_text[cut_point:].lstrip()
    
    return parts

async def send_direct_response(message: Message, answer: str, chat_id: int, question: str = None, context: str = None) -> None:
    """Отправляет ответ напрямую в чат с поддержкой длинных сообщений"""
    try:
        logger.info(f"[{chat_id}] Отправка ответа ({len(answer)} символов)")
        
        # Разбиваем длинное сообщение на части
        message_parts = await split_message(answer, max_length=4000)  # Оставляем запас для форматирования
        
        if len(message_parts) > 1:
            logger.info(f"[{chat_id}] Сообщение разбито на {len(message_parts)} частей")
        
        # Отправляем каждую часть
        bot_messages = []
        for i, part in enumerate(message_parts):
            # Добавляем индикатор части для многочастных сообщений
            if len(message_parts) > 1:
                part_indicator = f"\n\n📄 Часть {i+1}/{len(message_parts)}"
                # Добавляем индикатор только если он помещается
                if len(part) + len(part_indicator) < 4096:
                    part = part + part_indicator
            
            # Отправляем часть
            bot_message = None
            try:
                bot_message = await message.reply(part, parse_mode="HTML", disable_web_page_preview=True)
                logger.info(f"[{chat_id}] ✅ Часть {i+1}/{len(message_parts)} отправлена с HTML форматированием")
            except Exception as html_error:
                logger.warning(f"[{chat_id}] Ошибка HTML в части {i+1}: {html_error}, отправляем без форматирования")
                try:
                    bot_message = await message.reply(part, parse_mode=None)
                    logger.info(f"[{chat_id}] ✅ Часть {i+1}/{len(message_parts)} отправлена без форматирования")
                except Exception as send_error:
                    logger.error(f"[{chat_id}] Не удалось отправить часть {i+1}: {send_error}")
                    # Пробуем отправить укороченную версию
                    if len(part) > 1000:
                        try:
                            truncated = part[:1000] + "...\n\n⚠️ Сообщение обрезано из-за ошибки"
                            bot_message = await message.reply(truncated, parse_mode=None)
                            logger.info(f"[{chat_id}] Отправлена укороченная версия части {i+1}")
                        except:
                            logger.error(f"[{chat_id}] Не удалось отправить даже укороченную версию")
            
            if bot_message:
                bot_messages.append(bot_message)
            
            # Небольшая задержка между частями чтобы не флудить
            if i < len(message_parts) - 1:
                await asyncio.sleep(0.5)
        
        # Сохраняем информацию об ответе для возможности получить фидбек  
        # Используем первое сообщение из списка для фидбека
        if bot_messages and bot_messages[0]:
            question_text = question if question else message.text or ""
            context_text = context if context else None
            bot_messages_cache[(chat_id, bot_messages[0].message_id)] = (question_text, answer, context_text)
            logger.info(f"[{chat_id}] Сохранена информация об ответе для фидбека (msg_id: {bot_messages[0].message_id})")
            
        # Очищаем контекст чата после успешной отправки ответа
        if chat_id in chat_contexts:
            chat_contexts[chat_id].clear()
            logger.info(f"[{chat_id}] Контекст чата очищен после ответа")
            
        # Уведомляем об успешной отправке
        service_notifier = get_service_notifier()
        if service_notifier:
            processing_time = time.time() - message.date.timestamp()
            await service_notifier.notify_request_complete(chat_id, "success", processing_time)
            
    except Exception as e:
        logger.error(f"[{chat_id}] Ошибка при отправке ответа: {e}")

def add_to_response_cache(chat_id: int, question: str):
    """Добавляет вопрос в кеш ответов"""
    if chat_id not in recent_bot_responses:
        recent_bot_responses[chat_id] = []
    
    question_hash = _hash_question(question)
    recent_bot_responses[chat_id].append((question_hash, datetime.now()))
    
    # Ограничиваем размер кеша
    if len(recent_bot_responses[chat_id]) > 20:
        recent_bot_responses[chat_id] = recent_bot_responses[chat_id][-20:]

async def download_photo_as_base64(message: Message, photo: PhotoSize, max_size: int = 1024) -> Optional[str]:
    """Загружает фото, сжимает и конвертирует в base64"""
    try:
        # Создаем уникальный ID для отслеживания
        import uuid
        image_id = str(uuid.uuid4())[:8]
        logger.info(f"[IMAGE {image_id}] Начинаем загрузку изображения file_id={photo.file_id[:10]}...")
        
        # Загружаем файл
        file = await message.bot.get_file(photo.file_id)
        file_bytes = io.BytesIO()
        await message.bot.download_file(file.file_path, file_bytes)
        
        # Открываем изображение с помощью PIL
        file_bytes.seek(0)
        img = Image.open(file_bytes)
        
        # Конвертируем в RGB если нужно (для JPEG)
        if img.mode in ('RGBA', 'LA', 'P'):
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = rgb_img
        
        # Изменяем размер если изображение слишком большое
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            logger.info(f"Изображение сжато до {img.width}x{img.height}")
        
        # Сохраняем в буфер с оптимизацией качества
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)
        
        # Конвертируем в base64
        base64_image = base64.b64encode(output.read()).decode('utf-8')
        
        # Логируем размер
        size_kb = len(base64_image) / 1024
        logger.info(f"[IMAGE {image_id}] Размер изображения после сжатия: {size_kb:.1f} KB")
        
        # Возвращаем в формате data URL с ID в комментарии для отслеживания
        result = f"data:image/jpeg;base64,{base64_image}"
        logger.info(f"[IMAGE {image_id}] Изображение готово к отправке")
        return result
    except Exception as e:
        logger.error(f"Ошибка при загрузке изображения: {e}")
        return None

async def process_perplexity_queue():
    """Воркер для обработки очереди запросов к Perplexity"""
    global perplexity_processing
    
    # Максимальное время жизни задачи в очереди (2 минуты)
    MAX_QUEUE_TIME = 120.0
    
    while True:
        try:
            # Ждем следующий элемент из очереди
            task = await perplexity_queue.get()
            
            # Отмечаем, что идет обработка
            perplexity_processing = True
            logger.info(f"Начинаем обработку запроса из очереди. Размер очереди: {perplexity_queue.qsize()}")
            
            try:
                # Извлекаем данные из задачи
                message = task['message']
                text_to_process = task['text']
                context = task['context']
                images = task['images']
                is_direct = task['is_direct']
                created_at = task.get('created_at', time.time())
                chat_id = message.chat.id
                
                logger.info(f"[{chat_id}] Извлечены данные из задачи: images={len(images) if images else 0}")
                
                # Проверяем, не устарела ли задача
                queue_time = time.time() - created_at
                if queue_time > MAX_QUEUE_TIME:
                    logger.warning(f"[{chat_id}] Задача устарела после {queue_time:.1f}с в очереди")
                    continue
                
                # Логируем время ожидания в очереди
                logger.info(f"[{chat_id}] Время ожидания в очереди: {queue_time:.1f}с")
                
                # Уведомляем о начале обработки запроса
                service_notifier = get_service_notifier()
                if service_notifier:
                    user_name = message.from_user.full_name if message.from_user else "Unknown"
                    await service_notifier.notify_request_start(chat_id, user_name, text_to_process, images)
                    await service_notifier.notify_queue_status(perplexity_queue.qsize(), processing=True)
                
                # Выполняем запрос к Perplexity с ОГРАНИЧЕННЫМИ попытками
                attempt = 0
                MAX_ATTEMPTS = 5  # Максимум 5 попыток для занятого браузера
                # Рассчитываем базовое время ожидания в зависимости от размера очереди
                # Если это первый в очереди - проверяем чаще
                # Если далеко в очереди - проверяем реже
                current_queue_size = perplexity_queue.qsize()
                base_wait_time = min(10.0 + (current_queue_size * 5.0), 40.0)
                wait_time = base_wait_time
                max_wait_time = 60.0  # Максимум 60 секунд
                timeout_errors = 0  # Счетчик ошибок таймаута
                successful_response = False  # Флаг успешного получения ответа
                
                logger.info(f"[{chat_id}] Начальное время ожидания: {wait_time}с (позиция в очереди: {current_queue_size})")
                
                # НЕ используем флаг для отслеживания отправки!
                # Проблема: если создается новый чат, изображения должны быть отправлены заново
                # Решение: всегда передаем изображения при каждой попытке
                
                while attempt < MAX_ATTEMPTS and not successful_response:
                    attempt += 1  # Увеличиваем счетчик в начале цикла
                    
                    # Минимальная задержка между запросами к API (2 секунды)
                    if attempt > 1:  # Теперь проверяем > 1, так как счетчик увеличен
                        await asyncio.sleep(config.MIN_REQUEST_INTERVAL)
                    
                    logger.info(f"[{chat_id}] Попытка #{attempt} отправки запроса к Perplexity")
                    
                    # ВСЕГДА передаем изображения если они есть
                    # Это нужно потому что при ошибке может создаваться новый чат
                    current_images = images
                    
                    if current_images:
                        logger.info(f"[{chat_id}] Отправляем с {len(current_images)} изображениями")
                    else:
                        logger.info(f"[{chat_id}] Отправляем БЕЗ изображений")
                    
                    answer = await ask_perplexity_group(
                        text_to_process, 
                        context, 
                        current_images, 
                        is_direct_mention=is_direct
                    )
                    
                    # Если браузер занят, используем адаптивное ожидание
                    if answer == "BROWSER_BUSY":
                        logger.info(f"[{chat_id}] Браузер занят, попытка {attempt}/{MAX_ATTEMPTS}")
                        
                        if attempt >= MAX_ATTEMPTS:
                            logger.error(f"[{chat_id}] Превышено максимальное количество попыток ({MAX_ATTEMPTS})")
                            break
                        
                        # Обновляем позицию в очереди
                        current_queue_size = perplexity_queue.qsize()
                        
                        # Если мы следующие в очереди - проверяем чаще
                        if current_queue_size == 0:
                            wait_time = 5.0
                        else:
                            # Иначе ждем в зависимости от позиции
                            wait_time = min(wait_time * 1.2, max_wait_time)
                        
                        logger.warning(f"[{chat_id}] Браузер занят, попытка {attempt}/{MAX_ATTEMPTS}. Позиция в очереди: {current_queue_size}. Ожидание {wait_time} секунд...")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    # Если элемент не найден на странице, ждем немного и пробуем снова
                    elif answer == "ELEMENT_NOT_FOUND":
                        logger.warning(f"[{chat_id}] Элемент не найден, попытка {attempt}/{MAX_ATTEMPTS}. Ожидание 10 секунд...")
                        await asyncio.sleep(10.0)
                        continue
                    
                    # Если происходит перенаправление в пространство
                    elif answer == "REDIRECTING_TO_SPACE":
                        logger.warning(f"[{chat_id}] Перенаправление в пространство, попытка {attempt}/{MAX_ATTEMPTS}. Ожидание 5 секунд...")
                        await asyncio.sleep(5.0)
                        continue
                    
                    # Если получили None (ошибка), пробуем еще несколько раз
                    elif answer is None:
                        timeout_errors += 1
                        logger.error(f"[{chat_id}] Получен None от API (ошибка), попытка {attempt}/{MAX_ATTEMPTS}, ошибок таймаута: {timeout_errors}")
                        
                        if timeout_errors <= 3 and attempt < MAX_ATTEMPTS:
                            logger.warning(f"[{chat_id}] Ошибка запроса, попытка {attempt}/{MAX_ATTEMPTS}. Ожидание 10 секунд...")
                            logger.info(f"[{chat_id}] При следующей попытке изображения БУДУТ переданы снова")
                            await asyncio.sleep(10.0)
                            continue
                        else:
                            logger.error(f"[{chat_id}] Не удалось получить ответ после {attempt} попыток")
                            break
                    
                    else:
                        # Получили ответ (SKIP или текст) - выходим из цикла
                        successful_response = True
                        logger.info(f"[{chat_id}] Успешно получен ответ, прекращаем попытки")
                        break
                
                # Проверка на превышение лимита попыток
                if attempt >= MAX_ATTEMPTS and not answer:
                    logger.error(f"[{chat_id}] Не удалось получить ответ после {MAX_ATTEMPTS} попыток")
                    answer = None
                
                # Обрабатываем ответ
                processing_time = time.time() - created_at
                
                if answer:
                    if answer == "SKIP":
                        logger.info(f"[{chat_id}] Получен ответ SKIP")
                        # Уведомляем о пропуске с деталями
                        if service_notifier:
                            user_name = message.from_user.full_name if message.from_user else "Unknown"
                            await service_notifier.notify_skip_response(chat_id, user_name, text_to_process, processing_time)
                    else:
                        # Импортируем менеджер режимов
                        from ..utils.response_mode import response_mode_manager
                        
                        # Проверяем режим работы
                        if response_mode_manager.is_auto():
                            # В автоматическом режиме отправляем сразу
                            logger.info(f"[{chat_id}] Автоматический режим - отправляем ответ сразу")
                            await send_direct_response(message, answer, chat_id, text_to_process, context)
                            
                            # Уведомляем в сервисный чат о том, что ответ отправлен автоматически
                            if config.SERVICE_CHAT_ID and config.SERVICE_CHAT_ID != 0 and service_notifier:
                                user_name = message.from_user.full_name if message.from_user else "Unknown"
                                try:
                                    await message.bot.send_message(
                                        chat_id=config.SERVICE_CHAT_ID,
                                        text=f"🚀 <b>Ответ отправлен автоматически</b>\n\n"
                                             f"Чат: {chat_id}\n"
                                             f"Пользователь: {user_name}\n"
                                             f"Вопрос: {text_to_process[:100]}...\n\n"
                                             f"<b>Ответ:</b>\n{answer[:500]}...\n\n"
                                             f"⏱ Время обработки: {processing_time:.1f} сек",
                                        parse_mode="HTML",
                                        disable_web_page_preview=True
                                    )
                                except Exception as e:
                                    logger.error(f"Ошибка отправки уведомления в сервисный чат: {e}")
                            
                            # Уведомляем об автоматической отправке
                            if service_notifier:
                                await service_notifier.notify_request_complete(chat_id, "auto_sent", processing_time)
                        
                        # Проверяем, нужно ли подтверждение через сервисный чат (режим manual)
                        elif config.SERVICE_CHAT_ID and config.SERVICE_CHAT_ID != 0:
                            # Импортируем необходимые модули
                            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                            from ..utils.pending_responses import pending_manager, PendingResponse
                            import uuid
                            
                            # Создаем уникальный ключ для этого ответа
                            response_key = str(uuid.uuid4())[:8]
                            
                            # Сохраняем ответ в очереди ожидания
                            user_name = message.from_user.full_name if message.from_user else "Unknown"
                            pending = PendingResponse(
                                chat_id=chat_id,
                                message_id=message.message_id,
                                user_name=user_name,
                                question=text_to_process,
                                response=answer
                            )
                            await pending_manager.add(response_key, pending)
                            
                            # Создаем клавиатуру с кнопками
                            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                                [
                                    InlineKeyboardButton(text="✅ Отправить", callback_data=f"approve_{response_key}"),
                                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{response_key}")
                                ]
                            ])
                            
                            # Отправляем в сервисный чат для подтверждения
                            try:
                                mode_info = "🔒 <i>Режим с подтверждением</i>\n\n"
                                service_msg = await message.bot.send_message(
                                    chat_id=config.SERVICE_CHAT_ID,
                                    text=f"{mode_info}📨 <b>Новый ответ для подтверждения</b>\n\n"
                                         f"Чат: {chat_id}\n"
                                         f"Пользователь: {user_name}\n"
                                         f"Вопрос: {text_to_process}\n\n"
                                         f"<b>Ответ:</b>\n{answer}",
                                    parse_mode="HTML",
                                    reply_markup=keyboard,
                                    disable_web_page_preview=True
                                )
                                pending.service_message_id = service_msg.message_id
                                
                                logger.info(f"[{chat_id}] Ответ отправлен на подтверждение в сервисный чат")
                                
                                # Уведомляем об отправке на модерацию
                                if service_notifier:
                                    await service_notifier.notify_request_complete(chat_id, "pending_approval", processing_time)
                                    
                            except Exception as e:
                                logger.error(f"[{chat_id}] Ошибка отправки в сервисный чат: {e}")
                                # Если не удалось отправить в сервисный чат, отправляем напрямую
                                await send_direct_response(message, answer, chat_id, text_to_process, context)
                                
                        else:
                            # Если сервисный чат не настроен, отправляем напрямую
                            await send_direct_response(message, answer, chat_id, text_to_process, context)
                            
                        # Добавляем вопрос в кеш ответов
                        add_to_response_cache(chat_id, text_to_process)
                elif answer is None:
                    logger.error(f"[{chat_id}] Получен пустой ответ от API")
                    # Уведомляем об ошибке
                    if service_notifier:
                        await service_notifier.notify_error("Empty Response", "API вернул пустой ответ", f"Chat: {chat_id}")
                        await service_notifier.notify_request_complete(chat_id, "error", processing_time)
                
                # Очищаем изображения из памяти после обработки
                if images:
                    logger.info(f"[{chat_id}] Очистка {len(images)} изображений из памяти")
                    images.clear()
                    images = None
                    
            except Exception as e:
                logger.error(f"Ошибка при обработке запроса из очереди: {e}")
                # Уведомляем об ошибке
                if service_notifier:
                    await service_notifier.notify_error("Queue Processing Error", str(e), f"Chat: {chat_id}")
            finally:
                # Отмечаем завершение обработки
                perplexity_processing = False
                
                # Небольшая задержка между запросами (2 секунды как в конфиге)
                await asyncio.sleep(config.MIN_REQUEST_INTERVAL)
                
        except asyncio.CancelledError:
            logger.info("Воркер очереди Perplexity остановлен")
            break
        except Exception as e:
            logger.error(f"Критическая ошибка в воркере очереди: {e}")
            perplexity_processing = False
            # Уведомляем о критической ошибке
            service_notifier = get_service_notifier()
            if service_notifier:
                await service_notifier.notify_error("Critical Queue Error", str(e), "Воркер очереди перезапустится через 5 секунд")
            await asyncio.sleep(5)  # Пауза перед повтором при критической ошибке

async def process_media_group(messages: List[Message]) -> None:
    """Обрабатывает медиагруппу (альбом с несколькими фото)"""
    print(f"🟢 process_media_group вызван с {len(messages) if messages else 0} сообщениями")
    
    if not messages:
        print("⚠️ Нет сообщений для обработки")
        return
    
    chat_id = messages[0].chat.id
    print(f"[{chat_id}] Обработка медиагруппы из {len(messages)} сообщений")
    logger.info(f"[{chat_id}] Обработка медиагруппы из {len(messages)} сообщений")
    
    # Берем первое сообщение как основное
    main_message = messages[0]
    
    # Собираем все изображения
    all_images = []
    combined_caption = ""
    
    for msg in messages:
        if msg.photo:
            # Берем самое большое фото из каждого сообщения
            largest_photo = msg.photo[-1]
            logger.info(f"[{chat_id}] Загружаем фото {largest_photo.width}x{largest_photo.height}")
            
            try:
                image_base64 = await download_photo_as_base64(msg, largest_photo)
                if image_base64:
                    all_images.append(image_base64)
                    logger.info(f"[{chat_id}] Фото #{len(all_images)} загружено")
            except Exception as e:
                logger.error(f"[{chat_id}] Ошибка загрузки фото: {e}")
        
        # Собираем подписи
        if msg.caption and msg.caption not in combined_caption:
            if combined_caption:
                combined_caption += " "
            combined_caption += msg.caption
    
    logger.info(f"[{chat_id}] Загружено {len(all_images)} изображений из медиагруппы")
    logger.info(f"[{chat_id}] Объединенная подпись: {combined_caption[:100] if combined_caption else 'Нет'}")
    
    # Создаем словарь с дополнительными данными для медиагруппы
    media_group_data = {
        'images': all_images,
        'combined_caption': combined_caption
    }
    
    logger.info(f"[{chat_id}] 🚀 Отправляем медиагруппу на обработку...")
    # Отправляем на обработку с дополнительными данными
    await handle_group_message_with_media(main_message, media_group_data)

@router.message(F.chat.type.in_(["group", "supergroup"]) & F.media_group_id)
async def handle_media_group_message(message: Message) -> None:
    """Обработчик медиагрупп (альбомов) в группах"""
    print(f"🟣 МЕДИАГРУППА ПОЛУЧЕНА! media_group_id: {message.media_group_id}")
    
    chat_id = message.chat.id
    media_group_id = message.media_group_id
    
    print(f"[{chat_id}] 📸 Получено сообщение из медиагруппы {media_group_id}")
    print(f"[{chat_id}] Фото: {bool(message.photo)}, Подпись: {message.caption[:50] if message.caption else 'нет'}")
    print(f"[{chat_id}] От пользователя: {message.from_user.full_name if message.from_user else 'Unknown'}")
    
    # Очищаем старые медиагруппы
    current_time = datetime.now()
    expired_groups = [
        gid for gid, data in media_groups_cache.items()
        if current_time - data['last_update'] > MEDIA_GROUP_TTL
    ]
    for gid in expired_groups:
        if gid in media_groups_cache:
            await process_media_group(media_groups_cache[gid]['messages'])
            del media_groups_cache[gid]
    
    # Добавляем сообщение в кеш медиагруппы
    if media_group_id not in media_groups_cache:
        media_groups_cache[media_group_id] = {
            'messages': [],
            'last_update': current_time,
            'processing_scheduled': False  # Флаг, что обработка уже запланирована
        }
    
    media_groups_cache[media_group_id]['messages'].append(message)
    media_groups_cache[media_group_id]['last_update'] = current_time
    
    print(f"[{chat_id}] Сообщение добавлено в медиагруппу {media_group_id} (всего: {len(media_groups_cache[media_group_id]['messages'])})")
    
    # Планируем обработку только если еще не запланирована
    if not media_groups_cache[media_group_id]['processing_scheduled']:
        media_groups_cache[media_group_id]['processing_scheduled'] = True
        print(f"[{chat_id}] Планируем обработку медиагруппы {media_group_id}")
        asyncio.create_task(schedule_media_group_processing(media_group_id))
    else:
        print(f"[{chat_id}] Обработка медиагруппы {media_group_id} уже запланирована")

@router.message(F.chat.type.in_(["group", "supergroup"]))
async def handle_group_message(message: Message) -> None:
    """Основной обработчик сообщений в группах (не медиагруппы)"""
    # Проверим, что это действительно не медиагруппа
    if message.media_group_id:
        print(f"⚠️ ОШИБКА: Медиагруппа попала в обычный обработчик! media_group_id: {message.media_group_id}")
        # Не обрабатываем - должно быть обработано специальным обработчиком
        return
    
    print(f"🔴 ОБЫЧНОЕ СООБЩЕНИЕ В ГРУППЕ ПОЛУЧЕНО!")  # Прямой print для отладки
    
    chat_id = message.chat.id
    
    # Логируем обычное сообщение
    print(f"[{chat_id}] 📨 Обычное сообщение от {message.from_user.full_name if message.from_user else 'Unknown'}")
    print(f"[{chat_id}] text: {message.text[:50] if message.text else None}")
    print(f"[{chat_id}] photo: {bool(message.photo)}, caption: {message.caption[:50] if message.caption else None}")
    print(f"[{chat_id}] media_group_id: {message.media_group_id}")
    
    # Обработка обычного сообщения
    await handle_group_message_internal(message)

async def schedule_media_group_processing(media_group_id: str):
    """Планирует обработку медиагруппы через таймаут"""
    print(f"⏰ Планируем обработку медиагруппы {media_group_id} через 2 секунды...")
    await asyncio.sleep(2)  # Ждем 2 секунды для сбора всех фото
    
    print(f"⏰ Время вышло! Обрабатываем медиагруппу {media_group_id}")
    if media_group_id in media_groups_cache:
        messages = media_groups_cache[media_group_id]['messages']
        print(f"⏰ В медиагруппе {len(messages)} сообщений")
        await process_media_group(messages)
        # Безопасное удаление из кеша
        try:
            del media_groups_cache[media_group_id]
        except KeyError:
            print(f"⚠️ Медиагруппа {media_group_id} уже была удалена из кеша")
    else:
        print(f"⚠️ Медиагруппа {media_group_id} уже обработана или удалена")

async def handle_group_message_with_media(message: Message, media_group_data: dict = None) -> None:
    """Обработка сообщений с медиагруппами"""
    await handle_group_message_internal(message, media_group_data)

async def handle_group_message_internal(message: Message, media_group_data: dict = None) -> None:
    """Обработка сообщений в группах"""
    print(f"🟡 handle_group_message_internal ВЫЗВАН!")  # Прямой print
    
    global perplexity_worker_task
    chat_id = message.chat.id
    user_name = message.from_user.full_name if message.from_user else "Unknown"
    
    print(f"[{chat_id}] 🔍 handle_group_message_internal вызван для сообщения от {user_name}")
    logger.info(f"[{chat_id}] 🔍 handle_group_message_internal вызван для сообщения от {user_name}")
    logger.info(f"[{chat_id}] Тип сообщения: photo={bool(message.photo)}, text={bool(message.text)}, caption={bool(message.caption)}")
    if media_group_data and 'images' in media_group_data:
        logger.info(f"[{chat_id}] Есть предзагруженные изображения медиагруппы: {len(media_group_data['images'])}")
    user_id = message.from_user.id if message.from_user else None
    
    print(f"[{chat_id}] User ID: {user_id}, IGNORED_USER_IDS: {config.IGNORED_USER_IDS}")  # Отладка
    
    logger.debug(f"[{chat_id}] === НАЧАЛО ОБРАБОТКИ СООБЩЕНИЯ от {user_name} ===")
    
    # Проверяем, является ли сообщение прямым обращением к боту
    is_direct = is_direct_mention(message)
    
    # Если это НЕ прямое обращение, проверяем игнор-листы
    if not is_direct:
        # Проверяем, не в списке ли игнорируемых пользователей
        logger.debug(f"[{chat_id}] Проверка пользователя {user_name} (ID: {user_id}) на игнор-лист")
        if user_id and user_id in config.IGNORED_USER_IDS:
            logger.info(f"[{chat_id}] Игнорируем сообщение от пользователя {user_name} (ID: {user_id})")
            return
        
        # Проверяем, является ли пользователь администратором чата
        if config.IGNORE_CHAT_ADMINS and user_id:
            is_admin = await is_chat_admin(message, user_id)
            if is_admin:
                logger.info(f"[{chat_id}] Игнорируем сообщение от администратора {user_name} (ID: {user_id})")
                return
    else:
        logger.info(f"[{chat_id}] Прямое обращение к боту от {user_name} (ID: {user_id}) - обрабатываем несмотря на игнор-листы")
    
    # Добавляем сообщение в контекст чата
    add_to_context(chat_contexts, chat_id, message)
    
    # Получаем текст для обработки, включая цитируемое сообщение
    # Важно: для фото используется caption, а не text
    # Для медиагрупп используем объединенную подпись
    if media_group_data and 'combined_caption' in media_group_data:
        text_to_process = media_group_data['combined_caption'] or ""
        logger.info(f"[{chat_id}] Используем объединенную подпись медиагруппы: {text_to_process[:50]}")
    else:
        text_to_process = message.text or message.caption or ""
    
    has_photo = False
    
    logger.info(f"[{chat_id}] Начальный text_to_process: {text_to_process[:50] if text_to_process else 'пусто'}")
    photo_description = ""
    
    # Проверяем наличие изображений в сообщении
    if message.photo or (media_group_data and 'images' in media_group_data):
        has_photo = True
        # Для медиагрупп количество фото уже подсчитано
        if media_group_data and 'images' in media_group_data:
            photo_count = len(media_group_data['images'])
            logger.info(f"[{chat_id}] Используем предзагруженные изображения медиагруппы: {photo_count} шт")
        else:
            photo_count = len(message.photo)
        photo_description = f"[Пользователь прикрепил {photo_count} изображение(й)]"
        
        # text_to_process уже содержит caption, если он был
        if text_to_process:
            logger.info(f"[{chat_id}] Обнаружено изображение с подписью: {text_to_process[:50]}...")
        else:
            # Если нет подписи И это НЕ прямое обращение - игнорируем
            if not is_direct:
                logger.info(f"[{chat_id}] Изображение без подписи и без прямого обращения - ИГНОРИРУЕМ")
                return
            # Если есть прямое обращение, создаем вопрос по умолчанию
            text_to_process = "Что на этом изображении? Объясни что ты видишь."
            logger.info(f"[{chat_id}] Обнаружено изображение без подписи, но с прямым обращением, используем вопрос по умолчанию")
    
    # Обработка пересланных сообщений (forward)
    if message.forward_origin:
        logger.debug(f"[{chat_id}] Обнаружено пересланное сообщение")
        
        # Определяем источник пересылки
        forward_from = "Unknown"
        if hasattr(message.forward_origin, 'sender_user') and message.forward_origin.sender_user:
            forward_from = message.forward_origin.sender_user.full_name
        elif hasattr(message.forward_origin, 'sender_user_name') and message.forward_origin.sender_user_name:
            forward_from = message.forward_origin.sender_user_name
        elif hasattr(message.forward_origin, 'chat') and message.forward_origin.chat:
            forward_from = message.forward_origin.chat.title
        elif hasattr(message.forward_origin, 'sender_chat') and message.forward_origin.sender_chat:
            forward_from = message.forward_origin.sender_chat.title
        
        # Если есть текст в основном сообщении - это главное
        if text_to_process:
            # Добавляем информацию о пересылке как контекст
            text_to_process = f"{text_to_process}\n\n[Контекст: пересланное сообщение от {forward_from}]"
        else:
            # Если основного текста нет и это не прямое обращение - игнорируем
            if not is_direct:
                logger.info(f"[{chat_id}] Пересланное сообщение без текста и без прямого обращения - ИГНОРИРУЕМ")
                return
            # Если есть прямое обращение, используем текст "Что это за пересланное сообщение?"
            text_to_process = f"Что это за пересланное сообщение от {forward_from}?"
    
    # Если сообщение является ответом на другое сообщение (цитата)
    elif message.reply_to_message:
        quoted_user = message.reply_to_message.from_user.full_name if message.reply_to_message.from_user else "Unknown"
        
        # ВАЖНО: Сначала проверяем, есть ли основной текст в сообщении
        if not text_to_process and not has_photo:
            # Если нет основного текста и фото, и это не прямое обращение - игнорируем
            if not is_direct:
                logger.info(f"[{chat_id}] Цитата без основного вопроса и без прямого обращения - ИГНОРИРУЕМ")
                return
            # Если есть прямое обращение, создаем вопрос по умолчанию
            text_to_process = "Что ты думаешь об этом?"
        
        # Проверяем, есть ли выделенная часть цитаты
        if hasattr(message, 'quote') and message.quote:
            # Используем только выделенную часть
            quoted_text = message.quote.text
            text_to_process = f'Вопрос: {text_to_process}\n\n[Контекст: цитата от {quoted_user}: "{quoted_text}"]'
            logger.debug(f"[{chat_id}] Обнаружена частичная цитата от {quoted_user}: {quoted_text[:50]}...")
        elif message.reply_to_message.text:
            # Если выделенной части нет, используем весь текст сообщения
            text_to_process = f'Вопрос: {text_to_process}\n\n[Контекст: полная цитата от {quoted_user}: "{message.reply_to_message.text}"]'
            logger.debug(f"[{chat_id}] Обнаружена полная цитата от {quoted_user}")
        
        # Проверяем изображения в цитируемом сообщении
        if message.reply_to_message.photo:
            quoted_photo_count = len(message.reply_to_message.photo)
            text_to_process += f"\n[В цитируемом сообщении есть {quoted_photo_count} изображение(й)]"
    
    # Проверяем, является ли сообщение вопросом через GPT (с двойной проверкой)
    try:
        logger.info(f"[{chat_id}] Проверяем is_question для: {text_to_process[:50]}...")
        # Используем двойную проверку (gpt-4.1-nano + gpt-4.1-mini)
        if not await is_question(text_to_process, double_check=True):
            logger.info(f"[{chat_id}] Сообщение НЕ определено как вопрос (двойная проверка), пропускаем")
            return
        logger.info(f"[{chat_id}] Сообщение определено как вопрос")
    except Exception as e:
        logger.error(f"Ошибка при проверке вопроса: {e}")
        return
    
    logger.info(f"[{chat_id}] Вопрос от {user_name} (ID: {user_id}): {text_to_process[:config.MAX_LOG_MESSAGE_LENGTH]}...")
    
    # Проверяем, не отвечали ли мы на похожий вопрос недавно
    if is_recent_duplicate(chat_id, text_to_process):
        logger.info(f"[{chat_id}] Пропускаем дубликат вопроса: {text_to_process[:50]}...")
        # Уведомляем в сервисный чат о пропуске дубликата
        service_notifier = get_service_notifier()
        if service_notifier:
            await service_notifier.notify_duplicate_skip(chat_id, user_name, text_to_process)
        return
    
    # Запускаем воркер если он еще не запущен
    if perplexity_worker_task is None or perplexity_worker_task.done():
        perplexity_worker_task = asyncio.create_task(process_perplexity_queue())
        logger.info("Запущен воркер очереди Perplexity")
    
    # Получаем контекст (последние 5 сообщений)
    context = get_chat_context(chat_contexts, chat_id)
    logger.debug(f"[{chat_id}] Контекст: {len(context)} сообщений")
    
    # Загружаем изображения, если они есть
    images = []
    
    # Проверяем, были ли изображения предзагружены (для медиагрупп)
    if media_group_data and 'images' in media_group_data:
        images = media_group_data['images']
        logger.info(f"[{chat_id}] Используем {len(images)} предзагруженных изображений из медиагруппы")
    elif has_photo and message.photo:
        logger.info(f"[{chat_id}] Обнаружено {len(message.photo)} размеров изображения")
        
        # Берем самое большое изображение (последнее в массиве)
        largest_photo = message.photo[-1]
        logger.info(f"[{chat_id}] Загружаем изображение размером {largest_photo.width}x{largest_photo.height}")
        
        try:
            image_base64 = await download_photo_as_base64(message, largest_photo)
            if image_base64:
                images.append(image_base64)
                logger.info(f"[{chat_id}] Изображение успешно загружено и конвертировано в base64")
                logger.info(f"[{chat_id}] Размер base64: {len(image_base64)} символов")
            else:
                logger.warning(f"[{chat_id}] Не удалось загрузить изображение")
        except Exception as e:
            logger.error(f"[{chat_id}] Ошибка при загрузке изображения: {e}")
    
    # Создаем задачу для очереди
    task = {
        'message': message,
        'text': text_to_process,
        'context': context,
        'images': images if images else None,
        'is_direct': is_direct_mention(message),
        'created_at': time.time()  # Добавляем время создания задачи
    }
    
    # Логируем содержимое задачи
    logger.info(f"[{chat_id}] Создана задача: текст={len(text_to_process)} символов, " +
                f"контекст={len(context)} сообщений, изображения={len(images) if images else 0}")
    
    # Дополнительное логирование для отладки изображений
    if images:
        logger.info(f"[{chat_id}] [DEBUG] Текст вопроса с изображением: {text_to_process}")
        logger.info(f"[{chat_id}] [DEBUG] Размер первого изображения: {len(images[0])} символов")
    
    # Проверяем размер очереди ДО добавления
    queue_was_empty = perplexity_queue.qsize() == 0 and not perplexity_processing
    
    # Добавляем задачу в очередь
    await perplexity_queue.put(task)
    queue_size = perplexity_queue.qsize()
    
    # Если очередь была пустая и не было обработки - запрос начнется сразу
    # Иначе - он автоматически идет в конец очереди
    if queue_was_empty:
        logger.info(f"[{chat_id}] Запрос добавлен в очередь и начнется немедленно")
    else:
        logger.info(f"[{chat_id}] Запрос добавлен в конец очереди. Позиция: {queue_size}")
        logger.info(f"[{chat_id}] В очереди уже есть задачи или идет обработка - новый запрос ждет своей очереди")
    
    # ВАЖНО: Завершаем функцию после добавления в очередь!
    return

@router.message_reaction()
async def handle_reaction(update: types.MessageReactionUpdated):
    """Обработчик реакций на сообщения бота"""
    try:
        chat_id = update.chat.id
        message_id = update.message_id
        
        # Проверяем, что это реакция на сообщение бота
        cache_key = (chat_id, message_id)
        if cache_key not in bot_messages_cache:
            return
        
        # Получаем информацию об ответе
        question, answer, context = bot_messages_cache[cache_key]
        
        # Определяем тип реакции (новые реакции)
        new_reactions = update.new_reaction if update.new_reaction else []
        
        # Ищем лайки и дизлайки среди новых реакций
        has_like = False
        has_dislike = False
        
        for reaction in new_reactions:
            if hasattr(reaction, 'emoji'):
                emoji = reaction.emoji
                # Положительная реакция: 🔥 (огонек)
                if emoji == '🔥':
                    has_like = True
                # Отрицательная реакция: 🤨 (сомнение)
                elif emoji == '🤨':
                    has_dislike = True
        
        # Обрабатываем фидбек
        if has_like:
            result = feedback_manager.add_feedback(
                message_id=message_id,
                chat_id=chat_id,
                question=question,
                answer=answer,
                is_positive=True,
                user_id=update.user.id if update.user else None,
                context=context
            )
            logger.info(f"[{chat_id}] Получен положительный фидбек для сообщения {message_id}")
            
        elif has_dislike:
            result = feedback_manager.add_feedback(
                message_id=message_id,
                chat_id=chat_id,
                question=question,
                answer=answer,
                is_positive=False,
                user_id=update.user.id if update.user else None,
                context=context
            )
            logger.info(f"[{chat_id}] Получен отрицательный фидбек для сообщения {message_id}")
            
            # Просто логируем негативный фидбек
            logger.info(f"[{chat_id}] 🤨 Негативный фидбек сохранен. Проверьте data/feedback_export.txt")
        
        # Очищаем старые записи из кеша
        current_time = datetime.now()
        keys_to_remove = []
        for key, (_, _, _) in list(bot_messages_cache.items()):
            # Проверяем по времени (здесь нужно будет добавить timestamp в кеш)
            # Пока просто ограничиваем размер кеша
            if len(bot_messages_cache) > 1000:
                keys_to_remove.append(key)
        
        for key in keys_to_remove[:len(bot_messages_cache) - 1000]:
            del bot_messages_cache[key]
            
    except Exception as e:
        logger.error(f"Ошибка обработки реакции: {e}", exc_info=True)
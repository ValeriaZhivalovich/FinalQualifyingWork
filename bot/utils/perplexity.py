import httpx
import json
import logging
import asyncio
import re
from typing import Union, Dict, List, Tuple, Optional, Any

from ..config import config

logger = logging.getLogger(__name__)

# Импортируем константы из конфига
DEFAULT_TIMEOUT = config.DEFAULT_TIMEOUT
EXTENDED_TIMEOUT = config.EXTENDED_TIMEOUT
IMAGE_TIMEOUT = config.IMAGE_TIMEOUT
MAX_RETRIES = config.MAX_RETRIES
RETRY_DELAY = config.RETRY_DELAY

# Сообщения об ошибках
ERROR_MESSAGES = {
    'timeout': "⏱ Время ожидания ответа истекло. Попробуйте позже.",
    'server_error': "⚠️ Ошибка сервера: {status_code}",
    'connection_error': "🔌 Ошибка подключения.",
    'processing_error': "⚙️ Ошибка обработки данных.",
    'unknown_error': "❌ Произошла неизвестная ошибка.",
    'invalid_response': "⚠️ Неожиданный формат ответа от сервера."
}

# Паттерны для нетехнических ответов
NON_TECHNICAL_RESPONSES = ["SKIP", "NONE", ""]
NON_TECHNICAL_SUFFIXES = ["SKIP", "SKIP.", "NONE", "NONE."]


# Паттерн для языков программирования
CODE_LANGUAGE_PATTERN = r'^(python|javascript|java|cpp|c\+\+|csharp|c#|go|rust|ruby|php|typescript|swift|kotlin|scala|r|matlab|perl|bash|shell|sql|html|css|xml|json|yaml|dockerfile|makefile)([a-zA-Z])'

# Расширения файлов для фильтрации
FILE_EXTENSIONS = ['.json', '.pdf', '.txt', '.csv', '.xlsx', '.xls', '.doc', '.docx', 
                   '.png', '.jpg', '.jpeg', '.gif', '.zip', '.rar', '.tar', '.gz',
                   '.py', '.js', '.java', '.cpp', '.c', '.h', '.cs', '.php', '.rb',
                   '.go', '.rs', '.kt', '.swift', '.m', '.mm', '.sql', '.sh', '.bat',
                   '.xml', '.yaml', '.yml', '.ini', '.conf', '.config', '.env',
                   '.md', '.rst', '.tex', '.log', '.tmp', '.bak']

# Префиксы технических/нетехнических объяснений для фильтрации
TECHNICAL_PREFIXES = [
    r"^Это технический вопрос[\.:,\s]",
    r"^Данный вопрос является техническим[\.:,\s]",
    r"^Вопрос технический[\.:,\s]",
    r"^Это нетехнический вопрос[\.:,\s]",
    r"^Данный вопрос не является техническим[\.:,\s]",
    r"^Вопрос нетехнический[\.:,\s]",
    r"^This is a technical question[\.:,\s]",
    r"^This is not a technical question[\.:,\s]",
    r"^The question is technical[\.:,\s]",
    r"^The question is not technical[\.:,\s]"
]


def _extract_reply_text(data: dict) -> str:
    """Извлекает текст ответа из структуры данных API."""
    if "content" in data and isinstance(data["content"], list):
        reply_parts = []
        for content_block in data["content"]:
            if "text" in content_block:
                reply_parts.append(content_block["text"])
        return "".join(reply_parts)
    return ""


def _is_non_technical_response(text: str) -> bool:
    """Проверяет, является ли ответ нетехническим."""
    if not text:
        return True
        
    text_stripped = text.strip()
    text_upper = text_stripped.upper()
    
    # Проверка точного совпадения
    if text_upper in NON_TECHNICAL_RESPONSES:
        return True
    
    # Проверка на начало с SKIP
    if text_upper.startswith("SKIP"):
        return True
        
    # Проверка суффиксов
    for suffix in NON_TECHNICAL_SUFFIXES:
        if text_stripped.endswith(suffix):
            return True
    
    return False


def _clean_technical_prefixes(text: str) -> str:
    """Удаляет префиксы о техническом/нетехническом характере вопроса."""
    for prefix in TECHNICAL_PREFIXES:
        text = re.sub(prefix, '', text, flags=re.IGNORECASE)
    return text.strip()


def _format_links(text: str) -> str:
    """Форматирует ссылки в тексте для Telegram HTML."""
    import re
    
    # Исправляем искаженные ссылки (ttps:// -> https://)
    text = re.sub(r'\bttps://', 'https://', text)
    
    # Удаляем странные символы в конце ссылок (.[] и подобные)
    text = re.sub(r'(\bhttps?://[^\s\)\]]+?)\.?\[\]', r'\1', text)
    
    # Сначала найдем все индексы, которые имеют реальные ссылки
    # Паттерны для поиска ссылок с индексами
    linked_indices = set()
    
    # Паттерн 1: [индекс](URL)
    for match in re.finditer(r'\[(\d+)\]\(https?://[^\s\)]+\)', text):
        linked_indices.add(match.group(1))
    
    # Паттерн 2: [индекс] URL
    for match in re.finditer(r'\[(\d+)\]\s+https?://[^\s\[\]]+', text):
        linked_indices.add(match.group(1))
    
    # Паттерн 3: URL[индекс]
    for match in re.finditer(r'https?://[^\s\[\]]+\[(\d+)\]', text):
        linked_indices.add(match.group(1))
    
    logger.info(f"Найдены индексы со ссылками: {linked_indices}")
    
    # Теперь удаляем только индексы-сироты (без ссылок)
    def remove_orphan_index(match):
        index = match.group(1) if match.lastindex else match.group(0).strip('[]')
        if index and index not in linked_indices:
            logger.debug(f"Удаляем индекс-сироту: [{index}]")
            return ''
        return match.group(0)
    
    # Удаляем последовательности индексов типа [][2][3] только если это сироты
    text = re.sub(r'\.?\[\](\[\d+\])+', lambda m: '' if not any(idx in linked_indices for idx in re.findall(r'\d+', m.group(0))) else m.group(0), text)
    
    # Удаляем артефакты файлов источников (например: chat_export_2025_07_july.json+1)
    # Паттерн для имен файлов в любом месте текста, включая с точкой в начале
    text = re.sub(r'\.?[\w_\-]+\.(json|jsonl|txt|csv|xlsx|pdf|doc|docx)(\+\d+)?', '', text, flags=re.IGNORECASE)
    # Также удаляем если есть полный путь к файлу
    text = re.sub(r'[/\\]?[\w_\-/\\]+\.(json|jsonl|txt|csv|xlsx|pdf|doc|docx)(\+\d+)?', '', text, flags=re.IGNORECASE)
    
    # НЕ удаляем цифры после букв в формате "5,2x" или "5.2x"
    # НЕ удаляем индексы обычных ссылок - они будут обработаны позже
    
    # Сохраняем номера/текст ссылок на файлы перед их удалением
    file_reference_numbers = []
    
    # Паттерн для [любой текст](URL файла)
    file_link_pattern = r'\[([^\]]+)\]\((https?://[^\s\)]+)\)'
    
    def check_and_remove_file_link(match):
        url = match.group(2)
        url_lower = url.lower()
        is_file = any(url_lower.endswith(ext) for ext in FILE_EXTENSIONS)
        
        if is_file:
            # Сохраняем номер/текст ссылки для последующего удаления индексов
            link_text = match.group(1)
            if link_text.isdigit():
                file_reference_numbers.append(link_text)
            
            # Если это файл, удаляем всё совпадение
            return ''
        else:
            # Возвращаем ссылку в исходном виде для дальнейшей обработки
            return match.group(0)
    
    text = re.sub(file_link_pattern, check_and_remove_file_link, text)
    
    # Теперь удаляем ТОЛЬКО те индексы, которые ссылались на удаленные файлы
    # И только если они не имеют других ссылок
    if file_reference_numbers:
        # Фильтруем - удаляем только те, которые не имеют обычных ссылок
        orphan_file_indices = [num for num in file_reference_numbers if num not in linked_indices]
        if orphan_file_indices:
            logger.info(f"Удаляем индексы файлов-сирот: {orphan_file_indices}")
            for num in orphan_file_indices:
                # Удаляем [num] только если это индекс файла без ссылки
                text = re.sub(rf'\[{num}\]', '', text)
                # Удаляем отдельно стоящее число только если оно окружено пробелами
                text = re.sub(rf'(?<=\s){num}(?=[\s\.\,\;\:\!\?]|$)', '', text)
    
    # Очищаем лишние запятые и союзы после удаления ссылок
    text = re.sub(r',\s*,', ',', text)  # Удаляем двойные запятые
    text = re.sub(r':\s*,', ':', text)  # Удаляем запятые после двоеточия
    text = re.sub(r',\s*\.', '.', text)  # Удаляем запятые перед точкой
    text = re.sub(r',\s*и\s+,', ' и ', text)  # Удаляем запятые вокруг "и"
    text = re.sub(r'\s+и\s+и\s+', ' и ', text)  # Удаляем двойные "и"
    text = re.sub(r'^\s*,\s*', '', text)  # Удаляем запятые в начале
    text = re.sub(r',\s*$', '', text)  # Удаляем запятые в конце
    text = re.sub(r'^\s*и\s+', '', text)  # Удаляем "и" в начале
    text = re.sub(r'\s+и\s*$', '', text)  # Удаляем "и" в конце
    text = re.sub(r':\s*и\s*$', ':', text)  # Удаляем "и" после двоеточия в конце
    text = re.sub(r'\s+,\s*и\s+', ' и ', text)  # Удаляем запятую перед "и"
    
    # Теперь экранируем HTML символы
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    
    # Паттерн для поиска ссылок в формате [текст](URL) 
    # Изменен чтобы поддерживать не только числа, но и любой текст
    reference_pattern = r'\[([^\]]+)\]\((https?://[^\s\)]+)\)'
    
    # Заменяем ссылки на кликабельный формат для Telegram
    def replace_reference(match):
        link_text = match.group(1)
        url = match.group(2)
        
        # Все файлы уже удалены ранее, так что это обычная ссылка
        return f'<a href="{url}">[{link_text}]</a>'
    
    text = re.sub(reference_pattern, replace_reference, text)
    
    # Также паттерн для старого формата [номер] URL (на случай если остались)
    old_reference_pattern = r'\[(\d+)\]\s+(https?://[^\s\[\]]+)'
    
    def replace_old_reference(match):
        number = match.group(1)
        url = match.group(2)
        
        # Проверяем, является ли это ссылкой на файл
        url_lower = url.lower()
        is_file = any(url_lower.endswith(ext) for ext in FILE_EXTENSIONS)
        
        if is_file:
            # Удаляем ссылки на файлы
            return ''
        else:
            return f'<a href="{url}">{number}</a>'
    
    text = re.sub(old_reference_pattern, replace_old_reference, text)
    
    # Сначала обрабатываем URL с индексом в конце (например: https://example.com[2] или https://example.com.[][2])
    url_with_index_pattern = r'(https?://[^\s<>"{}|\\^`\[\]]+?)(?:\.?\[\])?(?:\s*)\[(\d+)\]'
    
    def replace_url_with_index(match):
        url = match.group(1)
        index = match.group(2)
        
        # Проверяем, является ли это ссылкой на файл
        url_lower = url.lower()
        is_file = any(url_lower.endswith(ext) for ext in FILE_EXTENSIONS)
        
        if is_file:
            # Удаляем ссылки на файлы и их индексы
            return ''
        else:
            # Превращаем в кликабельную ссылку с индексом
            return f'<a href="{url}">[{index}]</a>'
    
    text = re.sub(url_with_index_pattern, replace_url_with_index, text)
    
    # Затем обрабатываем обычные URL которые не в формате [номер]
    # но исключаем уже обработанные в тегах <a>
    url_pattern = r'(?<!href=")(?<!">)(https?://[^\s<>"{}|\\^`\[\]]+)(?!</a>)'
    
    def replace_plain_url(match):
        url = match.group(1)
        
        # Проверяем, является ли это ссылкой на файл
        url_lower = url.lower()
        is_file = any(url_lower.endswith(ext) for ext in FILE_EXTENSIONS)
        
        if is_file:
            # Удаляем ссылки на файлы
            return ''
        else:
            return f'<a href="{url}">{url}</a>'
    
    text = re.sub(url_pattern, replace_plain_url, text)
    
    # Очищаем лишние пробелы и разделители, которые могли остаться после удаления ссылок
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Удаляем оставшиеся висячие разделители после обработки ссылок
    text = re.sub(r'(?<=[<>])\s*,\s*', ' ', text)  # Удаляем запятые после тегов
    text = re.sub(r',\s*(?=[<>])', ' ', text)  # Удаляем запятые перед тегами
    text = re.sub(r'(?<=[<>])\s*и\s+', ' ', text)  # Удаляем "и" после тегов
    
    # Удаляем цифры-индексы (надстрочные ссылки на источники)
    # Более агрессивный подход - удаляем все цифры после букв, если это не часть слова
    # Исключения: v2.0, Web3, h264 и т.д.
    
    # Логирование для отладки
    import re
    
    # Сначала удаляем цифры сразу после удаления ссылок на файлы
    # Это поможет убрать индексы, которые ссылались на удаленные файлы
    
    # Паттерн 1: Цифры после букв/закрывающих скобок/кавычек
    superscript_matches = re.findall(r'(?<=[а-яА-Яa-zA-Z\)\]\}\»\"\'])(\d+)(?=[\s\.\,\;\:\!\?\-—–]|$)', text)
    if superscript_matches:
        logger.info(f"Найдены цифры-индексы для удаления: {superscript_matches}")
    
    # ЗАКОММЕНТИРОВАНО: Слишком агрессивное удаление цифр, портит "5,2x" и подобные значения
    # text = re.sub(r'(?<=[а-яА-Яa-zA-Z\)\]\}\»\"\'])(\d+)(?=[\s\.\,\;\:\!\?\-—–]|$)', '', text)
    
    # Паттерн 2: Цифры после точек в конце предложений
    text = re.sub(r'(?<=\.)(\d+)(?=\s|$)', '', text)
    
    # ЗАКОММЕНТИРОВАНО: Удаляет цифры из "5,2x"
    # text = re.sub(r'(?<=\,)(\d+)(?=[\s\.\,\;\:\!\?\-—–]|$)', '', text)
    
    # Паттерн 4: Отдельно стоящие цифры (которые могли остаться после удаления ссылок)
    # Только если цифра окружена пробелами с обеих сторон
    text = re.sub(r'(?<=\s)(\d+)(?=\s)', '', text)
    
    # Удаляем индексы-сироты в квадратных скобках (которые не являются частью тега <a>)
    def remove_orphan_brackets(match):
        index = match.group(1)
        if index not in linked_indices:
            logger.debug(f"Удаляем индекс-сироту в скобках: [{index}]")
            return ''
        return match.group(0)
    
    text = re.sub(r'\[(\d+)\](?!</a>)', remove_orphan_brackets, text)
    
    # Паттерн 6: Цифры после слов типа "файл", "документ", "источник"
    # Используем обычный паттерн вместо lookbehind с переменной длиной
    text = re.sub(r'(файл|документ|источник|файлы|документы|источники)\s*(\d+)', r'\1', text, flags=re.IGNORECASE)
    
    # ЗАКОММЕНТИРОВАНО: Удаляет цифры в конце строк, может портить данные
    # text = re.sub(r'(\d+)(?=\n|$)', '', text)
    
    # Финальная очистка пробелов
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Подсчитываем количество ссылок для логирования
    links_count = len(re.findall(r'<a href=', text))
    if links_count > 0:
        logger.info(f"Сделано кликабельными {links_count} ссылок")
    
    return text

def _format_code_languages(text: str) -> str:
    """Форматирует языки программирования в тексте."""
    if re.match(CODE_LANGUAGE_PATTERN, text, re.IGNORECASE):
        text = re.sub(CODE_LANGUAGE_PATTERN, r'\1\n\2', text, flags=re.IGNORECASE)
    return text


async def _make_api_request(payload: dict, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Выполняет запрос к API Perplexity."""
    if not config.PERPLEXITY_API_URL:
        raise RuntimeError("PERPLEXITY_API_URL не установлен в конфигурации. Проверьте файл .env")
    
    # Создаем более строгие настройки таймаутов
    timeout_config = httpx.Timeout(
        connect=5.0,  # Таймаут на подключение
        read=timeout,  # Таймаут на чтение данных
        write=5.0,  # Таймаут на запись
        pool=5.0  # Таймаут на получение соединения из пула
    )
    
    logger.info(f"Отправка запроса к {config.PERPLEXITY_API_URL} с таймаутом {timeout}с")
    logger.debug(f"Payload для API: {json.dumps(payload, ensure_ascii=False)[:500]}...")
    
    async with httpx.AsyncClient(timeout=timeout_config) as client:
        response = await client.post(config.PERPLEXITY_API_URL, json=payload)
        
        # Пробуем получить данные даже при ошибке
        try:
            data = response.json()
        except Exception as json_error:
            logger.error(f"Ошибка парсинга JSON: {json_error}")
            # Если это 429 ошибка, возвращаем специальные данные
            if response.status_code == 429:
                logger.warning("Получен 429 без валидного JSON - браузер занят")
                return {"error": "Browser is busy processing another request"}
            response.raise_for_status()
            raise
        
        # Если статус не 200, но есть данные - логируем
        if response.status_code != 200:
            logger.warning(f"Получен статус {response.status_code}, но пробуем обработать данные")
            logger.debug(f"Данные при статусе {response.status_code}: {json.dumps(data, ensure_ascii=False)[:200]}...")
            
            # Проверка на ошибку 429 - браузер занят
            if response.status_code == 429:
                logger.warning("Получен статус 429 - браузер занят")
                # НЕ выбрасываем исключение, пусть обработается через data
            
            # Проверка на ошибку 500 - сервер временно недоступен
            if response.status_code == 500:
                logger.error(f"Получен статус 500 - ошибка сервера")
                # Выбрасываем исключение для повторной попытки
                raise httpx.HTTPStatusError(
                    message=f"Server error: {response.status_code}",
                    request=response.request,
                    response=response
                )
            
            # Проверка на отсутствие расширения
            if response.status_code == 503 and isinstance(data, dict) and 'extension' in str(data.get('error', '')).lower():
                raise RuntimeError("Браузерное расширение не подключено. Откройте perplexity.ai в браузере.")
        
        # Возвращаем данные в любом случае - пусть обработчик решает что с ними делать
        # Даже при ошибке 400+ может быть полезный контент (например SKIP)
        
        return data


def _create_payload(messages: Union[str, List[Dict[str, str]], Dict[str, Any]]) -> dict:
    """Создает payload для API запроса."""
    # Если уже готовый payload
    if isinstance(messages, dict) and "messages" in messages:
        return messages
    
    # Если список сообщений
    if isinstance(messages, list):
        return {"messages": messages}
    
    # Если строка - пробуем парсить как JSON
    if isinstance(messages, str):
        try:
            parsed = json.loads(messages)
            if isinstance(parsed, dict) and "messages" in parsed:
                return parsed
            elif isinstance(parsed, list) and all("role" in m and "content" in m for m in parsed):
                return {"messages": parsed}
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Если обычный текст
        return {
            "messages": [
                {"role": "user", "content": messages}
            ]
        }
    
    raise ValueError("Некорректный формат входных данных")


async def ask_perplexity(user_input: str, context: Optional[List[Dict[str, Any]]] = None, images: Optional[List[str]] = None) -> str:
    """Отправляет запрос к Perplexity API для общих вопросов."""
    
    # Формируем полный текст с контекстом
    if context:
        context_text = "\n".join([f"{msg['user']}: {msg['text']}" for msg in context])
        full_input = f"Контекст чата:\n{context_text}\n\nВопрос: {user_input}"
    else:
        full_input = user_input
    
    try:
        # Создаем payload с поддержкой изображений
        if images:
            # Используем тот же формат что и в ask_perplexity_group - разные сообщения
            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": full_input  # Просто текст
                    },
                    {
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": "Изображения для анализа:"}
                        ]
                    }
                ]
            }
            
            # Добавляем изображения во второе сообщение
            for image_data in images:
                payload["messages"][1]["content"].append({
                    "type": "image_url",
                    "image_url": {"url": image_data}
                })
            
            timeout = IMAGE_TIMEOUT
        else:
            payload = _create_payload(full_input)
            timeout = EXTENDED_TIMEOUT
        
        data = await _make_api_request(payload, timeout=timeout)
        
        # Извлекаем текст ответа
        reply_text = _extract_reply_text(data)
        
        if not reply_text:
            reply_text = "Ответ пуст."
        elif "content" not in data:
            reply_text = ERROR_MESSAGES['invalid_response']
        else:
            # Форматирование ссылок для HTML (как в ask_perplexity_group)
            reply_text = _format_links(reply_text)
            
    except httpx.ReadTimeout:
        reply_text = ERROR_MESSAGES['timeout']
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP ошибка: {e.response.status_code}")
        reply_text = ERROR_MESSAGES['server_error'].format(status_code=e.response.status_code)
    except RuntimeError as e:
        logger.error(f"Ошибка конфигурации: {e}")
        reply_text = f"⚠️ Ошибка конфигурации: {e}"
    except Exception as e:
        logger.exception("Неожиданная ошибка при запросе к Perplexity:")
        reply_text = ERROR_MESSAGES['unknown_error']
        
    return reply_text


async def ask_perplexity_group(question: str, context: List[Dict[str, Any]], images: Optional[List[str]] = None, max_retries: int = 3, is_direct_mention: bool = False) -> Optional[str]:
    """Отправляет запрос к Perplexity API для технических вопросов в группах.
    
    Возвращает:
    - Текст ответа если получен нормальный ответ
    - "SKIP" если API вернул SKIP
    - None если произошла ошибка
    """
    import uuid
    call_id = str(uuid.uuid4())[:8]
    
    # Фидбек теперь только сохраняется, не используется для автоматического обучения
    
    # Формируем контекст
    context_text = "\n".join([f"{msg['user']}: {msg['text']}" for msg in context]) if context else ""
        
    logger.info(f"=== НАЧАЛО ОБРАБОТКИ ВОПРОСА [CALL {call_id}] ===")
    logger.info(f"[CALL {call_id}] Вопрос: {question[:100]}...")
    logger.info(f"[CALL {call_id}] Длина вопроса: {len(question.split())} слов")
    logger.info(f"[CALL {call_id}] Размер контекста: {len(context)} сообщений")
    logger.info(f"[CALL {call_id}] Контекст текст ({len(context_text)} символов): {context_text[:200]}...")
    logger.info(f"[CALL {call_id}] Изображения переданы: {len(images) if images else 0}")
    
    # Дополнительное логирование для отладки коротких вопросов
    if len(question.split()) <= 3:
        logger.info(f"КОРОТКИЙ ВОПРОС ОБНАРУЖЕН: '{question}'")
        if context_text:
            logger.info("Контекст присутствует - будет проанализирован для определения типа вопроса")
            # Логируем последнее сообщение контекста для анализа
            if context:
                last_msg = context[-1]
                logger.info(f"Последнее сообщение в контексте от {last_msg['user']}: {last_msg['text'][:100]}...")
        else:
            logger.info("Контекст отсутствует - вероятен SKIP")
    
    # Формируем промпт
    if context_text:
        # Ограничиваем размер контекста в промпте для оптимизации
        # Увеличиваем лимит до 1000 символов для лучшего понимания контекста
        context_for_prompt = context_text[:1000] + "..." if len(context_text) > 1000 else context_text
        
        # Если есть изображения, добавляем инструкцию об их анализе
        if images:
            prompt = f"""CONTEXT:
{context_for_prompt}

QUESTION: {question}

IMPORTANT: Analyze the provided image(s) and answer based on what you see.

⚠️ CRITICAL: Be EXTREMELY strict! In group chats, SKIP 90% of messages.
Only respond to clear, specific technical crypto questions.
When in ANY doubt - always choose SKIP.

Your response must be EXACTLY one of:
1. The single word: SKIP
2. A 2-3 sentence answer about DeFi/crypto ONLY

AUTOMATIC SKIP if ANY:
- Contains: админы, привет, что за, кто-нибудь, спасибо, понял, ясно, ок
- Contains: ты, вы, тебе, вам
- Less than 3 words
- General chat/greetings
- Reply to bot's message without new question
- Comments or reactions to previous answers
- Not a clear, specific technical question
Your response must be MAX 3 sentences, no more.
Answer crypto/DeFi questions about: protocols, tokens, bridges, swaps, liquidity, yield, staking, trading
Everything else = SKIP
When uncertain = SKIP
Default = SKIP"""
        else:
            prompt = f"""CONTEXT:
{context_for_prompt}

QUESTION: {question}

⚠️ CRITICAL: Be EXTREMELY strict! In group chats, SKIP 90% of messages.
Only respond to clear, specific technical crypto questions.
When in ANY doubt - always choose SKIP.

Your response must be EXACTLY one of:
1. The single word: SKIP
2. A 2-3 sentence answer about DeFi/crypto ONLY

AUTOMATIC SKIP if ANY:
- Contains: админы, привет, что за, кто-нибудь, спасибо, понял, ясно, ок
- Contains: ты, вы, тебе, вам
- Less than 3 words
- General chat/greetings
- Reply to bot's message without new question
- Comments or reactions to previous answers
- Not a clear, specific technical question
Your response must be MAX 3 sentences, no more.
Answer crypto/DeFi questions about: protocols, tokens, bridges, swaps, liquidity, yield, staking, trading
Everything else = SKIP
When uncertain = SKIP
Default = SKIP"""
    else:
        # Промпт для случая без контекста
        if images:
            prompt = f"""QUESTION: {question}

IMPORTANT: Analyze the provided image(s) and answer based on what you see.

⚠️ CRITICAL: Be EXTREMELY strict! Default to SKIP in 90% of cases.

ONLY answer about: crypto, DeFi, tokens, trading, bridges, swaps, liquidity
Everything else = SKIP
Your response must be MAX 3 sentences, no more.
Contains админы/привет/что за/спасибо/понял = SKIP
<3 words = SKIP
When uncertain = SKIP
Default = SKIP"""
        else:
            prompt = f"""QUESTION: {question}

⚠️ CRITICAL: Be EXTREMELY strict! Default to SKIP in 90% of cases.

ONLY answer about: crypto, DeFi, tokens, trading, bridges, swaps, liquidity
Everything else = SKIP
Your response must be MAX 3 sentences, no more.
Contains админы/привет/что за/спасибо/понял = SKIP
<3 words = SKIP
When uncertain = SKIP
Default = SKIP"""
    
    # Создаем сообщение с поддержкой изображений
    if images:
        # Логируем количество изображений
        logger.info(f"Обработка {len(images)} изображений")
        logger.info(f"Промпт для отправки: {prompt[:200]}..." if len(prompt) > 200 else f"Промпт для отправки: {prompt}")
        
        # Создаем одно сообщение со смешанным контентом (текст + изображения)
        content_blocks = [
            {"type": "text", "text": prompt}
        ]
        
        # Добавляем изображения в тот же массив content
        for idx, image_data in enumerate(images):
            logger.info(f"Добавление изображения {idx + 1}/{len(images)}, размер: {len(image_data)} символов")
            content_blocks.append({
                "type": "image_url",
                "image_url": {"url": image_data}
            })
        
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": content_blocks
                }
            ]
        }
        
        # Логируем структуру
        logger.info(f"Payload содержит 1 сообщение с {len(content_blocks)} блоками контента")
        logger.info(f"Блоки: 1 текст (промпт) + {len(images)} изображений")
        
        # Дополнительное логирование для отладки
        logger.info(f"[DEBUG] Текст промпта: {prompt[:200]}...")
        logger.info(f"[DEBUG] Количество изображений: {len(images)}")
        for i, img in enumerate(images):
            logger.info(f"[DEBUG] Изображение {i+1} начинается с: {img[:30]}...")
    else:
        payload = _create_payload(prompt)
        logger.info("Обработка без изображений")
    
    logger.info(f"Размер промпта: {len(prompt)} символов")
    logger.info(f"Размер payload: {len(str(payload))} символов")
    
    # Детальное логирование payload для отладки
    import json
    logger.info(f"[CALL {call_id}] ПОЛНЫЙ PAYLOAD:")
    
    # Создаем копию payload для логирования с обрезанными изображениями
    log_payload = json.loads(json.dumps(payload))
    if 'messages' in log_payload:
        for msg in log_payload['messages']:
            if isinstance(msg.get('content'), list):
                for content_item in msg['content']:
                    if content_item.get('type') == 'image_url' and 'image_url' in content_item:
                        # Обрезаем base64 данные для логирования
                        url = content_item['image_url'].get('url', '')
                        if url.startswith('data:image'):
                            content_item['image_url']['url'] = url[:50] + '...[BASE64_DATA_TRUNCATED]'
    
    logger.info(json.dumps(log_payload, ensure_ascii=False, indent=2))
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Отправляем запрос к API (попытка {attempt + 1}/{max_retries})...")
            logger.debug(f"Размер запроса: {len(str(payload))} символов")
            
            # Используем увеличенный таймаут для запросов с изображениями
            timeout = IMAGE_TIMEOUT if images else EXTENDED_TIMEOUT
            logger.info(f"Используем таймаут: {timeout} секунд")
            
            # Логируем перед отправкой
            if images:
                logger.info(f"[ВАЖНО] Отправляем запрос с {len(images)} изображениями")
                logger.info(f"[ВАЖНО] Вопрос: {question[:100]}...")
            
            data = await _make_api_request(payload, timeout=timeout)
            
            # Добавляем логирование для отладки
            logger.info(f"Получены данные от API: {json.dumps(data, ensure_ascii=False)[:500] if isinstance(data, dict) else str(data)[:500]}")
            
            # Проверяем на ошибку 429 - браузер занят
            if isinstance(data, dict) and 'error' in data and 'busy' in str(data.get('error', '')).lower():
                logger.warning(f"[CALL {call_id}] Браузер занят обработкой другого запроса - возвращаем BROWSER_BUSY")
                # Сразу возвращаем BROWSER_BUSY без повторных попыток
                return "BROWSER_BUSY"
            
            # Проверяем на ошибку "Response element not found" - элемент не найден на странице
            if isinstance(data, dict) and 'error' in data and 'element not found' in str(data.get('error', '')).lower():
                logger.warning(f"Элемент ответа не найден на странице - возможно страница еще загружается")
                # Возвращаем специальный код для повторной попытки
                return "ELEMENT_NOT_FOUND"
            
            # Проверяем на перенаправление в пространство
            if isinstance(data, dict) and 'error' in data and 'REDIRECTING_TO_SPACE' in str(data.get('error', '')):
                logger.warning(f"Происходит перенаправление обратно в пространство")
                # Возвращаем специальный код для повторной попытки
                return "REDIRECTING_TO_SPACE"
            
            # Проверяем на ошибку таймаута в данных
            if isinstance(data, dict) and 'error' in data and 'Request timeout' in str(data.get('error', '')):
                # При таймауте сервер может вернуть SKIP в поле content
                reply_text = _extract_reply_text(data)
                logger.info(f"Таймаут с текстом ответа: '{reply_text}'")
                
                if reply_text and reply_text.strip().upper() == "SKIP":
                    logger.info("Получен ответ SKIP (из таймаута)")
                    return "SKIP"
                else:
                    logger.error("Таймаут запроса от сервера без SKIP")
                    if attempt < max_retries - 1:
                        logger.warning(f"Повторная попытка после таймаута сервера...")
                        await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                        continue
                    return None
            
            reply_text = _extract_reply_text(data)
            
            # Ответ получен
            
            # Проверяем, пустой ли ответ
            if not reply_text:
                logger.error("Получен пустой ответ от API")
                logger.error("Empty response from API")
                return None
            
            # Проверка на NO_RESPONSE - нужна повторная попытка
            reply_text_upper = reply_text.strip().upper()
            if reply_text_upper == "NO_RESPONSE" or reply_text_upper.startswith("NO_RESPONSE"):
                logger.warning(f"Получен ответ NO_RESPONSE на попытке {attempt + 1}/{max_retries}: '{reply_text}'")
                if attempt < max_retries - 1:
                    logger.info("Повторяем запрос через 3 секунды...")
                    await asyncio.sleep(3.0)
                    continue
                else:
                    logger.error(f"NO_RESPONSE после всех попыток: '{reply_text}'")
                    return None
            
            # Проверка на SKIP (одно слово)
            if reply_text.strip().upper() == "SKIP":
                logger.info("Получен ответ SKIP")
                return "SKIP"
            
            # Очистка от технических префиксов
            reply_text = _clean_technical_prefixes(reply_text)
            
            # Форматирование кода
            reply_text = _format_code_languages(reply_text)
            
            # Форматирование ссылок для HTML
            logger.info(f"Текст ДО форматирования ссылок: {reply_text[:200]}...")
            reply_text = _format_links(reply_text)
            logger.info(f"Текст ПОСЛЕ форматирования ссылок: {reply_text[:200]}...")
            
            logger.info(f"Получен технический ответ длиной {len(reply_text)} символов")
            return reply_text
                
        except RuntimeError as e:
            logger.error(f"Ошибка конфигурации: {e}")
            return None  # Не пытаемся повторить при ошибке конфигурации
            
        # TimeoutError больше не выбрасывается из _make_api_request
        # except TimeoutError:
        #     logger.error(f"Таймаут запроса на попытке {attempt + 1}")
        #     if attempt < max_retries - 1:
        #         logger.warning(f"Повторная попытка после таймаута...")
        #         await asyncio.sleep(RETRY_DELAY * (attempt + 1))
        #         continue
        #     return None
            
        except httpx.ReadTimeout:
            logger.error(f"Время ожидания ответа от Perplexity истекло (попытка {attempt + 1})")
            if attempt < max_retries - 1:
                logger.warning(f"Повторная попытка после ReadTimeout...")
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                continue
            return None
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP ошибка: {e.response.status_code}")
            if e.response.status_code == 500 and attempt < max_retries - 1:
                logger.warning(f"Ошибка сервера 500, повторная попытка через {RETRY_DELAY * (attempt + 1)} сек...")
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                continue
            return None
            
        except Exception as e:
            logger.exception("Неожиданная ошибка при запросе к Perplexity:")
            return None
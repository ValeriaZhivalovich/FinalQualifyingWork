import httpx
import logging
import os
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Импортируем для уведомлений (опционально)
try:
    from ..utils.service_notify import get_service_notifier
except ImportError:
    get_service_notifier = None

OPENAI_API_KEY: str = os.getenv("OPENAI_KEY", "").strip()
OPENAI_API_URL: str = "https://api.openai.com/v1/chat/completions"

async def _check_question_with_model(text: str, model: str) -> Optional[bool]:
    """
    Проверяет, является ли текст вопросом, используя указанную модель
    """
    prompt = f"""Определи, является ли следующий текст вопросом. Ответь только "да" или "нет".
Текст: {text}"""
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                OPENAI_API_URL,
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "Ты помощник, который определяет, является ли текст вопросом. Отвечай только 'да' или 'нет'."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 10
                }
            )
            response.raise_for_status()
            
            data = response.json()
            answer = data["choices"][0]["message"]["content"].strip().lower()
            
            result = answer == "да" or answer == "yes"
            logger.info(f"Модель {model} определила текст как {'вопрос' if result else 'не вопрос'}: '{text[:50]}...'")
            return result
            
    except Exception as e:
        logger.error(f"Ошибка при обращении к {model}: {e}")
        return None


async def is_question(text: Optional[str], double_check: bool = True) -> bool:
    """
    Определяет, является ли текст вопросом.
    Если double_check=True, используется двойная проверка с gpt-4.1-nano и gpt-4.1-mini
    """
    if not text or not OPENAI_API_KEY:
        return False
    
    # Очищаем текст
    text = text.strip()
    if len(text) < 5:  # Слишком короткий текст
        return False
    
    # Первая проверка с gpt-4.1-nano
    nano_result = await _check_question_with_model(text, "gpt-4.1-nano")
    
    if nano_result is None:
        # При ошибке используем простую эвристику
        return any(q in text.lower() for q in ["?", "как", "что", "почему", "когда", "где", "кто", "зачем", "можно", "нужно"])
    
    if not nano_result or not double_check:
        # Если nano сказал "нет" или не нужна двойная проверка
        return nano_result
    
    # Вторая проверка с gpt-4.1-mini только если nano сказал "да"
    mini_result = await _check_question_with_model(text, "gpt-4.1-mini")
    
    if mini_result is None:
        # При ошибке доверяем результату nano
        return nano_result
    
    # Возвращаем True только если обе модели согласны
    final_result = nano_result and mini_result
    
    if nano_result != mini_result:
        logger.warning(f"Модели не согласны для текста: '{text[:50]}...' (nano: {nano_result}, mini: {mini_result})")
    
    # Отправляем уведомление о результатах двойной проверки (если доступно)
    if get_service_notifier:
        service_notifier = get_service_notifier()
        if service_notifier and double_check:
            try:
                import asyncio
                asyncio.create_task(service_notifier.notify_double_check_result(text, nano_result, mini_result))
            except Exception as e:
                logger.debug(f"Не удалось отправить уведомление о двойной проверке: {e}")
    
    return final_result
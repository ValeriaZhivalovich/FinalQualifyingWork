"""Модуль для хранения ожидающих подтверждения ответов"""
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import asyncio
import logging

logger = logging.getLogger(__name__)

class PendingResponse:
    """Класс для хранения информации об ожидающем ответе"""
    def __init__(self, 
                 chat_id: int,
                 message_id: int,
                 user_name: str,
                 question: str,
                 response: str,
                 service_message_id: Optional[int] = None):
        self.chat_id = chat_id
        self.message_id = message_id
        self.user_name = user_name
        self.question = question
        self.response = response
        self.service_message_id = service_message_id
        self.created_at = datetime.now()
        
    def is_expired(self, ttl_minutes: int = 10) -> bool:
        """Проверяет, истек ли срок ожидания подтверждения"""
        return datetime.now() - self.created_at > timedelta(minutes=ttl_minutes)

class PendingResponseManager:
    """Менеджер для управления ожидающими ответами"""
    def __init__(self):
        self._responses: Dict[str, PendingResponse] = {}
        self._lock = asyncio.Lock()
        
    async def add(self, key: str, response: PendingResponse) -> None:
        """Добавляет ответ в очередь ожидания"""
        async with self._lock:
            self._responses[key] = response
            logger.info(f"Added pending response: {key}")
            
    async def get(self, key: str) -> Optional[PendingResponse]:
        """Получает ответ из очереди"""
        async with self._lock:
            return self._responses.get(key)
            
    async def remove(self, key: str) -> Optional[PendingResponse]:
        """Удаляет и возвращает ответ из очереди"""
        async with self._lock:
            response = self._responses.pop(key, None)
            if response:
                logger.info(f"Removed pending response: {key}")
            return response
            
    async def cleanup_expired(self, ttl_minutes: int = 10) -> int:
        """Удаляет истекшие ответы"""
        async with self._lock:
            expired_keys = [
                key for key, response in self._responses.items()
                if response.is_expired(ttl_minutes)
            ]
            
            for key in expired_keys:
                del self._responses[key]
                
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired responses")
                
            return len(expired_keys)
            
    async def get_all(self) -> Dict[str, PendingResponse]:
        """Возвращает все ожидающие ответы"""
        async with self._lock:
            return self._responses.copy()

# Глобальный экземпляр менеджера
pending_manager = PendingResponseManager()
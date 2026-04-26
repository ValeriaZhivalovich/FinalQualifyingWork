"""
Обработчики команд для сервисного чата
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
import logging

from ..config import config
from ..utils.response_mode import response_mode_manager

logger = logging.getLogger(__name__)

router = Router()

@router.message(Command("auto"))
async def handle_auto_command(message: Message):
    """Включает автоматический режим (без подтверждения)"""
    # Проверяем, что команда отправлена в сервисном чате
    if message.chat.id != config.SERVICE_CHAT_ID:
        logger.warning(f"Попытка использовать /auto вне сервисного чата от {message.from_user.full_name}")
        return
    
    # Включаем автоматический режим
    response_mode_manager.set_auto()
    
    # Отправляем подтверждение
    await message.reply(
        "🚀 <b>Автоматический режим включен!</b>\n\n"
        "Теперь все ответы будут отправляться в чаты сразу, без подтверждения.\n"
        "Для возврата к режиму с подтверждением используйте /manual",
        parse_mode="HTML"
    )
    
    logger.info(f"Пользователь {message.from_user.full_name} включил автоматический режим")

@router.message(Command("manual"))
async def handle_manual_command(message: Message):
    """Включает режим с подтверждением"""
    # Проверяем, что команда отправлена в сервисном чате
    if message.chat.id != config.SERVICE_CHAT_ID:
        logger.warning(f"Попытка использовать /manual вне сервисного чата от {message.from_user.full_name}")
        return
    
    # Включаем режим с подтверждением
    response_mode_manager.set_manual()
    
    # Отправляем подтверждение
    await message.reply(
        "🔒 <b>Режим с подтверждением включен!</b>\n\n"
        "Теперь все ответы будут требовать подтверждения перед отправкой.\n"
        "Для переключения на автоматический режим используйте /auto",
        parse_mode="HTML"
    )
    
    logger.info(f"Пользователь {message.from_user.full_name} включил режим с подтверждением")

@router.message(Command("mode"))
async def handle_mode_command(message: Message):
    """Показывает текущий режим работы"""
    # Проверяем, что команда отправлена в сервисном чате
    if message.chat.id != config.SERVICE_CHAT_ID:
        logger.warning(f"Попытка использовать /mode вне сервисного чата от {message.from_user.full_name}")
        return
    
    # Получаем текущий режим
    mode_description = response_mode_manager.get_mode_description()
    
    # Отправляем информацию о текущем режиме
    await message.reply(
        f"<b>Текущий режим работы:</b>\n\n"
        f"{mode_description}\n\n"
        f"Доступные команды:\n"
        f"/auto - включить автоматический режим\n"
        f"/manual - включить режим с подтверждением\n"
        f"/mode - показать текущий режим",
        parse_mode="HTML"
    )
    
    logger.info(f"Пользователь {message.from_user.full_name} запросил информацию о режиме")
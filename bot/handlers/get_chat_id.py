from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

router = Router()

@router.message(Command("chatid"))
async def get_chat_id(message: Message):
    """Отправляет ID текущего чата"""
    chat_id = message.chat.id
    chat_type = message.chat.type
    chat_title = message.chat.title or "Личный чат"
    
    response = f"📍 <b>Информация о чате:</b>\n\n"
    response += f"ID чата: <code>{chat_id}</code>\n"
    response += f"Тип: {chat_type}\n"
    response += f"Название: {chat_title}"
    
    await message.reply(response, parse_mode="HTML")
"""Обработчики callback кнопок"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest
import logging

from ..utils.pending_responses import pending_manager
from ..config import config
from .groups import chat_contexts

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data.startswith("approve_"))
async def approve_response(callback: CallbackQuery):
    """Обработчик подтверждения ответа"""
    try:
        # Извлекаем ключ из callback data
        key = callback.data.replace("approve_", "")
        
        # Получаем ожидающий ответ
        pending = await pending_manager.get(key)
        if not pending:
            await callback.answer("❌ Ответ не найден или уже обработан", show_alert=True)
            return
            
        # Импортируем функцию разбивки сообщений
        from .groups import split_message
        
        # Разбиваем длинное сообщение на части
        message_parts = await split_message(pending.response, max_length=4000)
        
        # Отправляем ответ в целевой чат
        try:
            for i, part in enumerate(message_parts):
                # Добавляем индикатор части для многочастных сообщений
                if len(message_parts) > 1:
                    part_indicator = f"\n\n📄 Часть {i+1}/{len(message_parts)}"
                    if len(part) + len(part_indicator) < 4096:
                        part = part + part_indicator
                
                # Отправляем часть (reply только к первой части)
                if i == 0:
                    await callback.bot.send_message(
                        chat_id=pending.chat_id,
                        text=part,
                        reply_to_message_id=pending.message_id,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                else:
                    await callback.bot.send_message(
                        chat_id=pending.chat_id,
                        text=part,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                
                # Небольшая задержка между частями
                if i < len(message_parts) - 1:
                    import asyncio
                    await asyncio.sleep(0.5)
            
            logger.info(f"Sent approved response to chat {pending.chat_id} ({len(message_parts)} parts)")
            
            # Удаляем из очереди
            await pending_manager.remove(key)
            
            # Очищаем контекст чата после успешной отправки ответа
            if pending.chat_id in chat_contexts:
                chat_contexts[pending.chat_id].clear()
                logger.info(f"Контекст чата {pending.chat_id} очищен после модерации")
            
            # Обновляем сообщение в сервисном чате
            await callback.message.edit_text(
                f"✅ <b>ОТПРАВЛЕНО</b>\n\n"
                f"Чат: {pending.chat_id}\n"
                f"Пользователь: {pending.user_name}\n"
                f"Вопрос: {pending.question}\n\n"
                f"Ответ: {pending.response}",
                parse_mode="HTML"
            )
            
            await callback.answer("✅ Ответ отправлен!")
            
        except Exception as e:
            # Если сообщение для ответа не найдено, отправляем без reply
            if "message to be replied not found" in str(e).lower() or "message to reply not found" in str(e).lower():
                try:
                    # Отправляем все части без reply
                    for i, part in enumerate(message_parts):
                        # Добавляем индикатор части для многочастных сообщений
                        if len(message_parts) > 1:
                            part_indicator = f"\n\n📄 Часть {i+1}/{len(message_parts)}"
                            if len(part) + len(part_indicator) < 4096:
                                part = part + part_indicator
                        
                        await callback.bot.send_message(
                            chat_id=pending.chat_id,
                            text=part,
                            parse_mode="HTML",
                            disable_web_page_preview=True
                        )
                        
                        # Небольшая задержка между частями
                        if i < len(message_parts) - 1:
                            import asyncio
                            await asyncio.sleep(0.5)
                    
                    logger.info(f"Sent approved response to chat {pending.chat_id} without reply ({len(message_parts)} parts)")
                    
                    # Удаляем из очереди
                    await pending_manager.remove(key)
                    
                    # Очищаем контекст чата после успешной отправки ответа
                    if pending.chat_id in chat_contexts:
                        chat_contexts[pending.chat_id].clear()
                        logger.info(f"Контекст чата {pending.chat_id} очищен после модерации (без reply)")
                    
                    # Обновляем сообщение в сервисном чате
                    await callback.message.edit_text(
                        f"✅ <b>ОТПРАВЛЕНО</b> (без ответа на сообщение)\n\n"
                        f"Чат: {pending.chat_id}\n"
                        f"Пользователь: {pending.user_name}\n"
                        f"Вопрос: {pending.question}\n\n"
                        f"Ответ: {pending.response}",
                        parse_mode="HTML"
                    )
                    
                    await callback.answer("✅ Ответ отправлен (исходное сообщение удалено)")
                except Exception as e2:
                    logger.error(f"Failed to send approved response even without reply: {e2}")
                    await callback.answer(f"❌ Ошибка отправки: {str(e2)}", show_alert=True)
            else:
                logger.error(f"Failed to send approved response: {e}")
                await callback.answer(f"❌ Ошибка отправки: {str(e)}", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in approve_response: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.callback_query(F.data.startswith("reject_"))
async def reject_response(callback: CallbackQuery):
    """Обработчик отклонения ответа"""
    try:
        # Извлекаем ключ из callback data
        key = callback.data.replace("reject_", "")
        
        # Получаем и удаляем ожидающий ответ
        pending = await pending_manager.remove(key)
        if not pending:
            await callback.answer("❌ Ответ не найден или уже обработан", show_alert=True)
            return
            
        # Обновляем сообщение в сервисном чате
        await callback.message.edit_text(
            f"❌ <b>ОТКЛОНЕНО</b>\n\n"
            f"Чат: {pending.chat_id}\n"
            f"Пользователь: {pending.user_name}\n"
            f"Вопрос: {pending.question}\n\n"
            f"Ответ: {pending.response}",
            parse_mode="HTML"
        )
        
        logger.info(f"Rejected response for chat {pending.chat_id}")
        await callback.answer("❌ Ответ отклонен")
        
    except Exception as e:
        logger.error(f"Error in reject_response: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)
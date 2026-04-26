from aiogram import Router, types
from aiogram.filters import Command
import logging
from ..utils.feedback import feedback_manager
from ..config import config

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("feedback_stats"))
async def feedback_stats_command(message: types.Message):
    """Показывает статистику фидбека (только в сервисном чате)"""
    try:
        # Проверяем, что команда из сервисного чата
        if message.chat.id != config.SERVICE_CHAT_ID:
            return
        
        stats = feedback_manager.get_stats()
        
        response = f"""📊 <b>Статистика фидбека</b>

📈 <b>Общая статистика:</b>
• Всего оценок: {stats['total_feedback']}
• 🔥 Положительных: {stats['likes']}
• 🤨 Отрицательных: {stats['dislikes']}
• Процент положительных: {stats['like_rate']*100:.1f}%

📝 <b>Последние данные:</b>
• Сохранено положительных: {stats['recent_positive']}
• Сохранено отрицательных: {stats['recent_negative']}

📁 Фидбек автоматически экспортируется в:
<code>data/feedback_export.txt</code>"""
        
        if stats['like_rate'] < 0.5 and stats['total_feedback'] > 10:
            response += "\n\n⚠️ Низкий процент положительных оценок. Проверьте экспорт для анализа."
        elif stats['like_rate'] > 0.8:
            response += "\n\n✅ Отличный процент положительных оценок!"
        
        await message.reply(response, parse_mode="HTML")
        logger.info(f"Статистика фидбека отправлена в сервисный чат")
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики фидбека: {e}", exc_info=True)
        await message.reply("❌ Произошла ошибка при получении статистики")

@router.message(Command("feedback_export"))
async def feedback_export_command(message: types.Message):
    """Отправляет файл с экспортом фидбека"""
    try:
        # Проверяем, что команда из сервисного чата
        if message.chat.id != config.SERVICE_CHAT_ID:
            return
        
        # Принудительно экспортируем свежие данные
        feedback_manager.export_to_text()
        
        # Отправляем файл
        import os
        if os.path.exists(feedback_manager.export_file):
            with open(feedback_manager.export_file, 'rb') as f:
                await message.reply_document(
                    document=types.BufferedInputFile(
                        f.read(),
                        filename="feedback_export.txt"
                    ),
                    caption="📁 Экспорт фидбека для ручного анализа"
                )
            logger.info("Файл фидбека отправлен в сервисный чат")
        else:
            await message.reply("📭 Файл экспорта пока пуст")
            
    except Exception as e:
        logger.error(f"Ошибка при отправке экспорта: {e}", exc_info=True)
        await message.reply("❌ Произошла ошибка при отправке файла")

@router.message(Command("feedback_clear"))
async def feedback_clear_command(message: types.Message):
    """Очищает данные фидбека"""
    try:
        # Проверяем, что команда из сервисного чата
        if message.chat.id != config.SERVICE_CHAT_ID:
            return
        
        # Сбрасываем данные
        feedback_manager.feedback_data = {
            'positive': feedback_manager.feedback_data['positive'].__class__(maxlen=feedback_manager.max_items),
            'negative': feedback_manager.feedback_data['negative'].__class__(maxlen=feedback_manager.max_items),
            'stats': {
                'total_likes': 0,
                'total_dislikes': 0
            }
        }
        feedback_manager._save_feedback()
        
        await message.reply("🗑 Данные фидбека успешно очищены")
        logger.info(f"Данные фидбека очищены из сервисного чата")
        
    except Exception as e:
        logger.error(f"Ошибка при очистке фидбека: {e}", exc_info=True)
        await message.reply("❌ Произошла ошибка при очистке данных")
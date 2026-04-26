from aiogram import Router, types, F
import logging
import base64
import io
from PIL import Image
from typing import Optional

from ..utils.perplexity import ask_perplexity

router = Router()
logger = logging.getLogger(__name__)

async def download_and_compress_photo(message: types.Message, photo: types.PhotoSize, max_size: int = 1024) -> Optional[str]:
    """Загружает и сжимает фото"""
    try:
        file = await message.bot.get_file(photo.file_id)
        file_bytes = io.BytesIO()
        await message.bot.download_file(file.file_path, file_bytes)
        
        file_bytes.seek(0)
        img = Image.open(file_bytes)
        
        if img.mode in ('RGBA', 'LA', 'P'):
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = rgb_img
        
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            logger.info(f"Изображение сжато до {img.width}x{img.height}")
        
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)
        
        base64_image = base64.b64encode(output.read()).decode('utf-8')
        size_kb = len(base64_image) / 1024
        logger.info(f"Размер изображения: {size_kb:.1f} KB")
        
        return f"data:image/jpeg;base64,{base64_image}"
    except Exception as e:
        logger.error(f"Ошибка при обработке изображения: {e}")
        return None

# Обработчик текстовых сообщений в личке
@router.message(F.text & F.chat.type.in_(["private"]))
async def handle_user_message(message: types.Message) -> None:
    user_input: str = message.text
    logger.info(f"Личное сообщение от пользователя {message.from_user.id}: {user_input}")
    
    thinking_msg = await message.answer("🤔 Ищу ответ...")
    
    try:
        reply_text = await ask_perplexity(user_input)
        await thinking_msg.delete()
        logger.info(f"Отправляем ответ в личный чат {message.chat.id}")
        await message.answer(reply_text, parse_mode=None)
    except Exception as e:
        logger.exception("Ошибка при обработке запроса:")
        await thinking_msg.edit_text(f"⚠️ Произошла ошибка: {str(e)}")

# Обработчик изображений в личке
@router.message(F.photo & F.chat.type.in_(["private"]))
async def handle_user_photo(message: types.Message) -> None:
    logger.info(f"Получено изображение от пользователя {message.from_user.id}")
    
    thinking_msg = await message.answer("🖼️ Анализирую изображение...")
    
    try:
        # Берем самое большое изображение
        largest_photo = message.photo[-1]
        image_base64 = await download_and_compress_photo(message, largest_photo)
        
        if not image_base64:
            await thinking_msg.edit_text("⚠️ Не удалось загрузить изображение")
            return
        
        # Текст вопроса
        question = message.caption or "Проанализируй это изображение"
        
        # Используем ask_perplexity с поддержкой изображений для личных сообщений
        reply_text = await ask_perplexity(
            user_input=question,
            context=None,
            images=[image_base64]
        )
        
        await thinking_msg.delete()
        
        if reply_text and reply_text != "SKIP":
            logger.info(f"Отправляем ответ на изображение в личный чат {message.chat.id}")
            try:
                await message.answer(reply_text, parse_mode="HTML", disable_web_page_preview=True)
            except:
                await message.answer(reply_text, parse_mode=None)
        else:
            logger.info(f"Не удалось проанализировать изображение в личном чате {message.chat.id}")
            await message.answer("Не могу проанализировать это изображение")
            
    except Exception as e:
        logger.exception("Ошибка при обработке изображения:")
        await thinking_msg.edit_text(f"⚠️ Произошла ошибка: {str(e)}")
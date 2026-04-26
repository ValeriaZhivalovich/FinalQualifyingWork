from aiogram import Router, types
from aiogram.filters import Command

router = Router()

@router.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    help_text = """
📋 **Доступные команды:**

/start - Начать работу с ботом
/help - Показать это сообщение

💡 **Как использовать:**
• В личных сообщениях - просто отправьте вопрос о DeFi
• В группах - бот отвечает на вопросы о криптовалютах и DeFi
• Можно прикреплять изображения (скриншоты, графики)

📊 **Примеры вопросов:**
• Как работает Uniswap V3?
• Что такое impermanent loss?
• Как безопасно использовать DeFi протоколы?
• Объясни разницу между APY и APR

⚠️ **Важно:** Бот предоставляет только техническую информацию, не финансовые советы!
"""
    await message.answer(help_text, parse_mode=None)
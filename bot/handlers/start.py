from aiogram import Router, types
from aiogram.filters import CommandStart

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    await message.answer(
        f"🚀 Привет, {message.from_user.full_name}!\n\n"
        f"Я DeFi эксперт-бот, помогу с вопросами о:\n"
        f"• DeFi протоколах (Uniswap, Aave, Curve)\n"
        f"• Криптовалютах и токенах\n"
        f"• Yield farming и стейкинге\n"
        f"• Смарт-контрактах и безопасности\n\n"
        f"Просто задай вопрос в чате! Используй /help для подробностей.",
        parse_mode=None
    )
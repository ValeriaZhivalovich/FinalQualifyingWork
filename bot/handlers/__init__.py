from aiogram import Router

from . import start
from . import help
from . import user
from . import groups
from . import get_chat_id
from . import callbacks
from . import service_commands
from . import feedback_commands

def setup_routers() -> Router:
    router = Router()
    
    # Include all routers
    router.include_router(start.router)
    router.include_router(help.router)
    router.include_router(get_chat_id.router)
    router.include_router(feedback_commands.router)  # Команды фидбека для сервисного чата
    router.include_router(service_commands.router)  # Команды сервисного чата
    router.include_router(callbacks.router)  # Обработчики callback кнопок
    router.include_router(groups.router)  # Обработка групп идет перед user
    router.include_router(user.router)
    
    return router
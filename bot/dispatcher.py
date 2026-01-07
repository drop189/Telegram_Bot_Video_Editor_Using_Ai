from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from settings.config import TOKEN

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

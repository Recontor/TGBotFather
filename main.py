import asyncio
import logging
import sys
import os
from aiohttp import web  # Додано для веб-сервера
from aiogram import F
from aiogram.filters import Command
from aiogram.types import ErrorEvent

from bot import bot, dp
from database import init_db
from middlewares import LoggingMiddleware, AntiSpamMiddleware
import handlers
from handlers import BotStates

# --- 1. Налаштування логування ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# --- 2. Веб-сервер для "обману" Render (Port Binding) ---
async def handle(request):
    """Проста відповідь для Render Health Check"""
    return web.Response(text="Бот працює!")

async def start_web_server():
    """Запуск сервера на порту, який надає Render"""
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Отримуємо порт з оточення Render, за замовчуванням 10000
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Веб-сервер запущено на порту {port}")

# --- 3. Глобальний захист від падіння ---
@dp.errors()
async def error_handler(event: ErrorEvent):
    logger.error(f"Критична помилка: {event.exception}")
    try:
        if event.update.message:
            await event.update.message.answer(
                "⚠️ Вибачте, сталася внутрішня помилка. "
                "Спробуйте пізніше або зверніться до підтримки"
            )
    except Exception as e:
        logger.error(f"Не вдалося надіслати повідомлення про помилку: {e}")
    return True

async def main():
    # 4. Ініціалізація бази даних
    init_db()

    # 5. ЗАПУСК ВЕБ-СЕРВЕРА
    # Це дозволить Render бачити відкритий порт і тримати сервіс "Live"
    await start_web_server()

    # 6. Підключення Middlewares
    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(AntiSpamMiddleware(limit=1.2))

    # --- 7. Реєстрація хендлерів ---

    # Системні команди
    dp.message.register(handlers.start_handler, Command("start"))
    dp.message.register(handlers.login_handler, Command("login"))
    dp.message.register(handlers.logout_handler, Command("logout"))
    dp.message.register(handlers.get_rate_handler, Command("getrate"))
    dp.message.register(handlers.set_rate_handler, Command("setrate"))

    # Обробка головного меню
    dp.message.register(
        handlers.menu_handler, 
        F.text.in_(["💱 Курс валют", "ℹ️ Допомога", "📞 Контакти", "Тех. підтримка"])
    )

    # Вибір валюти
    dp.callback_query.register(
        handlers.currency_callback, 
        F.data.startswith("currency_")
    )

    # Підтвердження розрахунку або скасування
    dp.callback_query.register(
        handlers.calc_choice_handler, 
        F.data.in_(["confirm_calc", "cancel_calc"])
    )

    # Вибір типу операції (Купівля/Продаж)
    dp.callback_query.register(
        handlers.operation_type_handler, 
        F.data.startswith("op_")
    )

    # Введення суми
    dp.message.register(
        handlers.convert_handler, 
        BotStates.waiting_for_amount
    )

    # Адмін-панель
    dp.callback_query.register(
        handlers.admin_callback, 
        F.data.startswith("admin_")
    )

    # --- 8. Запуск бота ---
    try:
        logger.info("Бот запущений з підтримкою подвійних курсів та веб-сервером!")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"Помилка при запуску: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот зупинений")
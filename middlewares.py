import time
import logging
from aiogram import BaseMiddleware, types

class AntiSpamMiddleware(BaseMiddleware):
    def __init__(self, limit=1.0):
        self.last_message_time = {}
        self.limit = limit  # Затримка в секундах

    async def __call__(self, handler, event: types.Message, data):
        if not event.from_user:
            return await handler(event, data)
            
        user_id = event.from_user.id
        now = time.time()

        if user_id in self.last_message_time:
            delta = now - self.last_message_time[user_id]
            if delta < self.limit:
                # Якщо спамить дуже жорстко — просто ігноруємо (drop request)
                if delta < 0.5:
                    return
                await event.answer("⏳ Занадто часто! Почекайте секунду.")
                return

        self.last_message_time[user_id] = now
        return await handler(event, data)

class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: types.Message, data):
        if event.text:
            logging.info(f"User {event.from_user.id} sent: {event.text[:50]}") # Логуємо лише перші 50 символів
        return await handler(event, data)
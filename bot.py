import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from google import genai
from aiohttp import web

# ================= КОНФИГУРАЦИЯ =================
TELEGRAM_BOT_TOKEN = "8787596046:AAF3gkZGU9AhVnofbnNwK3YWpmd0w0D4R0s"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

SYSTEM_PROMPT = """
Ты — профессиональный TikTok Growth Agent для аккаунта @eny_engel4 (репатриация в Израиль, жизнь в Хайфе, поиск работы, адаптация).
Твоя задача — анализировать контент и создавать 10 вовлекающих комментариев по категориям:
A) Заставляют автора ответить
Б) Вызывают спор или обсуждение
В) Поддержка
Г) Личный опыт
Д) Вопросы к аудитории

Для каждого комментария ставь оценки (0-10) на шанс ответа, лайков и дискуссии. Выбирай ТОП-3 и объясняй выбор.
Пиши как живой человек, учитывай контекст Израиля и русскоязычных эмигрантов.
"""

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

logging.basicConfig(level=logging.INFO)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "👋 **Привет! Я твой TikTok Growth Agent.**\n\n"
        "Отправь мне описание ролика, тему или текст озвучки, "
        "и я сделаю разбор и подберу ТОП комментариев для продвижения!"
    )

@dp.message(F.text)
async def process_text(message: types.Message):
    wait_msg = await message.answer("🔄 Анализирую и генерирую комментарии...")
    try:
        api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)
        if not api_key:
            await wait_msg.edit_text("❌ Ошибка: GEMINI_API_KEY не задан в настройках Render (Environment).")
            return

        ai_client = genai.Client(api_key=api_key)
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Проанализируй контент и дай рекомендации по комментариям:\n\n{message.text}",
            config={"system_instruction": SYSTEM_PROMPT}
        )
        await wait_msg.delete()
        await message.answer(response.text, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Ошибка при обработке: {e}")
        await wait_msg.edit_text(f"❌ Произошла ошибка при вызове Gemini API:\n`{e}`")

async def handle_ping(request):
    return web.Response(text="Bot is alive!")

async def main():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

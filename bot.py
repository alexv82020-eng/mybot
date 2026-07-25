import os
import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from google import genai
from aiohttp import web

# ================= КОНФИГУРАЦИЯ =================
TELEGRAM_BOT_TOKEN = "8787596046:AAF3gkZGU9AhVnofbnNwK3YWpmd0w0D4R0s"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")

CHAT_ID_FOR_NOTIFICATIONS = None
LAST_VIDEO_ID = None

TIKTOK_USERNAME = "eny_engel4"

SYSTEM_PROMPT = """
Ты — профессиональный TikTok Growth Agent для аккаунта @eny_engel4 (репатриация в Израиль, жизнь в Хайфе, поиск работы, адаптация).
Твоя задача — проанализировать суть нового видео и создать 10 вовлекающих комментариев по категориям:
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

async def check_tiktok_and_generate():
    global LAST_VIDEO_ID, CHAT_ID_FOR_NOTIFICATIONS
    
    # Если бот ещё не знает кому слать или нет ключа RapidAPI
    if not CHAT_ID_FOR_NOTIFICATIONS or not RAPIDAPI_KEY or not GEMINI_API_KEY:
        return

    url = f"https://tiktok-api23.p.rapidapi.com/user/posts?unique_id={TIKTOK_USERNAME}&count=1"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "tiktok-api23.p.rapidapi.com"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    videos = data.get("itemList", [])
                    if videos:
                        latest_video = videos[0]
                        video_id = latest_video.get("id")
                        video_desc = latest_video.get("desc", "Без описания")
                        video_url = f"https://www.tiktok.com/@{TIKTOK_USERNAME}/video/{video_id}"

                        # При первом запуске просто запоминаем последнее видео
                        if LAST_VIDEO_ID is None:
                            LAST_VIDEO_ID = video_id
                        # Если появилось НОВОЕ видео:
                        elif LAST_VIDEO_ID != video_id:
                            LAST_VIDEO_ID = video_id
                            
                            # Бот передает информацию Gemini
                            ai_client = genai.Client(api_key=GEMINI_API_KEY)
                            response = ai_client.models.generate_content(
                                model="gemini-2.5-flash",
                                contents=f"Вышло новое видео на канале! Вот его описание/текст: {video_desc}",
                                config={"system_instruction": SYSTEM_PROMPT}
                            )

                            # Бот отправляет итоговый разбор пользователю
                            msg_text = (
                                f"🔔 **Вышло новое видео на канале @{TIKTOK_USERNAME}!**\n\n"
                                f"📝 **Суть/Описание:** {video_desc}\n"
                                f"🔗 **Ссылка:** {video_url}\n\n"
                                f"-----------------------------------\n"
                                f"💡 **Готовые комментарии от Gemini:**\n\n{response.text}"
                            )

                            await bot.send_message(CHAT_ID_FOR_NOTIFICATIONS, msg_text, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Ошибка проверки TikTok: {e}")

async def tiktok_tracker_loop():
    while True:
        await check_tiktok_and_generate()
        await asyncio.sleep(1800)  # Проверять каждые 30 минут

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    global CHAT_ID_FOR_NOTIFICATIONS
    CHAT_ID_FOR_NOTIFICATIONS = message.chat.id
    await message.answer(
        "👋 **Автоматическое отслеживание включено!**\n\n"
        f"Я слежу за каналом `@ {TIKTOK_USERNAME}`. Как только выйдет новое видео, "
        "я сам передам его Gemini, сформирую готовые комментарии и пришлю их тебе сюда."
    )

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

    # Запуск фоновой проверки TikTok
    asyncio.create_task(tiktok_tracker_loop())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

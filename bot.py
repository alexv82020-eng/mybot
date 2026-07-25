import os
import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
from google import genai
from aiohttp import web

# ================= КОНФИГУРАЦИЯ =================
TELEGRAM_BOT_TOKEN = "8787596046:AAF3gkZGU9AhVnofbnNwK3YWpmd0w0D4R0s"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")

CHAT_ID_FOR_NOTIFICATIONS = None
PROCESSED_COMMENTS = set()

TIKTOK_USERNAME = "eny_engel4"

SYSTEM_PROMPT = """
Ты — SMM Growth Agent и эксперт по алгоритмам TikTok для аккаунта @eny_engel4 (репатриация, жизнь в Израиле, Хайфа, адаптация).
Тебе передают комментарии под видео.
Твоя задача:
1. Оценить важность комментария для продвижения ролика (от 0 до 10).
2. Сформулировать идеальный ответ от имени автора, который спровоцирует пользователя или других зрителей продолжить дискуссию в ветке.
3. Коротко объяснить стратегию этого ответа.
"""

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

logging.basicConfig(level=logging.INFO)

async def set_bot_commands():
    """Установка синей кнопки 'Меню' с командами в Telegram"""
    commands = [
        BotCommand(command="start", description="🚀 Запустить авто-мониторинг"),
        BotCommand(command="check", description="🔍 Проверить новые комментарии прямо сейчас")
    ]
    await bot.set_my_commands(commands)

async def run_tiktok_check():
    """Основная функция проверки видео и комментариев"""
    global CHAT_ID_FOR_NOTIFICATIONS, PROCESSED_COMMENTS
    
    if not CHAT_ID_FOR_NOTIFICATIONS:
        return "⚠️ Сначала отправь боту команду /start, чтобы зафиксировать чат."
    
    if not RAPIDAPI_KEY or not GEMINI_API_KEY:
        return "⚠️ Не заданы API ключи в настройках Render."

    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "tiktok-api23.p.rapidapi.com"
    }

    found_new = False

    try:
        async with aiohttp.ClientSession() as session:
            # 1. Получаем последние 3 видео аккаунта
            posts_url = f"https://tiktok-api23.p.rapidapi.com/user/posts?unique_id={TIKTOK_USERNAME}&count=3"
            async with session.get(posts_url, headers=headers) as resp:
                if resp.status != 200:
                    return f"❌ Ошибка обращения к TikTok API (Статус: {resp.status})"
                posts_data = await resp.json()
                videos = posts_data.get("itemList", [])

            # 2. Проверяем комментарии к каждому видео
            for vid in videos:
                video_id = vid.get("id")
                video_desc = vid.get("desc", "Видео")
                video_url = f"https://www.tiktok.com/@{TIKTOK_USERNAME}/video/{video_id}"
                
                comments_url = f"https://tiktok-api23.p.rapidapi.com/post/comments?video_id={video_id}&count=10"
                async with session.get(comments_url, headers=headers) as c_resp:
                    if c_resp.status != 200:
                        continue
                    c_data = await c_resp.json()
                    comments = c_data.get("comments", [])

                    for c in comments:
                        c_id = c.get("cid")
                        c_text = c.get("text")
                        user_nickname = c.get("user", {}).get("nickname", "Зритель")

                        if c_id not in PROCESSED_COMMENTS:
                            PROCESSED_COMMENTS.add(c_id)
                            found_new = True

                            # Анализ через Gemini
                            ai_client = genai.Client(api_key=GEMINI_API_KEY)
                            prompt_text = (
                                f"Видео: '{video_desc}'\n"
                                f"Комментарий от {user_nickname}: '{c_text}'\n\n"
                                f"Дай оценку и лучший вариант ответа для раскрутки этого видео."
                            )
                            response = ai_client.models.generate_content(
                                model="gemini-2.5-flash",
                                contents=prompt_text,
                                config={"system_instruction": SYSTEM_PROMPT}
                            )

                            msg = (
                                f"📩 **Новая активность под видео!**\n\n"
                                f"🎬 **Ролик:** {video_desc}\n"
                                f"🔗 **Ссылка:** {video_url}\n"
                                f"👤 **{user_nickname}:** `{c_text}`\n\n"
                                f"-----------------------------------\n"
                                f"💡 **Стратегия ответа от Gemini:**\n\n{response.text}"
                            )
                            await bot.send_message(CHAT_ID_FOR_NOTIFICATIONS, msg, parse_mode="Markdown")

            if not found_new:
                return "ℹ️ Новых комментариев под последними видео пока нет."
            return "✅ Ручная проверка завершена, новые комментарии отправлены выше!"

    except Exception as e:
        logging.error(f"Ошибка проверки: {e}")
        return f"❌ Произошла ошибка: {e}"

async def tracker_loop():
    """Фоновый таймер (проверка раз в 12 часов)"""
    while True:
        await run_tiktok_check()
        await asyncio.sleep(43200) # 12 часов

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    global CHAT_ID_FOR_NOTIFICATIONS
    CHAT_ID_FOR_NOTIFICATIONS = message.chat.id
    await message.answer(
        "👋 **Мониторинг запущен!**\n\n"
        "🤖 **Штатный режим:** Я автоматически проверяю видео 2 раза в день.\n"
        "⚡ **Ручной запуск:** Используй меню или команду /check в любой момент, чтобы проверить комментарии прямо сейчас."
    )

@dp.message(Command("check"))
async def manual_check_handler(message: types.Message):
    await message.answer("🔍 Запускаю ручную проверку TikTok...")
    result_text = await run_tiktok_check()
    await message.answer(result_text)

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

    # Регистрируем меню команд в Telegram
    await set_bot_commands()

    asyncio.create_task(tracker_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

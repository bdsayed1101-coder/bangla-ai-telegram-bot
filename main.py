import os
import asyncio
import base64
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from openai import AsyncOpenAI

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "আসসালামু আলাইকুম! 🤖\n"
        "আমি তোমার AI Assistant।\n\n"
        "বাংলা বা ইংরেজিতে প্রশ্ন করো। "
        "ছবিও পাঠাতে পারো!"
    )


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    question = message.text.strip()

    if not question:
        return

    history = context.user_data.get("history", [])

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful AI assistant. "
                "Reply in the language the user uses. "
                "If the user speaks Bangla, reply in Bangla."
            ),
        },
        *history[-10:],
        {"role": "user", "content": question},
    ]

    try:
        await context.bot.send_chat_action(
            chat_id=message.chat_id, action="typing"
        )

        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
        )

        answer = response.choices[0].message.content
        answer = answer or "দুঃখিত, উত্তর তৈরি করা যায়নি।"

        history.extend([
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ])

        context.user_data["history"] = history[-10:]

        for i in range(0, len(answer), 4000):
            await message.reply_text(answer[i:i + 4000])

    except Exception:
        logging.exception("AI request failed")
        await message.reply_text(
            "দুঃখিত, সমস্যা হয়েছে। কিছুক্ষণ পর আবার চেষ্টা করো।"
        )


async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    try:
        await context.bot.send_chat_action(
            chat_id=message.chat_id, action="typing"
        )

        telegram_photo = message.photo[-1]
        file = await context.bot.get_file(telegram_photo.file_id)

        image_bytes = await file.download_as_bytearray()
        encoded = base64.b64encode(image_bytes).decode("utf-8")

        question = message.caption or "Describe this image in Bangla."

        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    "data:image/jpeg;base64," + encoded
                                )
                            },
                        },
                    ],
                }
            ],
        )

        answer = response.choices[0].message.content
        await message.reply_text(
            answer or "ছবিটি বিশ্লেষণ করা যায়নি।"
        )

    except Exception:
        logging.exception("Image analysis failed")
        await message.reply_text(
            "ছবিটি বিশ্লেষণ করা যায়নি। পরে আবার চেষ্টা করো।"
        )


async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, chat)
    )
    app.add_handler(MessageHandler(filters.PHOTO, photo))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

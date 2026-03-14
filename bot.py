import requests
import asyncio
import time
import re
from collections import defaultdict
from langdetect import detect

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters
)

# =====================
# 配置
# =====================

TELEGRAM_TOKEN = "8387363153:AAFKBHEPDJor5vsTGMM1rrshZU2VYdxw11c"

MERGE_TIME = 3
REQUEST_INTERVAL = 1

# =====================
# 缓存
# =====================

translate_cache = {}
last_request_time = {}

message_buffer = defaultdict(list)
buffer_tasks = {}

# =====================
# 工具函数
# =====================

def is_valid_text(text):

    if not text:
        return False

    text = text.strip()

    if len(text) < 2:
        return False

    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "]+",
        flags=re.UNICODE
    )

    if emoji_pattern.fullmatch(text):
        return False

    return True


def rate_limit(user_id):

    now = time.time()

    if user_id in last_request_time:
        if now - last_request_time[user_id] < REQUEST_INTERVAL:
            return False

    last_request_time[user_id] = now

    return True


def detect_language(text):

    try:
        lang = detect(text)
    except:
        return None

    if lang.startswith("zh"):
        return "zh"

    if lang == "vi":
        return "vi"

    return None


# =====================
# 翻译
# =====================

def translate(text, target):

    if text in translate_cache:
        return translate_cache[text]

    url = "https://libretranslate.de/translate"

    payload = {
        "q": text,
        "source": "auto",
        "target": target,
        "format": "text"
    }

    r = requests.post(url, json=payload)

    translated = r.json()["translatedText"]

    translate_cache[text] = translated

    return translated


# =====================
# 合并翻译
# =====================

async def process_buffer(chat_id):

    await asyncio.sleep(MERGE_TIME)

    messages = message_buffer[chat_id]

    if not messages:
        return

    combined_text = "\n".join([m["text"] for m in messages])

    lang = detect_language(combined_text)

    if lang == "zh":
        translated = translate(combined_text, "vi")

    elif lang == "vi":
        translated = translate(combined_text, "zh")

    else:
        message_buffer[chat_id] = []
        return

    first_message = messages[0]["message"]

    await first_message.reply_text(
        translated,
        reply_to_message_id=first_message.message_id
    )

    message_buffer[chat_id] = []


# =====================
# 主逻辑
# =====================

async def translate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message = update.message

    if not message:
        return

    if message.photo or message.video or message.sticker or message.document:
        return

    text = message.text

    if not is_valid_text(text):
        return

    user_id = message.from_user.id
    chat_id = message.chat_id

    if not rate_limit(user_id):
        return

    lang = detect_language(text)

    if lang not in ["zh", "vi"]:
        return

    message_buffer[chat_id].append({
        "text": text,
        "message": message
    })

    if chat_id not in buffer_tasks:

        buffer_tasks[chat_id] = asyncio.create_task(
            process_buffer(chat_id)
        )

        def done_callback(task):
            buffer_tasks.pop(chat_id, None)

        buffer_tasks[chat_id].add_done_callback(done_callback)


# =====================
# 启动
# =====================

def main():

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), translate_handler)
    )

    print("Free AI Translate Bot Running...")

    app.run_polling()


if __name__ == "__main__":
    main()

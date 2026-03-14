import asyncio
import time
import re
import requests
from collections import defaultdict

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters
)

from langdetect import detect

# ======================
# 配置
# ======================

TELEGRAM_TOKEN = "8387363153:AAFKBHEPDJor5vsTGMM1rrshZU2VYdxw11c"

# 翻译缓存
translate_cache = {}

# 消息缓冲（用于合并翻译）
message_buffer = defaultdict(list)

# 缓冲时间（秒）
BUFFER_TIME = 2


# ======================
# 判断是否纯表情
# ======================

def is_emoji_only(text):
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "]+",
        flags=re.UNICODE,
    )

    cleaned = emoji_pattern.sub("", text)
    return cleaned.strip() == ""


# ======================
# 翻译函数
# ======================

def translate(text, target):

    # 缓存命中
    cache_key = text + "_" + target
    if cache_key in translate_cache:
        return translate_cache[cache_key]

    # 主翻译 API
    try:
        url = "https://translate.argosopentech.com/translate"

        payload = {
            "q": text,
            "source": "auto",
            "target": target,
            "format": "text"
        }

        r = requests.post(url, data=payload, timeout=8)

        if r.status_code == 200:
            data = r.json()

            if "translatedText" in data:
                result = data["translatedText"]
                translate_cache[cache_key] = result
                return result

    except:
        pass

    # 备用 API
    try:
        url = "https://libretranslate.de/translate"

        payload = {
            "q": text,
            "source": "auto",
            "target": target,
            "format": "text"
        }

        r = requests.post(url, data=payload, timeout=8)

        if r.status_code == 200:
            data = r.json()

            if "translatedText" in data:
                result = data["translatedText"]
                translate_cache[cache_key] = result
                return result

    except:
        pass

    return text


# ======================
# 消息处理
# ======================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    msg = update.message

    if not msg.text:
        return

    text = msg.text.strip()

    if is_emoji_only(text):
        return

    chat_id = msg.chat_id

    message_buffer[chat_id].append((msg, text))


# ======================
# 消息缓冲处理
# ======================

async def process_buffer(app):

    while True:

        await asyncio.sleep(BUFFER_TIME)

        for chat_id in list(message_buffer.keys()):

            if not message_buffer[chat_id]:
                continue

            items = message_buffer[chat_id]
            message_buffer[chat_id] = []

            texts = []
            msgs = []

            for msg, text in items:
                texts.append(text)
                msgs.append(msg)

            combined_text = "\n".join(texts)

            try:
                lang = detect(combined_text)
            except:
                continue

            # 中文 -> 越南语
            if lang.startswith("zh"):
                translated = translate(combined_text, "vi")

            # 越南语 -> 中文
            elif lang == "vi":
                translated = translate(combined_text, "zh")

            else:
                continue

            # 拆分翻译
            results = translated.split("\n")

            for i, msg in enumerate(msgs):

                if i >= len(results):
                    continue

                try:
                    await msg.reply_text(
                        results[i],
                        reply_to_message_id=msg.message_id
                    )
                except:
                    pass


# ======================
# 主函数
# ======================

async def main():

    print("Free AI Translate Bot Running...")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    asyncio.create_task(process_buffer(app))

    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())

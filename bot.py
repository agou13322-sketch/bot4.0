import asyncio
import re
import requests
from collections import defaultdict
from langdetect import detect

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# =====================
# 配置
# =====================

TELEGRAM_TOKEN = "8387363153:AAFKBHEPDJor5vsTGMM1rrshZU2VYdxw11c"

BUFFER_TIME = 2

translate_cache = {}

message_buffer = defaultdict(list)


# =====================
# 判断是否表情
# =====================

def is_emoji_only(text):

    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "]+",
        flags=re.UNICODE
    )

    cleaned = emoji_pattern.sub("", text)

    return cleaned.strip() == ""


# =====================
# API1 Argos
# =====================

def translate_argos(text, target):

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
                return data["translatedText"]

    except:
        pass

    return None


# =====================
# API2 Libre
# =====================

def translate_libre(text, target):

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
                return data["translatedText"]

    except:
        pass

    return None


# =====================
# API3 Google
# =====================

def translate_google(text, target):

    try:

        url = "https://translate.googleapis.com/translate_a/single"

        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": target,
            "dt": "t",
            "q": text
        }

        r = requests.get(url, params=params, timeout=8)

        data = r.json()

        return data[0][0][0]

    except:
        pass

    return text


# =====================
# 三层翻译
# =====================

def translate(text, target):

    cache_key = text + "_" + target

    if cache_key in translate_cache:
        return translate_cache[cache_key]

    result = translate_argos(text, target)

    if not result:
        result = translate_libre(text, target)

    if not result:
        result = translate_google(text, target)

    translate_cache[cache_key] = result

    return result


# =====================
# 消息处理
# =====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    msg = update.message

    if not msg.text:
        return

    text = msg.text.strip()

    if is_emoji_only(text):
        return

    chat_id = msg.chat_id

    message_buffer[chat_id].append((msg, text))


# =====================
# 合并翻译
# =====================

async def process_buffer():

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

            combined = "\n".join(texts)

            try:
                lang = detect(combined)
            except:
                continue

            if lang.startswith("zh"):

                translated = translate(combined, "vi")

            elif lang == "vi":

                translated = translate(combined, "zh")

            else:
                continue

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


# =====================
# 主程序
# =====================

def main():

    print("Ultimate Translate Bot Running...")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    loop = asyncio.get_event_loop()

    loop.create_task(process_buffer())

    app.run_polling()


if __name__ == "__main__":
    main()

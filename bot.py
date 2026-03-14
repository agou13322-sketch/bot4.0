import asyncio
import time
import re
from collections import defaultdict

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters
)

from langdetect import detect
from openai import OpenAI


# ========================
# 配置
# ========================

TELEGRAM_TOKEN = "8387363153:AAFKBHEPDJor5vsTGMM1rrshZU2VYdxw11c"
OPENAI_API_KEY = "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"

client = OpenAI(api_key=OPENAI_API_KEY)

MERGE_TIME = 3
REQUEST_INTERVAL = 1


# ========================
# 全局状态
# ========================

bot_enabled = True

user_lang_cache = {}
translate_cache = {}

last_request_time = {}

message_buffer = defaultdict(list)
buffer_tasks = {}


# ========================
# 工具函数
# ========================

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
        flags=re.UNICODE,
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


def detect_language(user_id, text):

    if user_id in user_lang_cache:
        return user_lang_cache[user_id]

    try:
        lang = detect(text)
    except:
        return None

    if lang.startswith("zh"):
        lang = "zh"
    elif lang == "vi":
        lang = "vi"
    else:
        return None

    user_lang_cache[user_id] = lang

    return lang


async def ai_translate(text):

    if text in translate_cache:
        return translate_cache[text]

    prompt = f"""
你是专业翻译助手。

规则：
1. 中文翻译成越南语
2. 越南语翻译成中文
3. 保持自然表达
4. 只输出翻译结果

文本：
{text}
"""

    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    result = response.choices[0].message.content.strip()

    translate_cache[text] = result

    return result


# ========================
# 合并翻译
# ========================

async def process_buffer(chat_id):

    await asyncio.sleep(MERGE_TIME)

    messages = message_buffer[chat_id]

    if not messages:
        return

    combined_text = "\n".join([m["text"] for m in messages])

    try:
        translated = await ai_translate(combined_text)
    except Exception as e:
        print(e)
        return

    first_message = messages[0]["message"]

    await first_message.reply_text(
        translated,
        reply_to_message_id=first_message.message_id
    )

    message_buffer[chat_id] = []


# ========================
# 主翻译逻辑
# ========================

async def translate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global bot_enabled

    if not bot_enabled:
        return

    message = update.message

    if not message:
        return

    if message.photo or message.sticker or message.video or message.document:
        return

    text = message.text

    if not is_valid_text(text):
        return

    user_id = message.from_user.id
    chat_id = message.chat_id

    if not rate_limit(user_id):
        return

    lang = detect_language(user_id, text)

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


# ========================
# 管理命令
# ========================

async def bot_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_enabled
    bot_enabled = True
    await update.message.reply_text("翻译机器人已开启")


async def bot_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_enabled
    bot_enabled = False
    await update.message.reply_text("翻译机器人已关闭")


async def bot_status(update: Update, context: ContextTypes.DEFAULT_TYPE):

    status = "开启" if bot_enabled else "关闭"

    await update.message.reply_text(f"机器人状态：{status}")


# ========================
# 启动
# ========================

def main():

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("on", bot_on))
    app.add_handler(CommandHandler("off", bot_off))
    app.add_handler(CommandHandler("status", bot_status))

    app.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), translate_handler)
    )

    print("Ultimate AI Translate Bot Running...")

    app.run_polling()


if __name__ == "__main__":
    main()

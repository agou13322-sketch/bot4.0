import asyncio
import time
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
import openai

TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
OPENAI_API_KEY = "YOUR_OPENAI_KEY"

openai.api_key = OPENAI_API_KEY

bot_enabled = True

# 用户语言缓存
user_lang_cache = {}

# 防刷
last_request_time = {}
REQUEST_INTERVAL = 1.5

# 消息合并缓存
message_buffer = defaultdict(list)
buffer_tasks = {}

MERGE_TIME = 3  # 秒


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


def rate_limit(user_id):

    now = time.time()

    if user_id in last_request_time:
        if now - last_request_time[user_id] < REQUEST_INTERVAL:
            return False

    last_request_time[user_id] = now
    return True


def ai_translate(text):

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

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response['choices'][0]['message']['content'].strip()


async def process_buffer(chat_id, context):

    await asyncio.sleep(MERGE_TIME)

    messages = message_buffer[chat_id]

    if not messages:
        return

    combined_text = "\n".join([m["text"] for m in messages])

    try:
        translated = ai_translate(combined_text)
    except Exception as e:
        print(e)
        return

    first_message = messages[0]["message"]

    await first_message.reply_text(
        translated,
        reply_to_message_id=first_message.message_id
    )

    message_buffer[chat_id] = []


async def translate(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global bot_enabled

    if not bot_enabled:
        return

    if not update.message:
        return

    text = update.message.text
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    if not text:
        return

    if text.startswith("/"):
        return

    if not rate_limit(user_id):
        return

    lang = detect_language(user_id, text)

    if lang not in ["zh", "vi"]:
        return

    message_buffer[chat_id].append({
        "text": text,
        "message": update.message
    })

    if chat_id not in buffer_tasks:

        buffer_tasks[chat_id] = asyncio.create_task(
            process_buffer(chat_id, context)
        )

        def done_callback(task):
            buffer_tasks.pop(chat_id, None)

        buffer_tasks[chat_id].add_done_callback(done_callback)


# 管理命令
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

    await update.message.reply_text(f"机器人状态: {status}")


def main():

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("on", bot_on))
    app.add_handler(CommandHandler("off", bot_off))
    app.add_handler(CommandHandler("status", bot_status))

    app.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), translate)
    )

    print("Smart Translation Bot Running...")

    app.run_polling()


if __name__ == "__main__":
    main()
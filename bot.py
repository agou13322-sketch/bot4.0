import time
import re

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from langdetect import detect
import baidu_translate_api as translate

TELEGRAM_TOKEN = ""

bot_enabled = True

# 防刷限制
last_request_time = {}
REQUEST_INTERVAL = 1.2

# 用户语言缓存
user_lang_cache = {}

# 翻译缓存（提高速度）
translate_cache = {}


def is_valid_text(text):
    if not text:
        return False

    # 忽略只有表情或符号的消息
    text = text.strip()

    if len(text) < 2:
        return False

    # 如果只有表情符号
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
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


def translate_text(text, lang):

    # 翻译缓存
    if text in translate_cache:
        return translate_cache[text]

    if lang == "zh":
        result = translate.translate(text, to="vie")
        translated = result["trans_result"]["dst"]
        label = "🇻🇳 越南语"

    elif lang == "vi":
        result = translate.translate(text, to="zh")
        translated = result["trans_result"]["dst"]
        label = "🇨🇳 中文"

    else:
        return None, None

    translate_cache[text] = (translated, label)

    return translated, label


async def translate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global bot_enabled

    if not bot_enabled:
        return

    message = update.message

    if not message:
        return

    # 忽略图片 sticker 文件
    if message.photo or message.sticker or message.document or message.video:
        return

    text = message.text

    if not is_valid_text(text):
        return

    user_id = message.from_user.id

    if not rate_limit(user_id):
        return

    lang = detect_language(user_id, text)

    if lang not in ["zh", "vi"]:
        return

    try:
        translated, label = translate_text(text, lang)
    except Exception as e:
        print(e)
        return

    if not translated:
        return

    await message.reply_text(
        f"{label}\n{translated}",
        reply_to_message_id=message.message_id
    )


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


def main():

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("on", bot_on))
    app.add_handler(CommandHandler("off", bot_off))
    app.add_handler(CommandHandler("status", bot_status))

    app.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), translate_handler)
    )

    print("Fast Telegram Translate Bot Running...")

    app.run_polling()


if __name__ == "__main__":
    main()

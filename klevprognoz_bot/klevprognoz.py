import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

# === Переменные окружения ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# === Логирование ===
logging.basicConfig(level=logging.INFO)

# === Состояния ===
CHOOSING_REGION = 0

# === Данные ===
REGIONS = {"Минская область": "Minsk"}

# === Команды ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logging.info(f"Получен /start от user_id={update.effective_user.id}")
    keyboard = [[region] for region in REGIONS]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("🏞 Выберите область:", reply_markup=markup)
    return CHOOSING_REGION

async def choose_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    region = update.message.text
    if region not in REGIONS:
        await update.message.reply_text("❗ Неверный выбор. Повторите.")
        return CHOOSING_REGION
    await update.message.reply_text(f"✅ Вы выбрали: {region}", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# === Запуск ===

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_region)]
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(conv_handler)
    logging.info("🚀 Бот запущен. Ожидаю команды...")
    application.run_polling()

if __name__ == "__main__":
    main()

import time
import threading
import requests
from datetime import datetime, timedelta
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Настройки
TELEGRAM_TOKEN = '8090061122:AAHi3IUbmNQZC_YScG5QJgQH09pFBdWTYDA'        # <-- сюда вставь свой токен
TELEGRAM_CHAT_ID = '224639402'    # <-- сюда вставь свой chat ID
CHECK_INTERVAL = 60  # Проверка каждые 60 секунд

BASE_URL = "https://pub2.aibolit.md/api/v2/public/booking/glazkov-minsk/doctors/lx3peyfc284141fc8/timeslots"
BOOKING_SITE_URL = "https://fibonacci.center"

bot = Bot(token=TELEGRAM_TOKEN)

def build_url():
    today = datetime.now().date()
    end_date = today + timedelta(days=60)
    return f"{BASE_URL}?dateStart={today}&dateEnd={end_date}"

def check_available_slots():
    url = build_url()
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        available_slots = []

        for day in data:
            date = day.get('date')
            slots = day.get('slots', [])
            if slots:
                available_slots.append((date, [slot['time'] for slot in slots]))

        return available_slots

    except Exception as e:
        print(f"[{datetime.now()}] Ошибка запроса: {e}")
        return []

def send_message_with_slots(slots):
    try:
        message = "<b>🔥 Найдены доступные слоты к Якубовской!</b>\n\n"
        found_multiple = False

        for date, times in slots:
            times_list = ', '.join(times)
            if len(times) >= 2:
                found_multiple = True
                message += f"<b>{date}: {times_list} 🔥🔥🔥</b>\n"
            else:
                message += f"{date}: {times_list}\n"

        if found_multiple:
            message += "\n⚡ Отличная возможность взять сразу два слота подряд!\n"
        else:
            message += "\n⚡ Свободные окна! Успей записаться!\n"

        booking_button = InlineKeyboardButton(
            text="🔵 Записаться на сайте",
            url=BOOKING_SITE_URL
        )
        keyboard = InlineKeyboardMarkup([[booking_button]])

        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            parse_mode='HTML',
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

        save_last_slot_time()  # Сохраняем время последнего найденного слота

    except Exception as e:
        print(f"Ошибка отправки сообщения: {e}")

def save_last_slot_time():
    now = datetime.now()
    with open("last_slot.txt", "w") as f:
        f.write(str(now))

def log_slots(slots):
    with open("slots_log.txt", "a") as f:
        now = datetime.now()
        f.write(f"\n[{now}] Найдены слоты:\n")
        for date, times in slots:
            times_list = ', '.join(times)
            f.write(f"{date}: {times_list}\n")

def slot_monitor():
    while True:
        slots = check_available_slots()
        if slots:
            log_slots(slots)
            send_message_with_slots(slots)
            print(f"[{datetime.now()}] ➡️ Слоты найдены и отправлены!")
        else:
            print(f"[{datetime.now()}] Нет доступных слотов...")
        time.sleep(CHECK_INTERVAL)

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    slots = check_available_slots()
    if slots:
        message = "<b>🔥 Прямо сейчас доступны слоты к Якубовской!</b>\n\n"
        for date, times in slots:
            times_list = ', '.join(times)
            message += f"{date}: {times_list}\n"
        message += "\n⚡ Успей записаться прямо сейчас!"
    else:
        message = "К сожалению, свободных слотов у Якубовской пока нет. Но Димин скрипт за ними охотится! 🔥"

    booking_button = InlineKeyboardButton(
        text="🔵 Перейти на сайт",
        url=BOOKING_SITE_URL
    )
    keyboard = InlineKeyboardMarkup([[booking_button]])

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        parse_mode='HTML',
        reply_markup=keyboard,
        disable_web_page_preview=True
    )

# Обработчик команды /lastslot
async def last_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open("last_slot.txt", "r") as f:
            last_time = f.read().strip()
        message = f"🕰 Последний раз свободные слоты были найдены:\n<b>{last_time}</b>"
    except FileNotFoundError:
        message = "❓ Пока ещё не было найдено ни одного свободного окна."

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        parse_mode='HTML'
    )

if __name__ == "__main__":
    # Запускаем слот-монитор в отдельном потоке
    threading.Thread(target=slot_monitor, daemon=True).start()

    # Запускаем Telegram-бота отдельно
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('lastslot', last_slot))
    application.run_polling()
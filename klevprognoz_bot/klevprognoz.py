from datetime import datetime, timedelta
import logging
import requests
import ephem
import random
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters
)

# === Твои токены ===
TELEGRAM_TOKEN = '7297237331:AAEBR05LkndfAl-uJoiUmimctS6AZ7UxSwM'
OPENWEATHER_API_KEY = '355f0d0d5a864bdc9cb964863445f16c'

# === Состояния ===
CHOOSING_WATERBODY, CHOOSING_FISH, CHOOSING_DATE = range(3)

# === Логирование ===
logging.basicConfig(level=logging.INFO)

# === Базы данных ===
WATERBODIES = {
    "Озеро Нарочь": "Naroch",
    "Озеро Мястро": "Naroch",
    "Озеро Свирь": "Svir",
    "Вилейское водохранилище": "Vileyka",
    "Заславское водохранилище": "Zaslawye",
    "Крупское водохранилище": "Krupki",
    "Несвижские пруды": "Nyasvizh",
    "Лошанское водохранилище": "Uzda",
    "Река Березина": "Berezino",
    "Река Свислочь": "Minsk",
    "Река Птичь": "Pukhavichy",
    "Река Случь": "Slutsk",
    "Река Сож": "Gomel"
}

FISH_PROFILES = [
    {
        "name": "Карп",
        "active_temp_range": (18, 26),
        "pressure_preference": "стабильное высокое (>755 мм рт.ст.)",
        "best_weather": "Тёплая безветренная погода",
        "best_baits": ["кукуруза", "бойлы", "картофель"],
        "best_time_of_day": "утро и вечер",
        "fishing_methods": ["донка", "фидер", "поплавочная удочка"]
    },
    {
        "name": "Щука",
        "active_temp_range": (8, 18),
        "pressure_preference": "падающее давление",
        "best_weather": "Пасмурная погода, лёгкий ветер",
        "best_baits": ["живец", "воблер", "джиг-приманки"],
        "best_time_of_day": "утро и вечер",
        "fishing_methods": ["спиннинг", "живцовая снасть"]
    }
]

FISHING_TIPS = [
    "🌿 Используйте маскировку при ловле в прозрачной воде.",
    "💨 При сильном ветре ловите на подветренной стороне водоема.",
    "🎯 Лучшие уловы — на заре и закате.",
    "☀️ В жару ловите утром или вечером, в тени деревьев.",
    "🧤 В холодное время используйте медленные приманки.",
    "🌧 После дождя рыба особенно активна на червя.",
    "🔥 Весной хорошо работает живец и медленная проводка.",
    "🌑 При новолунии клев обычно усиливается днём."
]

# === Вспомогательные функции ===

def fetch_weather(city_name, date_offset=0):
    try:
        if date_offset == 0:
            url = f"https://api.openweathermap.org/data/2.5/weather?q={city_name},BY&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
        else:
            url = f"https://api.openweathermap.org/data/2.5/forecast?q={city_name},BY&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"

        response = requests.get(url)
        data = response.json()

        if response.status_code != 200:
            return None

        if date_offset == 0:
            return {
                "temp": data["main"]["temp"],
                "wind": data["wind"]["speed"],
                "pressure": data["main"]["pressure"],
                "description": data["weather"][0]["description"]
            }
        else:
            forecast_list = data.get("list", [])
            target_time = datetime.now() + timedelta(days=date_offset)
            target_day = target_time.date()

            for forecast in forecast_list:
                forecast_time = datetime.fromtimestamp(forecast['dt'])
                if forecast_time.date() == target_day and 9 <= forecast_time.hour <= 12:
                    return {
                        "temp": forecast["main"]["temp"],
                        "wind": forecast["wind"]["speed"],
                        "pressure": forecast["main"]["pressure"],
                        "description": forecast["weather"][0]["description"]
                    }
            return None
    except Exception as e:
        print(f"Ошибка погоды: {e}")
        return None

def get_moon_phase(target_date=None):
    moon = ephem.Moon()
    moon.compute(ephem.Date(target_date)) if target_date else moon.compute()
    phase = moon.phase
    if phase < 5:
        return "новолуние"
    elif 5 <= phase < 45:
        return "первая четверть"
    elif 45 <= phase < 55:
        return "полнолуние"
    else:
        return "последняя четверть"


def calculate_fishing_success(fish_profile, weather_data, time_of_day, moon_phase):
    score = 50
    temp = weather_data.get("temp")
    min_temp, max_temp = fish_profile["active_temp_range"]
    if min_temp <= temp <= max_temp:
        score += 20
    elif abs(temp - min_temp) <= 5 or abs(temp - max_temp) <= 5:
        score += 10
    else:
        score -= 10

    wind = weather_data.get("wind")
    if wind > 8:
        score -= 10
    elif 4 <= wind <= 8:
        score += 5
    else:
        score += 10

    pressure = weather_data.get("pressure")
    if "высокое" in fish_profile["pressure_preference"] and pressure > 755:
        score += 10
    elif "падающее" in fish_profile["pressure_preference"] and pressure < 750:
        score += 10
    else:
        score += 5

    if "полнолуние" in moon_phase.lower():
        score -= 5
    elif "новолуние" in moon_phase.lower():
        score += 5

    return min(max(score, 0), 100)

def save_user_id(user_id):
    try:
        with open('users.txt', 'r') as f:
            users = f.read().splitlines()
    except FileNotFoundError:
        users = []

    if str(user_id) not in users:
        with open('users.txt', 'a') as f:
            f.write(f"{user_id}\n")

def find_fish_profile(name):
    for fish in FISH_PROFILES:
        if fish["name"] == name:
            return fish
    return None

def parse_date(date_text):
    try:
        return datetime.strptime(date_text, "%d.%m.%Y")
    except ValueError:
        return None

# === Обработчики ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user_id(user_id)

    context.user_data.clear()
    welcome_text = (
        "🎣 Добро пожаловать в Klevprofish_bot!\n\n"
        "Этот бот поможет вам спланировать удачную рыбалку, "
        "учитывая реальную погоду, фазу Луны, давление и активность рыбы. 🐟\n\n"
        "Выберите действие:"
    )
    keyboard = [
        [KeyboardButton("🔵 Начать прогноз")],
        [KeyboardButton("🛟 Помощь"), KeyboardButton("ℹ️ О боте")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    return CHOOSING_WATERBODY

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await start(update, context)

async def choose_waterbody(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🔵 Начать прогноз":
        keyboard = [[name] for name in WATERBODIES.keys()]
        keyboard.append(["🔁 Вернуться в меню"])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("🎯 Выберите водоём:", reply_markup=reply_markup)
        return CHOOSING_WATERBODY

    elif text == "🛟 Помощь":
        await update.message.reply_text("🛠 Помощь:\n\nВыберите водоём ➔ Выберите рыбу ➔ Укажите дату ➔ Получите прогноз! 🎣")
        return CHOOSING_WATERBODY

    elif text == "ℹ️ О боте":
        await update.message.reply_text("ℹ️ Klevprofish_bot v1.2\nАвтор: @твойникнейм\nПредсказывает клёв на основе погоды и Луны!")
        return CHOOSING_WATERBODY

    elif text == "🔁 Вернуться в меню":
        return await start(update, context)

    elif text not in WATERBODIES:
        await update.message.reply_text("❗ Пожалуйста, выберите водоём из списка.")
        return CHOOSING_WATERBODY

    context.user_data['waterbody'] = text

    fish_list = ["Карп", "Щука"]
    keyboard = [[fish] for fish in fish_list]
    keyboard.append(["🔁 Вернуться в меню"])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text("🐟 Теперь выберите рыбу:", reply_markup=reply_markup)
    return CHOOSING_FISH

async def choose_fish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔁 Вернуться в меню":
        return await start(update, context)

    context.user_data['fish'] = text
    keyboard = [["Сегодня"], ["Завтра"], ["Своя дата"], ["🔁 Вернуться в меню"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("📅 На какой день хотите прогноз?", reply_markup=reply_markup)
    return CHOOSING_DATE

async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_choice = update.message.text.strip()

    if user_choice == "🔁 Вернуться в меню":
        return await start(update, context)

    if user_choice == "Сегодня":
        context.user_data['target_date'] = datetime.now()
        return await show_forecast(update, context)

    elif user_choice == "Завтра":
        context.user_data['target_date'] = datetime.now() + timedelta(days=1)
        return await show_forecast(update, context)

    elif user_choice == "Своя дата":
        context.user_data['awaiting_manual_date'] = True
        await update.message.reply_text("✏️ Введите дату в формате ДД.ММ.ГГГГ:")
        return CHOOSING_DATE

    elif context.user_data.get('awaiting_manual_date'):
        target_date = parse_date(user_choice)
        if not target_date:
            await update.message.reply_text("❗ Неверный формат даты!")
            return CHOOSING_DATE

        today = datetime.now().date()
        if not (today <= target_date.date() <= today + timedelta(days=5)):
            await update.message.reply_text("⚠️ Прогноз доступен на 5 дней вперёд.")
            return CHOOSING_DATE

        context.user_data['target_date'] = target_date
        context.user_data['awaiting_manual_date'] = False
        return await show_forecast(update, context)

async def show_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waterbody = context.user_data['waterbody']
    fish_name = context.user_data['fish']
    target_date = context.user_data['target_date']
    city = WATERBODIES[waterbody]
    offset = (target_date.date() - datetime.now().date()).days

    weather = fetch_weather(city, offset)
    if not weather:
        await update.message.reply_text("⚠️ Не удалось получить погоду.")
        return ConversationHandler.END

    fish_profile = find_fish_profile(fish_name)
    moon_phase = get_moon_phase(target_date)
    time_of_day = get_time_of_day(target_date)
    success = calculate_fishing_success(fish_profile, weather, time_of_day, moon_phase)

    forecast = f"""
📍 Водоём: {waterbody}
🐟 Рыба: {fish_name}
📅 Дата: {target_date.strftime("%d.%m.%Y")}
🌡 Температура: {weather['temp']}°C
💨 Ветер: {weather['wind']} м/с
📈 Давление: {weather['pressure']} мм рт. ст.
🌑 Фаза Луны: {moon_phase}

🔥 Индекс клёва: {success}%

🎣 Совет: Используйте {', '.join(fish_profile['best_baits'])}.
Лучшее время: {fish_profile['best_time_of_day']}.
Методы: {', '.join(fish_profile['fishing_methods'])}.
"""
    await update.message.reply_text(forecast, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Операция отменена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open('users.txt', 'r') as f:
            users = f.read().splitlines()
        count = len(users)
    except FileNotFoundError:
        count = 0

    await update.message.reply_text(f"📈 Уникальных пользователей: {count} 🎣")

# === Запуск ===
if __name__ == "__main__":
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_WATERBODY: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_waterbody)],
            CHOOSING_FISH: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_fish)],
            CHOOSING_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("menu", menu)],
    )

    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(conv_handler)

    print("🚀 Klevprofish_bot v1.2 полностью запущен!")
    application.run_polling()
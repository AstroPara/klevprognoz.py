from datetime import datetime, timedelta
import logging
import requests
import ephem
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, ConversationHandler, filters

TELEGRAM_TOKEN = '7297237331:AAEBR05LkndfAl-uJoiUmimctS6AZ7UxSwM'
OPENWEATHER_API_KEY = '355f0d0d5a864bdc9cb964863445f16c'

CHOOSING_OBLAST, CHOOSING_WATERBODY, CHOOSING_DATE = range(3)

logging.basicConfig(level=logging.INFO)

OBLASTS = {
    "Минская": ["Озеро Нарочь", "Река Березина"],
    "Гомельская": ["Река Сож"],
}

WATERBODY_TO_CITY = {
    "Озеро Нарочь": "Naroch",
    "Река Березина": "Berezino",
    "Река Сож": "Gomel",
}

WATERBODY_TO_FISH = {
    "Озеро Нарочь": ["Судак", "Щука", "Окунь"],
    "Река Березина": ["Сом", "Щука"],
    "Река Сож": ["Судак", "Сом"],
}

FISH_PROFILES = {
    "Судак": {"temp": (10, 18), "methods": "донка", "baits": "резина, живец"},
    "Щука": {"temp": (8, 18), "methods": "спиннинг", "baits": "воблеры"},
    "Окунь": {"temp": (12, 20), "methods": "поплавок", "baits": "мотыль"},
    "Сом": {"temp": (18, 25), "methods": "донка", "baits": "мясо, червь"},
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton(oblast)] for oblast in OBLASTS.keys()]
    await update.message.reply_text("Выберите область:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return CHOOSING_OBLAST

async def choose_oblast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oblast = update.message.text
    context.user_data["oblast"] = oblast
    keyboard = [[KeyboardButton(w)] for w in OBLASTS[oblast]]
    await update.message.reply_text("Выберите водоём:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return CHOOSING_WATERBODY

async def choose_waterbody(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waterbody = update.message.text
    context.user_data["waterbody"] = waterbody
    keyboard = [["Сегодня"], ["Завтра"]]
    await update.message.reply_text("Выберите дату:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return CHOOSING_DATE

async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    target_date = datetime.now() if choice == "Сегодня" else datetime.now() + timedelta(days=1)
    context.user_data["date"] = target_date

    city = WATERBODY_TO_CITY[context.user_data["waterbody"]]
    weather = fetch_weather(city)
    moon_phase = get_moon_phase(target_date)

    fish_forecasts = []
    for fish in WATERBODY_TO_FISH[context.user_data["waterbody"]]:
        profile = FISH_PROFILES[fish]
        score = score_fish(profile, weather)
        fish_forecasts.append(f"🐟 {fish} — {score}% клёва (приманки: {profile['baits']}, метод: {profile['methods']})")

    result = "\n".join(fish_forecasts)
    await update.message.reply_text(
        f"📍 Водоём: {context.user_data['waterbody']}\n📅 Дата: {target_date.strftime('%d.%m.%Y')}\n"
        f"🌡 {weather['temp']}°C | 💨 {weather['wind']} м/с | 📈 {weather['pressure']} мм\n🌑 Фаза Луны: {moon_phase}\n\n{result}",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

def fetch_weather(city):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city},BY&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
    r = requests.get(url).json()
    return {
        "temp": r["main"]["temp"],
        "wind": r["wind"]["speed"],
        "pressure": r["main"]["pressure"],
    }

def get_moon_phase(date):
    moon = ephem.Moon()
    moon.compute(date)
    p = moon.phase
    if p < 5: return "новолуние"
    if p < 45: return "первая четверть"
    if p < 55: return "полнолуние"
    return "последняя четверть"

def score_fish(profile, weather):
    t = weather["temp"]
    min_t, max_t = profile["temp"]
    if min_t <= t <= max_t:
        return 80
    elif abs(t - min_t) < 5 or abs(t - max_t) < 5:
        return 60
    return 30

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_OBLAST: [MessageHandler(filters.TEXT, choose_oblast)],
            CHOOSING_WATERBODY: [MessageHandler(filters.TEXT, choose_waterbody)],
            CHOOSING_DATE: [MessageHandler(filters.TEXT, choose_date)],
        },
        fallbacks=[]
    )
    app.add_handler(conv)
    app.run_polling()

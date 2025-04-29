import os
import logging
import requests
import ephem
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

# === Токены ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# === Состояния ===
CHOOSING_REGION, CHOOSING_DISTRICT, CHOOSING_WATERBODY, CHOOSING_DATE = range(4)

# === Заглушка для функции (чтобы не ломалась логика) ===
def save_user_id(user_id):
    pass

# === Базы данных ===
REGIONS = {
    "Минская область": "Minsk"
}

DISTRICTS_BY_REGION = {
    "Минская область": [
        "Березинский район", "Борисовский район", "Вилейский район", "Воложинский район",
        "Дзержинский район", "Клецкий район", "Копыльский район", "Крупский район",
        "Логойский район", "Любанский район", "Минский район", "Молодечненский район",
        "Мядельский район", "Несвижский район", "Пуховичский район", "Слуцкий район",
        "Смолевичский район", "Солигорский район", "Стародорожский район", "Столбцовский район",
        "Узденский район", "Червенский район"
    ]
}

WATERBODIES_BY_DISTRICT = {
    "Березинский район": ["Река Березина"],
    "Борисовский район": [],
    "Вилейский район": ["Вилейское водохранилище", "Озеро Селява"],
    "Воложинский район": [],
    "Дзержинский район": [],
    "Клецкий район": [],
    "Копыльский район": [],
    "Крупский район": ["Крупское водохранилище"],
    "Логойский район": ["Река Уса"],
    "Любанский район": ["Озеро Кромань"],
    "Минский район": ["Заславское водохранилище", "Дрозды", "Озеро Медвежино", "Река Свислочь"],
    "Молодечненский район": [],
    "Мядельский район": [],
    "Несвижский район": ["Несвижские пруды"],
    "Пуховичский район": ["Река Птичь"],
    "Слуцкий район": ["Река Случь"],
    "Смолевичский район": ["Озеро Белое"],
    "Солигорский район": ["Озеро Рудея"],
    "Стародорожский район": [],
    "Столбцовский район": ["Река Лоша"],
    "Узденский район": [],
    "Червенский район": ["Чигиринское водохранилище"]
}

WATERBODY_TO_CITY = {
    "Заславское водохранилище": "Zaslawye",
    "Вилейское водохранилище": "Vileyka",
    "Несвижские пруды": "Nyasvizh",
    "Крупское водохранилище": "Krupki",
    "Чигиринское водохранилище": "Chervyen",
    "Дрозды": "Minsk",
    "Озеро Медвежино": "Minsk",
    "Река Свислочь": "Minsk",
    "Река Птичь": "Pukhavichy",
    "Озеро Дикое": "Pleshchenitsy",
    "Река Уса": "Lahoisk",
    "Озеро Белое": "Smolevichi",
    "Река Березина": "Berezino",
    "Озеро Селява": "Krugloe",
    "Река Случь": "Slutsk",
    "Река Лоша": "Stolbtsy",
    "Озеро Кромань": "Lyuban",
    "Озеро Рудея": "Luban"
}

FISH_BY_WATERBODY = {
    "Заславское водохранилище": ["Щука", "Окунь", "Плотва"],
    "Вилейское водохранилище": ["Судак", "Щука", "Окунь", "Сом"],
    "Несвижские пруды": ["Карп", "Карась", "Лещ"],
    "Крупское водохранилище": ["Карась", "Лещ", "Плотва"],
    "Чигиринское водохранилище": ["Судак", "Щука", "Сом"],
    "Дрозды": ["Карась", "Карп", "Плотва"],
    "Озеро Медвежино": ["Карась", "Окунь"],
    "Река Свислочь": ["Карась", "Плотва", "Окунь"],
    "Река Птичь": ["Щука", "Карась", "Окунь", "Язь"],
    "Озеро Дикое": ["Карась", "Щука", "Плотва"],
    "Река Уса": ["Щука", "Окунь"],
    "Озеро Белое": ["Карась", "Карп"],
    "Река Березина": ["Щука", "Сом", "Жерех", "Голавль", "Лещ"],
    "Озеро Селява": ["Лещ", "Окунь", "Судак"],
    "Река Случь": ["Щука", "Язь", "Голавль"],
    "Река Лоша": ["Щука", "Плотва"],
    "Озеро Кромань": ["Карась", "Карп", "Лещ"],
    "Озеро Рудея": ["Судак", "Плотва"]
}

# === Логика ===

def fetch_weather(city):
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city},BY&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return {
                "temp": data["main"]["temp"],
                "wind": data["wind"]["speed"],
                "pressure": data["main"]["pressure"],
                "description": data["weather"][0]["description"]
            }
    except Exception as e:
        logging.error(f"Ошибка погоды: {e}")
    return None

def get_moon_phase(date=None):
    moon = ephem.Moon()
    moon.compute(ephem.Date(date) if date else ephem.now())
    phase = moon.phase
    if phase < 5:
        return "новолуние"
    elif 5 <= phase < 45:
        return "первая четверть"
    elif 45 <= phase < 55:
        return "полнолуние"
    else:
        return "последняя четверть"

def calculate_success(temp, wind, pressure, moon_phase):
    score = 50
    if 10 <= temp <= 20:
        score += 20
    if wind < 5:
        score += 10
    if pressure > 755:
        score += 10
    if "полнолуние" in moon_phase:
        score -= 5
    return min(100, max(0, score))

# === Обработчики ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    save_user_id(update.effective_user.id)
    keyboard = [[r] for r in REGIONS]
    await update.message.reply_text("🏞 Выберите область для рыбалки:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
=======
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
    context.user_data['region'] = region
    keyboard = [[d] for d in DISTRICTS_BY_REGION[region]]
    await update.message.reply_text("🏘 Выберите район:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return CHOOSING_DISTRICT

async def choose_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    district = update.message.text
    context.user_data['district'] = district
    waterbodies = WATERBODIES_BY_DISTRICT.get(district, [])
    if not waterbodies:
        await update.message.reply_text("❗Нет данных по водоёмам.")
        return ConversationHandler.END
    keyboard = [[w] for w in waterbodies]
    await update.message.reply_text("🌊 Выберите водоём:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return CHOOSING_WATERBODY

async def choose_waterbody(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['waterbody'] = update.message.text
    keyboard = [["Сегодня"], ["Завтра"]]
    await update.message.reply_text("📅 На какой день прогноз?", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return CHOOSING_DATE

async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['target_date'] = datetime.now() if update.message.text == "Сегодня" else datetime.now() + timedelta(days=1)
    return await show_forecast(update, context)

async def show_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    region = context.user_data["region"]
    district = context.user_data["district"]
    waterbody = context.user_data["waterbody"]
    target_date = context.user_data["target_date"]
    city = WATERBODY_TO_CITY.get(waterbody, REGIONS[region])
    weather = fetch_weather(city)
    if not weather:
        await update.message.reply_text("⚠️ Не удалось получить погоду.")
        return ConversationHandler.END
    moon = get_moon_phase(target_date)
    result = f"📍 Область: {region}\n📍 Район: {district}\n🌊 Водоём: {waterbody}\n\n"
    for fish in FISH_BY_WATERBODY.get(waterbody, []):
        chance = calculate_success(weather['temp'], weather['wind'], weather['pressure'], moon)
        result += f"🐟 {fish}: вероятность клёва {chance}%\n"
    result += (
        f"\n🌡 Температура: {weather['temp']}°C"
        f"\n💨 Ветер: {weather['wind']} м/с"
        f"\n📈 Давление: {weather['pressure']} мм рт. ст."
        f"\n🌑 Фаза Луны: {moon}"
    )
    await update.message.reply_text(result, reply_markup=ReplyKeyboardRemove())
=======
    await update.message.reply_text(f"✅ Вы выбрали: {region}", reply_markup=ReplyKeyboardRemove())
>>>>>>> ff8a209aaecf36ed97305f89b420679e61985ffd
    return ConversationHandler.END

# === Запуск ===

<<<<<<< HEAD
if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    conv = ConversationHandler(
=======
def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
>>>>>>> ff8a209aaecf36ed97305f89b420679e61985ffd
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_region)]
        },
        fallbacks=[CommandHandler("start", start)],
    )
<<<<<<< HEAD
    app.add_handler(conv)
    app.run_polling()
=======

    application.add_handler(conv_handler)
    logging.info("🚀 Бот запущен. Ожидаю команды...")
    application.run_polling()

if __name__ == "__main__":
    main()
>>>>>>> ff8a209aaecf36ed97305f89b420679e61985ffd

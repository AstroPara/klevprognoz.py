import os
import logging
import requests
import ephem
from telegram.constants import ChatAction 
from datetime import datetime, timedelta
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
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# === Состояния ===
CHOOSING_REGION, CHOOSING_DISTRICT, CHOOSING_WATERBODY, CHOOSING_DATE = range(4)

# === Логирование ===
logging.basicConfig(level=logging.INFO)

# === Заглушка для user_id ===
def save_user_id(user_id):
    pass

# === Словари ===

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
    "Березинский район": ["р. Березина", "оз. Селява", "оз. Чёрное", "оз. Белое"],
    "Борисовский район": ["р. Березина", "оз. Святец", "оз. Лоша", "Карьер Смолевичи 💵"],
    "Вилейский район": ["вдхр. Вилейское", "оз. Лесное", "оз. Ячонка", "б/о Вилейский край 💵"],
    "Воложинский район": ["р. Вилия", "р. Ислочь", "Пруд Ивенецкий 💵"],
    "Дзержинский район": ["р. Птичь", "Пруд Руденский 💵", "Пруд Дзержинский 💵"],
    "Клецкий район": ["р. Лань", "Пруд Копылевский 💵"],
    "Копыльский район": ["р. Лань", "оз. Оса"],
    "Крупский район": ["вдхр. Крупское", "р. Бобр"],
    "Логойский район": ["р. Уса", "оз. Медвежье", "оз. Чернобыльское", "б/о Силичи 💵"],
    "Любанский район": ["оз. Кромань", "оз. Рудея"],
    "Минский район": [
        "вдхр. Заславское", "Дрозды", "оз. Медвежино", "р. Свислочь",
        "б/о Дрозды-Клуб 💵", "б/о Минское море 💵"
    ],
    "Молодечненский район": ["оз. Свирь", "оз. Лешня", "Пруд Княгининский 💵"],
    "Мядельский район": ["оз. Нарочь", "оз. Мястро", "оз. Баторино", "оз. Болдук", "оз. Вилейка"],
    "Несвижский район": ["Несвижские пруды", "оз. Лань", "б/о Несвиж 💵"],
    "Пуховичский район": ["р. Птичь", "б/о Дружба 💵"],
    "Слуцкий район": ["р. Случь", "оз. Случ"],
    "Смолевичский район": ["оз. Белое", "Карьер Смолевичский 💵"],
    "Солигорский район": ["оз. Рудея", "вдхр. Солигорское"],
    "Стародорожский район": ["р. Оресса"],
    "Столбцовский район": ["р. Неман", "р. Лоша"],
    "Узденский район": ["р. Уса"],
    "Червенский район": ["вдхр. Чигиринское", "б/о Чигиринское 💵"]
}

WATERBODY_TO_CITY = {
    # Березинский район
    "р. Березина": "Berezino",
    "оз. Селява": "Krugloe",
    "оз. Чёрное": "Berezino",
    "оз. Белое": "Berezino",

    # Борисовский район
    "оз. Святец": "Barysaw",
    "оз. Лоша": "Barysaw",
    "Карьер Смолевичи 💵": "Smalyavichy",
    "р. Березина": "Barysaw",

    # Вилейский район
    "вдхр. Вилейское": "Vileyka",
    "оз. Лесное": "Vileyka",
    "оз. Ячонка": "Vileyka",
    "б/о Вилейский край 💵": "Vileyka",

    # Воложинский район
    "р. Вилия": "Valozhyn",
    "р. Ислочь": "Valozhyn",
    "Пруд Ивенецкий 💵": "Ivyanets",

    # Дзержинский район
    "р. Птичь": "Dzyarzhynsk",
    "Пруд Руденский 💵": "Rudensk",
    "Пруд Дзержинский 💵": "Dzyarzhynsk",

    # Клецкий район
    "р. Лань": "Kletsk",
    "Пруд Копылевский 💵": "Kopyl",

    # Копыльский район
    "оз. Оса": "Kopyl",

    # Крупский район
    "вдхр. Крупское": "Krupki",
    "р. Бобр": "Krupki",

    # Логойский район
    "р. Уса": "Lahoysk",
    "оз. Медвежье": "Lahoysk",
    "оз. Чернобыльское": "Lahoysk",
    "б/о Силичи 💵": "Lahoysk",

    # Любанский район
    "оз. Кромань": "Lyuban",
    "оз. Рудея": "Lyuban",

    # Минский район
    "вдхр. Заславское": "Zaslawye",
    "Дрозды": "Minsk",
    "оз. Медвежино": "Minsk",
    "р. Свислочь": "Minsk",
    "б/о Дрозды-Клуб 💵": "Minsk",
    "б/о Минское море 💵": "Zaslawye",

    # Молодечненский район
    "оз. Свирь": "Maladzyechna",
    "оз. Лешня": "Maladzyechna",
    "Пруд Княгининский 💵": "Maladzyechna",

    # Мядельский район
    "оз. Нарочь": "Narach",
    "оз. Мястро": "Narach",
    "оз. Баторино": "Narach",
    "оз. Болдук": "Narach",
    "оз. Вилейка": "Narach",

    # Несвижский район
    "Несвижские пруды": "Nyasvizh",
    "оз. Лань": "Nyasvizh",
    "б/о Несвиж 💵": "Nyasvizh",

    # Пуховичский район
    "б/о Дружба 💵": "Pukhavichy",
    "р. Птичь": "Pukhavichy",

    # Слуцкий район
    "р. Случь": "Slutsk",
    "оз. Случ": "Slutsk",

    # Смолевичский район
    "оз. Белое": "Smalyavichy",
    "Карьер Смолевичский 💵": "Smalyavichy",

    # Солигорский район
    "оз. Рудея": "Salihorsk",
    "вдхр. Солигорское": "Salihorsk",

    # Стародорожский район
    "р. Оресса": "Staradarozhsk",

    # Столбцовский район
    "р. Неман": "Stowbtsy",
    "р. Лоша": "Stowbtsy",

    # Узденский район
    "р. Уса": "Uzda",

    # Червенский район
    "вдхр. Чигиринское": "Chervyen",
    "б/о Чигиринское 💵": "Chervyen"
}

FISH_BY_WATERBODY = {
    # Березинский район
    "р. Березина": ["Щука", "Сом", "Жерех", "Голавль", "Лещ"],
    "оз. Селява": ["Лещ", "Окунь", "Судак"],
    "оз. Чёрное": ["Карась", "Щука"],
    "оз. Белое": ["Карась", "Карп"],

    # Борисовский район
    "р. Березина": ["Щука", "Сом", "Жерех", "Голавль", "Лещ"],
    "оз. Святец": ["Карась", "Лещ"],
    "оз. Лоша": ["Щука", "Плотва"],
    "Карьер Смолевичи 💵": ["Карп", "Карась"],

    # Вилейский район
    "вдхр. Вилейское": ["Судак", "Щука", "Окунь", "Сом"],
    "оз. Лесное": ["Щука", "Карась"],
    "оз. Ячонка": ["Лещ", "Плотва"],
    "б/о Вилейский край 💵": ["Карп", "Карась"],

    # Воложинский район
    "р. Вилия": ["Щука", "Жерех"],
    "р. Ислочь": ["Форель", "Хариус"],
    "Пруд Ивенецкий 💵": ["Карп", "Карась"],

    # Дзержинский район
    "р. Птичь": ["Щука", "Карась", "Окунь", "Язь"],
    "Пруд Руденский 💵": ["Карп", "Карась"],
    "Пруд Дзержинский 💵": ["Карп", "Карась"],

    # Клецкий район
    "р. Лань": ["Щука", "Плотва"],
    "Пруд Копылевский 💵": ["Карп", "Карась"],

    # Копыльский район
    "р. Лань": ["Щука", "Плотва"],
    "оз. Оса": ["Карась", "Плотва"],

    # Крупский район
    "вдхр. Крупское": ["Карась", "Лещ", "Плотва"],
    "р. Бобр": ["Щука", "Плотва"],

    # Логойский район
    "р. Уса": ["Щука", "Окунь"],
    "оз. Медвежье": ["Карась", "Щука"],
    "оз. Чернобыльское": ["Карась", "Окунь"],
    "б/о Силичи 💵": ["Карп", "Карась"],

    # Любанский район
    "оз. Кромань": ["Карась", "Карп", "Лещ"],
    "оз. Рудея": ["Судак", "Плотва"],

    # Минский район
    "вдхр. Заславское": ["Щука", "Окунь", "Плотва"],
    "Дрозды": ["Карась", "Карп", "Плотва"],
    "оз. Медвежино": ["Карась", "Окунь"],
    "р. Свислочь": ["Карась", "Плотва", "Окунь"],
    "б/о Дрозды-Клуб 💵": ["Карп", "Карась"],
    "б/о Минское море 💵": ["Карп", "Карась"],

    # Молодечненский район
    "оз. Свирь": ["Лещ", "Щука"],
    "оз. Лешня": ["Карась", "Окунь"],
    "Пруд Княгининский 💵": ["Карп", "Карась"],

    # Мядельский район
    "оз. Нарочь": ["Щука", "Лещ", "Окунь", "Судак"],
    "оз. Мястро": ["Карась", "Лещ"],
    "оз. Баторино": ["Щука", "Плотва"],
    "оз. Болдук": ["Щука", "Окунь"],
    "оз. Вилейка": ["Лещ", "Плотва"],

    # Несвижский район
    "Несвижские пруды": ["Карп", "Карась", "Лещ"],
    "оз. Лань": ["Щука", "Плотва"],
    "б/о Несвиж 💵": ["Карп", "Карась"],

    # Пуховичский район
    "р. Птичь": ["Щука", "Карась", "Окунь", "Язь"],
    "б/о Дружба 💵": ["Карп", "Карась"],

    # Слуцкий район
    "р. Случь": ["Щука", "Язь", "Голавль"],
    "оз. Случ": ["Карась", "Плотва"],

    # Смолевичский район
    "оз. Белое": ["Карась", "Карп"],
    "Карьер Смолевичский 💵": ["Карп", "Карась"],

    # Солигорский район
    "оз. Рудея": ["Судак", "Плотва"],
    "вдхр. Солигорское": ["Карась", "Окунь", "Лещ"],

    # Стародорожский район
    "р. Оресса": ["Щука", "Лещ"],

    # Столбцовский район
    "р. Неман": ["Щука", "Жерех"],
    "р. Лоша": ["Щука", "Плотва"],

    # Узденский район
    "р. Уса": ["Щука", "Окунь"],

    # Червенский район
    "вдхр. Чигиринское": ["Судак", "Щука", "Сом"],
    "б/о Чигиринское 💵": ["Карп", "Карась"]
}

# === Предпочтения рыб ===
FISH_CONDITIONS = {
    "Щука": {
        "temp_min": 12,
        "temp_max": 18,
        "wind_max": 5,
        "pressure_preference": "high",
    },
    "Окунь": {
        "temp_min": 10,
        "temp_max": 20,
        "wind_max": 7,
        "pressure_preference": "stable",
    },
    "Лещ": {
        "temp_min": 15,
        "temp_max": 22,
        "wind_max": 4,
        "pressure_preference": "stable",
    },
    "Карп": {
        "temp_min": 18,
        "temp_max": 24,
        "wind_max": 3,
        "pressure_preference": "low",
    },
    "Судак": {
        "temp_min": 15,
        "temp_max": 20,
        "wind_max": 5,
        "pressure_preference": "low",
    },
    "Сом": {
        "temp_min": 20,
        "temp_max": 26,
        "wind_max": 4,
        "pressure_preference": "low",
    },
    "Карась": {
        "temp_min": 16,
        "temp_max": 23,
        "wind_max": 2,
        "pressure_preference": "stable",
    },
    "Жерех": {
        "temp_min": 15,
        "temp_max": 20,
        "wind_max": 6,
        "pressure_preference": "high",
    },
    "Голавль": {
        "temp_min": 14,
        "temp_max": 20,
        "wind_max": 5,
        "pressure_preference": "stable",
    },
    "Плотва": {
        "temp_min": 10,
        "temp_max": 18,
        "wind_max": 4,
        "pressure_preference": "stable",
    },
    "Язь": {
        "temp_min": 12,
        "temp_max": 18,
        "wind_max": 5,
        "pressure_preference": "stable",
    }
}

# === Вспомогательные функции ===

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
        print(f"Ошибка погоды: {e}")
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

def calculate_success(temp, wind, pressure, moon_phase, fish):
    conditions = FISH_CONDITIONS.get(fish)

    if not conditions:
        return random.randint(30, 70)

    score = 50

    # Температура
    if conditions["temp_min"] <= temp <= conditions["temp_max"]:
        score += 20
    else:
        score -= 10

    # Ветер
    if wind <= conditions["wind_max"]:
        score += 10
    else:
        score -= 10

    # Давление
    if conditions["pressure_preference"] == "high" and pressure > 755:
        score += 10
    elif conditions["pressure_preference"] == "low" and pressure < 745:
        score += 10
    elif conditions["pressure_preference"] == "stable" and 745 <= pressure <= 755:
        score += 10
    else:
        score -= 5

    # Фаза Луны
    if moon_phase == "полнолуние":
        score -= 10
    elif moon_phase in ["новолуние", "первая четверть"]:
        score += 10

    # Время суток
    now_hour = datetime.now().hour
    if now_hour <= 9 or now_hour >= 18:
        score += 10

    return min(100, max(0, score))

# === Команды ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [["🎣 Начать"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привет! Нажми кнопку ниже, чтобы начать 🎣",
        reply_markup=markup
    )
    return CHOOSING_REGION

async def choose_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    region = update.message.text
    if region not in REGIONS:
        keyboard = [[r] for r in REGIONS.keys()] + [["❌ Отмена"]]
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("🏞 Пожалуйста, выбери область:", reply_markup=markup)
        return CHOOSING_REGION

    context.user_data["region"] = region
    keyboard = [[d] for d in DISTRICTS_BY_REGION[region]] + [["⬅ Назад"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("🏘 Теперь выбери район:", reply_markup=markup)
    return CHOOSING_DISTRICT

async def choose_district(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    district = update.message.text
    context.user_data["district"] = district

    waterbodies = WATERBODIES_BY_DISTRICT.get(district)
    if not waterbodies:
        await update.message.reply_text("❗ Нет данных по водоёмам в этом районе.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    keyboard = [[w] for w in waterbodies] + [["⬅ Назад"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("🌊 Выбери водоём:", reply_markup=markup)
    return CHOOSING_WATERBODY

async def choose_waterbody(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    waterbody = update.message.text
    context.user_data["waterbody"] = waterbody

    keyboard = [["Сегодня"], ["Завтра"], ["⬅ Назад"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("📅 Выбери день:", reply_markup=markup)
    return CHOOSING_DATE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🚫 Вы отменили выбор. Чтобы начать снова — нажмите 🎣 Начать.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    date_choice = update.message.text
    target_date = datetime.now() if date_choice == "Сегодня" else datetime.now() + timedelta(days=1)
    context.user_data["target_date"] = target_date
    return await show_forecast(update, context)

async def show_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    region = context.user_data["region"]
    district = context.user_data["district"]
    waterbody = context.user_data["waterbody"]
    target_date = context.user_data["target_date"]

    # Эффект "пишет..."
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    city = WATERBODY_TO_CITY.get(waterbody, REGIONS[region])
    weather = fetch_weather(city)
    if not weather:
        await update.message.reply_text("⚠️ Не удалось получить погоду.")
        return ConversationHandler.END

    moon = get_moon_phase(target_date)

    result = f"📍 {region} / {district} / {waterbody}\n\n"
    result += (
        f"🌡 Температура: {weather['temp']}°C\n"
        f"💨 Ветер: {weather['wind']} м/с\n"
        f"📈 Давление: {weather['pressure']} мм рт. ст.\n"
        f"🌑 Фаза Луны: {moon}\n\n"
        f"Вероятность клёва:\n"
    )

    for fish in FISH_BY_WATERBODY.get(waterbody, []):
        chance = calculate_success(weather['temp'], weather['wind'], weather['pressure'], moon, fish)
        result += f"- {fish}: {chance}%\n"

    await update.message.reply_text(result, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Кнопка для нового прогноза
    keyboard = [["🎣 Новый прогноз"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(result, reply_markup=markup)
    return CHOOSING_REGION

# === Запуск ===
def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🎣 Начать$"), start),
            CommandHandler("start", start)
        ],
        states={
            CHOOSING_REGION: [
                MessageHandler(filters.Regex("^❌ Отмена$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, choose_region)
            ],
            CHOOSING_DISTRICT: [
                MessageHandler(filters.Regex("^⬅️ Назад$"), start),
                MessageHandler(filters.Regex("^❌ Отмена$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, choose_district)
            ],
            CHOOSING_WATERBODY: [
                MessageHandler(filters.Regex("^⬅️ Назад$"), choose_region),
                MessageHandler(filters.Regex("^❌ Отмена$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, choose_waterbody)
            ],
            CHOOSING_DATE: [
                MessageHandler(filters.Regex("^⬅️ Назад$"), choose_district),
                MessageHandler(filters.Regex("^❌ Отмена$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, choose_date)
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Отмена$"), cancel)],
    )

    application.add_handler(conv_handler)
    logging.info("🚀 Бот запущен. Ожидаю команды...")
    application.run_polling()


if __name__ == "__main__":
    main()

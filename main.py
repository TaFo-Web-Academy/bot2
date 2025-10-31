import logging
import sqlite3
import csv
import os
import asyncio
import requests
import time
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, ContextTypes
from telegram.error import Conflict
from flask import Flask
from threading import Thread

# ========== CONFIG ==========
BOT_TOKEN = "8232853921:AAGx1Mo8EwJGX46t_3h2IIQBkI7A445Femk"
ADMIN_IDS = [7249758488]
REGISTRATION_LINK = "https://tafo-web-academy.github.io/Jannat-Registration/"
HEALTHCHECKS_URL = "https://hc-ping.com/08edb4bf-bdd9-4286-811c-64eee76d98c7"

# ========== DATABASE ==========
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('bot.db', check_same_thread=False)
        self.create_table()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                username TEXT,
                test_result TEXT,
                total_score INTEGER,
                registration_date TEXT
            )
        ''')
        self.conn.commit()

    def user_exists(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        return cursor.fetchone() is not None

    def add_user(self, user_id, username, test_result, total_score):
        cursor = self.conn.cursor()
        registration_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor.execute('''
                INSERT INTO users (user_id, username, test_result, total_score, registration_date)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, test_result, total_score, registration_date))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_all_users(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT user_id, username, test_result, total_score, registration_date FROM users ORDER BY registration_date DESC')
        return cursor.fetchall()

    def get_users_count(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        return cursor.fetchone()[0]

# ========== BOT LOGIC ==========
db = Database()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

QUESTIONS = 0

questions = [
    {
        'text': '1. <b>Кӣ барои зиндагии ту қарор мекунад?</b>',
        'options': ['А) Худам', 'Б) Оила ё дигарон', 'В) Баъзан ман, баъзан онҳо', 'Г) Метарсам қарор гирам'],
        'scores': [3, 1, 2, 0]
    },
    {
        'text': '2. <b>Вақте чизе хато мешавад, чӣ мегӯӣ?</b>',
        'options': ['А) Ман айбдорам', 'Б) Дигарон гунаҳкоранд', 'В) Тақдир ҳамин будааст', 'Г) Намедонам'],
        'scores': [3, 1, 0, 2]
    },
    {
        'text': '3. <b>Орзуи кӯдакиатро ёд дори?</b>',
        'options': ['А) Ҳа, ёдам ҳаст', 'Б) Не, фаромӯш кардам', 'В) Ман дигар орзу надорам'],
        'scores': [3, 1, 0]
    },
    {
        'text': '4. <b>"Зершуур" чӣ маъно дорад?</b>',
        'options': ['А) Қувваи дохилӣ', 'Б) Барои равоншиносон', 'В) Ман намефаҳмам, ле ҷолиб аст', 'Г) Ман бовар надорам'],
        'scores': [3, 1, 2, 0]
    },
    {
        'text': '5. <b>Оё касе зиндагии туро идора мекунад?</b>',
        'options': ['А) Ҳа, пай бурдаам', 'Б) Шояд, меҷӯям', 'В) Не, ҳамаашро ман медонам', 'Г) Намефаҳмам'],
        'scores': [3, 2, 1, 0]
    }
]

def get_result(total_score):
    if total_score >= 12:
        return "Ман тақдири худамам", "🎉 <b>Табрик мекунам! Ту аз он касоне, ки зиндагиашро худ месозад!</b>"
    elif total_score >= 7:
        return "Ман бедор шуда истодаам", "🌅 <b>Огоҳӣ! Ту дар оғози роҳе, ки ба сӯи озодӣ меравад.</b>"
    else:
        return "Ман хомӯш шудам", "🌱 <b>Вақти бедор шудан расидааст!</b>"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        user_id = update.effective_user.id
        
        if db.user_exists(user_id):
            await update.message.reply_text(
                "✨ Шумо аллакай ин тестро гузаронидаед! ✅\n\n"
                f"Барои сабти ном:\n{REGISTRATION_LINK}",
                parse_mode='HTML'
            )
            return ConversationHandler.END

        context.user_data.clear()
        context.user_data['current_question'] = 0
        context.user_data['score'] = 0

        await update.message.reply_text(
            "🎭 <b>ТЕСТ: ОЁ ТУ ЗИНДАГИИ ХУДРО ХУДАД МЕНАВИСӢ Ё НЕ?</b>\n\n"
            "📊 5 савол | ⏱ 3 дақиқа\n\n"
            "Барои оғоз тугмаро пахш кунед...",
            parse_mode='HTML'
        )

        await ask_question(update, context)
        return QUESTIONS
    except Exception as e:
        logger.error(f"Ошибка в команде /start: {e}")
        await update.message.reply_text("❌ Хато дар система. Лутфан баъдтар кӯшиш кунед.")
        return ConversationHandler.END

async def ask_question(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    try:
        if isinstance(update_or_query, Update):
            message_method = update_or_query.message.reply_text
        else:
            message_method = update_or_query.message.edit_text

        current_question = context.user_data.get('current_question', 0)

        if current_question < len(questions):
            question = questions[current_question]
            
            # Прогресс бар
            progress = "🟢" * (current_question + 1) + "⚪" * (len(questions) - current_question - 1)
            
            question_text = (
                f"📝 <b>Савол {current_question + 1}/{len(questions)}</b>\n"
                f"{progress}\n\n"
                f"{question['text']}\n\n"
                f"<b>Интихоби худро кунед:</b>"
            )

            buttons = []
            for index, option in enumerate(question['options']):
                button = InlineKeyboardButton(f"{option}", callback_data=f"ans_{current_question}_{index}")
                buttons.append([button])

            reply_markup = InlineKeyboardMarkup(buttons)
            await message_method(question_text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            total_score = context.user_data.get('score', 0)
            result_title, result_description = get_result(total_score)
            
            result_message = (
                f"🎯 <b>НАТИҶАИ ТЕСТИ ШУМО</b>\n\n"
                f"⭐ <b>Балли шумо:</b> {total_score}/15\n"
                f"🌟 <b>Статус:</b> {result_title}\n\n"
                f"{result_description}\n\n"
                f"🔗 <b>Барои сабти ном:</b>\n{REGISTRATION_LINK}"
            )

            await message_method(result_message, parse_mode='HTML')

            user_id = update_or_query.from_user.id
            username = update_or_query.from_user.username or "Номаълум"
            db.add_user(user_id, username, result_title, total_score)
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Ошибка в ask_question: {e}")
        if isinstance(update_or_query, Update):
            await update_or_query.message.reply_text("❌ Хато дар система. Лутфан /start-ро аз нав пахш кунед.")
        else:
            await update_or_query.message.reply_text("❌ Хато дар система. Лутфан /start-ро аз нав пахш кунед.")
        return ConversationHandler.END

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        query = update.callback_query
        await query.answer()

        parts = query.data.split('_')
        question_index = int(parts[1])
        answer_index = int(parts[2])

        current_question = context.user_data.get('current_question', 0)

        if question_index != current_question:
            return QUESTIONS

        question = questions[question_index]
        score = question['scores'][answer_index]
        context.user_data['score'] = context.user_data.get('score', 0) + score

        context.user_data['current_question'] = question_index + 1
        await ask_question(query, context)
        return QUESTIONS
    except Exception as e:
        logger.error(f"Ошибка в handle_answer: {e}")
        await query.message.reply_text("❌ Хато дар система. Лутфан /start-ро аз нав пахш кунед.")
        return ConversationHandler.END

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Дастраси манъ аст")
        return

    try:
        count = db.get_users_count()
        await update.message.reply_text(f"Ҳамаги корбарон: {count}")
    except Exception as e:
        await update.message.reply_text(f"Хато: {e}")

# ========== MONITORING ==========
def send_ping():
    """Отправляет пинг в Healthchecks.io"""
    try:
        response = requests.get(HEALTHCHECKS_URL, timeout=10)
        logger.info("✅ Пинг отправлен в Healthchecks.io")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки ping: {e}")

def ping_scheduler():
    """Планировщик для отправки пингов каждые 10 минут"""
    while True:
        try:
            send_ping()
            time.sleep(600)  # 10 минут
        except Exception as e:
            logger.error(f"Ошибка в планировщике: {e}")
            time.sleep(60)  # Подождать 1 минуту при ошибке

# ========== WEB SERVER FOR RENDER ==========
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Бот кор мекунад! Telegram: @JannatTrainingBot"

@app.route('/wakeup')
def wakeup():
    logger.info("Бот пробужден через HTTP запрос")
    return "Бот активен! ✅"

@app.route('/ping')
def ping():
    send_ping()
    return "pong", 200

@app.route('/health')
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}, 200

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок"""
    logger.error(f"Exception while handling an update: {context.error}")
    
    if isinstance(context.error, Conflict):
        logger.warning("Обнаружен конфликт - другой экземпляр бота запущен. Завершаем работу...")
        # Даем время другому экземпляру завершиться
        await asyncio.sleep(10)
        # Пытаемся перезапуститься
        await context.application.stop()
        await asyncio.sleep(5)
        await context.application.start()
        await context.application.updater.start_polling()
        logger.info("Бот перезапущен после конфликта")

def main():
    # Запускаем Flask сервер
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Запускаем мониторинг
    monitoring_thread = Thread(target=ping_scheduler)
    monitoring_thread.daemon = True
    monitoring_thread.start()

    # Запускаем бота с обработкой ошибок
    try:
        application = Application.builder().token(BOT_TOKEN).build()

        # Добавляем обработчик ошибок
        application.add_error_handler(error_handler)

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={
                QUESTIONS: [CallbackQueryHandler(handle_answer, pattern='^ans_')],
            },
            fallbacks=[],
            per_message=False  # Явно указываем этот параметр
        )

        application.add_handler(conv_handler)
        application.add_handler(CommandHandler("stats", admin_stats))

        logger.info("🤖 Бот оғоз ёфт...")
        
        # Запускаем бота с обработкой конфликтов
        application.run_polling(
            close_loop=False,
            stop_signals=None
        )
        
    except Conflict as e:
        logger.warning(f"Конфликт при запуске: {e}. Ждем 30 секунд и перезапускаем...")
        time.sleep(30)
        main()  # Рекурсивный перезапуск
    except Exception as e:
        logger.error(f"Критическая ошибка бота: {e}")
        # Перезапуск через 60 секунд
        time.sleep(60)
        main()  # Рекурсивный перезапуск

if __name__ == '__main__':
    main()

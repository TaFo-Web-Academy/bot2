import logging
import sqlite3
import csv
import os
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, ContextTypes
from flask import Flask
from threading import Thread

# ========== CONFIG ==========
BOT_TOKEN = "8232853921:AAGx1Mo8EwJGX46t_3h2IIQBkI7A445Femk"
ADMIN_IDS = [7249758488]
REGISTRATION_LINK = "https://tafo-web-academy.github.io/Jannat-Registration/"

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
logging.basicConfig(level=logging.INFO)
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
        return "Ман тақдири худамам", """🎉 <b>Табрик мекунам! Ту аз он касоне, ки зиндагиашро худ месозад!</b>

✨ Ту ба назари худ омадаастӣ, ки қудрат дар дасти туст.
Дигар ту ба тақдир шикоят намекунед, балки онро бо қарорҳои худ месозед.

💫 <b>Тренинг барои ту як мусоидат хоҳад буд, то боз ҳам зудтар пеш равед!</b>"""
    elif total_score >= 7:
        return "Ман бедор шуда истодаам", """🌅 <b>Огоҳӣ! Ту дар оғози роҳе, ки ба сӯи озодӣ меравад.</b>

Ту ҳис мекунӣ, ки чизе дар зиндагиат нодуруст аст, вале ҳанӯз роҳи дурустро наёфтаӣ.
Ин аломати оғози тағйироти бузург аст!

🚀 <b>Тренинг ба ту кӯмак мекунад, ки ин роҳро бо суръат ва умудвори зиёд тай кунеӣ.</b>"""
    else:
        return "Ман хомӯш шудам", """🌱 <b>Вақти бедор шудан расидааст!</b>

Наметарсӣ? Ин хеле табиӣ аст. Ҳама мо аз ҷое оғоз мекунем.
Аз ин сатр то он ҷое, ки мехоҳӣ, як қадам боқӣ мондааст.

❤️ <b>Тренинг ба ту нишон медиҳад, ки чӣ тавр ин қадамҳоро бо эътимод ва шукуфтан бигирӣ.</b>""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        "Барои оғоз тугмаро пахш кунед...",
        parse_mode='HTML'
    )

    await ask_question(update, context)
    return QUESTIONS

async def ask_question(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(update_or_query, Update):
        message_method = update_or_query.message.reply_text
    else:
        message_method = update_or_query.message.edit_text

    current_question = context.user_data.get('current_question', 0)

    if current_question < len(questions):
        question = questions[current_question]
        
        question_text = (
            f"📝 <b>Савол {current_question + 1}/{len(questions)}</b>\n\n"
            f"{question['text']}\n\n"
            f"<b>Интихоби худро кунед:</b>"
        )

        # Создаем кнопки с полными вариантами ответов
        buttons = []
        for index, option in enumerate(question['options']):
            # Используем полный текст варианта ответа для кнопки
            button = InlineKeyboardButton(f"{option}", callback_data=f"ans_{current_question}_{index}")
            buttons.append([button])

        reply_markup = InlineKeyboardMarkup(buttons)
        await message_method(question_text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        total_score = context.user_data.get('score', 0)
        result_title, result_description = get_result(total_score)

         # И в функции ask_question замените финальное сообщение на:
result_message = (
    f"🎯 <b>НАТИҶАИ ТЕСТИ ШУМО</b>\n\n"
    f"⭐ <b>Балли шумо:</b> {total_score}/15\n"
    f"🌟 <b>Статус:</b> {result_title}\n\n"
    f"{result_description}\n\n"
    f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    f"🎪 <b>ТАРЧИМАИ ТРЕНИНГ</b>\n\n"
    f"📅 <b>Сана:</b> 8 ноябр 2024\n"
    f"🕐 <b>Соат:</b> 14:00 - 17:00\n"
    f"📍 <b>Ҷой:</b> Душанбе, Профсаюз\n"
    f"       Доми София, 3 этаж\n"
    f"👥 <b>Ҷойҳо маҳдуд:</b> 40 нафар\n\n"
    f"💎 <b>Дар ин тренинг меомӯзед:</b>\n"
    f"• Барномаҳои зершуури худро шиносед\n"
    f"• Тақдири навро бо дасти худ нависед\n"
    f"• Ба садои дарунии худ гӯш диҳед\n"
    f"• Орзуҳои кӯдакиро зинда кунед\n\n"
    f"🔗 <b>Барои сабти ном:</b>\n"
    f"{REGISTRATION_LINK}\n\n"
    f"✨ <b>Мо дар интизори дидори шумоем!</b>\n"
    f"━━━━━━━━━━━━━━━━━━━━━━━━━"
)

        await message_method(result_message, parse_mode='HTML')

        user_id = update_or_query.from_user.id
        username = update_or_query.from_user.username or "Номаълум"
        db.add_user(user_id, username, result_title, total_score)
        return ConversationHandler.END

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    try:
        parts = query.data.split('_')
        question_index = int(parts[1])
        answer_index = int(parts[2])
    except (ValueError, IndexError):
        await query.message.reply_text("Хато. Лутфан аз нав кӯшиш кунед /start")
        return ConversationHandler.END

    current_question = context.user_data.get('current_question', 0)

    if question_index != current_question:
        return QUESTIONS

    question = questions[question_index]
    score = question['scores'][answer_index]
    context.user_data['score'] = context.user_data.get('score', 0) + score

    context.user_data['current_question'] = question_index + 1
    await ask_question(query, context)
    return QUESTIONS

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Дастраси манъ аст")
        return

    try:
        count = db.get_users_count()
        await update.message.reply_text(f"Ҳамаги корбарон: {count}")
    except Exception as e:
        await update.message.reply_text(f"Хато: {e}")

# ========== WEB SERVER FOR RENDER ==========
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот кор мекунад!"

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

def main():
    # Запускаем Flask сервер
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Запускаем бота
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            QUESTIONS: [CallbackQueryHandler(handle_answer, pattern='^ans_')],
        },
        fallbacks=[]
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("stats", admin_stats))

    logger.info("Бот оғоз ёфт...")
    application.run_polling()

if __name__ == '__main__':
    main()


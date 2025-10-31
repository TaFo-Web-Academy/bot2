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

# ========== ТАНЗИМОТ ==========
BOT_TOKEN = "8232853921:AAGx1Mo8EwJGX46t_3h2IIQBkI7A445Femk"
ADMIN_IDS = [7249758488]
REGISTRATION_LINK = "https://tafo-web-academy.github.io/Jannat-Registration/"

# ========== ПОЙГОҲИ ДОДА ==========
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
        cursor.execute('''
            SELECT user_id, username, test_result, total_score, registration_date
            FROM users ORDER BY registration_date DESC
        ''')
        return cursor.fetchall()

    def get_users_count(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        return cursor.fetchone()[0]

    def export_to_excel(self):
        users = self.get_all_users()
        filename = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['User ID', 'Username', 'Натиҷаи тест', 'Балл', 'Санаи сабти ном'])
            writer.writerows(users)
        return filename

# ========== МАНТИҚИ БОТ ==========
db = Database()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

QUESTIONS = 0

саволҳо = [
    {
        'матн': '1. <b>Кӣ барои зиндагии ту қарор мекунад?</b>\n\n💭 <i>Мисол: Ман худам интихоби касб, шавҳар, либосро мекунам ё дигарон мегӯянд?</i>',
        'ихтиёрҳо': ['А) Худам', 'Б) Оила ё дигарон', 'В) Баъзан ман, баъзан онҳо', 'Г) Метарсам қарор гирам'],
        'баллҳо': [3, 1, 2, 0]
    },
    {
        'матн': '2. <b>Вақте чизе хато мешавад, чӣ мегӯӣ?</b>\n\n💭 <i>Мисол: Агар кор нобарор шавад, кӣ гунаҳкор?</i>',
        'ихтиёрҳо': ['А) Ман айбдорам', 'Б) Дигарон гунаҳкоранд', 'В) Тақдир ҳамин будааст', 'Г) Намедонам'],
        'баллҳо': [3, 1, 0, 2]
    },
    {
        'матн': '3. <b>Орзуи кӯдакиатро ёд дори?</b>\n\n💭 <i>Мисол: Шавам духтур, актёр, сурудхон…</i>',
        'ихтиёрҳо': ['А) Ҳа, ёдам ҳаст', 'Б) Не, фаромӯш кардам', 'В) Ман дигар орзу надорам'],
        'баллҳо': [3, 1, 0]
    },
    {
        'матн': '4. <b>"Зершуур" чӣ маъно дорад?</b>\n\n💭 <i>Мисол: Фикрҳои пинҳон, ҳиссиёте ки медонӣ, вале намебинӣ</i>',
        'ихтиёрҳо': ['А) Қувваи дохилӣ', 'Б) Барои равоншиносон', 'В) Ман намефаҳмам, ле ҷолиб аст', 'Г) Ман бовар надорам'],
        'баллҳо': [3, 1, 2, 0]
    },
    {
        'матн': '5. <b>Оё касе зиндагии туро идора мекунад?</b>\n\n💭 <i>Мисол: Ман худам зиндагимро метарошам ё фикрҳои кӯҳна маро идора мекунанд?</i>',
        'ихтиёрҳо': ['А) Ҳа, пай бурдаам', 'Б) Шояд, меҷӯям', 'В) Не, ҳамаашро ман медонам', 'Г) Намефаҳмам'],
        'баллҳо': [3, 2, 1, 0]
    }
]

def гирифтани_натиҷа(балли_кулл):
    if балли_кулл >= 12:
        return "Ман тақдири худамам", """🎯 <b>Ту бедор шудаӣ!</b>

Ту дигар намегӯӣ:
• "Ҳечкас наметавонад бароям ҳаёт созад — ман худам!"
• "Хато кардам — дарс гирифтам, на шикоят"
• "Ман дигар маъюс нестам — ман офарандаам"

✨ <b>Агар туро чунин фикрҳо ҳамроҳӣ мекунанд, ту аллакай роҳро шурӯъ кардӣ!</b>"""
    elif балли_кулл >= 7:
        return "Ман бедор шуда истодаам", """🌱 <b>Ту ба худад савол медиҳӣ, вале ҷавобҳояшон норавшанд</b>

• "Ман орзу доштам… ле фаромӯш кардам"
• "Ман фикр мекунам дигарон дар зиндагим зиёд таъсир доранд"
• "Ман ҳис мекунам зиндагӣ худам нест…"

<b>Ин сатҳ — замини омода аст, вале ту ҳоло об надодаӣ</b>"""
    else:
        return "Ман хомӯш шудам", """💤 <b>Ту шояд фикр мекунӣ, ки зиндагӣ ҳамин аст</b>

• "Ҳарчи шуд, шуд. Ба ман чӣ? Ҳамааш тақдир"
• "Ман ҳеҷ корро дуруст намекунм, беҳтараш хомӯш"

😔 <b>Агар чунин фикрҳо дар ту бошанд — ин маънои бад надорад</b>
<b>Ин маъно дорад: вақти бедорӣ расидааст!</b>"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    
    if db.user_exists(user_id):
        await update.message.reply_text(
            "✨ <b>Шумо аллакай ин тестро гузаронидаед!</b> ✅\n\n"
            f"📅 <b>Тренинг:</b> 8 ноябр 2024\n"
            f"🕐 <b>Соат:</b> 14:00\n"
            f"📍 <b>Ҷой:</b> Душанбе, Профсаюз, Доми София, 3 этаж\n\n"
            f"🔗 <b>Барои сабти ном:</b>\n{REGISTRATION_LINK}",
            parse_mode='HTML'
        )
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data['current_question'] = 0
    context.user_data['score'] = 0

    # Анимация начала
    await update.message.reply_text("🧠 <b>ТЕСТИ ПСИХОЛОГӢ ОҚАЗАТ ШУД...</b>", parse_mode='HTML')
    await asyncio.sleep(1)
    
    await update.message.reply_text("📊 <b>САНҶИШИ ЗЕРШУУР...</b>", parse_mode='HTML')
    await asyncio.sleep(1)

    await update.message.reply_text(
        "🎭 <b>ТЕСТ: ОЁ ТУ ЗИНДАГИИ ХУДРО ХУДАД МЕНАВИСӢ Ё НЕ?</b>\n\n"
        "📌 <b>Тарзи кор:</b>\n"
        "• 5 савол\n"
        "• Барои ҳар ҷавоб балл мегиред\n"
        "• Дар охир ҷамъ карда мешавад\n\n"
        "⏱ <b>Вақт:</b> 2-3 дақиқа\n\n"
        "<i>Барои оғоз тугмаро пахш кунед...</i>",
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

    if current_question < len(саволҳо):
        савол = саволҳо[current_question]
        
        # Прогресс бар
        progress = "🟢" * (current_question + 1) + "⚪" * (len(саволҳо) - current_question - 1)
        
        савол_матн = (
            f"📝 <b>Савол {current_question + 1}/{len(саволҳо)}</b>\n"
            f"{progress}\n\n"
            f"{савол['матн']}\n\n"
            f"<b>Интихоби худро кунед:</b>"
        )

        # Создаем кнопки
        тугмаҳо = []
        for index, ихтиёр in enumerate(савол['ихтиёрҳо']):
            label = ихтиёр.split(')')[0]  # Берем только букву (А, Б, В, Г)
            тугма = InlineKeyboardButton(f"{label}", callback_data=f"ans_{current_question}_{index}")
            тугмаҳо.append([тугма])

        reply_markup = InlineKeyboardMarkup(тугмаҳо)
        await message_method(савол_матн, reply_markup=reply_markup, parse_mode='HTML')
    else:
        # Показываем результат
        балли_кулл = context.user_data.get('score', 0)
        унвони_натиҷа, тавсифи_натиҷа = гирифтани_натиҷа(балли_кулл)
        
        паёми_натиҷа = (
            f"🎯 <b>НАТИҶАИ ТЕСТ</b>\n\n"
            f"🏆 <b>Балли шумо:</b> {балли_кулл}/15\n"
            f"📊 <b>Статус:</b> {унвони_натиҷа}\n\n"
            f"{тавсифи_натиҷа}\n\n"
            f"✍️ <b>ХУЛОСА:</b>\n"
            f"Ҳар як ҷавоб нишон медиҳад, ки ту зиндагиро 'мехонӣ' ё 'менависӣ'.\n"
            f"<b>Агар мехоҳӣ нависанда бошӣ, биё ба тренинг!</b>"
        )

        if isinstance(update_or_query, Update):
            await update_or_query.message.reply_text(паёми_натиҷа, parse_mode='HTML')
        else:
            await update_or_query.message.reply_text(паёми_натиҷа, parse_mode='HTML')
        
        # Информация о тренинге
        паёми_тренинг = (
            f"🎪 <b>ТРЕНИНГИ АСОСӢ</b>\n\n"
            f"👥 <b>Ҷои маҳдуд:</b> 40 нафар\n"
            f"📅 <b>Рӯз:</b> 8 ноябр 2024\n"
            f"🕐 <b>Соат:</b> 14:00\n"
            f"📍 <b>Ҷой:</b> Душанбе, Профсаюз, Доми София, 3 этаж\n\n"
            f"🔗 <b>Барои сабти ном:</b>\n{REGISTRATION_LINK}\n\n"
            f"🌟 <b>Мо дар интизори шумоем!</b>"
        )
        
        if isinstance(update_or_query, Update):
            await update_or_query.message.reply_text(паёми_тренинг, parse_mode='HTML')
        else:
            await context.bot.send_message(chat_id=update_or_query.message.chat_id, text=паёми_тренинг, parse_mode='HTML')

        user_id = update_or_query.from_user.id
        username = update_or_query.from_user.username or "Номаълум"

        db.add_user(user_id, username, унвони_натиҷа, балли_кулл)
        return ConversationHandler.END

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    try:
        parts = query.data.split('_')
        question_index = int(parts[1])
        answer_index = int(parts[2])
    except (ValueError, IndexError):
        await query.message.reply_text("❌ <b>Хато. Лутфан аз нав кӯшиш кунед /start</b>", parse_mode='HTML')
        return ConversationHandler.END

    current_question = context.user_data.get('current_question', 0)

    if question_index != current_question:
        return QUESTIONS

    савол = саволҳо[question_index]
    балл = савол['баллҳо'][answer_index]
    context.user_data['score'] = context.user_data.get('score', 0) + балл

    context.user_data['current_question'] = question_index + 1
    await ask_question(query, context)
    return QUESTIONS

async def admin_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ <b>Дастраси манъ аст</b>", parse_mode='HTML')
        return

    try:
        filename = db.export_to_excel()
        with open(filename, 'rb') as file:
            await update.message.reply_document(
                document=file,
                caption=f"📊 <b>Экспорти дода ({db.get_users_count()} корбар)</b>",
                parse_mode='HTML'
            )
        os.remove(filename)
    except Exception as e:
        await update.message.reply_text(f"❌ <b>Хато дар экспорт: {e}</b>", parse_mode='HTML')

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ <b>Дастраси манъ аст</b>", parse_mode='HTML')
        return

    try:
        count = db.get_users_count()
        users = db.get_all_users()[:5]

        stats_text = (
            f"📈 <b>ОМОРИ СИСТЕМА</b>\n\n"
            f"👥 <b>Ҳамаги корбарон:</b> {count}\n\n"
            f"📋 <b>Охирин сабти ном:</b>\n"
        )

        for i, user in enumerate(users, 1):
            stats_text += f"{i}. @{user[1]} - {user[2]} ({user[3]} балл)\n"

        await update.message.reply_text(stats_text, parse_mode='HTML')
    except Exception as e:
        await update.message.reply_text(f"❌ <b>Хато: {e}</b>", parse_mode='HTML')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('👋 <b>Барои оғози нав /start</b>', parse_mode='HTML')
    return ConversationHandler.END

# ========== WEB SERVER FOR RENDER ==========
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Бот кор мекунад! Telegram: @JannatTrainingBot"

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
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("export", admin_export))
    application.add_handler(CommandHandler("stats", admin_stats))

    logger.info("🤖 Бот оғоз ёфт...")
    application.run_polling()

if __name__ == '__main__':
    main()

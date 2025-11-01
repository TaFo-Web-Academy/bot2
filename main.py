import logging
import sqlite3
import os
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, ContextTypes

# ========== CONFIG ==========
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8430856964:AAHjKGuExWXmpPX8fAGkHuR6wakEBitflks')
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

    def get_users_count(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        return cursor.fetchone()[0]

# ========== BOT LOGIC ==========
db = Database()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

QUESTIONS = 0

questions = [
    {
        'text': '1. <b>Кӣ қарорҳои муҳимро дар зиндагии ту мегирад?</b>\n\n<i>(Мисол: Касб, шавҳар, либос, тарзи зиндагӣ)</i>',
        'options': ['🅐 Худам', '🅑 Оила/дигарон', '🅒 Баъзан ман, баъзан онҳо', '🅓 Метарсам қарор гирам'],
        'scores': [3, 1, 2, 0]
    },
    {
        'text': '2. <b>Агар чизе хато шавад, чӣ фикр мекунӣ?</b>',
        'options': ['🅐 Худам айбдорам, дарс мегирам', '🅑 Дигарон гунаҳкоранд', '🅒 Тақдир ҳамин будааст', '🅓 Намефаҳмам, чаро шуд'],
        'scores': [3, 1, 0, 2]
    },
    {
        'text': '3. <b>Орзуи кӯдакиатро ёд дорӣ?</b>',
        'options': ['🅐 Бале, то ҳол дар ёдам ҳаст', '🅑 Не, фаромӯш кардам', '🅒 Ман дигар орзу надорам'],
        'scores': [3, 1, 0]
    },
    {
        'text': '4. <b>"Зершуур"( Подсознания 🧠) барои ту чӣ маъно дорад?</b>',
        'options': ['🅐 Қувваи пинҳонии дохили ман', '🅑 Гапи равоншиносон', '🅒 Ҷолиб аст, вале намефаҳмам', '🅓 Ба ин чизҳо бовар надорам'],
        'scores': [3, 1, 2, 0]
    },
    {
        'text': '5. <b>Оё ҳис мекунӣ, ки зиндагиятро худат менависӣ?</b>',
        'options': ['🅐 Ҳа, ҳамааш аз ман вобаста аст', '🅑 Баъзан ҳис мекунам', '🅒 Не, фикрҳои кӯҳна маро идора мекунанд', '🅓 Намефаҳмам, ки ки идора мекунад'],
        'scores': [3, 2, 0, 1]
    },
    {
        'text': '6. <b>Агар як варақи хол дошта бошӣ, чӣ менависӣ?</b>\n\n<i>(Мисол: "Мехоҳам хона дошта бошам", "Озодӣ мехоҳам", ё "Намедонам")</i>',
        'options': ['Орзу ё муҳаббат', 'Намедонам', '"Ҳарчи шавад, шавад"'],
        'scores': [3, 1, 0]
    },
    {
        'text': '7. <b>Дар дили ту чӣ овоз аст?</b>',
        'options': ['🅐 Метавонӣ! Шурӯъ кун!', '🅑 Эҳтимол набарояд…', '🅒 Сабр кун, ҳоло не', '🅓 Хомӯш аст'],
        'scores': [3, 1, 2, 0]
    },
    {
        'text': '8. <b>Омодаӣ зиндагиро дигар кунӣ?</b>',
        'options': ['🅐 Бале, ман тайёрам', '🅑 Мехоҳам, вале метарсам', '🅒 Ман намедонам, шояд', '🅓 Не, ҳамин ҳаётро қабул кардам'],
        'scores': [3, 2, 1, 0]
    }
]

def get_result(total_score):
    if total_score >= 21:
        return "Ту нависандаи тақдир ҳастӣ", "🔵 <b>Ту нависандаи тақдир ҳастӣ</b>\n\n• Ту бедор шудаӣ. Хатоҳоятро дарс мебинӣ. Барои зиндагӣ ҷавобгар ҳастӣ.\n• Блоки асосӣ: Шояд суръати баландтар мехоҳӣ, вале роҳат дуруст аст.\n• Қадами аввал: Ба тренинг биё, то эҷоди навбатиро бо зершуур суръат диҳӣ."
    elif total_score >= 13:
        return "Ту дар миёна ҳастӣ", "🟡 <b>Ту дар миёна ҳастӣ</b>\n\n• Ҳис мекунӣ, ки дигар хел мешавад, вале намедонӣ аз куҷо оғоз кунӣ.\n• Блоки асосӣ: Тарс, шубҳа, хотираҳои кӯҳна туро нигоҳ медоранд.\n• Қадами аввал: Ба зершуур нигоҳ кун. Ин тренинг барои ҳамин сохта шудааст."
    else:
        return "Ту хомӯш шудаӣ, вале…", "🔴 <b>Ту хомӯш шудаӣ, вале…</b>\n\n• Бовар надорӣ, ки чизе тағйир ёбад. Ҳис мекунӣ, зиндагӣ маҷбурист.\n• Блоки асосӣ: Таслимшавӣ, эҳсоси нолозим будан, тарси шикаст.\n• Қадами аввал: Дари бедориро кушо — бо ин тренинг. Ӯ аввалин чароғ мешавад."

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
            '🧠 <b>ТЕСТ: "Оё ту зиндагии худро худам менависам?"</b>\n\n'
            '📌 Ҳадаф: Фаҳмидани он ки ту воқеан "нависандаи тақдири худ" ҳастӣ ё зери таъсири зершуур, гузашта, фикрҳои дигарон зиндагӣ мекунӣ.\n\n'
            '📊 8 савол | ⏱ 5 дақиқа\n\n'
            '👉 Барои ҳар ҷавоб хол гир. Дар охир ҷамъ кун. Баъд натиҷаро хон.\n\n'
            'Барои оғоз тугмаро пахш кунед...',
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
                "🎯 <b>НАТИҶАИ ТЕСТИ ШУМО</b>\n\n"
                f"⭐ <b>Балли шумо:</b> {total_score}/24\n"
                f"🌟 <b>Статус:</b> {result_title}\n\n"
                f"{result_description}\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "✍️ <b>ХУЛОСА:</b>\n\n"
                "Ин тест \"диагностика\" аст. Агар холат баланд аст — аъло! Агар паст аст — вақти бедорӣ расидааст.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🎪 <b>ТРЕНИНГ</b>\n\n"
                "📅 <b>Сана:</b> 8 ноябр 2024\n"
                "🕐 <b>Соат:</b> 14:00 - 17:00\n"
                "📍 <b>Ҷой:</b> Душанбе, Профсаюз\n"
                "       Доми София, 3 стаж\n"
                "👥 <b>Ҷойҳо маҳдуд:</b> 40 нафар\n\n"
                "🔗 <b>Барои сабти ном:</b>\n"
                f"{REGISTRATION_LINK}\n\n"
                "✨ <b>Мо дар интизори дидори шумоем!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━"
            )

            await message_method(result_message, parse_mode='HTML')

            user_id = update_or_query.from_user.id
            username = update_or_query.from_user.username or "Номаълум"
            db.add_user(user_id, username, result_title, total_score)
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Ошибка в ask_question: {e}")
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
        return ConversationHandler.END

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Дастрасӣ манъ аст")
        return

    try:
        count = db.get_users_count()
        await update.message.reply_text(f"Ҳамагӣ корбарон: {count}")
    except Exception as e:
        await update.message.reply_text(f"Хато: {e}")

def main():
    try:
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

        logger.info("🤖 Бот оғоз ёфт...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Критическая ошибка бота: {e}")

if __name__ == '__main__':
    main()

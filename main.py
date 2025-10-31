import logging
import sqlite3
import csv
import os
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler
from flask import Flask
import threading

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
        'матн': '1. Кӣ барои зиндагии ту қарор мекунад?\n(Мисол: Ман худам интихоби касб, шавҳар, либосро мекунам ё дигарон мегӯянд?)',
        'ихтиёрҳо': ['А) Худам → 3 хол', 'Б) Оила ё дигарон ', 'В) Баъзан ман, баъзан онҳо',
                     'Г) Метарсам қарор гирам '],
        'баллҳо': [3, 1, 2, 0]
    },
    {
        'матн': '2. Вақте чизе хато мешавад, чӣ мегӯӣ?\n(Мисол: Агар кор нобарор шавад, кӣ гунаҳкор?)',
        'ихтиёрҳо': ['А) Ман айбдорам ', 'Б) Дигарон гунаҳкоранд ', 'В) Тақдир ҳамин будааст ',
                     'Г) Намедонам '],
        'баллҳо': [3, 1, 0, 2]
    },
    {
        'матн': '3. Орзуи кӯдакиатро ёд дори?\n(Мисол: Шавам духтур, актёр, сурудхон…)',
        'ихтиёрҳо': ['А) Ҳа, ёдам ҳаст ', 'Б) Не, фаромӯш кардам', 'В) Ман дигар орзу надорам '],
        'баллҳо': [3, 1, 0]
    },
    {
        'матн': '4. (🧠)"Зершуур" чӣ маъно дорад?\n(Мисол: Фикрҳои пинҳон, ҳиссиёте ки медонӣ, вале намебинӣ)',
        'ихтиёрҳо': ['А) Қувваи дохилӣ ', 'Б) Барои равоншиносон ',
                     'В) Ман намефаҳмам, ле ҷолиб аст ', 'Г) Ман бовар надорам '],
        'баллҳо': [3, 1, 2, 0]
    },
    {
        'матн': '5. Оё касе зиндагии туро идора мекунад?\n(Мисол: Ман худам зиндагимро метарошам ё фикрҳои кӯҳна маро идора мекунанд?)',
        'ихтиёрҳо': ['А) Ҳа, пай бурдаа', 'Б) Шояд, меҷӯям', 'В) Не, ҳамаашро ман медонам ',
                     'Г) Намефаҳмам'],
        'баллҳо': [3, 2, 1, 0]
    },
    {
        'матн': '6. Ту ҳис мекунӣ, ки зиндагиат аз они туст?\n(Мисол: Ин зиндагиро худам сохтаам ё маҷбурона зиндагӣ мекунам?)',
        'ихтиёрҳо': ['А) Ҳа, ман соҳиби зиндагиям ', 'Б) Баъзан чунин ҳис мекунам → ',
                     'В) Не, фикр мекунам барои дигарон зиндагӣ мекунам → 0 хол', 'Г) Ман намедонам '],
        'баллҳо': [3, 1, 0, 2]
    },
    {
        'матн': '7. Овози дили ту чӣ мегӯяд?\n(Мисол: Даруни ту чӣ мегӯяд — рав, бозист, тарс?)',
        'ихтиёрҳо': ['А) Метавонӣ!', 'Б) Эҳтимол набарояд… ', 'В) То ҳол сабр кун',
                     'Г) Хомӯш аст'],
        'баллҳо': [3, 1, 2, 0]
    },
    {
        'матн': '8. (🧠)Зершуур чӣ кор карда метавонад?\n(Мисол: Ба ман кӯмак мекунад ё не?)',
        'ихтиёрҳо': ['А) Маро озод мекунад ', 'Б) Ёрӣ медиҳад, ки бахшам ', 'В) Ман намефаҳмам ',
                     'Г) Ман ба ин чизҳо бовар надорам '],
        'баллҳо': [3, 2, 1, 0]
    },
    {
        'матн': '9. Агар як варақи хол дошта бошӣ, чӣ менависӣ?\n(Мисол: Шояд "Ман мехоҳам хона созам", ё "Намедонам чӣ бихоҳам")',
        'ихтиёрҳо': ['А) Орзую муҳаббат', 'Б) Намедонам ', 'В) "Ҳарчи шавад шавад " '],
        'баллҳо': [3, 1, 0]
    },
    {
        'матн': '10. Омодаӣ зиндагиро худад нависӣ?\n(Мисол: Ба ҷои шикоят, зиндагиро дигар кардан мехоҳӣ?)',
        'ихтиёрҳо': ['А) Ҳа, албатта → 3 хол', 'Б) Мехоҳам, вале метарсам → 2 хол', 'В) Ҳоло намефаҳмам ',
                     'Г) Не, ҳамин ҳаётро қабул кардам'],
        'баллҳо': [3, 2, 1, 0]
    }
]


def гирифтани_натиҷа(балли_кулл):
    if балли_кулл >= 25:
        return "Ман тақдири худамам", """Ту бедор шудаӣ. Ту дигар намегӯӣ:

"Ҳечкас наметавонад бароям ҳаёт созад — ман худам!"
"Хато кардам — дарс гирифтам, на шикоят."
"Ман дигар маъюс нестам — ман офарандаам."
"Қарорҳоро худам мегирам, ман барои зиндагим ҷавобгар ҳастам."

Агар туро чунин фикрҳо ҳамроҳӣ мекунанд, ту аллакай роҳро шурӯъ кардӣ. Тренинги "Тақдири худро бинавис" барои ту суръатдиҳанда мешавад."""
    elif балли_кулл >= 15:
        return "Ман бедор шуда истодаам, вале…", """Ту ба худад савол медиҳӣ, вале ҷавобҳояшон норавшанд.

"Ман орзу доштам… ле фаромӯш кардам."
"Ман фикр мекунам дигарон дар зиндагим зиёд таъсир доранд."
"Ман ҳис мекунам зиндагӣ худам нест…"
"Шояд ман ҳам метавонам, вале метарсам…"
"Ҳозир намедонам чӣ мехоҳам…"

Ин сатҳ — замини омода аст, вале ту ҳоло об надодаӣ.
Тренинг метавонад ин об шавад."""
    else:
        return "Ман хомӯш шудам", """Ту шояд фикр мекунӣ, ки зиндагӣ ҳамин аст.

"Ҳарчи шуд, шуд. Ба ман чӣ? Ҳамааш тақдир."
"Ман ҳеҷ корро дуруст намекунм, беҳтараш хомӯш."
"Орзӯ? Ҳозир вақти орзӯ нест."
"Худамро намешунавам, зиндагим на фаҳм дорад, на роҳ."

Агар чунин фикрҳо дар ту бошанд — ин маънои бад надорад.
Ин маъно дорад: вақти бедорӣ расидааст.

Тренинг метавонад он калид бошад, ки ба ҷони ту "БАС!" мегӯяд ва дарро мекушояд."""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if db.user_exists(user_id):
        await update.message.reply_text(
            "Шумо аллакай ин тестро гузаронидаед! ✅\n\n"
            f"Тренинг: 8 ноябр 2024\n"
            f"Соат: 14:00\n"
            f"Ҷой: Душанбе, Профсаюз, Доми София, 3 этаж\n\n"
            f"Барои сабти ном:\n{REGISTRATION_LINK}"
        )
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data['current_question'] = 0
    context.user_data['score'] = 0

    await update.message.reply_text(
        "🧠 ТЕСТ: Оё ту зиндагии худро худад менависӣ ё не?\n\n"
        "📌 Барои ҳар ҷавоб хол гир. Дар охир ҷамъ кун.\n"
        "Натиҷаҳоро хон, мефаҳмӣ дар куҷо ҳастӣ.\n\n"
        "Барои оғоз тугмаро пахш кунед:"
    )

    await ask_question(update, context)
    return QUESTIONS


async def ask_question(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(update_or_query, Update):
        message_method = update_or_query.message.reply_text
    else:
        message_method = update_or_query.message.reply_text

    current_question = context.user_data.get('current_question', 0)

    if current_question < len(саволҳо):
        савол = саволҳо[current_question]

        савол_матн = (
            f"Савол {current_question + 1}/{len(саволҳо)}\n\n"
            f"{савол['матн']}\n\n"
            "Интихоб кунед:\n"
        )

        for ихтиёр in савол['ихтиёрҳо']:
            савол_матн += f"{ихтиёр}\n"

        # Создаем кнопки динамически в зависимости от количества вариантов
        тугмаҳо = []
        for index in range(len(савол['ихтиёрҳо'])):
            label = "ABCD"[index]  # А, Б, В, Г
            тугма = InlineKeyboardButton(f"{label}", callback_data=f"ans_{current_question}_{index}")
            тугмаҳо.append([тугма])

        reply_markup = InlineKeyboardMarkup(тугмаҳо)
        await message_method(савол_матн, reply_markup=reply_markup)
    else:
        балли_кулл = context.user_data.get('score', 0)
        унвони_натиҷа, тавсифи_натиҷа = гирифтани_натиҷа(балли_кулл)

        паёми_натиҷа = (
            f"📊 НАТИҶАҲО\n\n"
            f"Балли шумо: {балли_кулл}/30\n"
            f"Статус: {унвони_натиҷа}\n\n"
            f"{тавсифи_натиҷа}\n\n"
            f"✍️ ХУЛОСА:\n"
            f"Ҳар як ҷавоб нишон медиҳад, ки ту зиндагиро 'мехонӣ' ё 'менависӣ'.\n"
            f"Агар мехоҳӣ нависанда бошӣ, биё ба тренинг.\n\n"
            f"ТРЕНИНГИ АСОСӢ:\n"
            f"Ҷои маҳдуд: 40 нафар\n"
            f"Рӯз: 8 ноябр 2024\n"
            f"Соат: 14:00\n"
            f"Ҷой: Душанбе, Профсаюз, Доми София, 3 этаж\n\n"
            f"Барои сабти ном:\n{REGISTRATION_LINK}\n\n"
            f"Мо дар интизори шумоем!"
        )

        await message_method(паёми_натиҷа)

        user_id = update_or_query.effective_user.id if isinstance(update_or_query,
                                                                  Update) else update_or_query.from_user.id
        username = (update_or_query.effective_user.username if isinstance(update_or_query, Update)
                    else update_or_query.from_user.username) or "Номаълум"

        db.add_user(user_id, username, унвони_натиҷа, балли_кулл)
        return ConversationHandler.END


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    савол = саволҳо[question_index]
    балл = савол['баллҳо'][answer_index]
    context.user_data['score'] = context.user_data.get('score', 0) + балл

    try:
        await query.message.delete()
    except:
        pass

    context.user_data['current_question'] = question_index + 1
    await ask_question(query, context)
    return QUESTIONS


async def admin_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Дастраси манъ аст")
        return

    try:
        filename = db.export_to_excel()
        with open(filename, 'rb') as file:
            await update.message.reply_document(
                document=file,
                caption=f"📊 Экспорти дода ({db.get_users_count()} корбар)"
            )
        os.remove(filename)
    except Exception as e:
        await update.message.reply_text(f"❌ Хато дар экспорт: {e}")


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Дастраси манъ аст")
        return

    try:
        count = db.get_users_count()
        users = db.get_all_users()[:5]

        stats_text = (
            f"📈 ОМОРИ\n\n"
            f"👥 Ҳамаги корбарон: {count}\n\n"
            f"📋 Охирин сабти ном:\n"
        )

        for i, user in enumerate(users, 1):
            stats_text += f"{i}. @{user[1]} - {user[2]} ({user[3]} балл)\n"

        await update.message.reply_text(stats_text)
    except Exception as e:
        await update.message.reply_text(f"❌ Хато: {e}")


async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Дастраси манъ аст")
        return

    if not context.args:
        await update.message.reply_text("Истифода: /broadcast <паём>")
        return

    message = ' '.join(context.args)
    users = db.get_all_users()
    success = 0
    failed = 0

    status_message = await update.message.reply_text(f"📤 Оғози фиристодан...\nКорбарон: {len(users)}")

    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=message)
            success += 1
        except Exception:
            failed += 1

    result_text = (
        f"📢 НАТИҶАИ ФИРИСТОДАН:\n\n"
        f"✅ Муваффақ: {success}\n"
        f"❌ Номуваффақ: {failed}\n"
        f"📊 Ҳамагӣ: {len(users)}"
    )

    await status_message.edit_text(result_text)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Барои оғози нав /start')
    return ConversationHandler.END


# ========== WEB SERVER FOR RENDER ==========
app = Flask(__name__)


@app.route('/')
def home():
    return "Бот кор мекунад! 🤖"


def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)


def main():
    # Запускаем Flask сервер
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Запускаем бота
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            QUESTIONS: [CallbackQueryHandler(handle_answer, pattern='^ans_')],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("export", admin_export))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CommandHandler("broadcast", admin_broadcast))

    logger.info("🤖 Бот оғоз ёфт...")
    application.run_polling()


if __name__ == '__main__':
    main()

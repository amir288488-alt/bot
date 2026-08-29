```python
import asyncio
import os
import sqlite3

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


# =========================================================
# تنظیمات
# =========================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN داخل فایل .env قرار داده نشده است.")

if not ADMIN_ID:
    raise ValueError("ADMIN_ID داخل فایل .env قرار داده نشده است.")

try:
    ADMIN_ID = int(ADMIN_ID)
except ValueError:
    raise ValueError("ADMIN_ID باید یک آیدی عددی تلگرام باشد.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================================================
# دیتابیس
# =========================================================

DB_FILE = "nova_vpn.db"


def get_connection():
    return sqlite3.connect(DB_FILE)


def init_database():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            used_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    connection.close()


init_database()


# =========================================================
# افزودن اکانت تست
# =========================================================

def add_test_account(account):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO test_accounts (account, used)
        VALUES (?, 0)
        """,
        (account,)
    )

    connection.commit()
    connection.close()


# =========================================================
# دریافت اولین اکانت تست آزاد
# =========================================================

def get_next_test_account(user_id):

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # شروع تراکنش
        connection.execute("BEGIN IMMEDIATE")

        cursor.execute("""
            SELECT id, account
            FROM test_accounts
            WHERE used = 0
            ORDER BY id ASC
            LIMIT 1
        """)

        row = cursor.fetchone()

        if not row:
            connection.rollback()
            return None

        account_id = row[0]
        account = row[1]

        cursor.execute("""
            UPDATE test_accounts
            SET used = 1,
                used_by = ?
            WHERE id = ?
              AND used = 0
        """, (user_id, account_id))

        if cursor.rowcount != 1:
            connection.rollback()
            return None

        connection.commit()

        return account

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# =========================================================
# لیست اکانت‌های تست
# =========================================================

def get_test_accounts():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, account, used, used_by
        FROM test_accounts
        ORDER BY id ASC
    """)

    rows = cursor.fetchall()

    connection.close()

    return rows


# =========================================================
# حذف اکانت تست
# =========================================================

def delete_test_account(account_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM test_accounts
        WHERE id = ?
        """,
        (account_id,)
    )

    deleted = cursor.rowcount

    connection.commit()
    connection.close()

    return deleted


# =========================================================
# آمار تست‌ها
# =========================================================

def get_test_stats():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            COUNT(*),
            SUM(CASE WHEN used = 0 THEN 1 ELSE 0 END),
            SUM(CASE WHEN used = 1 THEN 1 ELSE 0 END)
        FROM test_accounts
    """)

    row = cursor.fetchone()

    connection.close()

    total = row[0] or 0
    available = row[1] or 0
    used = row[2] or 0

    return total, available, used


# =========================================================
# قیمت سرویس‌ها
# =========================================================

PLANS = [
    ("۲ گیگابایت", "130,000"),
    ("۵ گیگابایت", "160,000"),
    ("۱۰ گیگابایت", "210,000"),
    ("۱۵ گیگابایت", "260,000"),
    ("۲۰ گیگابایت", "310,000"),
    ("۳۰ گیگابایت", "410,000"),
    ("۴۰ گیگابایت", "510,000"),
    ("۵۰ گیگابایت", "610,000"),
    ("۱۰۰ گیگابایت", "1,110,000"),
]


# =========================================================
# اطلاعات موقت سفارش‌ها
# =========================================================

pending_orders = {}

waiting_for_receipt = set()

waiting_for_test_account = set()


# =========================================================
# پیام خوشامدگویی
# =========================================================

WELCOME_TEXT = """
⚡ <b>به Nova VPN خوش اومدی!</b>

🚀 به ربات رسمی Nova VPN خوش آمدید.

🔐 سرویس‌های پایدار و پرسرعت
⚡ فعال‌سازی سریع
🛒 خرید آسان
📦 مدیریت سرویس‌ها از داخل ربات

👇 از منوی زیر گزینه موردنظرت رو انتخاب کن:
"""


# =========================================================
# منوی اصلی
# =========================================================

def main_menu():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🟢 🛒 خرید سرویس",
                    callback_data="buy"
                ),
                InlineKeyboardButton(
                    text="🔵 📦 سرویس‌های من",
                    callback_data="my_services"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎁 تست ۱۰۰ مگ",
                    callback_data="test_100"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔴 📖 راهنما",
                    callback_data="help"
                )
            ]
        ]
    )


# =========================================================
# منوی حجم سرویس‌ها
# =========================================================

def plans_menu():

    buttons = []

    for index, (volume, price) in enumerate(PLANS):

        buttons.append([
            InlineKeyboardButton(
                text=f"🔹 {volume} — {price} تومان",
                callback_data=f"plan_{index}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="🔙 بازگشت",
            callback_data="back"
        )
    ])

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


# =========================================================
# منوی مدیریت اکانت‌های تست
# =========================================================

def test_admin_menu():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ افزودن اکانت تست",
                    callback_data="admin_add_test"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 مشاهده اکانت‌ها",
                    callback_data="admin_list_tests"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 حذف اکانت",
                    callback_data="admin_delete_test"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 آمار تست‌ها",
                    callback_data="admin_test_stats"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data="admin_back"
                )
            ]
        ]
    )


# =========================================================
# /start
# =========================================================

@dp.message(CommandStart())
async def start(message: Message):

    await message.answer(
        WELCOME_TEXT,
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


# =========================================================
# تست ۱۰۰ مگ
# =========================================================

@dp.callback_query(F.data == "test_100")
async def test_100(callback: CallbackQuery):

    user_id = callback.from_user.id

    try:

        account = get_next_test_account(user_id)

    except Exception as error:

        print(f"Test account database error: {error}")

        await callback.answer(
            "❌ خطا در سیستم تست. دوباره تلاش کن.",
            show_alert=True
        )

        return

    # -----------------------------------------------------
    # اگر تست تمام شده باشد
    # -----------------------------------------------------

    if not account:

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 بازگشت",
                        callback_data="back"
                    )
                ]
            ]
        )

        await callback.message.edit_text(
            "😔 <b>اکانت تست موجود نیست.</b>\n\n"
            "تمام اکانت‌های تست ۱۰۰ مگ در حال حاضر استفاده شده‌اند.\n\n"
            "⏳ لطفاً بعداً دوباره تلاش کن.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await callback.answer(
            "❌ اکانت تست موجود نیست.",
            show_alert=True
        )

        return

    # -----------------------------------------------------
    # ارسال اکانت تست
    # -----------------------------------------------------

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏠 منوی اصلی",
                    callback_data="back"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        "🎁 <b>تست ۱۰۰ مگ شما آماده است!</b>\n\n"
        "📦 حجم: <b>۱۰۰ مگابایت</b>\n"
        "⏱ نوع: <b>اکانت تست</b>\n\n"
        "🔗 <b>اکانت تست شما:</b>\n\n"
        f"<code>{account}</code>\n\n"
        "⚠️ این اکانت فقط یک بار قابل دریافت است.\n\n"
        "⚡ با تشکر از انتخاب Nova VPN ❤️",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer(
        "🎁 تست ۱۰۰ مگ ارسال شد."
    )


# =========================================================
# خرید سرویس
# =========================================================

@dp.callback_query(F.data == "buy")
async def buy_service(callback: CallbackQuery):

    await callback.message.edit_text(
        "🛒 <b>خرید سرویس</b>\n\n"
        "📅 مدت سرویس: <b>۱ ماهه</b>\n\n"
        "📦 حجم موردنظر خودت رو انتخاب کن:",
        reply_markup=plans_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# انتخاب حجم
# =========================================================

@dp.callback_query(F.data.startswith("plan_"))
async def select_plan(callback: CallbackQuery):

    try:
        index = int(callback.data.split("_")[1])
    except (ValueError, IndexError):

        await callback.answer(
            "❌ سرویس نامعتبر است.",
            show_alert=True
        )

        return

    if index < 0 or index >= len(PLANS):

        await callback.answer(
            "❌ سرویس پیدا نشد.",
            show_alert=True
        )

        return

    volume, price = PLANS[index]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 ادامه پرداخت",
                    callback_data=f"pay_{index}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data="buy"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        f"⚡ <b>سرویس انتخابی</b>\n\n"
        f"📦 حجم: <b>{volume}</b>\n"
        f"📅 مدت: <b>۱ ماه</b>\n"
        f"💰 قیمت: <b>{price} تومان</b>\n\n"
        f"برای ادامه خرید روی دکمه زیر بزن:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# ادامه پرداخت
# =========================================================

@dp.callback_query(F.data.startswith("pay_"))
async def payment(callback: CallbackQuery):

    try:
        index = int(callback.data.split("_")[1])
    except (ValueError, IndexError):

        await callback.answer(
            "❌ سرویس نامعتبر است.",
            show_alert=True
        )

        return

    if index < 0 or index >= len(PLANS):

        await callback.answer(
            "❌ سرویس پیدا نشد.",
            show_alert=True
        )

        return

    volume, price = PLANS[index]

    user_id = callback.from_user.id

    pending_orders[user_id] = {
        "volume": volume,
        "price": price,
        "duration": "۱ ماه",
        "link": None,
        "waiting_for_link": False,
    }

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📸 ارسال رسید",
                    callback_data="send_receipt"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data="buy"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        f"💳 <b>ادامه پرداخت</b>\n\n"
        f"📦 سرویس: <b>{volume}</b>\n"
        f"📅 مدت: <b>۱ ماه</b>\n"
        f"💰 مبلغ: <b>{price} تومان</b>\n\n"
        f"لطفاً مبلغ را به کارت زیر واریز کنید:\n\n"
        f"💳 <b>شماره کارت:</b>\n"
        f"<code>5047061660546587</code>\n\n"
        f"👤 <b>به نام: مجید برزگر</b>\n\n"
        f"بعد از پرداخت، تصویر رسید را از طریق دکمه زیر ارسال کن.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# ارسال رسید
# =========================================================

@dp.callback_query(F.data == "send_receipt")
async def request_receipt(callback: CallbackQuery):

    user_id = callback.from_user.id

    if user_id not in pending_orders:

        await callback.answer(
            "❌ ابتدا یک سرویس انتخاب کن.",
            show_alert=True
        )

        return

    waiting_for_receipt.add(user_id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data="back"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        "📸 <b>ارسال رسید</b>\n\n"
        "لطفاً تصویر رسید پرداخت را همینجا ارسال کن.\n\n"
        "⚠️ تصویر رسید را به صورت عکس ارسال کن.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# دریافت رسید
# =========================================================

@dp.message(F.photo)
async def receive_receipt(message: Message):

    user_id = message.from_user.id

    if user_id not in waiting_for_receipt:
        return

    waiting_for_receipt.discard(user_id)

    order = pending_orders.get(user_id)

    if not order:

        await message.answer(
            "❌ اطلاعات سفارش پیدا نشد.\n"
            "لطفاً دوباره از قسمت خرید سرویس اقدام کن."
        )

        return

    volume = order["volume"]
    price = order["price"]
    duration = order["duration"]

    user = message.from_user

    username = (
        f"@{user.username}"
        if user.username
        else "ندارد"
    )

    admin_text = (
        "🔔 <b>رسید پرداخت جدید</b>\n\n"

        f"👤 نام مشتری: <b>{user.full_name}</b>\n"
        f"🆔 آیدی عددی: <code>{user.id}</code>\n"
        f"📱 یوزرنیم: {username}\n\n"

        f"📦 حجم: <b>{volume}</b>\n"
        f"📅 مدت: <b>{duration}</b>\n"
        f"💰 مبلغ: <b>{price} تومان</b>\n\n"

        "👇 بعد از بررسی پرداخت، لینک اشتراک را برای مشتری ارسال کن."
    )

    admin_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 فرستادن لینک اشتراک",
                    callback_data=f"send_link_{user_id}"
                )
            ]
        ]
    )

    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=message.photo[-1].file_id,
        caption=admin_text,
        reply_markup=admin_keyboard,
        parse_mode="HTML"
    )

    await message.answer(
        "✅ <b>رسید شما ثبت شد.</b>\n\n"
        "مشتری عزیز، رسید شما ثبت و برای ادمین ارسال خواهد شد.\n\n"
        "⏳ پس از پیگیری و تأیید پرداخت، لینک اشتراک شما ارسال خواهد شد.",
        parse_mode="HTML"
    )


# =========================================================
# ادمین - فرستادن لینک اشتراک
# =========================================================

@dp.callback_query(F.data.startswith("send_link_"))
async def admin_send_link(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        await callback.answer(
            "⛔ شما دسترسی ادمین ندارید.",
            show_alert=True
        )

        return

    try:
        user_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):

        await callback.answer(
            "❌ آیدی مشتری نامعتبر است.",
            show_alert=True
        )

        return

    if user_id not in pending_orders:

        await callback.answer(
            "❌ سفارش پیدا نشد.",
            show_alert=True
        )

        return

    pending_orders[user_id]["waiting_for_link"] = True

    await callback.message.answer(
        "🔗 <b>فرستادن لینک اشتراک</b>\n\n"
        f"👤 آیدی مشتری:\n"
        f"<code>{user_id}</code>\n\n"
        "حالا لینک اشتراک را در یک پیام ارسال کن.",
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# ادمین - دریافت لینک
# =========================================================

@dp.message(F.text)
async def receive_text(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    text = message.text.strip()

    # -----------------------------------------------------
    # اگر ادمین در حالت افزودن تست باشد
    # -----------------------------------------------------

    if ADMIN_ID in waiting_for_test_account:

        if not text:

            await message.answer(
                "❌ اکانت خالی است. دوباره ارسال کن."
            )

            return

        add_test_account(text)

        waiting_for_test_account.discard(ADMIN_ID)

        await message.answer(
            "✅ <b>اکانت تست با موفقیت اضافه شد.</b>\n\n"
            "اکانت در لیست تست‌ها قرار گرفت و برای کاربران قابل استفاده است.",
            parse_mode="HTML",
            reply_markup=test_admin_menu()
        )

        return

    # -----------------------------------------------------
    # دریافت لینک اشتراک مشتری
    # -----------------------------------------------------

    target_user_id = None

    for user_id, order in pending_orders.items():

        if order.get("waiting_for_link") is True:

            target_user_id = user_id
            break

    if not target_user_id:
        return

    pending_orders[target_user_id]["waiting_for_link"] = False
    pending_orders[target_user_id]["link"] = text

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏠 منوی اصلی",
                    callback_data="back"
                )
            ]
        ]
    )

    try:

        await bot.send_message(
            chat_id=target_user_id,
            text=(
                "🎉 <b>لینک اشتراک شما آماده است!</b>\n\n"

                "🔗 <b>لینک اشتراک شما:</b>\n\n"

                f"<code>{text}</code>\n\n"

                "⚡ با تشکر از انتخاب Nova VPN ❤️"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await message.answer(
            "✅ لینک با موفقیت برای مشتری ارسال شد."
        )

    except Exception as error:

        await message.answer(
            f"❌ ارسال لینک ناموفق بود:\n\n{error}"
        )


# =========================================================
# سرویس‌های من
# =========================================================

@dp.callback_query(F.data == "my_services")
async def my_services(callback: CallbackQuery):

    user_id = callback.from_user.id

    order = pending_orders.get(user_id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data="back"
                )
            ]
        ]
    )

    if order and order.get("link"):

        await callback.message.edit_text(
            "📦 <b>سرویس‌های من</b>\n\n"

            f"📦 حجم: <b>{order['volume']}</b>\n"
            f"📅 مدت: <b>{order['duration']}</b>\n"
            f"💰 مبلغ: <b>{order['price']} تومان</b>\n\n"

            "🔗 <b>لینک اشتراک:</b>\n"
            f"<code>{order['link']}</code>",

            reply_markup=keyboard,
            parse_mode="HTML"
        )

    else:

        await callback.message.edit_text(
            "📦 <b>سرویس‌های من</b>\n\n"
            "هنوز لینک اشتراکی برای حساب شما ثبت نشده است. ❌",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    await callback.answer()


# =========================================================
# راهنما
# =========================================================

@dp.callback_query(F.data == "help")
async def help_menu(callback: CallbackQuery):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data="back"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        "📖 <b>راهنمای Nova VPN</b>\n\n"

        "🛒 <b>خرید سرویس</b>\n"
        "از قسمت خرید سرویس، حجم موردنظرت را انتخاب کن.\n\n"

        "💳 <b>پرداخت</b>\n"
        "مبلغ سرویس را به شماره کارت اعلام‌شده واریز کن.\n\n"

        "📸 <b>ارسال رسید</b>\n"
        "بعد از پرداخت، تصویر رسید را ارسال کن.\n\n"

        "🎁 <b>تست ۱۰۰ مگ</b>\n"
        "در صورت وجود اکانت تست، یک اکانت تست ۱۰۰ مگ دریافت می‌کنی.\n\n"

        "📦 <b>سرویس‌های من</b>\n"
        "بعد از تأیید پرداخت، لینک اشتراک از این قسمت هم قابل مشاهده است.\n\n"

        "⚡ <b>Nova VPN</b>\n"
        "سریع، ساده و مطمئن.",

        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# بازگشت به منوی اصلی
# =========================================================

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery):

    user_id = callback.from_user.id

    waiting_for_receipt.discard(user_id)

    await callback.message.edit_text(
        WELCOME_TEXT,
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# =========================================================
# مدیریت اکانت‌های تست - ادمین
# =========================================================
# =========================================================


# =========================================================
# /testadmin
# =========================================================

@dp.message(F.text == "/testadmin")
async def test_admin(message: Message):

    if message.from_user.id != ADMIN_ID:

        await message.answer(
            "⛔ شما دسترسی ادمین ندارید."
        )

        return

    total, available, used = get_test_stats()

    await message.answer(
        "🎁 <b>مدیریت اکانت‌های تست</b>\n\n"
        f"📦 کل اکانت‌ها: <b>{total}</b>\n"
        f"✅ اکانت‌های آزاد: <b>{available}</b>\n"
        f"❌ استفاده‌شده: <b>{used}</b>\n\n"
        "از منوی زیر عملیات موردنظر را انتخاب کن:",
        reply_markup=test_admin_menu(),
        parse_mode="HTML"
    )


# =========================================================
# بازگشت به پنل تست
# =========================================================

@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        await callback.answer(
            "⛔ دسترسی ندارید.",
            show_alert=True
        )

        return

    total, available, used = get_test_stats()

    await callback.message.edit_text(
        "🎁 <b>مدیریت اکانت‌های تست</b>\n\n"
        f"📦 کل اکانت‌ها: <b>{total}</b>\n"
        f"✅ اکانت‌های آزاد: <b>{available}</b>\n"
        f"❌ استفاده‌شده: <b>{used}</b>\n\n"
        "از منوی زیر عملیات موردنظر را انتخاب کن:",
        reply_markup=test_admin_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# افزودن اکانت تست
# =========================================================

@dp.callback_query(F.data == "admin_add_test")
async def admin_add_test(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        await callback.answer(
            "⛔ دسترسی ندارید.",
            show_alert=True
        )

        return

    waiting_for_test_account.add(ADMIN_ID)

    await callback.message.answer(
        "➕ <b>افزودن اکانت تست</b>\n\n"
        "اکانت/کانفیگ تست ۱۰۰ مگ را در یک پیام ارسال کن.\n\n"
        "مثلاً:\n"
        "<code>vless://....</code>\n\n"
        "بعد از ارسال، اکانت به صورت خودکار ذخیره می‌شود.",
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# نمایش اکانت‌های تست
# =========================================================

@dp.callback_query(F.data == "admin_list_tests")
async def admin_list_tests(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        await callback.answer(
            "⛔ دسترسی ندارید.",
            show_alert=True
        )

        return

    accounts = get_test_accounts()

    if not accounts:

        text = (
            "📋 <b>لیست اکانت‌های تست</b>\n\n"
            "هیچ اکانتی ثبت نشده است. ❌"
        )

    else:

        lines = [
            "📋 <b>لیست اکانت‌های تست</b>\n"
        ]

        for account_id, account, used, used_by in accounts:

            if used:
                status = "❌ استفاده شده"
                user_info = f"\n👤 کاربر: <code>{used_by}</code>"
            else:
                status = "✅ آزاد"
                user_info = ""

            # برای جلوگیری از خراب شدن HTML
            safe_account = (
                account
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )

            lines.append(
                f"━━━━━━━━━━━━━━\n"
                f"🆔 شماره: <b>{account_id}</b>\n"
                f"📊 وضعیت: <b>{status}</b>"
                f"{user_info}\n"
                f"🔗 <code>{safe_account}</code>"
            )

        text = "\n".join(lines)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 بروزرسانی",
                    callback_data="admin_list_tests"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data="admin_back"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# آمار تست‌ها
# =========================================================

@dp.callback_query(F.data == "admin_test_stats")
async def admin_test_stats(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        await callback.answer(
            "⛔ دسترسی ندارید.",
            show_alert=True
        )

        return

    total, available, used = get_test_stats()

    await callback.message.edit_text(
        "📊 <b>آمار اکانت‌های تست</b>\n\n"
        f"📦 کل اکانت‌ها: <b>{total}</b>\n\n"
        f"✅ اکانت‌های آزاد: <b>{available}</b>\n\n"
        f"❌ اکانت‌های استفاده‌شده: <b>{used}</b>\n\n"
        "🎁 هر اکانت فقط یک بار تحویل داده می‌شود.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 بازگشت",
                        callback_data="admin_back"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# حذف اکانت تست
# =========================================================

@dp.callback_query(F.data == "admin_delete_test")
async def admin_delete_test(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        await callback.answer(
            "⛔ دسترسی ندارید.",
            show_alert=True
        )

        return

    accounts = get_test_accounts()

    if not accounts:

        await callback.answer(
            "❌ هیچ اکانتی وجود ندارد.",
            show_alert=True
        )

        return

    buttons = []

    for account_id, account, used, used_by in accounts:

        status = "❌ استفاده شده" if used else "✅ آزاد"

        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 #{account_id} — {status}",
                callback_data=f"delete_test_{account_id}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="🔙 بازگشت",
            callback_data="admin_back"
        )
    ])

    await callback.message.edit_text(
        "🗑 <b>حذف اکانت تست</b>\n\n"
        "اکانت موردنظر را انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# حذف اکانت انتخاب‌شده
# =========================================================

@dp.callback_query(F.data.startswith("delete_test_"))
async def delete_test(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        await callback.answer(
            "⛔ دسترسی ندارید.",
            show_alert=True
        )

        return

    try:
        account_id = int(
            callback.data.split("_")[2]
        )
    except (ValueError, IndexError):

        await callback.answer(
            "❌ شماره اکانت نامعتبر است.",
            show_alert=True
        )

        return

    deleted = delete_test_account(account_id)

    if deleted:

        await callback.answer(
            "✅ اکانت حذف شد.",
            show_alert=True
        )

    else:

        await callback.answer(
            "❌ اکانت پیدا نشد.",
            show_alert=True
        )

    # نمایش مجدد لیست حذف
    accounts = get_test_accounts()

    if not accounts:

        await callback.message.edit_text(
            "🗑 <b>حذف اکانت تست</b>\n\n"
            "هیچ اکانتی باقی نمانده است.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔙 بازگشت",
                            callback_data="admin_back"
                        )
                    ]
                ]
            ),
            parse_mode="HTML"
        )

        return

    buttons = []

    for acc_id, account, used, used_by in accounts:

        status = "❌ استفاده شده" if used else "✅ آزاد"

        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 #{acc_id} — {status}",
                callback_data=f"delete_test_{acc_id}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="🔙 بازگشت",
            callback_data="admin_back"
        )
    ])

    await callback.message.edit_text(
        "🗑 <b>حذف اکانت تست</b>\n\n"
        "اکانت موردنظر را انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
        parse_mode="HTML"
    )


# =========================================================
# اجرای ربات
# =========================================================

async def main():

    print("===================================")
    print("Nova VPN Bot Started")
    print("Test account system: ENABLED")
    print("Database: nova_vpn.db")
    print("===================================")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
```

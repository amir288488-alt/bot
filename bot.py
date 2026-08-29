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


def init_database():

    connection = sqlite3.connect(DB_FILE)
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
# مدیریت اکانت‌های تست
# =========================================================

def add_test_account(account):

    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute(
        "INSERT INTO test_accounts (account, used) VALUES (?, 0)",
        (account,)
    )

    connection.commit()
    connection.close()


def get_next_test_account(user_id):

    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    # اولین اکانت استفاده‌نشده
    cursor.execute("""
        SELECT id, account
        FROM test_accounts
        WHERE used = 0
        ORDER BY id ASC
        LIMIT 1
    """)

    row = cursor.fetchone()

    if not row:
        connection.close()
        return None

    account_id = row[0]
    account = row[1]

    # همان لحظه اکانت را مصرف‌شده می‌کنیم
    cursor.execute("""
        UPDATE test_accounts
        SET used = 1,
            used_by = ?
        WHERE id = ?
          AND used = 0
    """, (user_id, account_id))

    connection.commit()

    # بررسی اینکه واقعاً خودمان آن را گرفتیم
    if cursor.rowcount != 1:
        connection.close()
        return None

    connection.close()

    return account


def get_test_accounts():

    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, account, used, used_by
        FROM test_accounts
        ORDER BY id ASC
    """)

    rows = cursor.fetchall()

    connection.close()

    return rows


def delete_test_account(account_id):

    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM test_accounts WHERE id = ?",
        (account_id,)
    )

    deleted = cursor.rowcount

    connection.commit()
    connection.close()

    return deleted


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
                    text="🛒 خرید سرویس",
                    callback_data="buy"
                ),
                InlineKeyboardButton(
                    text="📦 سرویس‌های من",
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
                    text="📖 راهنما",
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
# منوی مدیریت تست برای ادمین
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

    # گرفتن اولین اکانت آزاد
    account = get_next_test_account(user_id)

    if not account:

        await callback.message.edit_text(
            "😔 <b>اکانت تست موجود نیست.</b>\n\n"
            "تمام اکانت‌های تست ۱۰۰ مگ در حال حاضر استفاده شده‌اند.\n\n"
            "لطفاً بعداً دوباره تلاش کن.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔙 بازگشت",
                            callback_data="back"
                        )
                    ]
                ]
            ),
            parse_mode="HTML"
        )

        await callback.answer()
        return

    # ارسال تست
    await callback.message.edit_text(
        "🎁 <b>تست ۱۰۰ مگ شما آماده است!</b>\n\n"
        "📦 حجم: <b>۱۰۰ مگابایت</b>\n"
        "⏱ مدت: <b>تست</b>\n\n"
        "🔗 <b>اکانت تست:</b>\n"
        f"<code>{account}</code>\n\n"
        "⚡ با تشکر از انتخاب Nova VPN ❤️",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🏠 منوی اصلی",
                        callback_data="back"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )

    await callback.answer(
        "🎁 تست ۱۰۰ مگ برای شما ارسال شد."
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

    index = int(callback.data.split("_")[1])

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

    index = int(callback.data.split("_")[1])

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

    user_id = int(callback.data.split("_")[2])

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
async def receive_link(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    link = message.text.strip()

    target_user_id = None

    for user_id, order in pending_orders.items():

        if order.get("waiting_for_link") is True:

            target_user_id = user_id
            break

    if not target_user_id:
        return

    pending_orders[target_user_id]["waiting_for_link"] = False
    pending_orders[target_user_id]["link"] = link

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

                f"<code>{link}</code>\n\n"

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
    waiting_for_test_account.discard(user_id)

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
# باز کردن پنل تست
# =========================================================

@dp.message(F.text == "/testadmin")
async def test_admin(message: Message):

    if message.from_user.id != ADMIN_ID:

        await message.answer(
            "⛔ شما دسترسی ادمین ندارید."
        )

        return

    await message.answer(
        "🎁 <b>مدیریت اکانت‌های تست</b>\n\n"
        "از منوی زیر عملیات موردنظر را انتخاب کن:",
        reply_markup=test_admin_menu(),
        parse_mode="HTML"
    )


# =========================================================
# بازگشت ادمین
# =========================================================

@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        await callback.answer(
            "⛔ دسترسی ندارید.",
            show_alert=True
        )

        return

    await callback.message.edit_text(
        "🎁 <b>مدیریت اکانت‌های تست</b>\n\n"
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
        "اکانت/کانفیگ تست را در یک پیام ارسال کن.\n\n"
        "مثلاً:\n"
        "<code>vless://....</code>\n\n"
        "بعد از ارسال، اکانت به لیست تست‌ها اضافه می‌شود.",
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# دریافت اکانت تست از ادمین
# =========================================================

@dp.message(F.text)
async def receive_test_account(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    if ADMIN_ID not in waiting_for_test_account:
        return

    account = message.text.strip()

    if not account:

        await message.answer(
            "❌ اکانت خالی است."
        )

        return

    add_test_account(account)

    waiting_for_test_account.discard(ADMIN_ID)

    await message.answer(
        "✅ <b>اکانت تست با موفقیت اضافه شد.</b>\n\n"
        f"🔗 اکانت:\n"
        f"<code>{account}</code>",
        parse_mode="HTML",
        reply_markup=test_admin_menu()
    )


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

            lines.append(
                f"━━━━━━━━━━━━━━\n"
                f"🆔 شماره: <b>{account_id}</b>\n"
                f"📊 وضعیت: <b>{status}</b>"
                f"{user_info}\n"
                f"🔗 <code>{account}</code>"
            )

        text = "\n".join(lines)

    await callback.message.edit_text(
        text,
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
# تأیید حذف اکانت
# =========================================================

@dp.callback_query(F.data.startswith("delete_test_"))
async def delete_test(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        await callback.answer(
            "⛔ دسترسی ندارید.",
            show_alert=True
        )

        return

    account_id = int(
        callback.data.split("_")[2]
    )

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

    await admin_delete_test(callback)


# =========================================================
# اجرای ربات
# =========================================================

async def main():

    print("Nova VPN Bot Started")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
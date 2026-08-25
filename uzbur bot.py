import os
import asyncio
import sqlite3
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# .env faylini o'qish
load_dotenv()

# ==================== SOZLAMALAR ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
GROUP_ID = int(os.getenv("GROUP_ID", 0))
CARD_NUMBER = os.getenv("CARD_NUMBER", "")

CITY = "Denov"
CALL_CENTER = "102"
DELIVERY_PRICE = 10000

# ==================== RENDER UCHUN WEB SERVER ====================
PORT = int(os.environ.get("PORT", 10000))

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"UzBurBot is running!")

def run_server():
    server = HTTPServer(("0.0.0.0", PORT), SimpleHandler)
    server.serve_forever()

# Serverni alohida oqimda ishga tushiramiz (Render uxlab qolmasligi uchun)
threading.Thread(target=run_server, daemon=True).start()

# ==================== FSM STATES ====================
class OrderState(StatesGroup):
    waiting_for_comment = State()

# ==================== MAHSULOTLAR BAZASI ====================
PRODUCTS_UZ = {
    "🍕 Pitsa": [
        {"name": "Pepperoni Pizza", "price": 180000, "emoji": "🍕"},
        {"name": "Margarita Pizza", "price": 165000, "emoji": "🍕"},
        {"name": "Tovuqli Pizza", "price": 170000, "emoji": "🍕"},
        {"name": "4 Pishloqli Pizza", "price": 180000, "emoji": "🧀"},
    ],
    "🍔 Burgerlar": [
        {"name": "Gamburger", "price": 25000, "emoji": "🍔"},
        {"name": "Chizburger", "price": 30000, "emoji": "🍔"},
        {"name": "Double Chizburger", "price": 45000, "emoji": "🍔"},
        {"name": "Tovuqli Burger", "price": 28000, "emoji": "🍔"},
    ],
    "🌯 Lavash / Shaurma": [
        {"name": "Oddiy Lavash", "price": 22000, "emoji": "🌯"},
        {"name": "Go'shtli Lavash", "price": 28000, "emoji": "🌯"},
        {"name": "Tovuqli Shaurma", "price": 25000, "emoji": "🌯"},
        {"name": "Katta Shaurma", "price": 35000, "emoji": "🌯"},
    ],
    "🍟 Garnirlar": [
        {"name": "Fri Kartoshkasi", "price": 12000, "emoji": "🍟"},
        {"name": "Fri (katta)", "price": 18000, "emoji": "🍟"},
        {"name": "Naggetslar (6 dona)", "price": 20000, "emoji": "🍗"},
    ],
    "🥤 Ichimliklar": [
        {"name": "Coca-Cola 0.5L", "price": 8000, "emoji": "🥤"},
        {"name": "Coca-Cola 1L", "price": 12000, "emoji": "🥤"},
        {"name": "Pepsi 0.5L", "price": 8000, "emoji": "🥤"},
        {"name": "Moxito", "price": 15000, "emoji": "🍋"},
        {"name": "Kofe", "price": 10000, "emoji": "☕"},
    ],
    "🍨 Desertlar": [
        {"name": "Muzqaymoq", "price": 10000, "emoji": "🍨"},
        {"name": "Ponchik", "price": 12000, "emoji": "🍩"},
    ],
}

PRODUCTS_RU = {
    "🍕 Пицца": [
        {"name": "Пепперони Пицца", "price": 180000, "emoji": "🍕"},
        {"name": "Маргарита Пицца", "price": 165000, "emoji": "🍕"},
        {"name": "Куриная Пицца", "price": 170000, "emoji": "🍕"},
        {"name": "Четыре сыра", "price": 180000, "emoji": "🧀"},
    ],
    "🍔 Бургеры": [
        {"name": "Гамбургер", "price": 25000, "emoji": "🍔"},
        {"name": "Чизбургер", "price": 30000, "emoji": "🍔"},
        {"name": "Двойной Чизбургер", "price": 45000, "emoji": "🍔"},
        {"name": "Куриный Бургер", "price": 28000, "emoji": "🍔"},
    ],
    "🌯 Лаваш / Шаурма": [
        {"name": "Обычный Лаваш", "price": 22000, "emoji": "🌯"},
        {"name": "Мясной Лаваш", "price": 28000, "emoji": "🌯"},
        {"name": "Куриная Шаурма", "price": 25000, "emoji": "🌯"},
        {"name": "Большая Шаурма", "price": 35000, "emoji": "🌯"},
    ],
    "🍟 Гарниры": [
        {"name": "Картофель Фри", "price": 12000, "emoji": "🍟"},
        {"name": "Фри (большой)", "price": 18000, "emoji": "🍟"},
        {"name": "Наггетсы (6 шт)", "price": 20000, "emoji": "🍗"},
    ],
    "🥤 Напитки": [
        {"name": "Coca-Cola 0.5L", "price": 8000, "emoji": "🥤"},
        {"name": "Coca-Cola 1L", "price": 12000, "emoji": "🥤"},
        {"name": "Pepsi 0.5L", "price": 8000, "emoji": "🥤"},
        {"name": "Мохито", "price": 15000, "emoji": "🍋"},
        {"name": "Кофе", "price": 10000, "emoji": "☕"},
    ],
    "🍨 Десерты": [
        {"name": "Мороженое", "price": 10000, "emoji": "🍨"},
        {"name": "Пончик", "price": 12000, "emoji": "🍩"},
    ],
}

# ==================== SQLITE BAZA ====================
def init_db():
    conn = sqlite3.connect('uzburbot.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            items TEXT,
            total_price INTEGER,
            phone TEXT,
            location TEXT,
            payment_type TEXT,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_order(user_id, items, total, phone, location, payment, comment):
    conn = sqlite3.connect('uzburbot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO orders (user_id, items, total_price, phone, location, payment_type, comment)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, items, total, phone, location, payment, comment))
    conn.commit()
    conn.close()

# ==================== XOTIRA VA HOLATLAR ====================
dp = Dispatcher(storage=MemoryStorage())
cart = {}
user_lang = {}
user_phone = {}
user_payment = {}
user_comment = {}
selected_product_temp = {}

# ==================== KLAVIATURALAR ====================
def lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O'zbek tili", callback_data="lang_uz")],
        [InlineKeyboardButton(text="🇷🇺 Русский язык", callback_data="lang_ru")]
    ])

def main_menu(lang):
    if lang == "ru":
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🍔 Меню"), KeyboardButton(text="🛒 Корзина")],
                [KeyboardButton(text="📍 Филиалы"), KeyboardButton(text="📞 Связь")],
                [KeyboardButton(text="ℹ️ О нас"), KeyboardButton(text="🌐 Сменить язык")]
            ],
            resize_keyboard=True
        )
    else:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🍔 Menyu"), KeyboardButton(text="🛒 Savat")],
                [KeyboardButton(text="📍 Filiallar"), KeyboardButton(text="📞 Aloqa")],
                [KeyboardButton(text="ℹ️ Biz haqimizda"), KeyboardButton(text="🌐 Tilni o'zgartirish")]
            ],
            resize_keyboard=True
        )

def get_categories(lang):
    keys = list(PRODUCTS_RU.keys() if lang == "ru" else PRODUCTS_UZ.keys())
    buttons = []
    for idx, category in enumerate(keys):
        buttons.append([InlineKeyboardButton(text=category, callback_data=f"cat_{idx}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def products_keyboard(cat_index, lang):
    products_dict = PRODUCTS_RU if lang == "ru" else PRODUCTS_UZ
    keys = list(products_dict.keys())
    category_name = keys[cat_index]
    
    buttons = []
    for index, product in enumerate(products_dict[category_name]):
        buttons.append([
            InlineKeyboardButton(
                text=f"{product['emoji']} {product['name']} - {product['price']:,} so'm",
                callback_data=f"prod_{cat_index}_{index}"
            )
        ])
    
    back_text = "🔙 К категориям" if lang == "ru" else "🔙 Kategoriyalarga qaytish"
    main_text = "🏠 В главноe меню" if lang == "ru" else "🏠 Asosiy bo'limga qaytish"
    
    buttons.append([InlineKeyboardButton(text=back_text, callback_data="back_to_cats")])
    buttons.append([InlineKeyboardButton(text=main_text, callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def product_detail_keyboard(cat_index, lang):
    if lang == "ru":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Добавить в корзину", callback_data="add_to_cart_action")],
            [InlineKeyboardButton(text="🛒 Перейти в корзину", callback_data="go_to_cart")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"cat_{cat_index}")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Savatga qo'shish", callback_data="add_to_cart_action")],
            [InlineKeyboardButton(text="🛒 Savatga o'tish", callback_data="go_to_cart")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"cat_{cat_index}")],
            [InlineKeyboardButton(text="🏠 Asosiy bo'limga qaytish", callback_data="back_to_main")]
        ])

def cart_keyboard(lang):
    if lang == "ru":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")],
            [InlineKeyboardButton(text="🔙 Продолжить покупки", callback_data="back_to_cats")],
            [InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="clear_cart")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")],
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Buyurtma berish", callback_data="checkout")],
            [InlineKeyboardButton(text="🔙 Xaridni davom ettirish", callback_data="back_to_cats")],
            [InlineKeyboardButton(text="🗑 Savatni tozalash", callback_data="clear_cart")],
            [InlineKeyboardButton(text="🏠 Asosiy bo'limga qaytish", callback_data="back_to_main")],
        ])

def payment_keyboard(lang):
    if lang == "ru":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💵 Наличными курьеру", callback_data="pay_cash")],
            [InlineKeyboardButton(text="💳 Картой (Click / Payme)", callback_data="pay_card")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="go_to_cart")],
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💵 Naqd pul (kurerga)", callback_data="pay_cash")],
            [InlineKeyboardButton(text="💳 Karta orqali (Click / Payme)", callback_data="pay_card")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="go_to_cart")],
        ])

def comment_keyboard(lang):
    if lang == "ru":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✍️ Написать свой комментарий", callback_data="add_comment")],
            [InlineKeyboardButton(text="⏭ Без комментариев (пропустить)", callback_data="skip_comment")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✍️ O'z istagimni yozaman", callback_data="add_comment")],
            [InlineKeyboardButton(text="⏭ Izoh kerak emas, davom etamiz", callback_data="skip_comment")]
        ])

# ==================== HANDLERLAR ====================
@dp.message(CommandStart())
async def start(msg: Message):
    await msg.answer(
        "Assalomu alaykum! Xush kelibsiz!\nПожалуйста, выберите язык / Iltimos, tilni tanlang:",
        reply_markup=lang_keyboard()
    )

@dp.callback_query(F.data.startswith("lang_"))
async def set_language(callback: CallbackQuery):
    lang = "ru" if "ru" in callback.data else "uz"
    user_lang[callback.from_user.id] = lang
    
    text = (
        "🇷🇺 Вы выбрали русский язык. Добро пожаловать в UzBurBot!" 
        if lang == "ru" else 
        "🇺🇿 O'zbek tilini tanladingiz. UzBurBot ga xush kelibsiz!"
    )
    
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    await callback.message.answer(text, reply_markup=main_menu(lang))
    await callback.answer()

@dp.message(F.text.in_(["🌐 Tilni o'zgartirish", "🌐 Сменить язык"]))
async def change_lang(msg: Message):
    await msg.answer("Tilni tanlang / Выберите язык:", reply_markup=lang_keyboard())

@dp.message(F.text.in_(["🍔 Menyu", "🍔 Меню"]))
async def show_categories(msg: Message):
    lang = user_lang.get(msg.from_user.id, "uz")
    text = "Выберите категорию:" if lang == "ru" else "Kategoriyani tanlang:"
    await msg.answer(text, reply_markup=get_categories(lang))

@dp.message(F.text.in_(["🛒 Savat", "🛒 Корзина"]))
async def show_cart(msg: Message):
    await display_cart(msg.from_user.id, msg)

async def display_cart(user_id, event):
    lang = user_lang.get(user_id, "uz")
    if user_id not in cart or len(cart[user_id]) == 0:
        text = "🛒 Корзина пуста!" if lang == "ru" else "🛒 Savatingiz bo'sh!"
        if isinstance(event, CallbackQuery):
            try:
                await event.message.edit_text(text, reply_markup=get_categories(lang))
            except Exception:
                await event.message.answer(text, reply_markup=get_categories(lang))
        else:
            await event.answer(text)
        return
    
    items = cart[user_id]
    total = sum(item["price"] for item in items)
    
    if lang == "ru":
        cart_text = "🛒 ВАША КОРЗИНА:\n\n"
        for i, item in enumerate(items, 1):
            cart_text += f"{i}. {item['emoji']} {item['name']} - {item['price']:,} сум\n"
        cart_text += f"\n💰 Итого: {total:,} сум"
        cart_text += f"\n🛵 Доставка: {DELIVERY_PRICE:,} сум"
        cart_text += f"\n✅ Всего к оплате: {total + DELIVERY_PRICE:,} сум"
    else:
        cart_text = "🛒 SIZNING SAVATINGIZ:\n\n"
        for i, item in enumerate(items, 1):
            cart_text += f"{i}. {item['emoji']} {item['name']} - {item['price']:,} so'm\n"
        cart_text += f"\n💰 Jami: {total:,} so'm"
        cart_text += f"\n🛵 Yetkazib berish: {DELIVERY_PRICE:,} so'm"
        cart_text += f"\n✅ Umumiy: {total + DELIVERY_PRICE:,} so'm"
    
    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(cart_text, reply_markup=cart_keyboard(lang))
        except Exception:
            await event.message.answer(cart_text, reply_markup=cart_keyboard(lang))
    else:
        await event.answer(cart_text, reply_markup=cart_keyboard(lang))

@dp.message(F.text.in_(["📍 Filiallar", "📍 Филиалы"]))
async def show_branches(msg: Message):
    lang = user_lang.get(msg.from_user.id, "uz")
    if lang == "ru":
        await msg.answer(f"📍 ФИЛИАЛЫ\n\n🏢 UzBurBot - {CITY}\n📍 Адрес: центр города {CITY}\n🕘 Время работы: 09:00 - 00:01\n📞 Колл-центр: {CALL_CENTER}")
    else:
        await msg.answer(f"📍 FILIALLAR\n\n🏢 UzBurBot - {CITY}\n📍 Manzil: {CITY} shahri, markaz\n🕘 Ish vaqti: 09:00 - 00:01\n📞 Qo'llab-quvvatlash markazi: {CALL_CENTER}")

@dp.message(F.text.in_(["📞 Aloqa", "📞 Связь"]))
async def show_contact(msg: Message):
    lang = user_lang.get(msg.from_user.id, "uz")
    call_text = f"📞 СВЯЗЬ\n\nКолл-центр: {CALL_CENTER}\nВремя работы: 09:00 - 00:01" if lang == "ru" else f"📞 ALOQA\n\nQo'llab-quvvatlash markazi: {CALL_CENTER}\nIsh vaqti: 09:00 - 00:01"
    await msg.answer(call_text)

@dp.message(F.text.in_(["ℹ️ Biz haqimizda", "ℹ️ О нас"]))
async def show_about(msg: Message):
    lang = user_lang.get(msg.from_user.id, "uz")
    about_text = f"ℹ️ UZBURBOT\n\nFastfood yetkazib berish xizmati\n{CITY} shahri, 09:00 - 00:01\n📞 {CALL_CENTER}" if lang == "uz" else f"ℹ️ UZBURBOT\n\nСлужба доставки фастфуда\nГород {CITY}, 09:00 - 00:01\n📞 {CALL_CENTER}"
    await msg.answer(about_text)

@dp.callback_query(F.data.startswith("cat_"))
async def show_products(callback: CallbackQuery):
    cat_index = int(callback.data.replace("cat_", ""))
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, "uz")
    
    products_dict = PRODUCTS_RU if lang == "ru" else PRODUCTS_UZ
    category_name = list(products_dict.keys())[cat_index]
    
    text = f"{category_name}:"
    markup = products_keyboard(cat_index, lang)
    
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data.startswith("prod_"))
async def show_product_detail(callback: CallbackQuery):
    parts = callback.data.split("_")
    cat_index = int(parts[1])
    index = int(parts[2])
    
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, "uz")
    products_dict = PRODUCTS_RU if lang == "ru" else PRODUCTS_UZ
    category_name = list(products_dict.keys())[cat_index]
    product = products_dict[category_name][index]
    
    selected_product_temp[user_id] = product
    
    if lang == "ru":
        caption = f"{product['emoji']} **{product['name']}**\n\n💰 Цена: {product['price']:,} сум\n\nДобавить в корзину?"
    else:
        caption = f"{product['emoji']} **{product['name']}**\n\n💰 Narxi: {product['price']:,} so'm\n\nSavatga qo'shishni xohlaysizmi?"
        
    markup = product_detail_keyboard(cat_index, lang)
    
    try:
        await callback.message.edit_text(text=caption, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text=caption, reply_markup=markup, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "add_to_cart_action")
async def add_to_cart_action(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, "uz")
    product = selected_product_temp.get(user_id)
    
    if not product:
        alert = "❌ Товар не найден!" if lang == "ru" else "❌ Mahsulot topilmadi!"
        await callback.answer(alert, show_alert=True)
        return
        
    if user_id not in cart:
        cart[user_id] = []
        
    cart[user_id].append(product)
    success_text = f"✅ {product['name']} добавлено в корзину!" if lang == "ru" else f"✅ {product['name']} savatga qo'shildi!"
    await callback.answer(success_text, show_alert=True)

@dp.callback_query(F.data == "go_to_cart")
async def go_to_cart_callback(callback: CallbackQuery):
    await display_cart(callback.from_user.id, callback)
    await callback.answer()

@dp.callback_query(F.data == "back_to_cats")
async def back_to_cats(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, "uz")
    text = "Выберите категорию:" if lang == "ru" else "Kategoriyani tanlang:"
    markup = get_categories(lang)
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, "uz")
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("Главное меню:" if lang == "ru" else "Asosiy bo'lim:", reply_markup=main_menu(lang))
    await callback.answer()

@dp.callback_query(F.data == "clear_cart")
async def clear_cart(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, "uz")
    if user_id in cart:
        cart[user_id] = []
    await callback.answer("✅ Корзина очищена!" if lang == "ru" else "✅ Savat tozalandi!")
    text = "🗑 Корзина пуста. Выберите категорию:" if lang == "ru" else "🗑 Savat tozalandi. Kategoriyani tanlang:"
    try:
        await callback.message.edit_text(text, reply_markup=get_categories(lang))
    except Exception:
        await callback.message.answer(text, reply_markup=get_categories(lang))

@dp.callback_query(F.data == "checkout")
async def checkout(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, "uz")
    if user_id not in cart or len(cart[user_id]) == 0:
        await callback.answer("❌ Корзина пуста!" if lang == "ru" else "❌ Savatingiz bo'sh!", show_alert=True)
        return
    
    text = "📝 ОФОРМЛЕНИЕ ЗАКАЗА\n\nКак вы хотите оплатить?" if lang == "ru" else "📝 BUYURTMA RASMIYLASHTIRISH\n\nTo'lovni qanday qilasiz?"
    markup = payment_keyboard(lang)
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except Exception:
        await callback.message.answer(text, reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, "uz")
    payment = ("Наличными" if "cash" in callback.data else "Click / Payme") if lang == "ru" else ("Naqd pul" if "cash" in callback.data else "Click / Payme")
    user_payment[user_id] = payment
    
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    if "card" in callback.data:
        card_msg = (
            f"💳 Переведите сумму на нашу карту:\n<code>{CARD_NUMBER}</code>\n\n"
            f"😊 Почти готово! Хотите оставить пожелание для повара?\n(Например: 'больше майонеза', 'без лука')"
            if lang == "ru" else
            f"💳 Karta raqamimizga o'tkazing:\n<code>{CARD_NUMBER}</code>\n\n"
            f"😊 Buyurtmangiz bo'yicha oshpazga biror narsa aytib qoldirasizmi?\n(Masalan: 'Mayonezi ko'proq bo'lsin', 'Piyoz solmang')"
        )
    else:
        card_msg = (
            f"😊 Почти готово! Хотите оставить пожелание для повара?\n(Например: 'больше майонеза', 'без лука')"
            if lang == "ru" else
            f"😊 Buyurtmangiz bo'yicha oshpazga biror narsa aytib qoldirasizmi?\n(Masalan: 'Mayonezi ko'proq bo'lsin', 'Piyoz solmang')"
        )
        
    await callback.message.answer(card_msg, parse_mode="HTML", reply_markup=comment_keyboard(lang))
    await callback.answer()

@dp.callback_query(F.data == "skip_comment")
async def skip_comment_action(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user_comment[user_id] = "Yo'q" if user_lang.get(user_id) == "uz" else "Нет"
    await ask_phone(callback.message, user_id)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()

@dp.callback_query(F.data == "add_comment")
async def add_comment_action(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, "uz")
    
    text = "✍️ Напишите ваше пожелание:" if lang == "ru" else "✍️ Iltimos, oshpazga o'z istagingizni yozib yuboring:"
    await callback.message.answer(text)
    await state.set_state(OrderState.waiting_for_comment)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()

@dp.message(OrderState.waiting_for_comment)
async def get_user_comment(msg: Message, state: FSMContext):
    user_id = msg.from_user.id
    user_comment[user_id] = msg.text
    await state.clear()
    await ask_phone(msg, user_id)

async def ask_phone(message: Message, user_id: int):
    lang = user_lang.get(user_id, "uz")
    phone_text = "📱 Пожалуйста, отправьте ваш номер телефона:" if lang == "ru" else "📱 Iltimos, telefon raqamingizni yuboring:"
    btn_text = "📱 Отправить номер телефона" if lang == "ru" else "📱 Telefon raqamni yuborish"
    
    phone_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=btn_text, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(phone_text, reply_markup=phone_keyboard)

@dp.message(F.contact)
async def get_phone_contact(msg: Message):
    user_id = msg.from_user.id
    lang = user_lang.get(user_id, "uz")
    phone = msg.contact.phone_number
    user_phone[user_id] = phone
    
    loc_text = "📍 Отлично! Теперь отправьте вашу геолокацию для доставки:" if lang == "ru" else "📍 Endi yetkazib berish uchun lokatsiyangizni yuboring:"
    btn_text = "📍 Отправить локацию" if lang == "ru" else "📍 Lokatsiya yuborish"
    
    location_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=btn_text, request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await msg.answer(loc_text, reply_markup=location_keyboard)

@dp.message(F.location)
async def get_location(msg: Message):
    user_id = msg.from_user.id
    lang = user_lang.get(user_id, "uz")
    location = f"{msg.location.latitude}, {msg.location.longitude}"
    
    if user_id in cart and len(cart[user_id]) > 0:
        items = cart[user_id]
        total = sum(item["price"] for item in items)
        phone = user_phone.get(user_id, "Noma'lum")
        payment = user_payment.get(user_id, "Naqd")
        comment = user_comment.get(user_id, "Yo'q")
        
        phone_formatted = phone if phone.startswith("+") else f"+{phone}"
        order_text = (
            f"🔔 YANGI BUYURTMA\n\n"
            f"👤 Mijoz: {msg.from_user.full_name}\n"
            f"📱 Telefon: {phone_formatted}\n"
            f"📍 Lokatsiya: {location}\n"
            f"💳 To'lov: {payment}\n"
            f"✍️ Istak/Izoh: {comment}\n\n"
            f"🛒 Buyurtma:\n"
        )
        
        for item in items:
            order_text += f"- {item['emoji']} {item['name']} - {item['price']:,} so'm\n"
        
        order_text += f"\n💰 Jami: {total + DELIVERY_PRICE:,} so'm"
        
        try:
            await msg.bot.send_message(ADMIN_ID, order_text)
            if GROUP_ID != 0:
                await msg.bot.send_message(GROUP_ID, order_text)
        except Exception as e:
            print(f"Xatolik: {e}")
        
        success_msg = (
            "✅ ЗАКАЗ ПРИНЯТ!\n\n💳 Оплата: " + payment + "\n🛵 Доставка: 30-50 минут\n📞 " + CALL_CENTER + "\nСпасибо! 😊"
            if lang == "ru" else
            "✅ BUYURTMANGIZ QABUL QILINDI!\n\n💳 To'lov: " + payment + "\n🛵 Yetkazib berish: 30-50 daqiqa\n📞 " + CALL_CENTER + "\nRahmat! 😊"
        )
        
        await msg.answer(success_msg, reply_markup=main_menu(lang))
        
        items_text = ", ".join([f"{item['name']} x1" for item in items])
        save_order(user_id, items_text, total + DELIVERY_PRICE, phone_formatted, location, payment, comment)
        
        cart[user_id] = []
    else:
        await msg.answer("❌ Корзина пуста!" if lang == "ru" else "❌ Savatingiz bo'sh!", reply_markup=main_menu(lang))

# ==================== MAIN ====================
async def main():
    init_db()
    print("✅ Baza ishga tushdi!")
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    print("🚀 UzBurBot muvaffaqiyatli ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

import logging
import json
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove,KeyboardButton, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes
)

# Logging konfiguratsiyasi
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Konfiguratsiya va Fayl Yo'llari ---
BOT_TOKEN = "7269655479:AAFnLkrZtysTbuVrILWCC_J0Wwfx_6xVwjE"  # Bu yerga bot tokeningizni kiriting
ADMIN_IDS = [156402303, 305620565]  # Admin ID'larini kiriting
PRODUCTS_FILE = "products.json"
USERS_FILE = "users.json"
ORDERS_FILE = "orders.json"
BACKUP_DIR = "backups"
LOW_STOCK_THRESHOLD = 5 # Mahsulot zaxirasi shu miqdordan kamaysa, admin ogohlantiriladi

# --- Suhbat Holatlari ---
NAME, PHONE, ADDRESS = range(3)
ADD_PRODUCT_NAME, ADD_PRODUCT_PRICE, ADD_PRODUCT_DESC, ADD_PRODUCT_CAT, ADD_PRODUCT_STOCK, ADD_PRODUCT_PHOTO = range(3, 9)
ADD_CATEGORY_NAME = 9
DELETE_CATEGORY_CONFIRM = 10
DELETE_PRODUCT_CONFIRM = 11
BROADCAST_MESSAGE = 12
SEARCH_PRODUCT = 13
ASK_ORDER_ID = 14 # /myorders uchun
RATE_PRODUCT = 15 # Baholash uchun holat
COMMENT_PRODUCT = 16 # Izoh qoldirish uchun holat

# --- Ma'lumotlarni Boshqarish Klassi ---
class DataManager:
    @staticmethod
    def load_data(filename):
        if not os.path.exists(filename):
            if filename == PRODUCTS_FILE:
                return {'products': [], 'categories': []}
            elif filename == USERS_FILE:
                return [] # Users fayli bo'sh ro'yxat bo'lishi kerak
            elif filename == ORDERS_FILE:
                return []
        with open(filename, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                # Users fayli uchun qo'shimcha tekshirish va tozalash
                if filename == USERS_FILE:
                    if not isinstance(data, list):
                        logger.warning(f"{USERS_FILE} fayli ro'yxat emas. Bo'sh ro'yxat qaytarildi.")
                        return []
                    # Har bir element lug'at ekanligini tekshirish
                    cleaned_data = [item for item in data if isinstance(item, dict) and 'id' in item]
                    if len(cleaned_data) < len(data):
                        logger.warning(f"{USERS_FILE} faylida noto'g'ri formatdagi foydalanuvchilar topildi va olib tashlandi.")
                    return cleaned_data
                return data
            except json.JSONDecodeError:
                logger.error(f"Faylni yuklashda xato: {filename} bo'sh yoki noto'g'ri formatda. Bo'sh ma'lumot qaytarildi.")
                if filename == PRODUCTS_FILE:
                    return {'products': [], 'categories': []}
                elif filename == USERS_FILE:
                    return []
                elif filename == ORDERS_FILE:
                    return []

    @staticmethod
    def save_data(filename, data):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Faylni saqlashda xato: {filename}, {e}")
            return False

    @staticmethod
    def backup_data():
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for filename in [PRODUCTS_FILE, USERS_FILE, ORDERS_FILE]:
            if os.path.exists(filename):
                backup_path = os.path.join(BACKUP_DIR, f"{filename}_{timestamp}.bak")
                try:
                    with open(filename, 'rb') as src, open(backup_path, 'wb') as dst:
                        dst.write(src.read())
                    logger.info(f"Zaxira nusxasi yaratildi: {backup_path}")
                except Exception as e:
                    logger.error(f"Zaxira nusxasi yaratishda xato: {filename}, {e}")

# --- Global Ma'lumotlar ---
db = DataManager.load_data(PRODUCTS_FILE)
users = DataManager.load_data(USERS_FILE)
orders = DataManager.load_data(ORDERS_FILE)

# --- Yordamchi Funktsiyalar ---
def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_product_by_id(product_id):
    global db
    db = DataManager.load_data(PRODUCTS_FILE) # Eng so'nggi ma'lumotni yuklash
    products = db.get('products', [])
    return next((p for p in products if p.get('id') == product_id), None)

def get_category_name(slug):
    global db
    db = DataManager.load_data(PRODUCTS_FILE) # Eng so'nggi ma'lumotni yuklash
    categories = db.get('categories', [])
    category = next((c for c in categories if c.get('slug') == slug), None)
    return category['name'] if category else "Noma'lum Kategoriya"

def format_price(price):
    return f"{price:,}".replace(",", " ")

def get_user_cart(user_id):
    global users
    users = DataManager.load_data(USERS_FILE) # Eng so'nggi ma'lumotni yuklash
    user_data = next((u for u in users if u.get('id') == user_id), None)
    return user_data.get('cart', []) if user_data else []

def update_user_cart(user_id, cart):
    global users
    users = DataManager.load_data(USERS_FILE) # Eng so'nggi ma'lumotni yuklash
    user_found = False
    for i, u in enumerate(users):
        if u.get('id') == user_id:
            users[i]['cart'] = cart
            user_found = True
            break
    if not user_found:
        # Yangi foydalanuvchi ma'lumotlarini to'g'ri formatda qo'shish
        users.append({'id': user_id, 'cart': cart, 'last_name': '', 'last_phone': '', 'username': '', 'first_name': ''}) 
    return DataManager.save_data(USERS_FILE, users)

def get_user_info(user_id):
    global users
    users = DataManager.load_data(USERS_FILE)
    user_data = next((u for u in users if u.get('id') == user_id), None)
    return user_data

def update_user_info(user_id, key, value):
    global users
    users = DataManager.load_data(USERS_FILE)
    user_found = False
    for i, u in enumerate(users):
        if u.get('id') == user_id:
            users[i][key] = value
            user_found = True
            break
    if not user_found:
        new_user_data = {'id': user_id, 'cart': [], 'last_name': '', 'last_phone': '', 'username': '', 'first_name': ''} # Boshlang'ich ma'lumotlar bilan
        new_user_data[key] = value
        users.append(new_user_data)
    return DataManager.save_data(USERS_FILE, users)

# --- Bot Buyruqlari va CallbackQuery Funktsiyalari ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Botni ishga tushiradi va asosiy menyuni ko'rsatadi."""
    user = update.effective_user
    user_id = user.id

    # Foydalanuvchini ro'yxatga olish yoki yangilash
    global users
    users = DataManager.load_data(USERS_FILE)
    
    # Hozirgi foydalanuvchining ma'lumotlarini tekshirish
    user_exists = False
    for u in users:
        # Faqat lug'atlar uchun .get() ni chaqiring
        if isinstance(u, dict) and u.get('id') == user_id:
            user_exists = True
            break
    
    if not user_exists:
        users.append({'id': user_id, 'username': user.username, 'first_name': user.first_name, 'cart': [], 'last_name': '', 'last_phone': ''})
        DataManager.save_data(USERS_FILE, users)
        logger.info(f"Yangi foydalanuvchi qo'shildi: {user_id} (@{user.username})")

    keyboard = [
        [InlineKeyboardButton("🛍️ Katalog", callback_data="catalog")],
        [InlineKeyboardButton("🛒 Savat", callback_data="show_cart")],
        [InlineKeyboardButton("📋 Buyurtmalarim", callback_data="my_orders")],
        [InlineKeyboardButton("🔎 Mahsulot izlash", callback_data="search_product_start")],
        [InlineKeyboardButton("❓ Yordam", callback_data="help")]
    ]
    
    # Admin tugmasini qo'shish
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("⚙️ Admin Paneli", callback_data="admin_panel")])

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            f"Assalomu alaykum, {user.first_name}! 🤗\n\n"
            "O'yinchoqlar do'konimizga xush kelibsiz! 🎉",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    else:
        await update.message.reply_html(
            f"Assalomu alaykum, {user.first_name}! 🤗\n\n"
            "O'yinchoqlar do'konimizga xush kelibsiz! 🎉",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kategoriyalarni ko'rsatadi."""
    query = update.callback_query
    await query.answer()

    global db
    db = DataManager.load_data(PRODUCTS_FILE)
    categories = db.get('categories', [])

    if not categories:
        await query.edit_message_text(
            "Hozircha kategoriyalar mavjud emas. Admin panelidan kategoriya qo'shishingiz mumkin.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")]
            ])
        )
        return

    keyboard = []
    for category in categories:
        keyboard.append([InlineKeyboardButton(category['name'], callback_data=f"cat_{category['slug']}")])
    keyboard.append([InlineKeyboardButton("⬅️ Bosh sahifa", callback_data="start")])

    await query.edit_message_text(
        "Kategoriyani tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ... (oldingi kod) ...

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tanlangan kategoriyadagi mahsulotlarni ko'rsatadi."""
    query = update.callback_query
    await query.answer()
    category_slug = query.data.split('_')[1]

    global db
    db = DataManager.load_data(PRODUCTS_FILE)
    products = [p for p in db.get('products', []) if p.get('category') == category_slug and not p.get('hidden', False)]

    keyboard = []
    if not products:
        message_text = f"'{get_category_name(category_slug)}' kategoriyasida hozircha mahsulotlar mavjud emas."
        keyboard.append([InlineKeyboardButton("⬅️ Kategoriyalarga qaytish", callback_data="catalog")])
        keyboard.append([InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")])
    else:
        message_text = f"<b>{get_category_name(category_slug)}</b> kategoriyasidagi mahsulotlar:"
        for product in products:
            keyboard.append([InlineKeyboardButton(f"{product['name']} - {format_price(product['price'])} so'm", callback_data=f"prod_{product['id']}")])
        keyboard.append([InlineKeyboardButton("⬅️ Kategoriyalarga qaytish", callback_data="catalog")])
        keyboard.append([InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")])

    # Yangi o'zgarish shu yerda:
    # Agar oldingi xabar rasm bo'lsa, uni tahrirlash o'rniga o'chiramiz
    # va yangi tekst xabarini yuboramiz.
    if query.message.photo: # Agar hozirgi xabar rasm bo'lsa
        await query.message.delete() # Eski rasmli xabarni o'chirish
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    else: # Aks holda, matnli xabarni tahrirlaymiz
        await query.edit_message_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

# ... (qolgan kod) ...    

async def show_product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mahsulot haqida batafsil ma'lumotni ko'rsatadi."""
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.split('_')[1])

    product = get_product_by_id(product_id)
    if not product:
        await query.edit_message_text("Mahsulot topilmadi.", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")]
        ]))
        return

    message_text = (
        f"<b>{product.get('name')}</b>\n\n"
        f"🏷️ <b>Narxi:</b> {format_price(product.get('price', 0))} so'm\n"
        f"📝 <b>Tavsifi:</b> {product.get('description', 'Tavsif yoʻq')}\n"
        f"📦 <b>Zaxira:</b> {product.get('stock', 0)} ta\n"
        f"📂 <b>Kategoriya:</b> {get_category_name(product.get('category', ''))}"
    )

    keyboard = [
        [InlineKeyboardButton("🛒 Savatga qo'shish", callback_data=f"addcart_{product_id}")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data=f"cat_{product.get('category')}")]
    ]

    if product.get('photo_id'):
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=product['photo_id'],
            caption=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        await query.delete_message() # Eski xabarni o'chirish
    else:
        await query.edit_message_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mahsulotni savatga qo'shadi."""
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.split('_')[1])
    user_id = query.from_user.id

    product = get_product_by_id(product_id)
    if not product:
        await query.answer("Mahsulot topilmadi.")
        return

    if product.get('stock', 0) <= 0:
        await query.answer("Kechirasiz, bu mahsulot hozirda zaxirada mavjud emas.")
        return

    cart = get_user_cart(user_id)
    item_found = False
    for item in cart:
        if item['id'] == product_id:
            if item['quantity'] < product['stock']:
                item['quantity'] += 1
                item['total'] = item['quantity'] * item['price']
                item_found = True
                await query.answer(f"'{product['name']}' savatga qo'shildi! Savatda {item['quantity']} ta.")
            else:
                await query.answer("Kechirasiz, mahsulot zaxirasi yetarli emas.")
            break
    
    if not item_found:
        if product['stock'] > 0:
            cart.append({
                'id': product_id,
                'name': product['name'],
                'price': product['price'],
                'quantity': 1,
                'total': product['price'],
                'category': product['category']
            })
            await query.answer(f"'{product['name']}' savatga qo'shildi!")
        else:
            await query.answer("Kechirasiz, bu mahsulot hozirda zaxirada mavjud emas.")

    if not update_user_cart(user_id, cart):
        await query.answer("Xatolik yuz berdi, iltimos qaytadan urinib ko'ring.")

    # Mahsulot tafsilotlari sahifasini yangilash
    product_detail_message = (
        f"<b>{product.get('name')}</b>\n\n"
        f"🏷️ <b>Narxi:</b> {format_price(product.get('price', 0))} so'm\n"
        f"📝 <b>Tavsifi:</b> {product.get('description', 'Tavsif yoʻq')}\n"
        f"📦 <b>Zaxira:</b> {product.get('stock', 0)} ta\n"
        f"📂 <b>Kategoriya:</b> {get_category_name(product.get('category', ''))}"
    )

    keyboard = [
        [InlineKeyboardButton("🛒 Savatga qo'shish", callback_data=f"addcart_{product_id}")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data=f"cat_{product.get('category')}")]
    ]
    
    # Rasmli xabarni yangilash imkoni yo'q, shuning uchun qayta yuborish kerak
    if product.get('photo_id'):
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=product['photo_id'],
            caption=product_detail_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        await query.delete_message()
    else:
        await query.edit_message_text(
            product_detail_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )


async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Savatdagi mahsulotlarni ko'rsatadi."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    cart = get_user_cart(user_id)
    if not cart:
        await query.edit_message_text(
            "Sizning savatingiz bo'sh. 😔",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛍️ Xarid qilish", callback_data="catalog")],
                [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")]
            ])
        )
        return

    message_text = "🛒 <b>Sizning savatingiz:</b>\n\n"
    total_price = 0
    keyboard = []

    for item in cart:
        message_text += (
            f"▪️ {item['name']}\n"
            f"   {format_price(item['price'])} so'm x {item['quantity']} = {format_price(item['total'])} so'm\n"
        )
        total_price += item['total']
        keyboard.append([
            InlineKeyboardButton(f"-", callback_data=f"minus_{item['id']}"),
            InlineKeyboardButton(f"{item['quantity']}", callback_data="no_op"), # No-op button
            InlineKeyboardButton(f"+", callback_data=f"plus_{item['id']}"),
            InlineKeyboardButton(f"❌", callback_data=f"remove_{item['id']}")
        ])
    
    message_text += f"\n<b>Umumiy: {format_price(total_price)} so'm</b>"

    keyboard.append([InlineKeyboardButton("✅ Buyurtma berish", callback_data="checkout")])
    keyboard.append([InlineKeyboardButton("🗑️ Savatni tozalash", callback_data="clear_cart")])
    keyboard.append([InlineKeyboardButton("⬅️ Xaridni davom ettirish", callback_data="catalog")]) # "orqaga qaytish"
    keyboard.append([InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")])


    await query.edit_message_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def adjust_cart_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Savatdagi mahsulot miqdorini o'zgartiradi yoki o'chiradi."""
    query = update.callback_query
    await query.answer()
    action, product_id_str = query.data.split('_')
    product_id = int(product_id_str)
    user_id = query.from_user.id

    cart = get_user_cart(user_id)
    product = get_product_by_id(product_id)

    if not product:
        await query.answer("Mahsulot topilmadi.")
        await show_cart(update, context) # Savatni qayta yuklash
        return

    new_cart = []
    item_modified = False
    
    for item in cart:
        if item['id'] == product_id:
            if action == 'plus':
                if item['quantity'] < product['stock']:
                    item['quantity'] += 1
                    item['total'] = item['quantity'] * item['price']
                    new_cart.append(item)
                    item_modified = True
                else:
                    await query.answer("Kechirasiz, mahsulot zaxirasi yetarli emas.")
                    new_cart.append(item) # O'zgartirmasdan qo'shish
            elif action == 'minus':
                if item['quantity'] > 1:
                    item['quantity'] -= 1
                    item['total'] = item['quantity'] * item['price']
                    new_cart.append(item)
                    item_modified = True
                else: # Agar 1 ta bo'lsa va minus bosilsa, o'chirish
                    await query.answer(f"'{item['name']}' savatdan olib tashlandi.")
                    item_modified = True
            elif action == 'remove':
                await query.answer(f"'{item['name']}' savatdan olib tashlandi.")
                item_modified = True
        else:
            new_cart.append(item)

    if not item_modified and action == 'remove': # Agar mahsulot topilmasa, lekin o'chirish buyrug'i bo'lsa
        await query.answer("Savatdan olib tashlash uchun mahsulot topilmadi.")
    
    if not update_user_cart(user_id, new_cart):
        await query.answer("Xatolik yuz berdi, iltimos qaytadan urinib ko'ring.")
    
    # Savatni yangilash
    await show_cart(update, context)

async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Savatni butunlay tozalaydi."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if update_user_cart(user_id, []):
        await query.edit_message_text(
            "Savat muvaffaqiyatli tozalandi! 👍",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛍️ Xarid qilish", callback_data="catalog")],
                [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")]
            ])
        )
    else:
        await query.answer("Savatni tozalashda xato yuz berdi.")

# --- Buyurtma Berish Suhbatlari ---
async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Buyurtma berish jarayonini boshlaydi."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    cart = get_user_cart(user_id)

    if not cart:
        await query.edit_message_text(
            "Sizning savatingiz bo'sh, buyurtma berish mumkin emas.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛍️ Xarid qilish", callback_data="catalog")],
                [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")]
            ])
        )
        return ConversationHandler.END

    # Foydalanuvchining oxirgi kiritilgan ma'lumotlarini yuklash
    user_info = get_user_info(user_id)
    last_name = user_info.get('last_name', '')
    
    if last_name:
        await query.message.reply_text(
            f"Ismingizni kiriting (oxirgi kiritilgan: <b>{last_name}</b>, uni tasdiqlash uchun shunchaki yuboring):",
            parse_mode='HTML'
        )
    else:
        await query.message.reply_text("Ismingizni kiriting:")
    
    return NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ismni qabul qiladi va telefon raqamini so'raydi."""
    user_name = update.message.text.strip()
    if not user_name:
        await update.message.reply_text("Ism bo'sh bo'lishi mumkin emas. Iltimos, ismingizni kiriting:")
        return NAME

    context.user_data['name'] = user_name
    update_user_info(update.effective_user.id, 'last_name', user_name) # Ismni saqlash

    user_info = get_user_info(update.effective_user.id)
    last_phone = user_info.get('last_phone', '')

    # Telefon raqamini so'rash uchun ReplyKeyboardMarkup yaratish
    contact_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📞 Raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    if last_phone:
        await update.message.reply_text(
            f"Telefon raqamingizni kiriting (oxirgi kiritilgan: <b>{last_phone}</b>, uni tasdiqlash uchun shunchaki yuboring, yoki 'Raqamni yuborish' tugmasini bosing):",
            reply_markup=contact_keyboard, # E'tibor bering: endi contact_keyboard (ReplyKeyboardMarkup) ishlatilyapti
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            "Telefon raqamingizni kiriting (masalan: +998901234567, yoki 'Raqamni yuborish' tugmasini bosing):",
            reply_markup=contact_keyboard # E'tibor bering: endi contact_keyboard (ReplyKeyboardMarkup) ishlatilyapti
        )
    return PHONE

async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Telefon raqamini qabul qiladi va manzilni so'raydi."""
    phone_number = None

    # Foydalanuvchi "Raqamni yuborish" tugmasini bosgan bo'lsa
    if update.message.contact:
        phone_number = update.message.contact.phone_number
    # Foydalanuvchi raqamni qo'lda yozgan bo'lsa
    elif update.message.text:
        phone_number = update.message.text.strip()

    if not phone_number:
        await update.message.reply_text("Telefon raqami bo'sh bo'lishi mumkin emas. Iltimos, telefon raqamingizni kiriting:")
        return PHONE

    context.user_data['phone'] = phone_number
    update_user_info(update.effective_user.id, 'last_phone', phone_number) # Raqamni saqlash

    # Raqam qabul qilingandan so'ng, Reply klaviaturani yashirish
    await update.message.reply_text("Raqamingiz qabul qilindi. Endi manzilingizni kiriting:", reply_markup=ReplyKeyboardRemove())

    return ADDRESS

async def process_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Buyurtmani yakunlaydi va tasdiqlaydi."""
    address = update.message.text.strip()
    if not address:
        await update.message.reply_text("Manzil bo'sh bo'lishi mumkin emas. Iltimos, yetkazib berish manzilingizni kiriting:")
        return ADDRESS

    user_id = update.effective_user.id
    user_name = context.user_data['name']
    user_phone = context.user_data['phone']
    
    cart = get_user_cart(user_id)
    if not cart:
        await update.message.reply_text("Sizning savatingiz bo'sh. Buyurtma berish mumkin emas.")
        return ConversationHandler.END

    total_price = sum(item['total'] for item in cart)

    # Buyurtma obyektini yaratish
    order_id = datetime.now().strftime("%Y%m%d%H%M%S") + str(user_id)[-4:] # Unique ID
    order_data = {
        'id': order_id,
        'customer': {
            'user_id': user_id,
            'username': update.effective_user.username,
            'name': user_name,
            'phone': user_phone,
            'address': address
        },
        'items': cart,
        'total': total_price,
        'status': 'pending', # Buyurtma holati
        'created_at': datetime.now().isoformat()
    }

    global orders
    orders = DataManager.load_data(ORDERS_FILE)
    orders.append(order_data)

    if DataManager.save_data(ORDERS_FILE, orders):
        # Mahsulot zaxirasini yangilash
        global db
        db_products = db.get('products', [])
        low_stock_alerts = []

        for cart_item in cart:
            for i, product in enumerate(db_products):
                if product['id'] == cart_item['id']:
                    if product['stock'] >= cart_item['quantity']:
                        db_products[i]['stock'] -= cart_item['quantity']
                        if db_products[i]['stock'] <= LOW_STOCK_THRESHOLD:
                            low_stock_alerts.append(f"⚠️ `{db_products[i]['name']}` mahsulotining zaxirasi kam qoldi: {db_products[i]['stock']} ta!")
                    else:
                        await update.message.reply_text(f"Kechirasiz, {product['name']} mahsulotidan yetarli miqdorda mavjud emas. Buyurtma bekor qilindi.")
                        # Stok yetmaganda buyurtmani bekor qilish yoki qayta so'rash
                        return ConversationHandler.END # Hozircha suhbatni tugatish
                    break
        
        db['products'] = db_products
        DataManager.save_data(PRODUCTS_FILE, db)

        # Savatni tozalash
        update_user_cart(user_id, [])

        order_summary = f"🎉 <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        order_summary += f"<b>Buyurtma ID:</b> <code>#{order_id}</code>\n"
        order_summary += f"<b>Mijoz:</b> {user_name}\n"
        order_summary += f"<b>Telefon:</b> {user_phone}\n"
        order_summary += f"<b>Manzil:</b> {address}\n\n"
        order_summary += "<b>Mahsulotlar:</b>\n"
        for item in cart:
            order_summary += f"▪️ {item['name']} x {item['quantity']} = {format_price(item['total'])} so'm\n"
        order_summary += f"\n<b>Umumiy narx: {format_price(total_price)} so'm</b>\n\n"
        order_summary += "Tez orada siz bilan bog'lanamiz!"

        await update.message.reply_html(order_summary,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")]
            ])
        )

        # Adminlarga yangi buyurtma haqida xabar berish
        admin_notification = f"🔔 <b>Yangi buyurtma!</b>\n"
        admin_notification += order_summary
        admin_notification += f"\nBuyurtmani ko'rish: /vieworder_{order_id}"

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=admin_notification, parse_mode='HTML')
            except Exception as e:
                logger.error(f"Admin {admin_id} ga yangi buyurtma haqida xabar yuborilmadi: {e}")
        
        # Adminlarga past stok haqida ogohlantirish
        if low_stock_alerts:
            stock_alert_message = "⚠️ <b>Zaxira tugash arafasida bo'lgan mahsulotlar:</b>\n\n" + "\n".join(low_stock_alerts)
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(chat_id=admin_id, text=stock_alert_message, parse_mode='HTML')
                except Exception as e:
                    logger.error(f"Admin {admin_id} ga zaxira ogohlantirishi yuborilmadi: {e}")

    else:
        await update.message.reply_text("Buyurtma berishda xato yuz berdi. Iltimos, qaytadan urinib ko'ring.")

    context.user_data.clear() # Foydalanuvchi ma'lumotlarini tozalash
    return ConversationHandler.END


# --- Mahsulot izlash funksiyasi ---
async def search_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mahsulot izlash suhbatini boshlaydi."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "🔎 <b>Mahsulot izlash</b>\n\n"
        "Iltimos, mahsulot nomini kiriting:",
        parse_mode='HTML'
    )
    return SEARCH_PRODUCT

async def search_product_by_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kiritilgan nom bo'yicha mahsulotlarni izlaydi."""
    search_query = update.message.text.strip().lower()
    if not search_query:
        await update.message.reply_text("Qidiruv so'rovi bo'sh bo'lishi mumkin emas. Iltimos, qaytadan kiriting:")
        return SEARCH_PRODUCT

    global db
    db = DataManager.load_data(PRODUCTS_FILE)
    products = db.get('products', [])
    
    found_products = [p for p in products if search_query in p.get('name', '').lower() and not p.get('hidden', False)]

    if not found_products:
        await update.message.reply_text(
            f"'{search_query}' so'rovi bo'yicha mahsulot topilmadi. 😔",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Qidiruvni qayta boshlash", callback_data="search_product_start")],
                [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")]
            ])
        )
        return ConversationHandler.END
    
    keyboard = []
    message_text = "🔎 <b>Izlash natijalari:</b>\n\n"
    for product in found_products:
        message_text += f"▪️ {product['name']} - {format_price(product['price'])} so'm\n"
        keyboard.append([InlineKeyboardButton(f"{product['name']}", callback_data=f"prod_{product['id']}")])
    
    keyboard.append([InlineKeyboardButton("↩️ Qidiruvni qayta boshlash", callback_data="search_product_start")])
    keyboard.append([InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")])

    await update.message.reply_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    return ConversationHandler.END


# --- Foydalanuvchi buyurtmalari tarixi ---
async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchining buyurtma tarixini ko'rsatadi."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    global orders
    orders = DataManager.load_data(ORDERS_FILE)
    user_orders = [o for o in orders if o.get('customer', {}).get('user_id') == user_id]

    if not user_orders:
        await query.edit_message_text(
            "Sizning hali hech qanday buyurtmangiz yo'q. 😔",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛍️ Xarid qilish", callback_data="catalog")],
                [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")]
            ])
        )
        return

    # Eng yangi buyurtmalarni yuqoriga chiqarish
    user_orders.sort(key=lambda x: datetime.fromisoformat(x.get('created_at')), reverse=True)

    message_text = "📋 <b>Sizning buyurtmalaringiz:</b>\n\n"
    keyboard = []

    for order in user_orders[:5]: # So'nggi 5 ta buyurtmani ko'rsatish
        order_id = order.get('id', 'N/A')
        total = format_price(order.get('total', 0))
        status = order.get('status', 'Noma\'lum')
        created_at = datetime.fromisoformat(order.get('created_at')).strftime("%Y-%m-%d %H:%M")

        message_text += (
            f"<b>Buyurtma ID:</b> <code>#{order_id}</code>\n"
            f"<b>Holati:</b> {status.capitalize()}\n"
            f"<b>Umumiy:</b> {total} so'm\n"
            f"<b>Sana:</b> {created_at}\n\n"
        )
        keyboard.append([InlineKeyboardButton(f"Tafsilotlar #{order_id}", callback_data=f"user_order_detail_{order_id}")])
    
    keyboard.append([InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")])

    await query.edit_message_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def user_order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi tanlagan buyurtma tafsilotini ko'rsatadi."""
    query = update.callback_query
    await query.answer()
    order_id = query.data.split('_')[3] # "user_order_detail_ORDER_ID"

    global orders
    orders = DataManager.load_data(ORDERS_FILE)
    order = next((o for o in orders if o.get('id') == order_id), None)

    if not order or order.get('customer', {}).get('user_id') != query.from_user.id:
        await query.edit_message_text("❌ Buyurtma topilmadi yoki sizga tegishli emas.", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Buyurtmalarim", callback_data="my_orders")]
        ]))
        return

    detail_message = f"🔔 <b>Buyurtma tafsilotlari #{order.get('id')}</b>\n\n"
    detail_message += f"📊 <b>Holati:</b> {order.get('status', 'pending').capitalize()}\n"
    detail_message += f"🗓️ <b>Buyurtma sanasi:</b> {datetime.fromisoformat(order.get('created_at')).strftime('%Y-%m-%d %H:%M:%S')}\n"
    detail_message += f"📍 <b>Yetkazish manzili:</b> {order.get('customer', {}).get('address', 'N/A')}\n\n"
    
    detail_message += "🛒 <b>Mahsulotlar:</b>\n"
    for item in order.get('items', []):
        detail_message += (
            f"▪️ {item.get('name', 'Nomalum')} ({format_price(item.get('price', 0))} so'm) x {item.get('quantity')}\n"
            f"   Jami: {format_price(item.get('total', 0))} so'm\n"
        )
    detail_message += f"\n💳 <b>Umumiy buyurtma miqdori:</b> <code>{format_price(order.get('total', 0))} so'm</code>"

    keyboard = [
        [InlineKeyboardButton("⬅️ Buyurtmalarim", callback_data="my_orders")],
        [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="start")]
    ]

    await query.edit_message_text(
        detail_message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )


# --- ADMIN FUNKSIYALARI ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin paneli imkoniyatlarini ko'rsatadi."""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Kirish rad etildi. Siz admin emassiz.")
        return

    keyboard = [
        [InlineKeyboardButton("➕ Mahsulot qo'shish", callback_data='admin_add_product')],
        [InlineKeyboardButton("➕ Kategoriya qo'shish", callback_data='admin_add_category')],
        [InlineKeyboardButton("🗑️ Mahsulotni o'chirish", callback_data='admin_delete_product')],
        [InlineKeyboardButton("🗑️ Kategoriyani o'chirish", callback_data='admin_delete_category')],
        [InlineKeyboardButton("📦 Zaxira miqdorini boshqarish", callback_data='admin_manage_stock')],
        [InlineKeyboardButton("📊 Buyurtmalarni ko'rish", callback_data='admin_view_orders')],
        [InlineKeyboardButton("📣 Xabar yuborish", callback_data='admin_broadcast')],
        [InlineKeyboardButton("🏠 Bosh sahifa", callback_data='start')]
    ]

    await query.edit_message_text(
        "⚙️ <b>Admin Paneli</b>\n\n"
        "Harakatni tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# --- MAHSULOT QO'SHISH SUHBATI ---
async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yangi mahsulot qo'shishni boshlaydi."""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Kirish rad etildi.")
        return

    await query.message.reply_text(
        "📝 <b>Yangi mahsulot qo'shish</b>\n\n"
        "Iltimos, mahsulot nomini kiriting:",
        parse_mode='HTML'
    )
    return ADD_PRODUCT_NAME

async def add_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mahsulot nomini oladi."""
    product_name = update.message.text.strip()
    if not product_name:
        await update.message.reply_text("Mahsulot nomi bo'sh bo'lishi mumkin emas. Iltimos, qaytadan kiriting:")
        return ADD_PRODUCT_NAME
    
    context.user_data['new_product'] = {'name': product_name}
    await update.message.reply_text(
        "💰 Mahsulot narxini kiriting (masalan, 15000):"
    )
    return ADD_PRODUCT_PRICE

async def add_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mahsulot narxini oladi."""
    try:
        price = int(update.message.text.strip())
        if price <= 0:
            await update.message.reply_text("Narx musbat son bo'lishi kerak. Iltimos, qaytadan kiriting:")
            return ADD_PRODUCT_PRICE
        
        context.user_data['new_product']['price'] = price
        await update.message.reply_text(
            "📝 Mahsulot tavsifini kiriting:"
        )
        return ADD_PRODUCT_DESC
    except ValueError:
        await update.message.reply_text("Narx noto'g'ri. Iltimos, son kiriting:")
        return ADD_PRODUCT_PRICE

async def add_product_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mahsulot tavsifini oladi."""
    description = update.message.text.strip()
    context.user_data['new_product']['description'] = description

    # Mavjud kategoriyalarni ko'rsatish
    global db
    db = DataManager.load_data(PRODUCTS_FILE)
    categories = db.get('categories', [])

    if not categories:
        await update.message.reply_text(
            "🚫 Kategoriyalar topilmadi. Iltimos, avval Admin Paneli orqali kategoriya qo'shing.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Admin Paneli", callback_data='admin_panel')]
            ])
        )
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(cat['name'], callback_data=f"select_cat_{cat['slug']}")] for cat in categories]
    await update.message.reply_text(
        "📂 Mahsulot kategoriyasini tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ADD_PRODUCT_CAT

async def add_product_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mahsulot kategoriyasini oladi."""
    query = update.callback_query
    await query.answer()
    category_slug = query.data.split('_')[2]
    context.user_data['new_product']['category'] = category_slug
    
    await query.message.reply_text(
        "📦 Mahsulotning zaxira miqdorini kiriting (masalan, 100):"
    )
    return ADD_PRODUCT_STOCK

async def add_product_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mahsulot zaxira miqdorini oladi."""
    try:
        stock = int(update.message.text.strip())
        if stock < 0:
            await update.message.reply_text("Zaxira miqdori manfiy bo'lishi mumkin emas. Iltimos, manfiy bo'lmagan son kiriting:")
            return ADD_PRODUCT_STOCK
        
        context.user_data['new_product']['stock'] = stock
        await update.message.reply_text(
            "📸 Iltimos, mahsulot uchun rasm yuboring (yoki rasmsiz bo'lsa /skip):"
        )
        return ADD_PRODUCT_PHOTO
    except ValueError:
        await update.message.reply_text("Zaxira miqdori noto'g'ri. Iltimos, son kiriting:")
        return ADD_PRODUCT_STOCK

async def add_product_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mahsulot rasmini oladi va mahsulotni saqlaydi."""
    if update.message.photo:
        context.user_data['new_product']['photo_id'] = update.message.photo[-1].file_id
    else:
        context.user_data['new_product']['photo_id'] = None

    new_product = context.user_data['new_product']
    
    global db
    products = db.get('products', [])
    new_product_id = max([p.get('id', 0) for p in products]) + 1 if products else 1
    new_product['id'] = new_product_id

    products.append(new_product)
    db['products'] = products

    if DataManager.save_data(PRODUCTS_FILE, db):
        await update.message.reply_text(
            f"✅ Mahsulot '<b>{new_product['name']}</b>' muvaffaqiyatli qo'shildi!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Admin Paneli", callback_data='admin_panel')]
            ]),
            parse_mode='HTML'
        )
        # Barcha foydalanuvchilarga yangi mahsulot haqida xabar yuborish (qo'shimcha funksiya)
        # Siz buni alohida broadcast funksiyasi orqali qilishingiz mumkin yoki shu yerda avtomatlashtirishingiz mumkin.
        # Misol uchun:
        # global users
        # for user_record in users:
        #     if user_record['id'] != update.effective_user.id: # Adminni o'zini istisno qilish
        #         try:
        #             await context.bot.send_message(
        #                 chat_id=user_record['id'],
        #                 text=f"🔔 Yangi mahsulot qo'shildi: <b>{new_product['name']}</b>!\n"
        #                      f"Narxi: {format_price(new_product['price'])} so'm",
        #                 parse_mode='HTML',
        #                 reply_markup=InlineKeyboardMarkup([
        #                     [InlineKeyboardButton("Ko'rish", callback_data=f"prod_{new_product['id']}")]
        #                 ])
        #             )
        #         except Exception as e:
        #             logger.warning(f"Foydalanuvchi {user_record['id']} ga yangi mahsulot haqida xabar yuborilmadi: {e}")

    else:
        await update.message.reply_text("❌ Mahsulotni qo'shishda xato yuz berdi. Iltimos, qaytadan urinib ko'ring.")

    context.user_data.pop('new_product', None)
    return ConversationHandler.END

async def skip_product_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mahsulot rasmini qo'shishni o'tkazib yuboradi."""
    context.user_data['new_product']['photo_id'] = None
    return await add_product_photo(update, context) # Mahsulotni saqlashga o'tish

# --- KATEGORIYA QO'SHISH SUHBATI ---
async def add_category_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yangi kategoriya qo'shishni boshlaydi."""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Kirish rad etildi.")
        return

    await query.message.reply_text(
        "📝 <b>Yangi kategoriya qo'shish</b>\n\n"
        "Iltimos, kategoriya nomini kiriting:",
        parse_mode='HTML'
    )
    return ADD_CATEGORY_NAME

async def add_category_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kategoriya nomini oladi va saqlaydi."""
    category_name = update.message.text.strip()
    if not category_name:
        await update.message.reply_text("Kategoriya nomi bo'sh bo'lishi mumkin emas. Iltimos, qaytadan kiriting:")
        return ADD_CATEGORY_NAME

    global db
    db = DataManager.load_data(PRODUCTS_FILE)
    categories = db.get('categories', [])
    category_slug = category_name.lower().replace(' ', '_')

    if any(c.get('slug') == category_slug for c in categories):
        await update.message.reply_text(
            "Bu nomdagi kategoriya allaqachon mavjud. Iltimos, boshqa nom tanlang:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Admin Paneli", callback_data='admin_panel')]
            ])
        )
        return ADD_CATEGORY_NAME

    categories.append({'name': category_name, 'slug': category_slug})
    db['categories'] = categories

    if DataManager.save_data(PRODUCTS_FILE, db):
        await update.message.reply_text(
            f"✅ Kategoriya '<b>{category_name}</b>' muvaffaqiyatli qo'shildi!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Admin Paneli", callback_data='admin_panel')]
            ]),
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text("❌ Kategoriyani qo'shishda xato yuz berdi. Iltimos, qaytadan urinib ko'ring.")
    
    return ConversationHandler.END

# --- KATEGORIYANI O'CHIRISH FUNKSIONALI ---
async def delete_category_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """O'chirish uchun kategoriyalarni ko'rsatadi."""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Kirish rad etildi.")
        return

    global db
    db = DataManager.load_data(PRODUCTS_FILE)
    categories = db.get('categories', [])

    if not categories:
        await query.edit_message_text(
            "🚫 O'chirish uchun kategoriyalar mavjud emas.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Admin Paneli", callback_data='admin_panel')]
            ])
        )
        return

    keyboard = [[InlineKeyboardButton(cat['name'], callback_data=f"delcat_{cat['slug']}")] for cat in categories]
    keyboard.append([InlineKeyboardButton("⬅️ Admin Paneli", callback_data='admin_panel')])

    await query.edit_message_text(
        "🗑️ <b>Kategoriyani o'chirish</b>\n\n"
        "O'chirish uchun kategoriyani tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def delete_category_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kategoriyani o'chirishni tasdiqlaydi."""
    query = update.callback_query
    await query.answer()
    category_slug = query.data.split('_')[1]

    context.user_data['delete_category_slug'] = category_slug
    category_name = get_category_name(category_slug)

    keyboard = [
        [InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"confirm_delcat_{category_slug}")],
        [InlineKeyboardButton("❌ Yo'q, bekor qilish", callback_data='admin_panel')]
    ]

    await query.edit_message_text(
        f"⚠️ '<b>{category_name}</b>' kategoriyasini o'chirmoqchimisiz?\n\n"
        "<b>Bu kategoriyadagi barcha mahsulotlar ham o'chiriladi!</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    return DELETE_CATEGORY_CONFIRM

async def delete_category_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kategoriyani o'chirishni amalga oshiradi."""
    query = update.callback_query
    await query.answer()
    category_slug = context.user_data.pop('delete_category_slug', None)

    if not category_slug:
        await query.edit_message_text("❌ O'chirish uchun kategoriya tanlanmagan.")
        return ConversationHandler.END

    global db
    db = DataManager.load_data(PRODUCTS_FILE)
    
    # Kategoriyani filtrlash
    initial_category_count = len(db.get('categories', []))
    db['categories'] = [cat for cat in db.get('categories', []) if cat.get('slug') != category_slug]
    category_deleted = len(db.get('categories', [])) < initial_category_count

    # Bu kategoriyadagi mahsulotlarni filtrlash
    initial_product_count = len(db.get('products', []))
    db['products'] = [p for p in db.get('products', []) if p.get('category') != category_slug]
    products_deleted_count = initial_product_count - len(db.get('products', []))

    if DataManager.save_data(PRODUCTS_FILE, db) and category_deleted:
        await query.edit_message_text(
            f"✅ '{get_category_name(category_slug)}' kategoriyasi va undagi {products_deleted_count} ta mahsulot o'chirildi.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Admin Paneli", callback_data='admin_panel')]
            ]),
            parse_mode='HTML'
        )
    else:
        await query.edit_message_text(
            "❌ Kategoriyani o'chirishda xato yuz berdi yoki kategoriya topilmadi.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Admin Paneli", callback_data='admin_panel')]
            ])
        )
    return ConversationHandler.END

# --- MAHSULOTNI O'CHIRISH FUNKSIONALI ---
async def delete_product_select_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """O'chirish uchun mahsulotni tanlash uchun kategoriyalarni ko'rsatadi."""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Kirish rad etildi.")
        return

    global db
    db = DataManager.load_data(PRODUCTS_FILE)
    categories = db.get('categories', [])

    if not categories:
        await query.edit_message_text(
            "🚫 Mahsulotlarni tanlash uchun kategoriyalar mavjud emas.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Admin Paneli", callback_data='admin_panel')]
            ])
        )
        return

    keyboard = [[InlineKeyboardButton(cat['name'], callback_data=f"delprodcat_{cat['slug']}")] for cat in categories]
    keyboard.append([InlineKeyboardButton("⬅️ Admin Paneli", callback_data='admin_panel')])

    await query.edit_message_text(
        "🗑️ <b>Mahsulotni o'chirish</b>\n\n"
        "Mahsulotlarni ko'rish uchun kategoriyani tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def delete_product_select_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tanlangan kategoriyadagi mahsulotlarni o'chirish uchun ko'rsatadi."""
    query = update.callback_query
    await query.answer()
    category_slug = query.data.split('_')[1]

    context.user_data['delete_product_category_slug'] = category_slug

    global db
    db = DataManager.load_data(PRODUCTS_FILE)
    products_in_category = [
        p for p in db.get('products', []) 
        if p.get('category') == category_slug
    ]

    if not products_in_category:
        await query.edit_message_text(
            f"🚫 '<b>{get_category_name(category_slug)}</b>' da o'chirish uchun mahsulotlar mavjud emas.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Kategoriyalarga qaytish", callback_data='admin_delete_product')]
            ]),
            parse_mode='HTML'
        )
        return

    keyboard = [[InlineKeyboardButton(p['name'], callback_data=f"delprodid_{p['id']}")] for p in products_in_category]
    keyboard.append([InlineKeyboardButton("⬅️ Kategoriyalarga qaytish", callback_data='admin_delete_product')])

    await query.edit_message_text(
        f"🗑️ <b>{get_category_name(category_slug)} dan mahsulotni o'chirish</b>\n\n"
        "O'chirish uchun mahsulotni tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def delete_product_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mahsulotni o'chirishni tasdiqlaydi."""
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.split('_')[1])

    context.user_data['delete_product_id'] = product_id
    product = get_product_by_id(product_id)

    if not product:
        await query.edit_message_text("❌ Mahsulot topilmadi.", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Admin Paneli", callback_data='admin_panel')]
        ]))
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"confirm_delprod_{product_id}")],
        [InlineKeyboardButton("❌ Yo'q, bekor qilish", callback_data=f"delprodcat_{product.get('category')}")]
    ]

    await query.edit_message_text(
        f"⚠️ '<b>{product.get('name')}</b>' mahsulotini o'chirmoqchimisiz?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    return DELETE_PRODUCT_CONFIRM

async def delete_product_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mahsulotni o'chirishni amalga oshiradi."""
    query = update.callback_query
    await query.answer()
    product_id = context.user_data.pop('delete_product_id', None)

    if product_id is None:
        await query.edit_message_text("❌ O'chirish uchun mahsulot tanlanmagan.")
        return ConversationHandler.END

    global db
    db = DataManager.load_data(PRODUCTS_FILE)
    
    initial_product_count = len(db.get('products', []))
    product_name_deleted = "Noma'lum mahsulot"
    
    # O'chirishdan oldin mahsulot nomini topish
    for p in db.get('products', []):
        if p.get('id') == product_id:
            product_name_deleted = p.get('name', "Noma'lum mahsulot")
            break

    db['products'] = [p for p in db.get('products', []) if p.get('id') != product_id]
    product_deleted = len(db.get('products', [])) < initial_product_count

    if DataManager.save_data(PRODUCTS_FILE, db) and product_deleted:
        await query.edit_message_text(
            f"✅ Mahsulot '<b>{product_name_deleted}</b>' o'chirildi.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Admin Paneli", callback_data='admin_panel')]
            ]),
            parse_mode='HTML'
        )
    else:
        await query.edit_message_text(
            "❌ Mahsulotni o'chirishda xato yuz berdi yoki mahsulot topilmadi.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Admin Paneli", callback_data='admin_panel')]
            ])
        )
    return ConversationHandler.END


# --- ZAXIRA MIQDORINI BOSHQARISH (Soddalashtirilgan - kengaytirilishi mumkin) ---
async def admin_manage_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Zaxira miqdorini boshqarish uchun mahsulotlarni ro'yxatlaydi (soddalashtirilgan)."""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Kirish rad etildi.")
        return

    global db
    db = DataManager.load_data(PRODUCTS_FILE)
    products = db.get('products', [])

    if not products:
        await query.edit_message_text(
            "🚫 Zaxira miqdorini boshqarish uchun mahsulotlar mavjud emas.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Admin Paneli", callback_data='admin_panel')]
            ])
        )
        return

    keyboard = []
    for p in products:
        keyboard.append([InlineKeyboardButton(
            f"📦 {p.get('name')} (Zaxira: {p.get('stock', 0)})", 
            callback_data=f"editstock_{p.get('id')}"
        )])
    keyboard.append([InlineKeyboardButton("⬅️ Admin Paneli", callback_data='admin_panel')])

    await query.edit_message_text(
        "📦 <b>Mahsulot zaxira miqdorini boshqarish</b>\n\n"
        "Zaxira miqdorini tahrirlash uchun mahsulotni tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def edit_product_stock_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adminni yangi zaxira miqdorini kiritishga undaydi."""
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.split('_')[1])
    
    product = get_product_by_id(product_id)
    if not product:
        await query.edit_message_text("❌ Mahsulot topilmadi.")
        return ConversationHandler.END

    context.user_data['edit_stock_product_id'] = product_id

    await query.message.reply_text(
        f"📦 '<b>{product.get('name')}</b>' uchun yangi zaxira miqdorini kiriting (joriy: {product.get('stock', 0)}):",
        parse_mode='HTML'
    )
    return ADD_PRODUCT_STOCK # Zaxira holatini qayta ishlatish

async def update_product_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mahsulot zaxira miqdorini yangilaydi."""
    product_id = context.user_data.pop('edit_stock_product_id', None)
    if product_id is None:
        await update.message.reply_text("❌ Zaxira miqdorini yangilash uchun mahsulot tanlanmagan.")
        return ConversationHandler.END

    try:
        new_stock = int(update.message.text.strip())
        if new_stock < 0:
            await update.message.reply_text("Zaxira miqdori manfiy bo'lishi mumkin emas. Iltimos, manfiy bo'lmagan son kiriting:")
            context.user_data['edit_stock_product_id'] = product_id # Holatni saqlash
            return ADD_PRODUCT_STOCK
        
        global db
        db = DataManager.load_data(PRODUCTS_FILE)
        product_found = False
        for i, p in enumerate(db.get('products', [])):
            if p.get('id') == product_id:
                db['products'][i]['stock'] = new_stock
                product_found = True
                break
        
        if product_found and DataManager.save_data(PRODUCTS_FILE, db):
            await update.message.reply_text(
                f"✅ '<b>{get_product_by_id(product_id).get('name')}</b>' mahsuloti zaxira miqdori {new_stock} ga yangilandi.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Admin Paneli", callback_data='admin_panel')]
                ]),
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("❌ Zaxira miqdorini yangilashda xato yuz berdi yoki mahsulot topilmadi.")
    except ValueError:
        await update.message.reply_text("Zaxira miqdori noto'g'ri. Iltimos, son kiriting:")
        context.user_data['edit_stock_product_id'] = product_id # Holatni saqlash
        return ADD_PRODUCT_STOCK

    return ConversationHandler.END


# --- BUYURTMALARNI KO'RISH ---
async def admin_view_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Administratorlarga so'nggi buyurtmalarni ko'rsatadi."""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Kirish rad etildi.")
        return
    
    global orders
    orders = DataManager.load_data(ORDERS_FILE)
    
    if not orders:
        await query.edit_message_text(
            "📋 <b>Hali buyurtmalar yo'q.</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Admin Paneli", callback_data='admin_panel')]
            ]),
            parse_mode='HTML'
        )
        return

    # Buyurtmalarni yaratilish sanasi bo'yicha saralash, eng yangisi birinchi
    sorted_orders = sorted(orders, key=lambda x: datetime.fromisoformat(x.get('created_at')), reverse=True)
    
    order_list_text = "📋 <b>So'nggi buyurtmalar:</b>\n\n"
    keyboard = []
    
    for order in sorted_orders[:10]: # So'nggi 10 ta buyurtmani ko'rsatish
        order_id = order.get('id', 'N/A')
        customer_name = order.get('customer', {}).get('name', 'N/A')
        total_price = format_price(order.get('total', 0))
        status = order.get('status', 'pending')
        created_at = datetime.fromisoformat(order.get('created_at')).strftime("%Y-%m-%d %H:%M")
        
        order_list_text += (
            f"<b>#{order_id}</b> ({status.capitalize()})\n"
            f"  👤 {customer_name}\n"
            f"  💰 {total_price} so'm\n"
            f"  🕰️ {created_at}\n\n"
        )
        keyboard.append([InlineKeyboardButton(f"Buyurtma #{order_id} ni ko'rish", callback_data=f"vieworder_{order_id}")])

    keyboard.append([InlineKeyboardButton("⬅️ Admin Paneli", callback_data='admin_panel')])

    await query.edit_message_text(
        order_list_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def admin_view_order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muayyan buyurtma haqida batafsil ma'lumotni ko'rsatadi."""
    query = update.callback_query
    await query.answer()
    order_id = query.data.split('_')[1]

    global orders
    orders = DataManager.load_data(ORDERS_FILE)
    order = next((o for o in orders if o.get('id') == order_id), None)

    if not order:
        await query.edit_message_text(
            "❌ Buyurtma topilmadi.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Buyurtmalarga qaytish", callback_data='admin_view_orders')]
            ])
        )
        return

    detail_message = f"🔔 <b>Buyurtma tafsilotlari #{order.get('id')}</b>\n\n"
    detail_message += f"👤 <b>Mijoz:</b> {order.get('customer', {}).get('name', 'N/A')}\n"
    detail_message += f"📞 <b>Telefon:</b> {order.get('customer', {}).get('phone', 'N/A')}\n"
    detail_message += f"📍 <b>Manzil:</b> {order.get('customer', {}).get('address', 'N/A')}\n"
    detail_message += f"👤 <b>Telegram ID:</b> {order.get('customer', {}).get('user_id', 'N/A')}\n"
    username = order.get('customer', {}).get('username', 'N/A')
    if username != 'N/A':
        detail_message += f"🔗 <b>Telegram Username:</b> @{username}\n"
    detail_message += f"🗓️ <b>Buyurtma sanasi:</b> {datetime.fromisoformat(order.get('created_at')).strftime('%Y-%m-%d %H:%M:%S')}\n"
    detail_message += f"📊 <b>Holati:</b> {order.get('status', 'pending').capitalize()}\n\n"
    
    detail_message += "🛒 <b>Mahsulotlar:</b>\n"
    for item in order.get('items', []):
        detail_message += (
            f"▪️ {item.get('name', 'Nomalum')} ({format_price(item.get('price', 0))} so'm) x {item.get('quantity')}\n"
            f"   Jami: {format_price(item.get('total', 0))} so'm\n"
        )
    detail_message += f"\n💳 <b>Umumiy buyurtma miqdori:</b> <code>{format_price(order.get('total', 0))} so'm</code>"

    keyboard = [
        [InlineKeyboardButton("⬅️ Buyurtmalarga qaytish", callback_data='admin_view_orders')],
        [InlineKeyboardButton("🏠 Bosh sahifa", callback_data='start')]
    ]

    await query.edit_message_text(
        detail_message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# --- XABAR YUBORISH ---
async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Barcha foydalanuvchilarga xabar yuborish jarayonini boshlaydi."""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Kirish rad etildi.")
        return

    await query.message.reply_text(
        "📣 <b>Xabar yuborish</b>\n\n"
        "Iltimos, barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni kiriting:",
        parse_mode='HTML'
    )
    return BROADCAST_MESSAGE

async def admin_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Barcha foydalanuvchilarga xabar yuboradi."""
    broadcast_text = update.message.text
    if not broadcast_text:
        await update.message.reply_text("Xabar bo'sh bo'lishi mumkin emas. Iltimos, qaytadan kiriting:")
        return BROADCAST_MESSAGE

    global users
    users = DataManager.load_data(USERS_FILE)
    sent_count = 0
    failed_count = 0

    await update.message.reply_text("Xabar yuborilmoqda... Bu biroz vaqt olishi mumkin.")

    for user_record in users:
        user_id = user_record.get('id')
        if user_id and user_id != update.effective_user.id: # O'ziga yubormaslik
            try:
                await context.bot.send_message(chat_id=user_id, text=broadcast_text)
                sent_count += 1
            except Exception as e:
                logger.error(f"Foydalanuvchi {user_id} ga xabar yuborilmadi: {e}")
                failed_count += 1
    
    await update.message.reply_text(
        f"✅ Xabar {sent_count} ta foydalanuvchiga yuborildi.\n"
        f"❌ {failed_count} ta foydalanuvchiga yuborilmadi.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Admin Paneli", callback_data='admin_panel')]
        ])
    )
    return ConversationHandler.END

# --- YORDAM FUNKSIYASI ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yordam xabarini ko'rsatadi."""
    query = update.callback_query
    await query.answer()
    
    help_text = (
        "📋 <b>Yordam va ma'lumot</b>\n\n"
        "Bu yerda ba'zi buyruqlar va ularning vazifalari:\n\n"
        "• /start - Botni ishga tushiring va asosiy menyuni ko'ring.\n"
        "• <b>Katalog</b> - Barcha mavjud o'yinchoqlarni ko'rib chiqing.\n"
        "• <b>Savat</b> - Tanlagan narsalaringizni ko'ring va buyurtma bering.\n"
        "• <b>Buyurtmalarim</b> - O'zingizning oldingi buyurtmalaringizni ko'ring.\n"
        "• <b>Mahsulot izlash</b> - Mahsulotni nomi bo'yicha toping.\n"
        "• <b>Bosh sahifa</b> - Istalgan vaqtda asosiy menyuga qayting.\n\n"
        "Agar savollaringiz bo'lsa yoki muammolarga duch kelsangiz, iltimos, bizning administratorlar bilan bog'laning."
    )
    
    await query.edit_message_text(
        help_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Bosh sahifa", callback_data='start')]
        ]),
        parse_mode='HTML'
    )


# --- ASOSIY FUNKSIYA ---
def main() -> None:
    """Botni ishga tushiradi."""
    DataManager.backup_data() # Bot ishga tushganda ma'lumotlar zaxirasini yaratish
    application = Application.builder().token(BOT_TOKEN).build()

    # Suhbat boshqaruvchilari (Conversation Handlers)
    order_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(checkout, pattern='^checkout$')],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND | filters.CONTACT, ask_phone)],
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_order)],
        },
        fallbacks=[CommandHandler('start', start), CallbackQueryHandler(start, pattern='^start$')],
    )

    add_product_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_product_start, pattern='^admin_add_product$')],
        states={
            ADD_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_name)],
            ADD_PRODUCT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_price)],
            ADD_PRODUCT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_description)],
            ADD_PRODUCT_CAT: [CallbackQueryHandler(add_product_category, pattern='^select_cat_')],
            ADD_PRODUCT_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_stock)],
            ADD_PRODUCT_PHOTO: [
                MessageHandler(filters.PHOTO & ~filters.COMMAND, add_product_photo),
                CommandHandler('skip', skip_product_photo)
            ],
        },
        fallbacks=[CommandHandler('start', start), CallbackQueryHandler(admin_panel, pattern='^admin_panel$')]
    )

    add_category_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_category_start, pattern='^admin_add_category$')],
        states={
            ADD_CATEGORY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_category_name)],
        },
        fallbacks=[CommandHandler('start', start), CallbackQueryHandler(admin_panel, pattern='^admin_panel$')]
    )

    delete_category_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_category_confirm, pattern='^delcat_')],
        states={
            DELETE_CATEGORY_CONFIRM: [CallbackQueryHandler(delete_category_execute, pattern='^confirm_delcat_')],
        },
        fallbacks=[CommandHandler('start', start), CallbackQueryHandler(admin_panel, pattern='^admin_panel$')]
    )

    delete_product_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_product_confirm, pattern='^delprodid_')],
        states={
            DELETE_PRODUCT_CONFIRM: [CallbackQueryHandler(delete_product_execute, pattern='^confirm_delprod_')],
        },
        fallbacks=[CommandHandler('start', start), CallbackQueryHandler(admin_panel, pattern='^admin_panel$')]
    )

    broadcast_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast_start, pattern='^admin_broadcast$')],
        states={
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_message)],
        },
        fallbacks=[CommandHandler('start', start), CallbackQueryHandler(admin_panel, pattern='^admin_panel$')]
    )

    search_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(search_product_start, pattern='^search_product_start$')],
        states={
            SEARCH_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_product_by_name)],
        },
        fallbacks=[CommandHandler('start', start), CallbackQueryHandler(start, pattern='^start$')]
    )

    # Boshqaruvchilar (Handlers)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(start, pattern='^start$'))
    application.add_handler(CallbackQueryHandler(show_categories, pattern='^catalog$'))
    application.add_handler(CallbackQueryHandler(show_products, pattern='^cat_'))
    application.add_handler(CallbackQueryHandler(show_product_detail, pattern='^prod_'))
    application.add_handler(CallbackQueryHandler(add_to_cart, pattern='^addcart_'))
    application.add_handler(CallbackQueryHandler(show_cart, pattern='^show_cart$'))
    application.add_handler(CallbackQueryHandler(clear_cart, pattern='^clear_cart$'))
    application.add_handler(CallbackQueryHandler(adjust_cart_item, pattern='^(plus_|minus_|remove_).*')) # Savatdagi miqdorni o'zgartirish/o'chirish
    application.add_handler(CallbackQueryHandler(help_command, pattern='^help$'))
    application.add_handler(CallbackQueryHandler(my_orders, pattern='^my_orders$'))
    application.add_handler(CallbackQueryHandler(user_order_detail, pattern='^user_order_detail_'))


    # Admin Boshqaruvchilari
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
    application.add_handler(CallbackQueryHandler(delete_category_select, pattern='^admin_delete_category$'))
    application.add_handler(CallbackQueryHandler(delete_product_select_category, pattern='^admin_delete_product$'))
    application.add_handler(CallbackQueryHandler(delete_product_select_product, pattern='^delprodcat_'))
    application.add_handler(CallbackQueryHandler(admin_manage_stock, pattern='^admin_manage_stock$'))
    application.add_handler(CallbackQueryHandler(edit_product_stock_prompt, pattern='^editstock_'))
    application.add_handler(CallbackQueryHandler(admin_view_orders, pattern='^admin_view_orders$'))
    application.add_handler(CallbackQueryHandler(admin_view_order_detail, pattern='^vieworder_'))


    # Suhbat boshqaruvchilarini qo'shish
    application.add_handler(order_conv_handler)
    application.add_handler(add_product_conv_handler)
    application.add_handler(add_category_conv_handler)
    application.add_handler(delete_category_conv_handler)
    application.add_handler(delete_product_conv_handler)
    application.add_handler(broadcast_conv_handler)
    application.add_handler(search_conv_handler) # Mahsulot izlash suhbati

    # Botni Ctrl-C bosilguncha ishga tushirish
    logger.info("Bot so'rovlarni qabul qilishni boshladi...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
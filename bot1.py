# import logging
# import json
# import os
# from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
# from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# # --- SOZLAMALAR ---
# BOT_TOKEN = ""  # @BotFather dan olingan token
# ADMIN_CHAT_ID = ""  # Buyurtmalar keladigan guruh IDsi
# ADMIN_USER_IDS = []  # O'zingizning Telegram ID sini yozing
# LOW_STOCK_THRESHOLD = 5 # Nechta mahsulot qolganda "kam qoldi" deb belgilash

# # import os
# # BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# # json_path = os.path.join(BASE_DIR, 'products.json')

# # try:
# #     with open(json_path, 'r', encoding='utf-8') as f:
# #         db = json.load(f)
# # except FileNotFoundError:
# #     print("❌ products.json topilmadi!")
# #     db = {"categories": [], "products": []}

# # --- FAYLLAR BILAN ISHLASH ---
# PRODUCTS_FILE = 'products.json'
# USERS_FILE = 'users.json'

# def load_data(filename):
#     if not os.path.exists(filename):
#         data = [] if 'users' in filename else {"categories": [], "products": []}
#         with open(filename, 'w') as f: json.dump(data, f)
#     with open(filename, 'r', encoding='utf-8') as f:
#         return json.load(f)

# def save_data(filename, data):
#     with open(filename, 'w', encoding='utf-8') as f:
#         json.dump(data, f, indent=4, ensure_ascii=False)

# db = load_data(PRODUCTS_FILE)
# users = load_data(USERS_FILE)

# def add_user(user_id):
#     if user_id not in users: users.append(user_id); save_data(USERS_FILE, users)

# logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
# logger = logging.getLogger(__name__)

# # --- HOLATLAR (STATES) ---
# (NAME, PHONE, ADDRESS) = range(3)
# (ADD_PRODUCT_NAME, ADD_PRODUCT_PRICE, ADD_PRODUCT_DESC, ADD_PRODUCT_CAT, ADD_PRODUCT_STOCK, ADD_PRODUCT_PHOTO, BROADCAST_MESSAGE) = range(3, 10)

# # --- FOYDALANUVCHI FUNKSIYALARI ---
# async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user = update.effective_user
#     add_user(user.id)
#     context.user_data['cart'] = {}
#     keyboard = [[InlineKeyboardButton("🛍️ Mahsulotlar Katalogi", callback_data='catalog')]]
#     await update.message.reply_html(f"Assalomu alaykum, {user.mention_html()}!\n<b>O'yinchoqlar olamiga</b> xush kelibsiz!", reply_markup=InlineKeyboardMarkup(keyboard))

# async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     db = load_data(PRODUCTS_FILE)
#     query = update.callback_query
#     await query.answer()
#     print("[DEBUG] Kategoriyalar:", db.get('categories'))
#     keyboard = [[InlineKeyboardButton(cat['name'], callback_data=f"cat_{cat['slug']}")] for cat in db['categories']]
#     keyboard.append([InlineKeyboardButton("🛒 Savat", callback_data='show_cart')])
#     await query.edit_message_text('👇 Kategoriyalardan birini tanlang:', reply_markup=InlineKeyboardMarkup(keyboard))

# async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     db = load_data(PRODUCTS_FILE)
#     query = update.callback_query
#     category_slug = query.data.split('_')[1]
#     await query.answer()
#     products_in_category = [p for p in db['products'] if p['category'] == category_slug and p['stock'] > 0]
#     keyboard = [[InlineKeyboardButton(f"{p['name']} - {p['price']:,} so'm", callback_data=f"prod_{p['id']}")] for p in products_in_category]
#     keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data='catalog')])
#     await query.edit_message_text('👇 Mahsulot tanlang:', reply_markup=InlineKeyboardMarkup(keyboard))

# async def show_product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     db = load_data(PRODUCTS_FILE)
#     query = update.callback_query
#     product_id = int(query.data.split('_')[1])
#     product = next((p for p in db['products'] if p['id'] == product_id), None)
#     await query.answer()

#     if product and product['stock'] > 0:
#         caption = f"<b>{product['name']}</b>\n\n"
#         caption += f"<i>{product['description']}</i>\n\n"
#         caption += f"💰 Narxi: <b>{product['price']:,} so'm</b>\n"
#         caption += f"📦 Omborda: {product['stock']} dona mavjud"
        
#         keyboard = [
#             [InlineKeyboardButton("🛒 Savatga qo'shish", callback_data=f"addcart_{product_id}")],
#             [InlineKeyboardButton("⬅️ Orqaga", callback_data=f"cat_{product['category']}")]
#         ]
        
#         await query.message.delete() # Oldingi matnli xabarni o'chirish
#         if product.get('photo_id'):
#             await context.bot.send_photo(chat_id=query.from_user.id, photo=product['photo_id'], caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
#         else:
#             await context.bot.send_message(chat_id=query.from_user.id, text=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
#     else:
#         await query.edit_message_text("❌ Uzr, bu mahsulot hozirda mavjud emas.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data='catalog')]]))

# async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     product_id = int(query.data.split('_')[1])
#     cart = context.user_data.get('cart', {})
#     product = next((p for p in db['products'] if p['id'] == product_id), None)
    
#     if product and product['stock'] > cart.get(product_id, 0):
#         cart[product_id] = cart.get(product_id, 0) + 1
#         context.user_data['cart'] = cart
#         await query.answer("✅ Savatga qo'shildi!", show_alert=True)
#     else:
#         await query.answer("❌ Uzr, bu mahsulotdan boshqa qo'shib bo'lmaydi yoki u tugagan.", show_alert=True)

# async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query; await query.answer()
#     cart = context.user_data.get('cart', {})
#     if not cart:
#         await query.edit_message_text("🛒 Savatingiz bo'sh.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Katalogga qaytish", callback_data='catalog')]]))
#         return

#     cart_text = "🛒 **Sizning savatingiz:**\n\n"
#     total_price = 0
#     keyboard = []
#     for prod_id, qty in cart.items():
#         product = next((p for p in db['products'] if p['id'] == prod_id), None)
#         if product:
#             total_price += product['price'] * qty
#             cart_text += f"▪️ {product['name']} ({qty} dona) - {product['price']*qty:,} so'm\n"
#     cart_text += f"\n\n💰 **Jami:** {total_price:,} so'm"
#     keyboard.append([InlineKeyboardButton("✅ Buyurtmani rasmiylashtirish", callback_data='checkout')])
#     keyboard.append([InlineKeyboardButton(" Katalogga qaytish", callback_data='catalog')])
#     await query.edit_message_text(cart_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query; await query.answer()
#     await query.message.reply_text("👤 Ismingizni kiriting:")
#     return NAME

# async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     context.user_data['name'] = update.message.text
#     await update.message.reply_text("📞 Telefon raqamingizni kiriting:")
#     return PHONE

# async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     context.user_data['phone'] = update.message.text
#     await update.message.reply_text("📍 Yetkazib berish manzilini to'liq kiriting:")
#     return ADDRESS

# async def process_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     context.user_data['address'] = update.message.text
#     user_data = context.user_data; cart = user_data.get('cart', {}); user = update.effective_user
    
#     admin_message = f"🔔 **Yangi buyurtma!**\n\n"
#     admin_message += f"👤 **Mijoz:** {user_data['name']}\n"
#     admin_message += f"📞 **Telefon:** {user_data['phone']}\n"
#     admin_message += f"📍 **Manzil:** {user_data['address']}\n"
#     admin_message += f"👤 **Telegram:** @{user.username} (ID: {user.id})\n\n"
#     admin_message += "🛒 **Buyurtma tarkibi:**\n"
#     total_price = 0
    
#     for prod_id, qty in cart.items():
#         product_index = next((i for i, p in enumerate(db['products']) if p['id'] == prod_id), None)
#         if product_index is not None:
#             db['products'][product_index]['stock'] -= qty

#             product = db['products'][product_index]
#             # Kategoriya nomini topish
#             category_name = "Noma'lum kategoriya"
#             for category in db['categories']:
#                 if category['slug'] == product['category']:
#                     category_name = category['name']
#                     break
#             total_price += product['price'] * qty
#             admin_message += f"▪️ {product['name']} - {category_name} ({qty} dona)\n"
#     admin_message += f"\n💰 **Jami summa:** {total_price:,} so'm"
#     save_data(PRODUCTS_FILE, db)

#     await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_message, parse_mode="Markdown")
#     await update.message.reply_text("✅ Rahmat! Buyurtmangiz qabul qilindi. Tez orada siz bilan bog'lanamiz.")
#     user_data['cart'] = {}
#     return ConversationHandler.END

# # --- ADMIN FUNKSIYALARI ---
# def is_admin(update: Update) -> bool: return update.effective_user.id in ADMIN_USER_IDS

# async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     if not is_admin(update): return await update.message.reply_text("Sizda bu buyruq uchun ruxsat yo'q.")
#     keyboard = [[InlineKeyboardButton("➕ Mahsulot qo'shish", callback_data='admin_add_prod')], [InlineKeyboardButton("📋 Mahsulotlar ro'yxati", callback_data='admin_list_prods')], [InlineKeyboardButton("📢 Xabar yuborish", callback_data='admin_broadcast')], [InlineKeyboardButton("📊 Statistika", callback_data='admin_stats')]]
#     await update.message.reply_text("👑 Admin paneli:", reply_markup=InlineKeyboardMarkup(keyboard))

# async def list_products_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query; await query.answer()
#     prod_list_text = "📋 **Mavjud mahsulotlar:**\n\n"
#     for p in db['products']:
#         if p['stock'] == 0: emoji = "🔴"
#         elif p['stock'] <= LOW_STOCK_THRESHOLD: emoji = "🟡"
#         else: emoji = "🟢"
#         prod_list_text += f"{emoji} {p['name']} (Qoldiq: {p['stock']}, Narxi: {p['price']:,})\n"
#     await query.edit_message_text(prod_list_text, parse_mode='Markdown')

# async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query; await query.answer()
#     await query.message.reply_text(f"📊 Botdagi jami foydalanuvchilar soni: **{len(users)}** ta.", parse_mode='Markdown')

# async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query; await query.answer()
#     await query.message.reply_text("Mahsulot nomini kiriting:")
#     return ADD_PRODUCT_NAME

# async def add_product_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     context.user_data['new_product'] = {'name': update.message.text}
#     await update.message.reply_text("Mahsulot narxini kiriting (so'mda, faqat son):")
#     return ADD_PRODUCT_PRICE

# async def add_product_get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     try:
#         context.user_data['new_product']['price'] = int(update.message.text)
#         await update.message.reply_text("Mahsulot haqida ma'lumot (tavsif) kiriting:")
#         return ADD_PRODUCT_DESC
#     except ValueError:
#         return await update.message.reply_text("❌ Xato! Narxni faqat sonlarda kiriting.")

# async def add_product_get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     context.user_data['new_product']['description'] = update.message.text
#     keyboard = [[InlineKeyboardButton(cat['name'], callback_data=f"addcat_{cat['slug']}")] for cat in db['categories']]
#     await update.message.reply_text("Kategoriyani tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
#     return ADD_PRODUCT_CAT

# async def add_product_get_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     context.user_data['new_product']['category'] = query.data.split('_')[1]
#     await query.message.reply_text("Mahsulotning ombordagi sonini kiriting (faqat son):")
#     return ADD_PRODUCT_STOCK

# async def add_product_get_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     try:
#         context.user_data['new_product']['stock'] = int(update.message.text)
#         await update.message.reply_text("🖼️ Endi mahsulot rasmini yuboring:")
#         return ADD_PRODUCT_PHOTO
#     except ValueError:
#         return await update.message.reply_text("❌ Xato! Sonni to'g'ri kiriting.")

# async def add_product_get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     new_product = context.user_data['new_product']
#     new_product['photo_id'] = update.message.photo[-1].file_id
#     new_product['id'] = max([p['id'] for p in db['products']], default=0) + 1
#     db['products'].append(new_product)
#     save_data(PRODUCTS_FILE, db)
#     await update.message.reply_text(f"✅ Muvaffaqiyatli qo'shildi!\nMahsulot: {new_product['name']}")
#     del context.user_data['new_product']
#     return ConversationHandler.END

# async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query; await query.answer()
#     await query.message.reply_text("Barcha foydalanuvchilarga yuboriladigan xabarni kiriting (matn, rasm, video...)\nBekor qilish uchun /cancel.")
#     return BROADCAST_MESSAGE

# async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     message_to_send = update.message
#     successful_sends, failed_sends = 0, 0
#     await update.message.reply_text(f"Xabar yuborish boshlandi...")
#     for user_id in users:
#         try:
#             await context.bot.copy_message(chat_id=user_id, from_chat_id=message_to_send.chat_id, message_id=message_to_send.message_id)
#             successful_sends += 1
#         except Exception as e:
#             failed_sends += 1; logger.error(f"Could not send to {user_id}: {e}")
#     await update.message.reply_text(f"✅ Xabar yuborish yakunlandi!\nMuvaffaqiyatli: {successful_sends}\nXatolik: {failed_sends}")
#     return ConversationHandler.END

# async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text("Amal bekor qilindi.")
#     if 'new_product' in context.user_data: del context.user_data['new_product']
#     return ConversationHandler.END

# def main():
#     application = Application.builder().token(BOT_TOKEN).build()

#     # Handlers
#     user_checkout_handler = ConversationHandler(
#         entry_points=[CallbackQueryHandler(checkout, pattern='^checkout$')],
#         states={ NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)], PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone)], ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_order)]},
#         fallbacks=[CommandHandler('cancel', cancel)]
#     )
#     add_product_handler = ConversationHandler(
#         entry_points=[CallbackQueryHandler(add_product_start, pattern='^admin_add_prod$')],
#         states={
#             ADD_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_get_name)],
#             ADD_PRODUCT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_get_price)],
#             ADD_PRODUCT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_get_desc)],
#             ADD_PRODUCT_CAT: [CallbackQueryHandler(add_product_get_category, pattern='^addcat_')],
#             ADD_PRODUCT_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_get_stock)],
#             ADD_PRODUCT_PHOTO: [MessageHandler(filters.PHOTO, add_product_get_photo)],
#         }, fallbacks=[CommandHandler('cancel', cancel)]
#     )
#     broadcast_handler = ConversationHandler(
#         entry_points=[CallbackQueryHandler(broadcast_start, pattern='^admin_broadcast$')],
#         states={BROADCAST_MESSAGE: [MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_message)]},
#         fallbacks=[CommandHandler('cancel', cancel)]
#     )

#     application.add_handler(CommandHandler("start", start))
#     application.add_handler(CommandHandler("admin", admin_panel))
#     application.add_handler(CallbackQueryHandler(show_categories, pattern='^catalog$'))
#     application.add_handler(CallbackQueryHandler(show_products, pattern='^cat_'))
#     application.add_handler(CallbackQueryHandler(show_product_detail, pattern='^prod_'))
#     application.add_handler(CallbackQueryHandler(add_to_cart, pattern='^addcart_'))
#     application.add_handler(CallbackQueryHandler(show_cart, pattern='^show_cart$'))
#     application.add_handler(CallbackQueryHandler(list_products_admin, pattern='^admin_list_prods$'))
#     application.add_handler(CallbackQueryHandler(show_stats, pattern='^admin_stats$'))
#     application.add_handler(user_checkout_handler)
#     application.add_handler(add_product_handler)
#     application.add_handler(broadcast_handler)

#     application.run_polling()

# if __name__ == '__main__':
#     main()

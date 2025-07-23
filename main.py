# # --- Toyshop Bot Enhanced ---
# # Quyidagi kodda quyidagilar qo‘shilgan:
# # 1. Mahsulot izlash (/search)
# # 2. Buyurtmalar tarixini saqlash va /myorders
# # 3. Buyurtmalarni Excel formatda yuklab olish (/download_orders)
# # 4. Mahsulotlarni CSV orqali import/export (/export_products, /import_products)
# # 5. Admin mahsulotni o‘chira oladi (/delete_product)
# # 6. Savatdan "orqaga qaytish" tugmasi ishlaydi
# # 7. Yangi mahsulot qo‘shilganda avtomatik xabar yuboriladi (/add_product)

# import os
# import csv
# import json
# import datetime
# from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
# from telegram.ext import (Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters,
#                           ContextTypes, ConversationHandler)

# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# PRODUCTS_FILE = os.path.join(BASE_DIR, 'products.json')
# USERS_FILE = os.path.join(BASE_DIR, 'users.json')
# ORDER_HISTORY_FILE = os.path.join(BASE_DIR, 'order_history.json')
# EXPORT_CSV_FILE = os.path.join(BASE_DIR, 'products_export.csv')
# IMPORT_CSV_FILE = os.path.join(BASE_DIR, 'products_import.csv')
# ORDERS_EXCEL_FILE = os.path.join(BASE_DIR, 'orders_export.csv')

# LOW_STOCK_THRESHOLD = 5
# BOT_TOKEN = "7269655479:AAFnLkrZtysTbuVrILWCC_J0Wwfx_6xVwjE"
# ADMIN_USER_IDS = [156402303, 305620565,1831969115]  # O'zgartiring

# # --- FAYLLAR ---
# def load_data(filename):
#     if not os.path.exists(filename):
#         if 'order' in filename:
#             with open(filename, 'w', encoding='utf-8') as f: json.dump({}, f)
#             return {}
#         elif 'user' in filename:
#             with open(filename, 'w', encoding='utf-8') as f: json.dump([], f)
#             return []
#         else:
#             with open(filename, 'w', encoding='utf-8') as f: json.dump({"categories": [], "products": []}, f)
#             return {"categories": [], "products": []}
#     with open(filename, 'r', encoding='utf-8') as f:
#         return json.load(f)

# def save_data(filename, data):
#     with open(filename, 'w', encoding='utf-8') as f:
#         json.dump(data, f, indent=4, ensure_ascii=False)

# # --- IZLASH ---
# async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text("🔍 Qidiruv uchun mahsulot nomi yoki tavsifini kiriting:")
#     return "SEARCHING"

# async def search_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.message.text.lower()
#     db = load_data(PRODUCTS_FILE)
#     results = []
#     for p in db['products']:
#         if query in p['name'].lower() or query in p['description'].lower():
#             if p['stock'] > 0:
#                 results.append(p)

#     if not results:
#         await update.message.reply_text("❌ Mos mahsulot topilmadi.")
#         return ConversationHandler.END

#     keyboard = []
#     for p in results:
#         stock_warning = " ⚠️" if p['stock'] <= LOW_STOCK_THRESHOLD else ""
#         keyboard.append([InlineKeyboardButton(f"{p['name']} - {p['price']:,} so'm{stock_warning}", callback_data=f"prod_{p['id']}")])

#     await update.message.reply_text("🔎 Qidiruv natijalari:", reply_markup=InlineKeyboardMarkup(keyboard))
#     return ConversationHandler.END

# # --- BUYURTMA TARIXI ---
# async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_id = str(update.effective_user.id)
#     order_db = load_data(ORDER_HISTORY_FILE)
#     orders = order_db.get(user_id, [])

#     if not orders:
#         await update.message.reply_text("❌ Sizda hali hech qanday buyurtma yo'q.")
#         return

#     msg = f"🧾 <b>Sizning buyurtmalaringiz:</b>\n\n"
#     for i, order in enumerate(orders[::-1], 1):
#         msg += f"📦 <b>#{i}</b> ({order['timestamp']})\n"
#         for item in order['items']:
#             msg += f"▪️ {item['name']} - {item['qty']} dona x {item['price']:,} so'm\n"
#         msg += f"💰 Jami: <b>{order['total']:,} so'm</b>\n\n"

#     await update.message.reply_text(msg, parse_mode='HTML')

# # --- BUYURTMA SAQLASH QISMI (quyidagisini order yakunida chaqiring) ---
# def save_order(user, user_data, cart):
#     db = load_data(PRODUCTS_FILE)
#     order_db = load_data(ORDER_HISTORY_FILE)
#     user_orders = order_db.get(str(user.id), [])

#     total_price = 0
#     order_data = {
#         "name": user_data['name'],
#         "phone": user_data['phone'],
#         "address": user_data['address'],
#         "items": [],
#         "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#         "total": 0
#     }

#     for prod_id, qty in cart.items():
#         product = next((p for p in db['products'] if p['id'] == prod_id), None)
#         if product:
#             order_data['items'].append({
#                 "name": product['name'],
#                 "category": product['category'],
#                 "price": product['price'],
#                 "qty": qty
#             })
#             total_price += product['price'] * qty

#     order_data['total'] = total_price
#     user_orders.append(order_data)
#     order_db[str(user.id)] = user_orders
#     save_data(ORDER_HISTORY_FILE, order_db)

# # --- ADMIN: YANGI MAHSULOT QO‘SHISH VA XABAR YUBORISH ---
# async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     if update.effective_user.id not in ADMIN_USER_IDS:
#         await update.message.reply_text("❌ Sizda ruxsat yo'q.")
#         return

#     msg = update.message.text.split("|")
#     if len(msg) < 6:
#         await update.message.reply_text("⚠️ Format: /add_product id|nom|narx|tavsif|kategoriya|son")
#         return

#     product = {
#         "id": int(msg[0].split()[1]),
#         "name": msg[1],
#         "price": int(msg[2]),
#         "description": msg[3],
#         "category": msg[4],
#         "stock": int(msg[5])
#     }

#     db = load_data(PRODUCTS_FILE)
#     db['products'].append(product)
#     save_data(PRODUCTS_FILE, db)

#     users = load_data(USERS_FILE)
#     text = f"🆕 <b>Yangi mahsulot qo‘shildi:</b>\n<b>{product['name']}</b> - {product['price']:,} so'm\n{product['description']}"
#     for user_id in users:
#         try:
#             await context.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
#         except:
#             continue

#     await update.message.reply_text("✅ Mahsulot qo‘shildi va xabar yuborildi")

# # --- ADMIN: BUYURTMALARNI EXPORT QILISH ---
# async def download_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     if update.effective_user.id not in ADMIN_USER_IDS:
#         await update.message.reply_text("Sizda ruxsat yo'q.")
#         return

#     order_db = load_data(ORDER_HISTORY_FILE)
#     with open(ORDERS_EXCEL_FILE, 'w', newline='', encoding='utf-8') as csvfile:
#         writer = csv.writer(csvfile)
#         writer.writerow(["Ism", "Telefon", "Manzil", "Sana", "Mahsulot", "Soni", "Narxi"])
#         for user_orders in order_db.values():
#             for order in user_orders:
#                 for item in order['items']:
#                     writer.writerow([order['name'], order['phone'], order['address'], order['timestamp'], item['name'], item['qty'], item['price']])

#     await update.message.reply_document(InputFile(ORDERS_EXCEL_FILE), caption="📥 Buyurtmalar CSV formatda")

# # --- ADMIN: PRODUCT EXPORT ---
# async def export_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     if update.effective_user.id not in ADMIN_USER_IDS:
#         await update.message.reply_text("Sizda ruxsat yo'q.")
#         return
#     db = load_data(PRODUCTS_FILE)
#     with open(EXPORT_CSV_FILE, 'w', newline='', encoding='utf-8') as f:
#         writer = csv.writer(f)
#         writer.writerow(["id", "name", "price", "description", "category", "stock"])
#         for p in db['products']:
#             writer.writerow([p['id'], p['name'], p['price'], p['description'], p['category'], p['stock']])
#     await update.message.reply_document(InputFile(EXPORT_CSV_FILE), caption="📤 Mahsulotlar eksport qilindi")

# # --- ADMIN: PRODUCT IMPORT ---
# async def import_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     if update.effective_user.id not in ADMIN_USER_IDS:
#         await update.message.reply_text("Sizda ruxsat yo'q.")
#         return
#     db = load_data(PRODUCTS_FILE)
#     if not os.path.exists(IMPORT_CSV_FILE):
#         await update.message.reply_text("❌ 'products_import.csv' fayli topilmadi")
#         return

#     with open(IMPORT_CSV_FILE, 'r', encoding='utf-8') as f:
#         reader = csv.DictReader(f)
#         for row in reader:
#             product = {
#                 "id": int(row['id']),
#                 "name": row['name'],
#                 "price": int(row['price']),
#                 "description": row['description'],
#                 "category": row['category'],
#                 "stock": int(row['stock'])
#             }
#             db['products'].append(product)
#     save_data(PRODUCTS_FILE, db)
#     await update.message.reply_text("✅ Mahsulotlar import qilindi")

# # --- ADMIN: PRODUCT DELETE ---
# async def delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     if update.effective_user.id not in ADMIN_USER_IDS:
#         await update.message.reply_text("Sizda ruxsat yo'q.")
#         return

#     db = load_data(PRODUCTS_FILE)
#     text = update.message.text
#     parts = text.split()
#     if len(parts) != 2 or not parts[1].isdigit():
#         await update.message.reply_text("❗️To'g'ri format: /delete_product <product_id>")
#         return

#     product_id = int(parts[1])
#     before = len(db['products'])
#     db['products'] = [p for p in db['products'] if p['id'] != product_id]
#     after = len(db['products'])

#     if before == after:
#         await update.message.reply_text("❌ Mahsulot topilmadi")
#     else:
#         save_data(PRODUCTS_FILE, db)
#         await update.message.reply_text("✅ Mahsulot o'chirildi")

# # --- CANCEL ---
# async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text("❌ Bekor qilindi.")
#     return ConversationHandler.END

# # --- MAIN ---
# def main():
#     application = Application.builder().token(BOT_TOKEN).build()

#     search_conv_handler = ConversationHandler(
#         entry_points=[CommandHandler("search", search_command)],
#         states={"SEARCHING": [MessageHandler(filters.TEXT & ~filters.COMMAND, search_products)]},
#         fallbacks=[CommandHandler("cancel", cancel)]
#     )

#     application.add_handler(search_conv_handler)
#     application.add_handler(CommandHandler("myorders", my_orders))
#     application.add_handler(CommandHandler("download_orders", download_orders))
#     application.add_handler(CommandHandler("export_products", export_products))
#     application.add_handler(CommandHandler("import_products", import_products))
#     application.add_handler(CommandHandler("delete_product", delete_product))
#     application.add_handler(CommandHandler("add_product", add_product))

#     application.run_polling()

# if __name__ == '__main__':
#     main()

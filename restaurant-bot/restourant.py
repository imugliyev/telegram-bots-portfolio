import asyncio
import gspread
from aiogram import Bot, Dispatcher, types
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# ======== НАСТРОЙКИ GOOGLE SHEETS ========
SCOPES = [
]
CREDENTIALS_FILE = 'credentials.json'
SPREADSHEET_NAME = 'Telegram Orders'

ADMIN_CHAT_ID = '' # ID чата администраторов
ADMIN_BOT_TOKEN = ""  # Токен бота-администратора

def google_sheets_auth():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPES)
    client = gspread.authorize(creds)
    return client.open(SPREADSHEET_NAME).sheet1

# ======== ИНИЦИАЛИЗАЦИЯ БОТА ========
bot = Bot(token="токен бота")
dp = Dispatcher()
sheet = google_sheets_auth()

# ======== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ========
user_carts = {}
user_data = {}
order_states = {}

menu_items = {
    "Плов": 250,
    "Шашлык": 300,
    "Лагман": 200,
    "Самса": 80,
    "Салат овощной": 150,
    "Чай": 50
}

# ======== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ========
def initialize_user(user_id: int):
    """Инициализирует данные пользователя, если они отсутствуют"""
    if user_id not in user_carts:
        user_carts[user_id] = {}
    if user_id not in user_data:
        user_data[user_id] = {"name": "", "address": "", "phone": ""}
    if user_id not in order_states:
        order_states[user_id] = "start"

# ======== КЛАВИАТУРЫ ========
main_builder = ReplyKeyboardBuilder()
main_builder.row(
    types.KeyboardButton(text="Заказать"),
    types.KeyboardButton(text="Меню"),
    types.KeyboardButton(text="Корзина")
)
main_builder.row(
    types.KeyboardButton(text="Халяль-сертификат"),
    types.KeyboardButton(text="Время доставки")
)
main_keyboard = main_builder.as_markup(resize_keyboard=True)

# ======== ОБРАБОТЧИКИ СООБЩЕНИЙ ========
@dp.message(lambda m: m.text == "/start")
async def start_handler(m: types.Message):
    user_id = m.from_user.id
    initialize_user(user_id)
    await m.answer(
        "🍴 Добро пожаловать в наш ресторан!\nВыберите действие:",
        reply_markup=main_keyboard
    )

@dp.message(lambda m: m.text == "Меню")
async def menu_handler(m: types.Message):
    initialize_user(m.from_user.id)
    builder = InlineKeyboardBuilder()
    for item, price in menu_items.items():
        builder.add(types.InlineKeyboardButton(
            text=f"{item} - {price}₽",
            callback_data=f"add_{item}"
        ))
    builder.adjust(2)
    await m.answer("🍔 Наше меню:", reply_markup=builder.as_markup())

@dp.message(lambda m: m.text == "Корзина")
async def cart_handler(m: types.Message):
    user_id = m.from_user.id
    initialize_user(user_id)
    
    cart = user_carts.get(user_id, {})
    if not cart:
        await m.answer("🛒 Ваша корзина пуста")
        return
    
    total = 0
    cart_text = "🛒 Ваша корзина:\n\n"
    for item, quantity in cart.items():
        price = menu_items[item] * quantity
        total += price
        cart_text += f"{item} x{quantity} = {price}₽\n"
    
    cart_text += f"\n💳 Итого: {total}₽"
    
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text="Очистить корзину",
        callback_data="clear_cart"
    ))
    builder.add(types.InlineKeyboardButton(
        text="Удалить позицию",
        callback_data="remove_item"
    ))
    await m.answer(cart_text, reply_markup=builder.as_markup())

@dp.message(lambda m: m.text == "Заказать")
async def order_handler(m: types.Message):
    user_id = m.from_user.id
    initialize_user(user_id)
    
    cart = user_carts.get(user_id, {})
    if not cart:
        await m.answer("Ваша корзина пуста! Добавьте товары из меню.")
        return
    
    order_states[user_id] = "waiting_name"
    await m.answer("📝 Для оформления заказа введите ваше имя:")

@dp.message(lambda m: order_states.get(m.from_user.id) == "waiting_name")
async def name_handler(m: types.Message):
    user_id = m.from_user.id
    initialize_user(user_id)  # Дополнительная проверка
    
    user_data[user_id]["name"] = m.text
    order_states[user_id] = "waiting_address"
    await m.answer("Отлично! Теперь введите адрес доставки:")

@dp.message(lambda m: order_states.get(m.from_user.id) == "waiting_address")
async def address_handler(m: types.Message):
    user_id = m.from_user.id
    initialize_user(user_id)  # Дополнительная проверка
    
    user_data[user_id]["address"] = m.text
    order_states[user_id] = "waiting_phone"
    await m.answer("Прекрасно! Теперь введите ваш телефон:")

@dp.message(lambda m: order_states.get(m.from_user.id) == "waiting_phone")
async def phone_handler(m: types.Message):
    user_id = m.from_user.id
    initialize_user(user_id)  # Дополнительная проверка
    
    user_data[user_id]["phone"] = m.text
    cart = user_carts.get(user_id, {})
    
    # Формируем текст заказа
    total = 0
    order_text = "✅ Ваш заказ оформлен!\n\n"
    order_text += f"👤 Имя: {user_data[user_id]['name']}\n"
    order_text += f"📱 Телефон: {user_data[user_id]['phone']}\n"
    order_text += f"🏠 Адрес: {user_data[user_id]['address']}\n\n"
    order_text += "🍽 Заказ:\n"
    
    order_items = []
    for item, quantity in cart.items():
        price = menu_items[item] * quantity
        total += price
        order_text += f"- {item} x{quantity} = {price}₽\n"
        order_items.append(f"{item} x{quantity}")
    
    order_text += f"\n💳 Итого: {total}₽\n\n"
    order_text += "⌛ Ожидайте доставку в течение часа!"
    
    # Записываем в Google Sheets
    try:
        row = [
            user_data[user_id]["name"],
            user_data[user_id]["phone"],
            user_data[user_id]["address"],
            ", ".join(order_items),
            str(total),
            str(user_id),
            f"@{m.from_user.username}" if m.from_user.username else "",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ]
        sheet.append_row(row)
    except Exception as e:
        print(f"Ошибка записи в Google Sheets: {e}")
        await m.answer("⚠ Произошла ошибка при сохранении заказа. Пожалуйста, повторите попытку позже.")
        return
    
    # Очищаем корзину и сбрасываем состояние
    user_carts[user_id] = {}
    order_states[user_id] = None
    
    await m.answer(order_text)

    # В функции phone_handler после записи в таблицу:
    # ... (после записи в Google Sheets)

    # Отправка уведомления в чат администраторов
    try:
        order_data = {
            "name": user_data[user_id]["name"],
            "phone": user_data[user_id]["phone"],
            "address": user_data[user_id]["address"],
            "items": ", ".join(order_items),
            "total": total,
            "user_id": user_id,
            "username": f"@{m.from_user.username}" if m.from_user.username else "",
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Создаем временного бота для отправки уведомления
        admin_bot = Bot(token=ADMIN_BOT_TOKEN)
        await admin_bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"🚀 Новый заказ!\n\n"
                f"👤 Имя: {order_data['name']}\n"
                f"📞 Телефон: {order_data['phone']}\n"
                f"🏠 Адрес: {order_data['address']}\n"
                f"🍽 Заказ: {order_data['items']}\n"
                f"💳 Сумма: {order_data['total']} руб.\n"
                f"🆔 User ID: {order_data['user_id']}\n"
                f"👤 Username: {order_data['username']}\n"
                f"📅 Дата: {order_data['datetime']}"
        )
        await admin_bot.close()
    except Exception as e:
        print(f"Ошибка отправки уведомления администратору: {e}")

@dp.message(lambda m: m.text == "Халяль-сертификат")
async def halal_handler(m: types.Message):
    initialize_user(m.from_user.id)
    await m.answer_photo(
        "https://sun9-37.userapi.com/impf/c824604/v824604537/458ae/s_dKkTlomFw.jpg?size=368x258&quality=96&sign=4588dcaf399b6faa8792422abe1b64c0&c_uniq_tag=CaE_hlt5vqAnvWAYIDYOaooymX8q6Blr83APoCD7Jmc&type=albumл",
        caption="Наш халяль-сертификат"
    )

@dp.message(lambda m: m.text == "Время доставки")
async def delivery_time_handler(m: types.Message):
    initialize_user(m.from_user.id)
    await m.answer(
        "⏰ Время работы и доставки:\n\n"
        "Понедельник-Пятница: 10:00 - 23:00\n"
        "Суббота-Воскресенье: 11:00 - 00:00\n\n"
        "🚚 Доставка занимает 30-60 минут"
    )

# ======== ОБРАБОТЧИКИ CALLBACK-КНОПОК ========
@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_to_cart(c: types.CallbackQuery):
    user_id = c.from_user.id
    initialize_user(user_id)
    
    item = c.data[4:]
    if user_id not in user_carts:
        user_carts[user_id] = {}
    
    if item not in user_carts[user_id]:
        user_carts[user_id][item] = 1
    else:
        user_carts[user_id][item] += 1
    
    await c.answer(f"{item} добавлен в корзину!")

@dp.callback_query(lambda c: c.data == "clear_cart")
async def clear_cart(c: types.CallbackQuery):
    user_id = c.from_user.id
    initialize_user(user_id)
    
    if user_id in user_carts:
        user_carts[user_id] = {}
    await c.message.edit_text("🛒 Корзина очищена!")
    await c.answer()

@dp.callback_query(lambda c: c.data == "remove_item")
async def remove_item_prompt(c: types.CallbackQuery):
    user_id = c.from_user.id
    initialize_user(user_id)
    
    cart = user_carts.get(user_id, {})
    if not cart:
        await c.answer("Корзина уже пуста!")
        return
    
    builder = InlineKeyboardBuilder()
    for item in cart.keys():
        builder.add(types.InlineKeyboardButton(
            text=item,
            callback_data=f"remove_{item}"
        ))
    builder.adjust(2)
    
    await c.message.edit_text(
        "Выберите позицию для удаления:",
        reply_markup=builder.as_markup()
    )
    await c.answer()

@dp.callback_query(lambda c: c.data.startswith("remove_"))
async def remove_item(c: types.CallbackQuery):
    user_id = c.from_user.id
    initialize_user(user_id)
    
    item = c.data[7:]
    if user_id in user_carts and item in user_carts[user_id]:
        if user_carts[user_id][item] > 1:
            user_carts[user_id][item] -= 1
            await c.answer(f"Удален один {item}")
        else:
            del user_carts[user_id][item]
            await c.answer(f"{item} полностью удален")
        
        # Обновляем сообщение с корзиной
        cart = user_carts.get(user_id, {})
        if cart:
            total = 0
            cart_text = "🛒 Ваша корзина:\n\n"
            for item, quantity in cart.items():
                price = menu_items[item] * quantity
                total += price
                cart_text += f"{item} x{quantity} = {price}₽\n"
            
            cart_text += f"\n💳 Итого: {total}₽"
            
            builder = InlineKeyboardBuilder()
            builder.add(types.InlineKeyboardButton(
                text="Очистить корзину",
                callback_data="clear_cart"
            ))
            builder.add(types.InlineKeyboardButton(
                text="Удалить позицию",
                callback_data="remove_item"
            ))
            await c.message.edit_text(cart_text, reply_markup=builder.as_markup())
        else:
            await c.message.edit_text("🛒 Ваша корзина пуста")
    else:
        await c.answer("Этого товара нет в корзине")

# ======== ОБРАБОТЧИК ЛЮБЫХ СООБЩЕНИЙ ========
@dp.message()
async def any_message_handler(m: types.Message):
    """Обработчик для любых сообщений, не попавших в другие обработчики"""
    initialize_user(m.from_user.id)
    await m.answer("Используйте кнопки меню для навигации")


# ======== ЗАПУСК БОТА ========
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
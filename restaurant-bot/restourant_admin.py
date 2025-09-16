import asyncio
import gspread
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Настройки
SCOPES = []
CREDENTIALS_FILE = 'credentials.json'
SPREADSHEET_NAME = 'Telegram Orders'
ADMIN_BOT_TOKEN = ""
ADMIN_CHAT_ID = 123456789  # ID вашего админ-чата

# Инициализация бота
bot = Bot(token=ADMIN_BOT_TOKEN)
dp = Dispatcher()

# Кэш для авторизации в Google Sheets
_client = None

def get_sheet():
    global _client
    if not _client:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPES)
        _client = gspread.authorize(creds)
    return _client.open(SPREADSHEET_NAME).sheet1

# Проверка прав администратора
async def is_admin(message: types.Message) -> bool:
    return message.chat.id == ADMIN_CHAT_ID

# Команда /start
@dp.message(Command("start"))
async def start_command(message: types.Message):
    if await is_admin(message):
        await message.answer("🤖 Бот администратора запущен!\n"
                            "Доступные команды:\n"
                            "/get_orders - все заказы\n"
                            "/recent_orders - последние заказы\n"
                            "/stats - статистика")
    else:
        await message.answer("⛔ Доступ запрещен!")

# Команда /get_orders
@dp.message(Command("get_orders"))
async def get_orders(message: types.Message):
    if not await is_admin(message):
        return await message.answer("⛔ Только для администраторов!")
    
    try:
        sheet = get_sheet()
        records = sheet.get_all_records()
        
        if not records:
            return await message.answer("📭 Заказов пока нет")
        
        response = "📋 Все заказы:\n\n"
        for i, record in enumerate(records, 1):
            response += (
                f"🔹 Заказ #{i}\n"
                f"👤 Имя: {record.get('Имя', 'Нет данных')}\n"
                f"📞 Телефон: {record.get('Телефон', 'Нет данных')}\n"
                f"🏠 Адрес: {record.get('Адрес', 'Нет данных')}\n"
                f"🍽 Заказ: {record.get('Заказ', 'Нет данных')}\n"
                f"💳 Сумма: {record.get('Сумма', 0)} руб.\n"
                f"🆔 User ID: {record.get('User ID', 'Нет данных')}\n"
                f"👤 Username: @{record.get('Username', 'Нет данных')}\n"
                f"📅 Дата: {record.get('Дата/Время', 'Нет данных')}\n"
                f"──────────────────\n"
            )
        
        # Разбиваем длинные сообщения
        if len(response) > 4000:
            for x in range(0, len(response), 4000):
                await message.answer(response[x:x+4000])
        else:
            await message.answer(response)
            
    except Exception as e:
        await message.answer(f"🚨 Ошибка: {str(e)}")

# Команда для получения последних N заказов
@dp.message(Command("recent_orders"))
async def recent_orders(message: types.Message):
    if not await is_admin(message):
        return await message.answer("⛔ Только для администраторов!")
    
    try:
        sheet = get_sheet()
        records = sheet.get_all_records()
        n = min(10, max(1, int(message.text.split()[1]) if len(message.text.split()) > 1 else 5))
        
        if not records:
            return await message.answer("📭 Заказов пока нет")
        
        response = f"📋 Последние {n} заказов:\n\n"
        for record in records[-n:]:
            response += (
                f"👤 Имя: {record.get('Имя', 'Нет данных')}\n"
                f"📞 Телефон: {record.get('Телефон', 'Нет данных')}\n"
                f"💳 Сумма: {record.get('Сумма', 0)} руб.\n"
                f"📅 Дата: {record.get('Дата/Время', 'Нет данных')}\n"
                f"──────────────────\n"
            )
        
        await message.answer(response)
    except Exception as e:
        await message.answer(f"🚨 Ошибка: {str(e)}")

# Команда для получения статистики
@dp.message(Command("stats"))
async def get_stats(message: types.Message):
    if not await is_admin(message):
        return await message.answer("⛔ Только для администраторов!")
    
    try:
        sheet = get_sheet()
        records = sheet.get_all_records()
        
        if not records:
            return await message.answer("📭 Заказов пока нет")
        
        total_orders = len(records)
        total_revenue = sum(float(record.get('Сумма', 0)) for record in records)
        
        # Статистика по продуктам
        products = {}
        for record in records:
            order_items = record.get('Заказ', '').split(',')
            for item in order_items:
                item = item.strip()
                if item:
                    products[item] = products.get(item, 0) + 1
        
        top_products = sorted(products.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Форматируем даты для временной статистики
        dates = []
        for record in records:
            date_str = record.get('Дата/Время', '')
            if date_str:
                try:
                    dt = datetime.strptime(date_str, '%d.%m.%Y %H:%M:%S')
                    dates.append(dt)
                except:
                    pass
        
        response = (
            "📊 Статистика заказов:\n\n"
            f"🔢 Всего заказов: {total_orders}\n"
            f"💰 Общая выручка: {total_revenue:.2f} руб.\n\n"
            "🏆 Топ товаров:\n"
        )
        
        for i, (product, count) in enumerate(top_products, 1):
            response += f"{i}. {product}: {count} зак.\n"
        
        if dates:
            min_date = min(dates).strftime('%d.%m.%Y')
            max_date = max(dates).strftime('%d.%m.%Y')
            response += f"\n📅 Период: с {min_date} по {max_date}"
        
        await message.answer(response)
    except Exception as e:
        await message.answer(f"🚨 Ошибка: {str(e)}")

# Уведомление о новом заказе
async def send_new_order(order_data: dict):
    try:
        message = (
            "🚀 НОВЫЙ ЗАКАЗ!\n\n"
            f"👤 Имя: {order_data.get('name', '')}\n"
            f"📞 Телефон: {order_data.get('phone', '')}\n"
            f"🏠 Адрес: {order_data.get('address', '')}\n"
            f"🍽 Заказ: {order_data.get('items', '')}\n"
            f"💳 Сумма: {order_data.get('total', 0)} руб.\n"
            f"🆔 User ID: {order_data.get('user_id', '')}\n"
            f"👤 Username: @{order_data.get('username', '')}\n"
            f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
        )
        await bot.send_message(ADMIN_CHAT_ID, message)
    except Exception as e:
        print(f"Ошибка отправки уведомления: {str(e)}")

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ChatMemberAdministrator
from aiogram import F
import pytz

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

MOSCOW_TZ = pytz.timezone('Europe/Moscow')

def get_moscow_time():
    return datetime.now(MOSCOW_TZ)

active_feedings = {}

def get_start_keyboard():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🍼 Начать кормление", callback_data="start_feeding")]
    ])

def get_finish_keyboard():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Завершить кормление", callback_data="finish_feeding"),
         types.InlineKeyboardButton(text="❌ Отменить кормление", callback_data="cancel_feeding")]
    ])

async def is_user_admin(chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return isinstance(member, ChatMemberAdministrator) or member.status == "creator"
    except Exception as e:
        logger.error(f"Ошибка при проверке прав администратора: {e}")
        return False

async def has_permission(chat_id: int, user_id: int, feeding_user_id: int) -> bool:
    if user_id == feeding_user_id:
        return True
    return await is_user_admin(chat_id, user_id)

@dp.message(Command("start", "help"))
async def start_cmd(message: types.Message):
    text = (
        "👶 Бот для отслеживания кормлений\n\n"
        "Команды:\n"
        "/start - Начать работу\n"
        "/help - Показать справку\n"
        "/feeding - Начать кормление\n"
        "/end_feeding - Завершить кормление\n"
        "/cancel - Отменить кормление\n\n"
        "Просто нажмите кнопку ниже, чтобы начать:"
    )
    await message.answer(text, reply_markup=get_start_keyboard())

async def ask_prepared_ml(chat_id: int):
    msg = await bot.send_message(chat_id, "Сколько мл приготовлено?")
    active_feedings[chat_id]['prepared_request_id'] = msg.message_id
    active_feedings[chat_id]['state'] = 'waiting_prepared'

async def ask_eaten_ml(chat_id: int):
    msg = await bot.send_message(chat_id, "Сколько мл съедено?")
    active_feedings[chat_id]['eaten_request_id'] = msg.message_id
    active_feedings[chat_id]['state'] = 'waiting_eaten'

async def delete_messages(chat_id: int, *message_ids):
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id, msg_id)
        except Exception as e:
            logger.error(f"Ошибка при удалении сообщения {msg_id}: {e}")

@dp.callback_query(F.data == "start_feeding")
async def start_feeding_callback(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    user_name = callback.from_user.full_name
    
    if chat_id in active_feedings:
        await callback.answer("❌ Уже есть активное кормление!", show_alert=True)
        return
    
    start_time = get_moscow_time()
    text = (
        "🍼 Кормление начато!\n"
        f"👤 Кто кормит: {user_name}\n"
        f"📅 Дата: {start_time.strftime('%d.%m.%Y')}\n"
        f"⏱️ Начало: {start_time.strftime('%H:%M')}\n"
        f"🛑 Конец: в процессе..."
    )
    
    msg = await bot.send_message(chat_id, text, reply_markup=get_finish_keyboard())
    
    active_feedings[chat_id] = {
        "message_id": msg.message_id,
        "start_time": start_time,
        "user_id": user_id,
        "user_name": user_name,
        "prepared_ml": None,
        "eaten_ml": None,
        "state": None,
        "prepared_request_id": None,
        "eaten_request_id": None
    }
    
    await ask_prepared_ml(chat_id)
    await callback.answer()

@dp.callback_query(F.data == "finish_feeding")
async def end_feeding_callback(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    
    if chat_id not in active_feedings:
        await callback.answer("❌ Нет активного кормления!", show_alert=True)
        return
    
    feeding_data = active_feedings[chat_id]
    if not await has_permission(chat_id, user_id, feeding_data["user_id"]):
        await callback.answer("⚠️ Только инициатор или администратор может завершить кормление!", show_alert=True)
        return
    
    await ask_eaten_ml(chat_id)
    await callback.answer("✅ Введите количество съеденного в мл")

@dp.callback_query(F.data == "cancel_feeding")
async def cancel_feeding_callback(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    
    if chat_id not in active_feedings:
        await callback.answer("❌ Нет активного кормления!", show_alert=True)
        return
    
    feeding_data = active_feedings[chat_id]
    if not await has_permission(chat_id, user_id, feeding_data["user_id"]):
        await callback.answer("⚠️ Только инициатор или администратор может отменить кормление!", show_alert=True)
        return
    
    # Удаляем сообщения с запросами
    request_ids = []
    if feeding_data['prepared_request_id']:
        request_ids.append(feeding_data['prepared_request_id'])
    if feeding_data['eaten_request_id']:
        request_ids.append(feeding_data['eaten_request_id'])
    
    await delete_messages(chat_id, *request_ids)
    
    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=feeding_data["message_id"],
        text="❌ Кормление отменено",
        reply_markup=get_start_keyboard()
    )
    
    del active_feedings[chat_id]
    await callback.answer("❌ Кормление отменено!")

@dp.message(Command("feeding"))
async def start_feeding_cmd(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    
    if chat_id in active_feedings:
        await message.reply("❌ Уже есть активное кормление! Сначала завершите его.")
        return
    
    start_time = get_moscow_time()
    text = (
        "🍼 Кормление начато!\n"
        f"👤 Кто кормит: {user_name}\n"
        f"📅 Дата: {start_time.strftime('%d.%m.%Y')}\n"
        f"⏱️ Начало: {start_time.strftime('%H:%M')}\n"
        f"🛑 Конец: в процессе..."
    )
    
    msg = await message.reply(text, reply_markup=get_finish_keyboard())
    
    active_feedings[chat_id] = {
        "message_id": msg.message_id,
        "start_time": start_time,
        "user_id": user_id,
        "user_name": user_name,
        "prepared_ml": None,
        "eaten_ml": None,
        "state": None,
        "prepared_request_id": None,
        "eaten_request_id": None
    }
    
    await ask_prepared_ml(chat_id)

@dp.message(Command("end_feeding"))
async def end_feeding_cmd(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if chat_id not in active_feedings:
        await message.reply("❌ Нет активного кормления!")
        return
    
    feeding_data = active_feedings[chat_id]
    if not await has_permission(chat_id, user_id, feeding_data["user_id"]):
        await message.reply("⚠️ Только инициатор или администратор может завершить кормление!")
        return
    
    await ask_eaten_ml(chat_id)

@dp.message(Command("cancel"))
async def cancel_feeding_cmd(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if chat_id not in active_feedings:
        await message.reply("❌ Нет активного кормления!")
        return
    
    feeding_data = active_feedings[chat_id]
    if not await has_permission(chat_id, user_id, feeding_data["user_id"]):
        await message.reply("⚠️ Только инициатор или администратор может отменить кормление!")
        return
    
    # Удаляем сообщения с запросами
    request_ids = []
    if feeding_data['prepared_request_id']:
        request_ids.append(feeding_data['prepared_request_id'])
    if feeding_data['eaten_request_id']:
        request_ids.append(feeding_data['eaten_request_id'])
    
    await delete_messages(chat_id, *request_ids)
    
    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=feeding_data["message_id"],
        text="❌ Кормление отменено",
        reply_markup=get_start_keyboard()
    )
    
    del active_feedings[chat_id]

@dp.message(F.text)
async def handle_ml_input(message: types.Message):
    chat_id = message.chat.id
    if chat_id not in active_feedings:
        return

    feeding_data = active_feedings[chat_id]
    state = feeding_data['state']
    
    if state not in ['waiting_prepared', 'waiting_eaten']:
        return

    try:
        ml = int(message.text)
        if ml < 0:
            raise ValueError
    except ValueError:
        await message.reply("Пожалуйста, введите корректное положительное число (например: 150)")
        return

    # Удаляем сообщение пользователя и запрос
    request_id = None
    if state == 'waiting_prepared':
        feeding_data['prepared_ml'] = ml
        request_id = feeding_data['prepared_request_id']
        feeding_data['state'] = None
        
        # Обновляем основное сообщение
        start_time = feeding_data['start_time']
        text = (
            "🍼 Кормление начато!\n"
            f"👤 Кто кормит: {feeding_data['user_name']}\n"
            f"📅 Дата: {start_time.strftime('%d.%m.%Y')}\n"
            f"⏱️ Начало: {start_time.strftime('%H:%M')}\n"
            f"🍶 Приготовлено: {ml} мл\n"
            f"🛑 Конец: в процессе..."
        )
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=feeding_data['message_id'],
            text=text,
            reply_markup=get_finish_keyboard()
        )
        
    elif state == 'waiting_eaten':
        feeding_data['eaten_ml'] = ml
        request_id = feeding_data['eaten_request_id']
        feeding_data['state'] = None
        
        # Завершаем кормление
        end_time = get_moscow_time()
        start_time = feeding_data['start_time']
        duration = end_time - start_time
        minutes = duration.seconds // 60
        finisher_name = message.from_user.full_name
        
        prepared = feeding_data['prepared_ml'] or "не указано"
        eaten = ml
        
        text = (
            "✅ Кормление завершено!\n"
            f"👤 Кто кормил: {feeding_data['user_name']}\n"
            f"👤 Завершил: {finisher_name}\n"
            f"📅 Дата: {start_time.strftime('%d.%m.%Y')}\n"
            f"⏱️ Начало: {start_time.strftime('%H:%M')}\n"
            f"⏱️ Конец: {end_time.strftime('%H:%M')}\n"
            f"⏳ Длительность: {minutes} мин\n"
            f"🍶 Приготовлено: {prepared} мл\n"
            f"🍴 Съедено: {eaten} мл"
        )
        
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=feeding_data['message_id'],
            text=text,
            reply_markup=get_start_keyboard()
        )
        
        del active_feedings[chat_id]
    
    # Удаляем запрос и сообщение пользователя
    await delete_messages(chat_id, request_id, message.message_id)




if __name__ == "__main__":
    logger.info("Бот запущен!")
    dp.run_polling(bot)
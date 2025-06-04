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

bot = Bot(token=os.getenv("BOT_TOKEN"))
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
        "user_name": user_name
    }
    
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
    
    end_time = get_moscow_time()
    start_time = feeding_data["start_time"]
    duration = end_time - start_time
    minutes = duration.seconds // 60
    finisher_name = callback.from_user.full_name
    
    text = (
        "✅ Кормление завершено!\n"
        f"👤 Кто кормил: {feeding_data['user_name']}\n"
        f"👤 Завершил: {finisher_name}\n"
        f"📅 Дата: {start_time.strftime('%d.%m.%Y')}\n"
        f"⏱️ Начало: {start_time.strftime('%H:%M')}\n"
        f"⏱️ Конец: {end_time.strftime('%H:%M')}\n"
        f"⏳ Длительность: {minutes} мин"
    )
    
    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=feeding_data["message_id"],
        text=text,
        reply_markup=get_start_keyboard()
    )
    
    del active_feedings[chat_id]
    await callback.answer("✅ Кормление завершено!")

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
        "user_name": user_name
    }

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
    
    end_time = get_moscow_time()
    start_time = feeding_data["start_time"]
    duration = end_time - start_time
    minutes = duration.seconds // 60
    finisher_name = message.from_user.full_name
    
    text = (
        "✅ Кормление завершено!\n"
        f"👤 Кто кормил: {feeding_data['user_name']}\n"
        f"👤 Завершил: {finisher_name}\n"
        f"📅 Дата: {start_time.strftime('%d.%m.%Y')}\n"
        f"⏱️ Начало: {start_time.strftime('%H:%M')}\n"
        f"⏱️ Конец: {end_time.strftime('%H:%M')}\n"
        f"⏳ Длительность: {minutes} мин"
    )
    
    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=feeding_data["message_id"],
        text=text,
        reply_markup=get_start_keyboard()
    )
    
    del active_feedings[chat_id]

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
    
    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=feeding_data["message_id"],
        text="❌ Кормление отменено",
        reply_markup=get_start_keyboard()
    )
    
    del active_feedings[chat_id]

if __name__ == "__main__":
    logger.info("Бот запущен!")
    dp.run_polling(bot)
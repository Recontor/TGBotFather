import asyncio
import logging
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import ADMIN_PASSWORD
from database import set_rate, get_rate, log_action, get_global_stats

# --- Стани бота (FSM) ---
class BotStates(StatesGroup):
    waiting_for_amount = State()   # Очікування введення суми
    admin_active = State()         # Стан авторизованого адміна

# --- Клавіатури ---
main_menu = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text="💱 Курс валют"), types.KeyboardButton(text="ℹ️ Допомога")],
        [types.KeyboardButton(text="📞 Контакти"), types.KeyboardButton(text="Тех. підтримка")]
    ],
    resize_keyboard=True
)

def currency_buttons():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="💵USD новий", callback_data="currency_USD"),
         types.InlineKeyboardButton(text="🇺🇸USD старий", callback_data="currency_USD White")],
        [types.InlineKeyboardButton(text="🇪🇺EUR", callback_data="currency_EUR"),
         types.InlineKeyboardButton(text="🇵🇱PLN", callback_data="currency_PLN")],
        [types.InlineKeyboardButton(text="🇬🇧GBP", callback_data="currency_GBP"),
         types.InlineKeyboardButton(text="🇨🇦CAD", callback_data="currency_CAD")],
        [types.InlineKeyboardButton(text="🇨🇿CZK", callback_data="currency_CZK"),
         types.InlineKeyboardButton(text="🇸🇪SEK", callback_data="currency_SEK")],
        [types.InlineKeyboardButton(text="🇨🇭CHF", callback_data="currency_CHF")]
    ])

def calculation_choice_buttons():
    return types.InlineKeyboardMarkup(inline_keyboard=[[
        types.InlineKeyboardButton(text="🧮 Розрахувати суму", callback_data="confirm_calc"),
        types.InlineKeyboardButton(text="❌ Відміна", callback_data="cancel_calc")
    ]])

def operation_type_buttons():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="Купляємо валюту(ми беремо)", callback_data="op_buy"),
            types.InlineKeyboardButton(text="Продаємо валюту(ми видаємо)", callback_data="op_sell")
        ],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="cancel_calc")]
    ])

# --- Хендлери користувача ---
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Вітаємо! Я допоможу вам дізнатися актуальний курс валют\n"
        "Оберіть потрібний розділ меню нижче:",
        reply_markup=main_menu,
        parse_mode="Markdown"
    )

async def menu_handler(message: types.Message, state: FSMContext):
    if message.text == "💱 Курс валют":
        await message.answer("Оберіть валюту для перегляду курсу:", reply_markup=currency_buttons())
    elif message.text == "ℹ️ Допомога":
        await message.answer(
            "📖 **Як користуватися ботом:**\n"
            "1. Оберіть валюту в розділі «Курс валют»\n"
            "2. Бот покаже курс купівлі та продажу\n"
            "3. Натисніть «Розрахувати», щоб конвертувати суму в грн\n\n"
            "⚠️ **Важливо:** Курси динамічні та можуть змінюватися протягом дня(навіть пару разів на день)\n"
            "Оновлення відбувається щогодини\n"
            "Бот лише відображає офіційні дані, він не встановлює курси та не впливає на їх зміну\n"
            "ℹ️ Якщо курс змінився — це рішення банку/обмінника, а бот просто показує актуальну інформацію",
            parse_mode="Markdown"
        )
    elif message.text == "📞 Контакти":
        await message.answer(
            "📞 **Наші контакти:**\n\nКиївстар: `+380 96 782 4474`\nVodafone: `+380 95 454 0922`\n Написати в телеграм: +380 95 454 0922",
            parse_mode="Markdown"
        )
    elif message.text == "Меню":
        await start_handler(message, state)
        
async def currency_callback(callback: types.CallbackQuery, state: FSMContext):
    currency = callback.data.replace("currency_", "")
    rates = get_rate(currency) # Тепер очікуємо кортеж (buy, sell)
    
    if not rates:
        await callback.answer("❌ Курс ще не встановлено", show_alert=True)
        return

    buy, sell = rates
    await state.update_data(chosen_currency=currency, rate_buy=buy, rate_sell=sell)
    
    await callback.message.answer(
        f"📊 **Курс {currency}:**\n"
        f"Купівля: `{buy:.2f} UAH`\n"
        f"Продаж: `{sell:.2f} UAH`\n\n"
        "Бажаєте розрахувати конкретну суму?",
        reply_markup=calculation_choice_buttons(),
        parse_mode="Markdown"
    )
    await callback.answer()
    log_action(callback.from_user.id, "view_rate", currency)

async def calc_choice_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "confirm_calc":
        await callback.message.edit_text("Оберіть тип операції:", reply_markup=operation_type_buttons())
    elif callback.data == "cancel_calc":
        await state.clear()
        await callback.message.edit_text("🏠 Скасовано. Оберіть валюту в меню")
    await callback.answer()

async def operation_type_handler(callback: types.CallbackQuery, state: FSMContext):
    op_type = callback.data.replace("op_", "")
    await state.update_data(op_type=op_type)
    
    data = await state.get_data()
    currency = data.get("chosen_currency")
    
    await state.set_state(BotStates.waiting_for_amount)
    action_text = "купити" if op_type == "buy" else "продати"
    await callback.message.edit_text(f"💰 Введіть суму в **{currency}**, яку ви хочете {action_text}:")

async def convert_handler(message: types.Message, state: FSMContext):
    if len(message.text) > 12:
        await message.answer("⚠️ Число занадто велике")
        return

    data = await state.get_data()
    currency = data.get("chosen_currency")
    op_type = data.get("op_type")
    
    rate = data.get("rate_buy") if op_type == "buy" else data.get("rate_sell")

    try:
        amount = float(message.text.replace(",", ".").strip())
        if amount <= 0:
            await message.answer("⚠️ Введіть число більше нуля")
            return

        result = amount * rate
        action_name = "Купівля" if op_type == "buy" else "Продаж"
        
        await message.answer(
            f"✅ **Результат ({action_name}):**\n"
            f"{amount} {currency} = **{result:.2f} UAH**\n\n"
            f"_За курсом {rate:.2f}_",
            parse_mode="Markdown"
        )
        await state.clear() # Очищуємо після розрахунку
        log_action(message.from_user.id, f"convert_{op_type}", currency)
    except ValueError:
        await message.answer("🔢 Будь ласка, введіть число")

# --- Адмін-функції ---

async def login_handler(message: types.Message, state: FSMContext):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ `/login пароль`")
        return
    if parts[1] == ADMIN_PASSWORD:
        await state.set_state(BotStates.admin_active)
        await message.answer("🔓 Адмін-доступ активовано на 10 хв")
        await show_admin_panel(message)
    else:
        await message.answer("⛔ Відмова")

async def set_rate_handler(message: types.Message, state: FSMContext):
    if await state.get_state() != BotStates.admin_active:
        await message.answer("⛔ Спочатку /login")
        return
    try:
        # Формат: /setrate USD 41.2 41.8
        _, currency, buy, sell = message.text.split()
        set_rate(currency.upper(), float(buy.replace(",", ".")), float(sell.replace(",", ".")))
        await message.answer(f"✅ Курс {currency.upper()} оновлено:\nКупівля: {buy}\nПродаж: {sell}")
    except:
        await message.answer("⚠️ Формат: `/setrate USD 41.2 41.8` ")

async def logout_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🔒 Вихід виконано")

async def show_admin_panel(message: types.Message):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [types.InlineKeyboardButton(text="✏️ Змінити курс", callback_data="admin_edit")]
    ])
    await message.answer("⚙️ **Адмін-панель:**", reply_markup=kb, parse_mode="Markdown")

async def admin_callback(callback: types.CallbackQuery, state: FSMContext):
    if await state.get_state() != BotStates.admin_active:
        await callback.answer("❌ Сесія завершена", show_alert=True)
        return
    if callback.data == "admin_stats":
        u, a = get_global_stats()
        await callback.message.answer(f"📊 Користувачів: {u}\nЗапитів: {a}")
    elif callback.data == "admin_edit":
        await callback.message.answer("Команда: `/setrate ВАЛЮТА КУПІВЛЯ ПРОДАЖ`")
    await callback.answer()
    
async def get_rate_handler(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("Використання: `/getrate USD`", parse_mode="Markdown")
            return
            
        curr = parts[1].upper()
        rates = get_rate(curr)
        
        if rates:
            buy, sell = rates
            await message.answer(
                f"💱 **Курс {curr}:**\n"
                f"🔵 Купівля: `{buy:.2f} UAH`\n"
                f"🔴 Продаж: `{sell:.2f} UAH`", 
                parse_mode="Markdown"
            )
        else:
            await message.answer(f"❌ Валюту {curr} не знайдено в базі")
    except Exception as e:
        logging.error(f"Error in get_rate_handler: {e}")
        await message.answer("⚠️ Помилка при отриманні курсу")
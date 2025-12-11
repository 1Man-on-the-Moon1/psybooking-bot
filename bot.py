"""
PsyBooking Telegram Bot - главный файл
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler
)

import config
from database import Database
from scheduler import Scheduler

# Google Calendar - опционально
try:
    from google_calendar import get_calendar_client
    GOOGLE_CALENDAR_ENABLED = True
except Exception as e:
    logger.warning(f"Google Calendar недоступен: {e}")
    GOOGLE_CALENDAR_ENABLED = False
    get_calendar_client = None

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога
SELECTING_DATE, SELECTING_SLOT = range(2)

# Инициализация
db = Database()
scheduler = Scheduler(db)

# Инициализация Google Calendar (если доступен)
if GOOGLE_CALENDAR_ENABLED:
    try:
        calendar_client = get_calendar_client()
        if not calendar_client.is_authenticated():
            logger.warning("Google Calendar не авторизован")
            GOOGLE_CALENDAR_ENABLED = False
            calendar_client = None
    except Exception as e:
        logger.warning(f"Ошибка инициализации Google Calendar: {e}")
        GOOGLE_CALENDAR_ENABLED = False
        calendar_client = None
else:
    calendar_client = None


# === Вспомогательные функции ===

def check_rate_limit(user_id: int) -> bool:
    """Проверить rate limit для пользователя"""
    return db.check_rate_limit(user_id, config.RATE_LIMIT_REQUESTS_PER_MINUTE, 1)


def check_max_bookings(user_id: int) -> bool:
    """Проверить, не превышен ли лимит активных записей"""
    active_bookings = db.get_active_bookings_for_user(user_id)
    return len(active_bookings) < config.MAX_ACTIVE_BOOKINGS_PER_USER


def format_booking_confirmation(booking: dict, event_link: str) -> str:
    """Форматировать сообщение подтверждения записи"""
    tz = pytz.timezone(config.PRIMARY_TZ)
    start_utc = datetime.fromisoformat(booking['start_time_utc']).replace(tzinfo=pytz.utc)
    start_local = start_utc.astimezone(tz)
    
    message = f"""
✅ <b>Запись подтверждена!</b>

📅 Дата: {start_local.strftime('%d.%m.%Y')}
🕐 Время: {start_local.strftime('%H:%M')} (по времени Минска)
⏱ Длительность: {config.SESSION_DURATION_MINUTES} минут

Событие добавлено в календарь.
Вы получите напоминание за час до консультации.

<a href="{event_link}">📎 Добавить в свой календарь</a>

Если вам нужно отменить или перенести запись, пожалуйста, свяжитесь с психологом заранее.
"""
    return message


# === Команды бота ===

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    welcome_message = f"""
👋 Здравствуйте, {user.first_name}!

Я бот для записи на консультации к психологу.

Здесь вы можете:
• Просмотреть доступные слоты для записи
• Записаться на удобное время
• Получить ссылку для добавления встречи в календарь

Нажмите кнопку ниже, чтобы начать запись.
"""
    
    keyboard = [
        [InlineKeyboardButton("📅 Записаться на консультацию", callback_data="book_start")],
        [InlineKeyboardButton("📋 Мои записи", callback_data="my_bookings"),
         InlineKeyboardButton("🕐 Доступные слоты", callback_data="slots")],
        [InlineKeyboardButton("🆘 SOS - Связаться с психологом", url="tg://user?id=783321437")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
ℹ️ <b>Справка по использованию бота</b>

<b>Доступные команды:</b>
/start - Начать работу с ботом
/book - Записаться на консультацию
/slots - Посмотреть ближайшие свободные слоты
/mybookings - Мои записи
/help - Показать эту справку

<b>Как записаться:</b>
1. Нажмите "Записаться" или используйте команду /book
2. Выберите удобную дату
3. Выберите подходящее время
4. Получите подтверждение с ссылкой на событие

<b>Важно:</b>
• Запись возможна минимум за {config.MIN_HOURS_BEFORE_BOOKING} часа
• Длительность консультации: {config.SESSION_DURATION_MINUTES} минут
• Максимум активных записей: {config.MAX_ACTIVE_BOOKINGS_PER_USER}

Если у вас возникли вопросы, свяжитесь с психологом напрямую.
"""
    
    keyboard = [
        [InlineKeyboardButton("📅 Записаться", callback_data="book_start")],
        [InlineKeyboardButton("🆘 SOS - Связаться с психологом", url="tg://user?id=783321437")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(help_text, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await update.callback_query.message.edit_text(help_text, parse_mode='HTML', reply_markup=reply_markup)


async def book_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /book - начало процесса записи"""
    user_id = update.effective_user.id
    
    # Проверка rate limit
    if not check_rate_limit(user_id):
        await update.message.reply_text(
            "⚠️ Слишком много запросов. Пожалуйста, подождите немного и попробуйте снова."
        )
        return ConversationHandler.END
    
    # Проверка лимита записей
    if not check_max_bookings(user_id):
        await update.message.reply_text(
            f"⚠️ У вас уже есть максимальное количество активных записей ({config.MAX_ACTIVE_BOOKINGS_PER_USER}).\n"
            "Пожалуйста, дождитесь консультации или отмените одну из записей."
        )
        return ConversationHandler.END
    
    # Показать выбор даты
    return await show_date_selection(update, context)


async def show_date_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать выбор даты"""
    available_dates = scheduler.get_available_dates()
    
    if not available_dates:
        message = "😔 К сожалению, в ближайшее время нет доступных дат для записи."
        
        if update.message:
            await update.message.reply_text(message)
        else:
            await update.callback_query.message.edit_text(message)
        
        return ConversationHandler.END
    
    # Создать кнопки для дат
    keyboard = []
    
    # Сегодня и завтра (если доступны)
    today = datetime.now(pytz.timezone(config.PRIMARY_TZ)).date()
    tomorrow = today + timedelta(days=1)
    
    quick_buttons = []
    if today in available_dates:
        quick_buttons.append(
            InlineKeyboardButton("Сегодня", callback_data=f"date_{today.isoformat()}")
        )
    if tomorrow in available_dates:
        quick_buttons.append(
            InlineKeyboardButton("Завтра", callback_data=f"date_{tomorrow.isoformat()}")
        )
    
    if quick_buttons:
        keyboard.append(quick_buttons)
    
    # Остальные даты (первые 7)
    other_dates = [d for d in available_dates if d not in [today, tomorrow]][:7]
    for date_obj in other_dates:
        date_str = scheduler.format_date_local(date_obj)
        keyboard.append([
            InlineKeyboardButton(date_str, callback_data=f"date_{date_obj.isoformat()}")
        ])
    
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = "📅 Выберите удобную дату для консультации:"
    
    if update.message:
        await update.message.reply_text(message, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.edit_text(message, reply_markup=reply_markup)
    
    return SELECTING_DATE


async def date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора даты"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Проверка rate limit
    if not check_rate_limit(user_id):
        await query.message.edit_text(
            "⚠️ Слишком много запросов. Пожалуйста, подождите немного."
        )
        return ConversationHandler.END
    
    # Извлечь дату из callback_data
    date_str = query.data.replace("date_", "")
    selected_date = date.fromisoformat(date_str)
    
    # Сохранить выбранную дату в контексте
    context.user_data['selected_date'] = selected_date
    
    # Получить доступные слоты
    available_slots = scheduler.get_available_slots(selected_date)
    
    if not available_slots:
        await query.message.edit_text(
            f"😔 К сожалению, на {scheduler.format_date_local(selected_date)} нет свободных слотов.\n"
            "Пожалуйста, выберите другую дату.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Выбрать другую дату", callback_data="book_start")
            ]])
        )
        return SELECTING_DATE
    
    # Создать кнопки для слотов
    keyboard = []
    for slot in available_slots[:12]:  # Показать максимум 12 слотов
        time_range = f"{slot['start_local']} - {slot['end_local']}"
        keyboard.append([
            InlineKeyboardButton(
                time_range, 
                callback_data=f"slot_{slot['start_utc'].isoformat()}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Выбрать другую дату", callback_data="book_start")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = f"🕐 Выберите удобное время на {scheduler.format_date_local(selected_date)}:"
    
    await query.message.edit_text(message, reply_markup=reply_markup)
    
    return SELECTING_SLOT


async def slot_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора слота - создание записи"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    user_id = user.id
    
    # Извлечь время начала из callback_data
    start_time_str = query.data.replace("slot_", "")
    start_time_utc = datetime.fromisoformat(start_time_str).replace(tzinfo=pytz.utc)
    end_time_utc = start_time_utc + timedelta(minutes=config.SESSION_DURATION_MINUTES)
    
    # Показать индикатор загрузки
    await query.message.edit_text("⏳ Создаю запись...")
    
    # Попытка создать запись в БД
    booking_id = db.create_booking(
        client_telegram_id=user_id,
        client_username=user.username,
        client_first_name=user.first_name,
        client_last_name=user.last_name,
        start_time_utc=start_time_utc.isoformat(),
        end_time_utc=end_time_utc.isoformat()
    )
    
    if booking_id is None:
        # Слот уже занят
        await query.message.edit_text(
            "😔 К сожалению, этот слот уже занят другим клиентом.\n"
            "Пожалуйста, выберите другое время.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Выбрать другое время", callback_data="book_start")
            ]])
        )
        return ConversationHandler.END
    
    # Создать событие в Google Calendar
    if not GOOGLE_CALENDAR_ENABLED or not calendar_client or not calendar_client.is_authenticated():
        # Календарь не подключен - просто подтвердить запись
        db.update_booking_with_google_event(booking_id, '', '')
        
        tz = pytz.timezone(config.PRIMARY_TZ)
        start_local = start_time_utc.astimezone(tz)
        
        await query.message.edit_text(
            f"✅ Запись создана!\n\n"
            f"📅 Дата: {start_local.strftime('%d.%m.%Y')}\n"
            f"🕐 Время: {start_local.strftime('%H:%M')} (по времени Минска)\n"
            f"⏱ Длительность: {config.SESSION_DURATION_MINUTES} минут\n\n"
            f"⚠️ Календарь не подключен, событие не создано автоматически."
        )
        return ConversationHandler.END
    
    # Создать событие
    calendar_id = config.GOOGLE_CALENDAR_ID
    
    client_name = user.first_name
    if user.last_name:
        client_name += f" {user.last_name}"
    if user.username:
        client_name += f" (@{user.username})"
    
    event_result = calendar_client.create_event(
        calendar_id=calendar_id,
        summary=f"Консультация: {client_name}",
        description=f"Клиент: {client_name}\nTelegram ID: {user_id}",
        start_time=start_time_utc,
        end_time=end_time_utc
    )
    
    if event_result is None:
        # Ошибка создания события
        await query.message.edit_text(
            "⚠️ Запись создана, но произошла ошибка при добавлении в календарь.\n"
            "Пожалуйста, свяжитесь с психологом для подтверждения."
        )
        return ConversationHandler.END
    
    # Обновить запись с данными события
    db.update_booking_with_google_event(
        booking_id,
        event_result['event_id'],
        event_result['event_link']
    )
    
    # Получить обновленную запись
    booking = db.get_booking(booking_id)
    
    # Отправить подтверждение
    confirmation_message = format_booking_confirmation(booking, event_result['event_link'])
    
    # Добавить кнопки для дальнейших действий
    keyboard = [
        [InlineKeyboardButton("📅 Записаться ещё раз", callback_data="book_start"),
         InlineKeyboardButton("📋 Мои записи", callback_data="my_bookings")],
        [InlineKeyboardButton("🆘 SOS", url="tg://user?id=783321437"),
         InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(
        confirmation_message,
        parse_mode='HTML',
        disable_web_page_preview=True,
        reply_markup=reply_markup
    )
    
    return ConversationHandler.END


async def slots_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать ближайшие доступные слоты"""
    user_id = update.effective_user.id
    
    if not check_rate_limit(user_id):
        await update.message.reply_text(
            "⚠️ Слишком много запросов. Пожалуйста, подождите немного."
        )
        return
    
    next_slots = scheduler.get_next_available_slots(limit=10)
    
    if not next_slots:
        await update.message.reply_text(
            "😔 К сожалению, в ближайшее время нет доступных слотов."
        )
        return
    
    message = "🕐 <b>Ближайшие доступные слоты:</b>\n\n"
    
    current_date = None
    for slot in next_slots:
        slot_date = slot['date']
        if slot_date != current_date:
            current_date = slot_date
            message += f"\n📅 <b>{scheduler.format_date_local(slot_date)}</b>\n"
        
        message += f"   • {slot['start_local']} - {slot['end_local']}\n"
    
    message += "\n\nДля записи используйте команду /book"
    
    await update.message.reply_text(message, parse_mode='HTML')


async def my_bookings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать записи пользователя"""
    user_id = update.effective_user.id
    
    bookings = db.get_active_bookings_for_user(user_id)
    
    if not bookings:
        await update.message.reply_text(
            "У вас пока нет активных записей.\n\n"
            "Используйте /book для записи на консультацию."
        )
        return
    
    message = "📋 <b>Ваши записи:</b>\n\n"
    
    tz = pytz.timezone(config.PRIMARY_TZ)
    
    for booking in bookings:
        start_utc = datetime.fromisoformat(booking['start_time_utc']).replace(tzinfo=pytz.utc)
        start_local = start_utc.astimezone(tz)
        
        status_emoji = "✅" if booking['status'] == 'confirmed' else "⏳"
        
        message += f"{status_emoji} {start_local.strftime('%d.%m.%Y в %H:%M')}\n"
        
        if booking['event_link']:
            message += f"   <a href=\"{booking['event_link']}\">Ссылка на событие</a>\n"
        
        message += "\n"
    
    message += "Для отмены записи свяжитесь с психологом."
    
    await update.message.reply_text(
        message,
        parse_mode='HTML',
        disable_web_page_preview=True
    )


async def book_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Записаться'"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Проверка rate limit
    if not check_rate_limit(user_id):
        await query.message.edit_text(
            "⚠️ Слишком много запросов. Пожалуйста, подождите немного."
        )
        return ConversationHandler.END
    
    # Проверка лимита записей
    if not check_max_bookings(user_id):
        await query.message.edit_text(
            f"⚠️ У вас уже есть максимальное количество активных записей ({config.MAX_ACTIVE_BOOKINGS_PER_USER}).\n"
            "Пожалуйста, дождитесь консультации или отмените одну из записей."
        )
        return ConversationHandler.END
    
    return await show_date_selection(update, context)


async def my_bookings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Мои записи'"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    bookings = db.get_active_bookings_for_user(user_id)
    
    if not bookings:
        keyboard = [
            [InlineKeyboardButton("📅 Записаться", callback_data="book_start")],
            [InlineKeyboardButton("🆘 SOS", url="tg://user?id=783321437"),
             InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            "У вас пока нет активных записей.\n\n"
            "Нажмите кнопку ниже, чтобы записаться.",
            reply_markup=reply_markup
        )
        return
    
    message = "📋 <b>Ваши записи:</b>\n\n"
    
    tz = pytz.timezone(config.PRIMARY_TZ)
    
    for booking in bookings:
        start_utc = datetime.fromisoformat(booking['start_time_utc']).replace(tzinfo=pytz.utc)
        start_local = start_utc.astimezone(tz)
        
        status_emoji = "✅" if booking['status'] == 'confirmed' else "⏳"
        
        message += f"{status_emoji} {start_local.strftime('%d.%m.%Y в %H:%M')}\n"
        
        if booking['event_link']:
            message += f"   <a href=\"{booking['event_link']}\">Ссылка на событие</a>\n"
        
        message += "\n"
    
    message += "Для отмены записи свяжитесь с психологом."
    
    keyboard = [
        [InlineKeyboardButton("📅 Записаться ещё раз", callback_data="book_start")],
        [InlineKeyboardButton("🆘 SOS", url="tg://user?id=783321437"),
         InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(
        message,
        parse_mode='HTML',
        disable_web_page_preview=True,
        reply_markup=reply_markup
    )


async def slots_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Доступные слоты'"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if not check_rate_limit(user_id):
        await query.message.edit_text(
            "⚠️ Слишком много запросов. Пожалуйста, подождите немного."
        )
        return
    
    next_slots = scheduler.get_next_available_slots(limit=10)
    
    if not next_slots:
        keyboard = [
            [InlineKeyboardButton("🆘 SOS", url="tg://user?id=783321437"),
             InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            "😔 К сожалению, в ближайшее время нет доступных слотов.\n\n"
            "Свяжитесь с психологом для уточнения расписания.",
            reply_markup=reply_markup
        )
        return
    
    message = "🕐 <b>Ближайшие доступные слоты:</b>\n\n"
    
    current_date = None
    for slot in next_slots:
        slot_date = slot['date']
        if slot_date != current_date:
            current_date = slot_date
            message += f"\n📅 <b>{scheduler.format_date_local(slot_date)}</b>\n"
        
        message += f"   • {slot['start_local']} - {slot['end_local']}\n"
    
    message += "\n\nДля записи нажмите кнопку ниже."
    
    keyboard = [
        [InlineKeyboardButton("📅 Записаться", callback_data="book_start")],
        [InlineKeyboardButton("🆘 SOS", url="tg://user?id=783321437"),
         InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(
        message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Помощь'"""
    query = update.callback_query
    await query.answer()
    
    await help_command(update, context)


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Главное меню'"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    
    welcome_message = f"""
👋 Здравствуйте, {user.first_name}!

Я бот для записи на консультации к психологу.

Здесь вы можете:
• Просмотреть доступные слоты для записи
• Записаться на удобное время
• Получить ссылку для добавления встречи в календарь

Нажмите кнопку ниже, чтобы начать запись.
"""
    
    keyboard = [
        [InlineKeyboardButton("📅 Записаться на консультацию", callback_data="book_start")],
        [InlineKeyboardButton("📋 Мои записи", callback_data="my_bookings"),
         InlineKeyboardButton("🕐 Доступные слоты", callback_data="slots")],
        [InlineKeyboardButton("🆘 SOS - Связаться с психологом", url="tg://user?id=783321437")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(welcome_message, reply_markup=reply_markup)


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Отмена'"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(
        "❌ Запись отменена.\n\n"
        "Используйте /book когда будете готовы записаться.",
        reply_markup=reply_markup
    )
    
    return ConversationHandler.END


def main():
    """Запуск бота"""
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен!")
        return
    
    # Создать приложение
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # Conversation handler для процесса записи
    booking_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('book', book_command),
            CallbackQueryHandler(book_start_callback, pattern='^book_start$')
        ],
        states={
            SELECTING_DATE: [
                CallbackQueryHandler(date_selected, pattern='^date_'),
                CallbackQueryHandler(book_start_callback, pattern='^book_start$')
            ],
            SELECTING_SLOT: [
                CallbackQueryHandler(slot_selected, pattern='^slot_'),
                CallbackQueryHandler(book_start_callback, pattern='^book_start$')
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_callback, pattern='^cancel$')
        ],
    )
    
    # Добавить обработчики
    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('slots', slots_command))
    application.add_handler(CommandHandler('mybookings', my_bookings_command))
    application.add_handler(booking_conv_handler)
    application.add_handler(CallbackQueryHandler(help_callback, pattern='^help$'))
    application.add_handler(CallbackQueryHandler(my_bookings_callback, pattern='^my_bookings$'))
    application.add_handler(CallbackQueryHandler(slots_callback, pattern='^slots$'))
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern='^main_menu$'))
    
    # Запустить бота
    logger.info("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

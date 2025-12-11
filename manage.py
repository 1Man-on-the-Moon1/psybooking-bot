#!/usr/bin/env python3
"""
Скрипт управления PsyBooking Bot
"""
import sys
import argparse
from datetime import datetime
import pytz
from database import Database
from scheduler import Scheduler
import config


def init_db():
    """Инициализировать базу данных"""
    print("Инициализация базы данных...")
    db = Database()
    print("✅ База данных инициализирована успешно!")
    print(f"📁 Путь к БД: {config.DATABASE_PATH}")


def show_working_hours():
    """Показать текущие рабочие часы"""
    db = Database()
    hours = db.get_working_hours()
    
    days = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
    
    print("\n📅 Рабочие часы:")
    print("-" * 60)
    
    for h in hours:
        day_name = days[h['day_of_week']]
        status = "✅ Активен" if h['is_active'] else "❌ Выключен"
        print(f"{day_name:15} {h['start_time']} - {h['end_time']}  {status}")
    
    print("-" * 60)


def set_working_hours(day: int, start: str, end: str, active: bool = True):
    """Установить рабочие часы для дня"""
    db = Database()
    
    days = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
    
    if day < 0 or day > 6:
        print("❌ Ошибка: день недели должен быть от 0 (Вс) до 6 (Сб)")
        return
    
    db.update_working_hours(day, start, end, active)
    
    status = "активен" if active else "выключен"
    print(f"✅ Рабочие часы для {days[day]} обновлены: {start}-{end} ({status})")


def show_bookings(future_only: bool = True):
    """Показать записи"""
    db = Database()
    
    if future_only:
        bookings = db.get_all_future_bookings()
        print("\n📋 Будущие записи:")
    else:
        # Для показа всех записей нужно добавить метод в database.py
        bookings = db.get_all_future_bookings()
        print("\n📋 Все записи:")
    
    if not bookings:
        print("Нет записей")
        return
    
    print("-" * 80)
    
    tz = pytz.timezone(config.PRIMARY_TZ)
    
    for booking in bookings:
        start_utc = datetime.fromisoformat(booking['start_time_utc']).replace(tzinfo=pytz.utc)
        start_local = start_utc.astimezone(tz)
        
        client_name = booking['client_first_name'] or 'Неизвестно'
        if booking['client_last_name']:
            client_name += f" {booking['client_last_name']}"
        if booking['client_username']:
            client_name += f" (@{booking['client_username']})"
        
        status_emoji = {
            'pending': '⏳',
            'confirmed': '✅',
            'cancelled': '❌'
        }.get(booking['status'], '❓')
        
        print(f"ID: {booking['id']}")
        print(f"Клиент: {client_name}")
        print(f"Telegram ID: {booking['client_telegram_id']}")
        print(f"Дата/время: {start_local.strftime('%d.%m.%Y %H:%M')} (Минск)")
        print(f"Статус: {status_emoji} {booking['status']}")
        if booking['google_event_id']:
            print(f"Google Event ID: {booking['google_event_id']}")
        if booking['event_link']:
            print(f"Ссылка: {booking['event_link']}")
        print("-" * 80)


def cancel_booking(booking_id: int):
    """Отменить запись"""
    db = Database()
    
    booking = db.get_booking(booking_id)
    if not booking:
        print(f"❌ Запись с ID {booking_id} не найдена")
        return
    
    if booking['status'] == 'cancelled':
        print(f"⚠️ Запись {booking_id} уже отменена")
        return
    
    # Отменить в БД
    db.cancel_booking(booking_id)
    
    # TODO: Отменить событие в Google Calendar
    # if booking['google_event_id']:
    #     calendar_client = get_calendar_client()
    #     calendar_client.delete_event(config.GOOGLE_CALENDAR_ID, booking['google_event_id'])
    
    print(f"✅ Запись {booking_id} отменена")


def show_available_slots(date_str: str = None):
    """Показать доступные слоты на дату"""
    db = Database()
    scheduler = Scheduler(db)
    
    tz = pytz.timezone(config.PRIMARY_TZ)
    
    if date_str:
        # Парсить дату
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            print("❌ Неверный формат даты. Используйте YYYY-MM-DD")
            return
    else:
        # Сегодня
        date_obj = datetime.now(tz).date()
    
    print(f"\n🕐 Доступные слоты на {scheduler.format_date_local(date_obj)}:")
    print("-" * 60)
    
    slots = scheduler.get_available_slots(date_obj)
    
    if not slots:
        print("Нет доступных слотов")
        return
    
    for slot in slots:
        print(f"  {slot['start_local']} - {slot['end_local']}")
    
    print("-" * 60)
    print(f"Всего слотов: {len(slots)}")


def show_settings():
    """Показать настройки"""
    db = Database()
    
    print("\n⚙️ Настройки системы:")
    print("-" * 60)
    
    settings_keys = ['primary_tz', 'min_hours_before_booking']
    
    for key in settings_keys:
        value = db.get_setting(key)
        print(f"{key}: {value}")
    
    print("-" * 60)


def main():
    parser = argparse.ArgumentParser(description='Управление PsyBooking Bot')
    subparsers = parser.add_subparsers(dest='command', help='Команды')
    
    # init
    subparsers.add_parser('init', help='Инициализировать базу данных')
    
    # working-hours
    wh_parser = subparsers.add_parser('working-hours', help='Управление рабочими часами')
    wh_subparsers = wh_parser.add_subparsers(dest='wh_command')
    
    wh_subparsers.add_parser('show', help='Показать рабочие часы')
    
    wh_set = wh_subparsers.add_parser('set', help='Установить рабочие часы')
    wh_set.add_argument('day', type=int, help='День недели (0=Вс, 1=Пн, ..., 6=Сб)')
    wh_set.add_argument('start', help='Время начала (HH:MM)')
    wh_set.add_argument('end', help='Время окончания (HH:MM)')
    wh_set.add_argument('--inactive', action='store_true', help='Сделать день неактивным')
    
    # bookings
    bookings_parser = subparsers.add_parser('bookings', help='Управление записями')
    bookings_subparsers = bookings_parser.add_subparsers(dest='bookings_command')
    
    bookings_subparsers.add_parser('show', help='Показать записи')
    
    cancel_parser = bookings_subparsers.add_parser('cancel', help='Отменить запись')
    cancel_parser.add_argument('id', type=int, help='ID записи')
    
    # slots
    slots_parser = subparsers.add_parser('slots', help='Показать доступные слоты')
    slots_parser.add_argument('--date', help='Дата (YYYY-MM-DD), по умолчанию сегодня')
    
    # settings
    subparsers.add_parser('settings', help='Показать настройки')
    
    args = parser.parse_args()
    
    if args.command == 'init':
        init_db()
    
    elif args.command == 'working-hours':
        if args.wh_command == 'show':
            show_working_hours()
        elif args.wh_command == 'set':
            set_working_hours(args.day, args.start, args.end, not args.inactive)
        else:
            wh_parser.print_help()
    
    elif args.command == 'bookings':
        if args.bookings_command == 'show':
            show_bookings()
        elif args.bookings_command == 'cancel':
            cancel_booking(args.id)
        else:
            bookings_parser.print_help()
    
    elif args.command == 'slots':
        show_available_slots(args.date)
    
    elif args.command == 'settings':
        show_settings()
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()

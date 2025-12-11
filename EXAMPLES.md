# Примеры использования PsyBooking Bot

## Примеры работы с manage.py

### Инициализация и настройка

```bash
# Инициализация базы данных
python3 manage.py init

# Просмотр настроек системы
python3 manage.py settings

# Просмотр рабочих часов
python3 manage.py working-hours show
```

### Настройка рабочего расписания

```bash
# Установить рабочие часы для понедельника (день 1)
python3 manage.py working-hours set 1 09:00 18:00

# Установить рабочие часы для вторника
python3 manage.py working-hours set 2 10:00 19:00

# Установить рабочие часы для среды
python3 manage.py working-hours set 3 09:00 18:00

# Установить рабочие часы для четверга
python3 manage.py working-hours set 4 10:00 19:00

# Установить рабочие часы для пятницы
python3 manage.py working-hours set 5 09:00 17:00

# Включить субботу с сокращенным днем
python3 manage.py working-hours set 6 10:00 14:00

# Выключить воскресенье
python3 manage.py working-hours set 0 10:00 14:00 --inactive
```

### Управление записями

```bash
# Показать все будущие записи
python3 manage.py bookings show

# Отменить запись с ID 5
python3 manage.py bookings cancel 5
```

### Просмотр доступных слотов

```bash
# Показать слоты на сегодня
python3 manage.py slots

# Показать слоты на конкретную дату
python3 manage.py slots --date 2024-12-15

# Показать слоты на завтра
python3 manage.py slots --date $(date -d tomorrow +%Y-%m-%d)
```

## Примеры использования Python API

### Работа с базой данных

```python
from database import Database
from datetime import datetime, timedelta
import pytz

# Инициализация
db = Database()

# Получить настройку
timezone = db.get_setting('primary_tz')
print(f"Timezone: {timezone}")

# Установить настройку
db.set_setting('min_hours_before_booking', '2')

# Получить рабочие часы
working_hours = db.get_working_hours()
for wh in working_hours:
    print(f"День {wh['day_of_week']}: {wh['start_time']}-{wh['end_time']}")

# Получить рабочие часы для понедельника (1)
monday_hours = db.get_working_hours_for_day(1)
print(f"Понедельник: {monday_hours}")

# Создать запись
booking_id = db.create_booking(
    client_telegram_id=123456789,
    client_username="john_doe",
    client_first_name="John",
    client_last_name="Doe",
    start_time_utc=(datetime.now(pytz.utc) + timedelta(days=1)).isoformat(),
    end_time_utc=(datetime.now(pytz.utc) + timedelta(days=1, hours=1)).isoformat()
)

if booking_id:
    print(f"Запись создана с ID: {booking_id}")
    
    # Обновить с данными Google Calendar
    db.update_booking_with_google_event(
        booking_id,
        "google_event_id_123",
        "https://calendar.google.com/event?eid=..."
    )
else:
    print("Ошибка: слот уже занят")

# Получить активные записи пользователя
user_bookings = db.get_active_bookings_for_user(123456789)
print(f"Активных записей: {len(user_bookings)}")

# Отменить запись
db.cancel_booking(booking_id)
```

### Работа с планировщиком слотов

```python
from database import Database
from scheduler import Scheduler
from datetime import datetime, timedelta
import pytz

# Инициализация
db = Database()
scheduler = Scheduler(db)

# Получить доступные даты на следующие 14 дней
available_dates = scheduler.get_available_dates(days_ahead=14)
print(f"Доступных дат: {len(available_dates)}")

for date in available_dates[:5]:
    print(scheduler.format_date_local(date))

# Получить доступные слоты на конкретную дату
tz = pytz.timezone('Europe/Minsk')
today = datetime.now(tz).date()
tomorrow = today + timedelta(days=1)

slots = scheduler.get_available_slots(tomorrow)
print(f"\nДоступных слотов на завтра: {len(slots)}")

for slot in slots[:5]:
    print(f"{slot['start_local']} - {slot['end_local']}")

# Получить следующие 10 доступных слотов
next_slots = scheduler.get_next_available_slots(limit=10)
print(f"\nСледующие {len(next_slots)} доступных слотов:")

for slot in next_slots:
    print(f"{slot['date']}: {slot['start_local']} - {slot['end_local']}")
```

### Работа с Google Calendar

```python
from google_calendar import get_calendar_client
from datetime import datetime, timedelta
import pytz

# Получить клиент
calendar_client = get_calendar_client()

# Проверить аутентификацию
if calendar_client.is_authenticated():
    print("✅ Аутентификация успешна")
    
    # Получить список календарей
    calendars = calendar_client.get_calendars()
    print(f"\nДоступных календарей: {len(calendars)}")
    
    for cal in calendars[:3]:
        print(f"- {cal['summary']} (ID: {cal['id']})")
    
    # Получить занятые интервалы
    tz = pytz.timezone('Europe/Minsk')
    now = datetime.now(pytz.utc)
    tomorrow_start = now + timedelta(days=1)
    tomorrow_end = tomorrow_start + timedelta(days=1)
    
    busy_intervals = calendar_client.get_busy_intervals(
        'primary',
        tomorrow_start,
        tomorrow_end
    )
    
    print(f"\nЗанятых интервалов завтра: {len(busy_intervals)}")
    for start, end in busy_intervals:
        start_local = start.astimezone(tz)
        end_local = end.astimezone(tz)
        print(f"- {start_local.strftime('%H:%M')} - {end_local.strftime('%H:%M')}")
    
    # Создать событие
    event_start = datetime.now(pytz.utc) + timedelta(days=2, hours=10)
    event_end = event_start + timedelta(hours=1)
    
    event_result = calendar_client.create_event(
        calendar_id='primary',
        summary='Тестовая консультация',
        description='Это тестовое событие',
        start_time=event_start,
        end_time=event_end
    )
    
    if event_result:
        print(f"\n✅ Событие создано:")
        print(f"Event ID: {event_result['event_id']}")
        print(f"Link: {event_result['event_link']}")
        
        # Удалить событие
        deleted = calendar_client.delete_event('primary', event_result['event_id'])
        if deleted:
            print("✅ Событие удалено")
    
else:
    print("❌ Требуется аутентификация")
```

### Проверка Rate Limiting

```python
from database import Database
import time

db = Database()
user_id = 123456789

# Проверить лимит
for i in range(15):
    allowed = db.check_rate_limit(user_id, max_requests=10, window_minutes=1)
    print(f"Запрос {i+1}: {'✅ Разрешен' if allowed else '❌ Заблокирован'}")
    time.sleep(0.1)

# Очистить старые записи
db.cleanup_old_rate_limits()
```

## Примеры сценариев использования

### Сценарий 1: Полный цикл записи

```python
from database import Database
from scheduler import Scheduler
from google_calendar import get_calendar_client
from datetime import datetime, timedelta
import pytz
import config

# Инициализация
db = Database()
scheduler = Scheduler(db)
calendar_client = get_calendar_client()

# Данные клиента
user_id = 123456789
username = "test_user"
first_name = "Тест"
last_name = "Пользователь"

# 1. Проверить rate limit
if not db.check_rate_limit(user_id):
    print("❌ Слишком много запросов")
    exit()

# 2. Проверить лимит активных записей
active_bookings = db.get_active_bookings_for_user(user_id)
if len(active_bookings) >= config.MAX_ACTIVE_BOOKINGS_PER_USER:
    print(f"❌ Максимум активных записей: {config.MAX_ACTIVE_BOOKINGS_PER_USER}")
    exit()

# 3. Получить доступные даты
available_dates = scheduler.get_available_dates()
if not available_dates:
    print("❌ Нет доступных дат")
    exit()

print(f"✅ Доступных дат: {len(available_dates)}")

# 4. Выбрать первую доступную дату
selected_date = available_dates[0]
print(f"📅 Выбрана дата: {scheduler.format_date_local(selected_date)}")

# 5. Получить доступные слоты
available_slots = scheduler.get_available_slots(selected_date)
if not available_slots:
    print("❌ Нет доступных слотов")
    exit()

print(f"✅ Доступных слотов: {len(available_slots)}")

# 6. Выбрать первый слот
selected_slot = available_slots[0]
print(f"🕐 Выбран слот: {selected_slot['start_local']} - {selected_slot['end_local']}")

# 7. Создать запись в БД
booking_id = db.create_booking(
    client_telegram_id=user_id,
    client_username=username,
    client_first_name=first_name,
    client_last_name=last_name,
    start_time_utc=selected_slot['start_utc'].isoformat(),
    end_time_utc=selected_slot['end_utc'].isoformat()
)

if not booking_id:
    print("❌ Слот уже занят")
    exit()

print(f"✅ Запись создана в БД (ID: {booking_id})")

# 8. Создать событие в Google Calendar
if calendar_client.is_authenticated():
    event_result = calendar_client.create_event(
        calendar_id=config.GOOGLE_CALENDAR_ID,
        summary=f"Консультация: {first_name} {last_name}",
        description=f"Клиент: @{username}\nTelegram ID: {user_id}",
        start_time=selected_slot['start_utc'],
        end_time=selected_slot['end_utc']
    )
    
    if event_result:
        print(f"✅ Событие создано в Google Calendar")
        print(f"Event ID: {event_result['event_id']}")
        print(f"Link: {event_result['event_link']}")
        
        # 9. Обновить запись с данными события
        db.update_booking_with_google_event(
            booking_id,
            event_result['event_id'],
            event_result['event_link']
        )
        print("✅ Запись обновлена с данными события")
    else:
        print("⚠️ Ошибка создания события в календаре")
else:
    print("⚠️ Google Calendar не подключен")

# 10. Получить финальную запись
booking = db.get_booking(booking_id)
print("\n📋 Итоговая запись:")
print(f"ID: {booking['id']}")
print(f"Клиент: {booking['client_first_name']} {booking['client_last_name']}")
print(f"Время: {booking['start_time_utc']}")
print(f"Статус: {booking['status']}")
print(f"Ссылка: {booking['event_link']}")
```

### Сценарий 2: Отмена записи

```python
from database import Database
from google_calendar import get_calendar_client
import config

db = Database()
calendar_client = get_calendar_client()

booking_id = 1  # ID записи для отмены

# Получить запись
booking = db.get_booking(booking_id)
if not booking:
    print("❌ Запись не найдена")
    exit()

print(f"📋 Запись {booking_id}:")
print(f"Клиент: {booking['client_first_name']} {booking['client_last_name']}")
print(f"Время: {booking['start_time_utc']}")
print(f"Статус: {booking['status']}")

# Отменить в БД
db.cancel_booking(booking_id)
print("✅ Запись отменена в БД")

# Удалить событие из Google Calendar
if booking['google_event_id'] and calendar_client.is_authenticated():
    deleted = calendar_client.delete_event(
        config.GOOGLE_CALENDAR_ID,
        booking['google_event_id']
    )
    if deleted:
        print("✅ Событие удалено из Google Calendar")
    else:
        print("⚠️ Ошибка удаления события")
```

## Интеграция с другими системами

### Webhook для уведомлений

```python
import requests
from database import Database

def send_webhook_notification(booking):
    """Отправить webhook уведомление о новой записи"""
    webhook_url = "https://your-system.com/webhook"
    
    payload = {
        "event": "booking_created",
        "booking_id": booking['id'],
        "client_telegram_id": booking['client_telegram_id'],
        "client_name": f"{booking['client_first_name']} {booking['client_last_name']}",
        "start_time": booking['start_time_utc'],
        "end_time": booking['end_time_utc'],
        "google_event_link": booking['event_link']
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=5)
        response.raise_for_status()
        print("✅ Webhook отправлен")
    except Exception as e:
        print(f"⚠️ Ошибка отправки webhook: {e}")

# Использование
db = Database()
booking = db.get_booking(1)
if booking:
    send_webhook_notification(booking)
```

### Экспорт данных в CSV

```python
import csv
from database import Database
from datetime import datetime
import pytz

db = Database()
bookings = db.get_all_future_bookings()

tz = pytz.timezone('Europe/Minsk')

with open('bookings_export.csv', 'w', newline='', encoding='utf-8') as csvfile:
    fieldnames = ['ID', 'Клиент', 'Username', 'Дата', 'Время', 'Статус', 'Ссылка']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    
    writer.writeheader()
    
    for booking in bookings:
        start_utc = datetime.fromisoformat(booking['start_time_utc']).replace(tzinfo=pytz.utc)
        start_local = start_utc.astimezone(tz)
        
        writer.writerow({
            'ID': booking['id'],
            'Клиент': f"{booking['client_first_name']} {booking['client_last_name']}",
            'Username': booking['client_username'] or '',
            'Дата': start_local.strftime('%d.%m.%Y'),
            'Время': start_local.strftime('%H:%M'),
            'Статус': booking['status'],
            'Ссылка': booking['event_link'] or ''
        })

print("✅ Данные экспортированы в bookings_export.csv")
```

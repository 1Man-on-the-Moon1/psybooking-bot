# Архитектура PsyBooking Telegram Bot

## Обзор системы

Система состоит из следующих компонентов:

### 1. Telegram Bot (Python)
- **Библиотека**: python-telegram-bot
- **Функции**:
  - Обработка команд `/start`, `/book`, `/slots`, `/help`
  - Интерактивный выбор даты и времени через inline-клавиатуру
  - Создание бронирований
  - Отправка подтверждений

### 2. База данных (SQLite для MVP)
- **Таблицы**:
  - `settings` - настройки системы (токены, calendar_id, timezone)
  - `working_hours` - рабочие часы по дням недели
  - `bookings` - записи клиентов
  - `admin_users` - администраторы системы

### 3. Google Calendar Integration
- **API**: Google Calendar API v3
- **OAuth 2.0**: offline access с refresh token
- **Операции**:
  - Получение занятых слотов (freebusy)
  - Создание событий
  - Удаление событий при отмене

### 4. Модули системы

```
psybooking-bot/
├── bot.py                    # Главный файл бота
├── database.py               # Работа с БД
├── google_calendar.py        # Интеграция с Google Calendar
├── scheduler.py              # Расчет свободных слотов
├── config.py                 # Конфигурация
├── requirements.txt          # Зависимости Python
├── .env.example              # Пример переменных окружения
├── README.md                 # Документация
└── data/
    └── psybooking.db         # База данных SQLite
```

## Основные потоки данных

### Поток записи клиента:
1. Клиент → `/book` → Telegram Bot
2. Bot → Database → получение рабочих часов
3. Bot → Google Calendar API → получение занятых слотов
4. Bot → Scheduler → расчет свободных слотов
5. Bot → Клиент → отображение доступных слотов
6. Клиент выбирает слот → Bot
7. Bot → Database → создание записи (транзакция)
8. Bot → Google Calendar API → создание события
9. Bot → Database → обновление записи (event_id, link)
10. Bot → Клиент → подтверждение с ссылкой

### Защита от двойного бронирования:
- Уникальный индекс на `(start_time_utc)` в таблице bookings
- Проверка доступности перед вставкой
- Обработка ошибки `UNIQUE constraint failed`

## Timezone обработка

- **PRIMARY_TZ**: `Europe/Minsk`
- **Хранение в БД**: UTC (timestamptz)
- **Отображение пользователю**: локальное время Минска
- **Библиотека**: `pytz` для конвертации

## Безопасность

- Telegram webhook с секретным токеном
- Google OAuth credentials в переменных окружения
- Ограничение: максимум 3 активных записи на пользователя
- Rate limiting: 10 запросов в минуту на пользователя

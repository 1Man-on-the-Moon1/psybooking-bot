# Руководство по развертыванию PsyBooking Bot

## Быстрый старт (локальное тестирование)

### 1. Установка зависимостей

```bash
cd psybooking-bot
pip3 install -r requirements.txt
```

### 2. Создание Telegram бота

1. Откройте [@BotFather](https://t.me/BotFather)
2. Отправьте `/newbot`
3. Введите имя бота (например, "PsyBooking Test Bot")
4. Введите username (например, "psybooking_test_bot")
5. Скопируйте полученный токен

### 3. Настройка команд бота

Отправьте @BotFather команду `/setcommands` и выберите вашего бота.
Затем отправьте следующий текст:

```
start - Начать работу с ботом
book - Записаться на консультацию
slots - Посмотреть доступные слоты
mybookings - Мои записи
help - Справка
```

### 4. Настройка Google Calendar API

#### 4.1. Создание проекта в Google Cloud

1. Перейдите на https://console.cloud.google.com/
2. Создайте новый проект или выберите существующий
3. Запомните название проекта

#### 4.2. Включение Calendar API

1. В меню слева: APIs & Services → Library
2. Найдите "Google Calendar API"
3. Нажмите "Enable"

#### 4.3. Создание OAuth 2.0 credentials

1. APIs & Services → Credentials
2. Нажмите "Create Credentials" → "OAuth client ID"
3. Если требуется, настройте OAuth consent screen:
   - User Type: External
   - App name: PsyBooking Bot
   - User support email: ваш email
   - Developer contact: ваш email
   - Scopes: не добавляйте (будут настроены автоматически)
   - Test users: добавьте свой Google аккаунт
4. Вернитесь к созданию OAuth client ID:
   - Application type: Desktop app
   - Name: PsyBooking Bot
5. Нажмите "Create"
6. Скачайте JSON файл
7. Сохраните его как `credentials.json` в корне проекта

### 5. Настройка переменных окружения

```bash
cp .env.example .env
nano .env
```

Заполните:

```env
TELEGRAM_BOT_TOKEN=ваш_токен_от_botfather
GOOGLE_CALENDAR_ID=primary
ADMIN_TELEGRAM_IDS=ваш_telegram_id
```

Чтобы узнать свой Telegram ID:
1. Напишите боту [@userinfobot](https://t.me/userinfobot)
2. Скопируйте ваш ID

### 6. Инициализация базы данных

```bash
python3 manage.py init
```

### 7. Настройка рабочих часов (опционально)

Просмотр текущих настроек:

```bash
python3 manage.py working-hours show
```

Изменение рабочих часов:

```bash
# Установить для понедельника (1) с 9:00 до 18:00
python3 manage.py working-hours set 1 09:00 18:00

# Включить субботу (6) с 10:00 до 14:00
python3 manage.py working-hours set 6 10:00 14:00

# Выключить воскресенье (0)
python3 manage.py working-hours set 0 10:00 14:00 --inactive
```

### 8. Первый запуск и авторизация Google

```bash
python3 bot.py
```

При первом запуске:
1. Откроется браузер с запросом авторизации Google
2. Войдите в аккаунт психолога
3. Разрешите доступ к календарю
4. Вернитесь в терминал - бот должен запуститься

### 9. Тестирование

1. Найдите вашего бота в Telegram
2. Отправьте `/start`
3. Попробуйте записаться на консультацию
4. Проверьте, что событие создалось в Google Calendar

## Продакшн развертывание

### Вариант 1: VPS с systemd

#### 1. Подготовка сервера

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Python и зависимостей
sudo apt install python3 python3-pip python3-venv git -y

# Создание пользователя для бота
sudo useradd -m -s /bin/bash psybot
sudo su - psybot
```

#### 2. Установка проекта

```bash
cd ~
git clone <ваш_репозиторий> psybooking-bot
cd psybooking-bot

# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
```

#### 3. Настройка

Скопируйте `.env` и `credentials.json` на сервер:

```bash
# На локальной машине
scp .env psybot@your-server:/home/psybot/psybooking-bot/
scp credentials.json psybot@your-server:/home/psybot/psybooking-bot/
```

#### 4. Первичная авторизация Google

На сервере с GUI или через SSH forwarding:

```bash
# SSH с forwarding
ssh -L 8080:localhost:8080 psybot@your-server

# На сервере
cd ~/psybooking-bot
source venv/bin/activate
python3 bot.py
# Откройте http://localhost:8080 в браузере и авторизуйтесь
```

После авторизации остановите бота (Ctrl+C).

#### 5. Создание systemd service

```bash
sudo nano /etc/systemd/system/psybooking-bot.service
```

Содержимое:

```ini
[Unit]
Description=PsyBooking Telegram Bot
After=network.target

[Service]
Type=simple
User=psybot
WorkingDirectory=/home/psybot/psybooking-bot
Environment="PATH=/home/psybot/psybooking-bot/venv/bin"
ExecStart=/home/psybot/psybooking-bot/venv/bin/python3 /home/psybot/psybooking-bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 6. Запуск сервиса

```bash
sudo systemctl daemon-reload
sudo systemctl enable psybooking-bot
sudo systemctl start psybooking-bot

# Проверка статуса
sudo systemctl status psybooking-bot

# Просмотр логов
sudo journalctl -u psybooking-bot -f
```

### Вариант 2: Docker

#### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . .

# Создание директории для данных
RUN mkdir -p /app/data

# Запуск
CMD ["python3", "bot.py"]
```

#### docker-compose.yml

```yaml
version: '3.8'

services:
  bot:
    build: .
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./credentials.json:/app/credentials.json:ro
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

#### Запуск

```bash
# Первый запуск с авторизацией Google (интерактивно)
docker-compose run --rm bot python3 bot.py

# После авторизации - обычный запуск
docker-compose up -d

# Логи
docker-compose logs -f
```

### Вариант 3: Webhook (рекомендуется для продакшна)

Для использования webhook вместо polling нужно:

1. Иметь домен с SSL сертификатом
2. Модифицировать `bot.py` для работы с webhook
3. Использовать веб-сервер (nginx) в качестве reverse proxy

Пример конфигурации nginx:

```nginx
server {
    listen 443 ssl;
    server_name bot.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /webhook {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Мониторинг и обслуживание

### Просмотр записей

```bash
python3 manage.py bookings show
```

### Просмотр доступных слотов

```bash
# На сегодня
python3 manage.py slots

# На конкретную дату
python3 manage.py slots --date 2024-12-15
```

### Отмена записи

```bash
python3 manage.py bookings cancel <ID>
```

### Резервное копирование

Настройте cron для автоматического бэкапа:

```bash
crontab -e
```

Добавьте:

```cron
# Бэкап БД каждый день в 3:00
0 3 * * * cp /home/psybot/psybooking-bot/data/psybooking.db /home/psybot/backups/psybooking.db.$(date +\%Y\%m\%d)

# Очистка старых бэкапов (старше 30 дней)
0 4 * * * find /home/psybot/backups -name "psybooking.db.*" -mtime +30 -delete
```

### Обновление бота

```bash
cd ~/psybooking-bot
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart psybooking-bot
```

## Безопасность

### Рекомендации

1. **Файрвол**: Откройте только необходимые порты (22 для SSH, 443 для webhook)

```bash
sudo ufw allow 22
sudo ufw allow 443
sudo ufw enable
```

2. **Регулярные обновления**:

```bash
sudo apt update && sudo apt upgrade -y
```

3. **Права доступа к файлам**:

```bash
chmod 600 .env
chmod 600 credentials.json
chmod 600 data/token.pickle
```

4. **Логирование**: Регулярно проверяйте логи на подозрительную активность

5. **Бэкапы**: Настройте автоматическое резервное копирование БД и конфигурации

## Troubleshooting

### Бот не запускается

```bash
# Проверка логов
sudo journalctl -u psybooking-bot -n 50

# Проверка переменных окружения
source venv/bin/activate
python3 -c "import config; print(config.TELEGRAM_BOT_TOKEN[:10])"
```

### Ошибки Google Calendar

```bash
# Удалить токен и авторизоваться заново
rm data/token.pickle
python3 bot.py
```

### База данных повреждена

```bash
# Восстановление из бэкапа
cp data/psybooking.db data/psybooking.db.corrupted
cp /path/to/backup/psybooking.db.YYYYMMDD data/psybooking.db
sudo systemctl restart psybooking-bot
```

## Масштабирование

Для обработки большого количества пользователей:

1. **Переход на PostgreSQL** вместо SQLite
2. **Использование Redis** для кэширования
3. **Настройка webhook** вместо polling
4. **Horizontal scaling** с несколькими инстансами бота
5. **Мониторинг** с Prometheus + Grafana

## Поддержка

При возникновении проблем:
1. Проверьте логи
2. Изучите документацию
3. Проверьте настройки Google Calendar API
4. Убедитесь, что все переменные окружения установлены корректно

"""
Конфигурация для PsyBooking Bot
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_WEBHOOK_SECRET = os.getenv('TELEGRAM_WEBHOOK_SECRET', '')

# Google Calendar
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
GOOGLE_CALENDAR_ID = os.getenv('GOOGLE_CALENDAR_ID', 'primary')

# Database
DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/psybooking.db')

# Timezone
PRIMARY_TZ = 'Europe/Minsk'

# Booking settings
MIN_HOURS_BEFORE_BOOKING = 3
SESSION_DURATION_MINUTES = 60
MAX_ACTIVE_BOOKINGS_PER_USER = 3
RATE_LIMIT_REQUESTS_PER_MINUTE = 10
DAYS_AHEAD_TO_SHOW = 14

# Admin
ADMIN_TELEGRAM_IDS = [int(x) for x in os.getenv('ADMIN_TELEGRAM_IDS', '').split(',') if x]

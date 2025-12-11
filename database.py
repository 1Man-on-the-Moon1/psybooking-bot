"""
Модуль для работы с базой данных SQLite
"""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import config
import os


class Database:
    def __init__(self, db_path: str = config.DATABASE_PATH):
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_db()
    
    def _ensure_db_dir(self):
        """Создать директорию для БД если не существует"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Получить соединение с БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Инициализация базы данных"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Таблица настроек
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица рабочих часов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS working_hours (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day_of_week INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                UNIQUE(day_of_week)
            )
        ''')
        
        # Таблица записей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_telegram_id INTEGER NOT NULL,
                client_username TEXT,
                client_first_name TEXT,
                client_last_name TEXT,
                start_time_utc TEXT NOT NULL,
                end_time_utc TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                google_event_id TEXT,
                event_link TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(start_time_utc)
            )
        ''')
        
        # Таблица для rate limiting
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rate_limits (
                user_id INTEGER NOT NULL,
                request_time TEXT NOT NULL,
                PRIMARY KEY (user_id, request_time)
            )
        ''')
        
        # Индексы
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_bookings_status 
            ON bookings(status)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_bookings_client 
            ON bookings(client_telegram_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_bookings_time 
            ON bookings(start_time_utc)
        ''')
        
        # Инициализация настроек по умолчанию
        cursor.execute('''
            INSERT OR IGNORE INTO settings (key, value) 
            VALUES ('primary_tz', ?)
        ''', (config.PRIMARY_TZ,))
        
        cursor.execute('''
            INSERT OR IGNORE INTO settings (key, value) 
            VALUES ('min_hours_before_booking', ?)
        ''', (str(config.MIN_HOURS_BEFORE_BOOKING),))
        
        # Рабочие часы по умолчанию (Пн-Пт 10:00-19:00)
        default_hours = [
            (1, '10:00', '19:00', 1),  # Понедельник
            (2, '10:00', '19:00', 1),  # Вторник
            (3, '10:00', '19:00', 1),  # Среда
            (4, '10:00', '19:00', 1),  # Четверг
            (5, '10:00', '19:00', 1),  # Пятница
            (6, '10:00', '14:00', 0),  # Суббота (неактивна)
            (0, '10:00', '14:00', 0),  # Воскресенье (неактивно)
        ]
        
        for day, start, end, active in default_hours:
            cursor.execute('''
                INSERT OR IGNORE INTO working_hours 
                (day_of_week, start_time, end_time, is_active)
                VALUES (?, ?, ?, ?)
            ''', (day, start, end, active))
        
        conn.commit()
        conn.close()
    
    # === Settings ===
    
    def get_setting(self, key: str) -> Optional[str]:
        """Получить значение настройки"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        conn.close()
        return row['value'] if row else None
    
    def set_setting(self, key: str, value: str):
        """Установить значение настройки"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (key, value))
        conn.commit()
        conn.close()
    
    # === Working Hours ===
    
    def get_working_hours(self) -> List[Dict]:
        """Получить все рабочие часы"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT day_of_week, start_time, end_time, is_active
            FROM working_hours
            ORDER BY day_of_week
        ''')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_working_hours_for_day(self, day_of_week: int) -> Optional[Dict]:
        """Получить рабочие часы для конкретного дня недели (0=Вс, 6=Сб)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT day_of_week, start_time, end_time, is_active
            FROM working_hours
            WHERE day_of_week = ?
        ''', (day_of_week,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def update_working_hours(self, day_of_week: int, start_time: str, 
                            end_time: str, is_active: bool = True):
        """Обновить рабочие часы для дня"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO working_hours 
            (day_of_week, start_time, end_time, is_active)
            VALUES (?, ?, ?, ?)
        ''', (day_of_week, start_time, end_time, 1 if is_active else 0))
        conn.commit()
        conn.close()
    
    # === Bookings ===
    
    def create_booking(self, client_telegram_id: int, client_username: Optional[str],
                      client_first_name: Optional[str], client_last_name: Optional[str],
                      start_time_utc: str, end_time_utc: str) -> Optional[int]:
        """
        Создать новую запись
        Возвращает ID записи или None при ошибке (например, слот занят)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO bookings 
                (client_telegram_id, client_username, client_first_name, 
                 client_last_name, start_time_utc, end_time_utc, status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
            ''', (client_telegram_id, client_username, client_first_name,
                  client_last_name, start_time_utc, end_time_utc))
            
            booking_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return booking_id
            
        except sqlite3.IntegrityError as e:
            # Слот уже занят (UNIQUE constraint)
            conn.close()
            return None
    
    def update_booking_with_google_event(self, booking_id: int, 
                                        google_event_id: str, event_link: str):
        """Обновить запись данными из Google Calendar"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE bookings 
            SET google_event_id = ?, event_link = ?, 
                status = 'confirmed', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (google_event_id, event_link, booking_id))
        conn.commit()
        conn.close()
    
    def get_booking(self, booking_id: int) -> Optional[Dict]:
        """Получить запись по ID"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM bookings WHERE id = ?', (booking_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_active_bookings_for_user(self, client_telegram_id: int) -> List[Dict]:
        """Получить активные записи пользователя"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM bookings 
            WHERE client_telegram_id = ? 
            AND status IN ('pending', 'confirmed')
            AND start_time_utc >= datetime('now')
            ORDER BY start_time_utc
        ''', (client_telegram_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_bookings_for_date_range(self, start_utc: str, end_utc: str) -> List[Dict]:
        """Получить все активные записи в диапазоне дат"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM bookings 
            WHERE status IN ('pending', 'confirmed')
            AND start_time_utc < ?
            AND end_time_utc > ?
            ORDER BY start_time_utc
        ''', (end_utc, start_utc))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def cancel_booking(self, booking_id: int) -> bool:
        """Отменить запись"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE bookings 
            SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (booking_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0
    
    def get_all_future_bookings(self) -> List[Dict]:
        """Получить все будущие записи"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM bookings 
            WHERE start_time_utc >= datetime('now')
            AND status IN ('pending', 'confirmed')
            ORDER BY start_time_utc
        ''')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    # === Rate Limiting ===
    
    def check_rate_limit(self, user_id: int, max_requests: int = 10, 
                        window_minutes: int = 1) -> bool:
        """
        Проверить rate limit для пользователя
        Возвращает True если лимит не превышен
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Удалить старые записи
        cursor.execute('''
            DELETE FROM rate_limits 
            WHERE request_time < datetime('now', '-' || ? || ' minutes')
        ''', (window_minutes,))
        
        # Посчитать запросы пользователя за последнюю минуту
        cursor.execute('''
            SELECT COUNT(*) as count FROM rate_limits 
            WHERE user_id = ? 
            AND request_time >= datetime('now', '-' || ? || ' minutes')
        ''', (user_id, window_minutes))
        
        count = cursor.fetchone()['count']
        
        if count >= max_requests:
            conn.close()
            return False
        
        # Добавить новый запрос
        cursor.execute('''
            INSERT INTO rate_limits (user_id, request_time)
            VALUES (?, CURRENT_TIMESTAMP)
        ''', (user_id,))
        
        conn.commit()
        conn.close()
        return True
    
    def cleanup_old_rate_limits(self):
        """Очистить старые записи rate limiting"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM rate_limits 
            WHERE request_time < datetime('now', '-1 hour')
        ''')
        conn.commit()
        conn.close()

"""
Модуль для расчета свободных слотов
"""
from datetime import datetime, timedelta, time
from typing import List, Dict, Tuple, Optional
import pytz
import config
from database import Database
from google_calendar import get_calendar_client


class Scheduler:
    def __init__(self, db: Database):
        self.db = db
        self.calendar_client = get_calendar_client()
        self.primary_tz = pytz.timezone(config.PRIMARY_TZ)
    
    def get_available_slots(self, date: datetime.date, 
                           calendar_id: str = config.GOOGLE_CALENDAR_ID) -> List[Dict]:
        """
        Получить доступные слоты для конкретной даты
        Возвращает список словарей с ключами:
        - start_utc: datetime
        - end_utc: datetime
        - start_local: str (форматированное время)
        - end_local: str (форматированное время)
        """
        # Получить рабочие часы для этого дня недели
        day_of_week = date.weekday()  # 0=Пн, 6=Вс
        # Конвертировать в формат БД (0=Вс, 1=Пн, ..., 6=Сб)
        db_day_of_week = (day_of_week + 1) % 7
        
        working_hours = self.db.get_working_hours_for_day(db_day_of_week)
        
        if not working_hours or not working_hours['is_active']:
            return []
        
        # Парсить рабочие часы
        start_time_str = working_hours['start_time']  # "10:00"
        end_time_str = working_hours['end_time']      # "19:00"
        
        start_hour, start_minute = map(int, start_time_str.split(':'))
        end_hour, end_minute = map(int, end_time_str.split(':'))
        
        # Создать datetime объекты в локальной timezone
        work_start_local = self.primary_tz.localize(
            datetime.combine(date, time(start_hour, start_minute))
        )
        work_end_local = self.primary_tz.localize(
            datetime.combine(date, time(end_hour, end_minute))
        )
        
        # Конвертировать в UTC для работы
        work_start_utc = work_start_local.astimezone(pytz.utc)
        work_end_utc = work_end_local.astimezone(pytz.utc)
        
        # Проверить минимальное время до записи
        min_hours = int(self.db.get_setting('min_hours_before_booking') or 
                       config.MIN_HOURS_BEFORE_BOOKING)
        now_utc = datetime.now(pytz.utc)
        earliest_booking = now_utc + timedelta(hours=min_hours)
        
        if work_end_utc < earliest_booking:
            # Весь рабочий день уже прошел или слишком близко
            return []
        
        if work_start_utc < earliest_booking:
            work_start_utc = earliest_booking
        
        # Сгенерировать все возможные слоты
        session_duration = timedelta(minutes=config.SESSION_DURATION_MINUTES)
        all_slots = []
        
        current_slot_start = work_start_utc
        while current_slot_start + session_duration <= work_end_utc:
            all_slots.append({
                'start_utc': current_slot_start,
                'end_utc': current_slot_start + session_duration
            })
            current_slot_start += session_duration
        
        if not all_slots:
            return []
        
        # Получить занятые интервалы из Google Calendar
        busy_intervals = []
        if self.calendar_client.is_authenticated():
            busy_intervals = self.calendar_client.get_busy_intervals(
                calendar_id,
                work_start_utc,
                work_end_utc
            )
        
        # Получить занятые слоты из БД
        db_bookings = self.db.get_bookings_for_date_range(
            work_start_utc.isoformat(),
            work_end_utc.isoformat()
        )
        
        for booking in db_bookings:
            start = datetime.fromisoformat(booking['start_time_utc']).replace(tzinfo=pytz.utc)
            end = datetime.fromisoformat(booking['end_time_utc']).replace(tzinfo=pytz.utc)
            busy_intervals.append((start, end))
        
        # Отфильтровать занятые слоты
        available_slots = []
        for slot in all_slots:
            if not self._is_slot_busy(slot, busy_intervals):
                # Конвертировать обратно в локальное время для отображения
                start_local = slot['start_utc'].astimezone(self.primary_tz)
                end_local = slot['end_utc'].astimezone(self.primary_tz)
                
                available_slots.append({
                    'start_utc': slot['start_utc'],
                    'end_utc': slot['end_utc'],
                    'start_local': start_local.strftime('%H:%M'),
                    'end_local': end_local.strftime('%H:%M'),
                    'start_local_full': start_local.strftime('%d.%m.%Y %H:%M'),
                    'end_local_full': end_local.strftime('%d.%m.%Y %H:%M')
                })
        
        return available_slots
    
    def _is_slot_busy(self, slot: Dict, busy_intervals: List[Tuple[datetime, datetime]]) -> bool:
        """Проверить, занят ли слот"""
        slot_start = slot['start_utc']
        slot_end = slot['end_utc']
        
        for busy_start, busy_end in busy_intervals:
            # Проверка на пересечение интервалов
            if self._intervals_overlap(slot_start, slot_end, busy_start, busy_end):
                return True
        
        return False
    
    def _intervals_overlap(self, start1: datetime, end1: datetime, 
                          start2: datetime, end2: datetime) -> bool:
        """Проверить пересечение двух интервалов"""
        return start1 < end2 and start2 < end1
    
    def get_available_dates(self, days_ahead: int = config.DAYS_AHEAD_TO_SHOW) -> List[datetime.date]:
        """
        Получить список дат, на которые можно записаться
        (дни с активными рабочими часами)
        """
        available_dates = []
        today = datetime.now(self.primary_tz).date()
        
        working_hours = self.db.get_working_hours()
        active_days = {wh['day_of_week'] for wh in working_hours if wh['is_active']}
        
        for i in range(days_ahead):
            check_date = today + timedelta(days=i)
            day_of_week = (check_date.weekday() + 1) % 7  # Конвертировать в формат БД
            
            if day_of_week in active_days:
                available_dates.append(check_date)
        
        return available_dates
    
    def format_date_local(self, date: datetime.date) -> str:
        """Форматировать дату для отображения"""
        dt = datetime.combine(date, time(0, 0))
        dt_local = self.primary_tz.localize(dt)
        
        # Определить название дня недели
        weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        weekday_name = weekdays[date.weekday()]
        
        return f"{weekday_name}, {dt_local.strftime('%d.%m.%Y')}"
    
    def get_next_available_slots(self, limit: int = 10) -> List[Dict]:
        """
        Получить следующие доступные слоты (для быстрого просмотра)
        """
        all_slots = []
        dates = self.get_available_dates()
        
        for date in dates:
            slots = self.get_available_slots(date)
            for slot in slots:
                slot['date'] = date
                all_slots.append(slot)
                
                if len(all_slots) >= limit:
                    return all_slots
        
        return all_slots

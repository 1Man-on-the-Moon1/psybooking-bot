"""
Модуль для работы с Google Calendar API
"""
import os
import pickle
import json
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import config
import pytz


SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_PICKLE_PATH = 'data/token.pickle'
CREDENTIALS_JSON_PATH = 'credentials.json'


class GoogleCalendarClient:
    def __init__(self):
        self.creds = None
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Аутентификация в Google Calendar API"""
        # Проверить сохраненный токен
        if os.path.exists(TOKEN_PICKLE_PATH):
            with open(TOKEN_PICKLE_PATH, 'rb') as token:
                self.creds = pickle.load(token)
        # Или из переменной окружения (для Bothost)
        elif os.getenv('GOOGLE_TOKEN_PICKLE_BASE64'):
            try:
                token_data = base64.b64decode(os.getenv('GOOGLE_TOKEN_PICKLE_BASE64'))
                self.creds = pickle.loads(token_data)
            except Exception as e:
                print(f"Ошибка загрузки токена из переменной окружения: {e}")
                self.creds = None
        
        # Если нет валидных credentials, получить новые
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    print(f"Ошибка обновления токена: {e}")
                    self.creds = None
            
            if not self.creds:
                # Требуется новая авторизация
                # НЕ ЗАПУСКАЕМ интерактивную авторизацию на сервере без GUI
                print("⚠️ Google Calendar не авторизован")
                print("Для авторизации Google Calendar:")
                print("1. Запустите auth_google.py локально")
                print("2. Загрузите token.pickle на сервер")
                print("3. Или установите переменную GOOGLE_TOKEN_PICKLE_BASE64")
                print("")
                print("Бот будет работать БЕЗ Google Calendar")
                return
            
            # Сохранить credentials
            os.makedirs(os.path.dirname(TOKEN_PICKLE_PATH), exist_ok=True)
            with open(TOKEN_PICKLE_PATH, 'wb') as token:
                pickle.dump(self.creds, token)
        
        if self.creds:
            self.service = build('calendar', 'v3', credentials=self.creds)
    
    def is_authenticated(self) -> bool:
        """Проверить, аутентифицирован ли клиент"""
        return self.service is not None
    
    def get_calendars(self) -> List[Dict]:
        """Получить список календарей"""
        if not self.service:
            return []
        
        try:
            calendar_list = self.service.calendarList().list().execute()
            return calendar_list.get('items', [])
        except HttpError as error:
            print(f'Ошибка получения списка календарей: {error}')
            return []
    
    def get_busy_intervals(self, calendar_id: str, time_min: datetime, 
                          time_max: datetime) -> List[Tuple[datetime, datetime]]:
        """
        Получить занятые интервалы из календаря
        Возвращает список кортежей (start, end) в UTC
        """
        if not self.service:
            return []
        
        try:
            body = {
                "timeMin": time_min.isoformat(),
                "timeMax": time_max.isoformat(),
                "timeZone": 'UTC',
                "items": [{"id": calendar_id}]
            }
            
            freebusy_result = self.service.freebusy().query(body=body).execute()
            calendars = freebusy_result.get('calendars', {})
            
            if calendar_id not in calendars:
                return []
            
            busy_intervals = []
            for busy_period in calendars[calendar_id].get('busy', []):
                start = datetime.fromisoformat(busy_period['start'].replace('Z', '+00:00'))
                end = datetime.fromisoformat(busy_period['end'].replace('Z', '+00:00'))
                busy_intervals.append((start, end))
            
            return busy_intervals
            
        except HttpError as error:
            print(f'Ошибка получения занятых интервалов: {error}')
            return []
    
    def create_event(self, calendar_id: str, summary: str, description: str,
                    start_time: datetime, end_time: datetime, 
                    timezone: str = config.PRIMARY_TZ) -> Optional[Dict]:
        """
        Создать событие в календаре
        Возвращает словарь с event_id и event_link
        """
        if not self.service:
            return None
        
        # Конвертировать в локальное время для события
        tz = pytz.timezone(timezone)
        start_local = start_time.astimezone(tz)
        end_local = end_time.astimezone(tz)
        
        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_local.isoformat(),
                'timeZone': timezone,
            },
            'end': {
                'dateTime': end_local.isoformat(),
                'timeZone': timezone,
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 60},
                    {'method': 'popup', 'minutes': 30},
                ],
            },
        }
        
        try:
            created_event = self.service.events().insert(
                calendarId=calendar_id, 
                body=event
            ).execute()
            
            return {
                'event_id': created_event['id'],
                'event_link': created_event.get('htmlLink', '')
            }
            
        except HttpError as error:
            print(f'Ошибка создания события: {error}')
            return None
    
    def delete_event(self, calendar_id: str, event_id: str) -> bool:
        """Удалить событие из календаря"""
        if not self.service:
            return False
        
        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            return True
            
        except HttpError as error:
            print(f'Ошибка удаления события: {error}')
            return False
    
    def get_event(self, calendar_id: str, event_id: str) -> Optional[Dict]:
        """Получить событие по ID"""
        if not self.service:
            return None
        
        try:
            event = self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            return event
            
        except HttpError as error:
            print(f'Ошибка получения события: {error}')
            return None


# Singleton instance
_calendar_client = None


def get_calendar_client() -> GoogleCalendarClient:
    """Получить singleton instance календарного клиента"""
    global _calendar_client
    if _calendar_client is None:
        _calendar_client = GoogleCalendarClient()
    return _calendar_client

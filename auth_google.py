#!/usr/bin/env python3
"""
Скрипт для авторизации Google Calendar в headless режиме
"""
import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_PATH = 'data/token.pickle'
CREDENTIALS_PATH = 'credentials.json'

def authenticate():
    """Авторизация в Google Calendar"""
    creds = None
    
    # Проверяем существующий токен
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)
    
    # Если токена нет или он невалиден
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Обновление токена...")
            creds.refresh(Request())
        else:
            print("🔐 Запуск процесса авторизации...")
            print("\n📋 Инструкция:")
            print("1. Скопируйте URL ниже")
            print("2. Откройте его в браузере")
            print("3. Войдите в Google аккаунт")
            print("4. Разрешите доступ к календарю")
            print("5. Скопируйте код авторизации")
            print("6. Вставьте код здесь\n")
            
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, 
                SCOPES,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob'
            )
            
            # Получаем URL для авторизации
            auth_url, _ = flow.authorization_url(prompt='consent')
            
            print("=" * 80)
            print("🔗 URL для авторизации:")
            print(auth_url)
            print("=" * 80)
            print()
            
            # Запрашиваем код
            code = input("Введите код авторизации: ").strip()
            
            # Обмениваем код на токен
            flow.fetch_token(code=code)
            creds = flow.credentials
        
        # Сохраняем токен
        os.makedirs('data', exist_ok=True)
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)
        
        print("✅ Авторизация успешна!")
        print(f"📁 Токен сохранен: {TOKEN_PATH}")
    else:
        print("✅ Токен уже существует и валиден")
    
    return creds

if __name__ == '__main__':
    try:
        authenticate()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        exit(1)

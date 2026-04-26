#!/usr/bin/env python3
"""
Скрипт для импорта cookies в Chrome профиль
"""

import json
import sqlite3
import os
import sys
from pathlib import Path
import shutil
from datetime import datetime
import tempfile

def import_cookies_to_chrome(cookies_json_path, chrome_profile_path):
    """
    Импортирует cookies из JSON файла в Chrome профиль
    """
    # Путь к базе данных cookies
    cookies_db_path = Path(chrome_profile_path) / "Default" / "Cookies"
    
    # Создаем директории если их нет
    cookies_db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Читаем cookies из JSON
    with open(cookies_json_path, 'r') as f:
        cookies = json.load(f)
    
    print(f"Загружено {len(cookies)} cookies из {cookies_json_path}")
    
    # Создаем временную копию базы данных
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db_path = temp_db.name
    temp_db.close()
    
    # Если база существует, копируем её
    if cookies_db_path.exists():
        shutil.copy2(cookies_db_path, temp_db_path)
        print(f"Используем существующую базу данных cookies")
    else:
        print(f"Создаем новую базу данных cookies")
    
    # Подключаемся к временной базе
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    
    # Создаем таблицу cookies если её нет
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cookies (
            creation_utc INTEGER NOT NULL,
            host_key TEXT NOT NULL,
            top_frame_site_key TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            value TEXT NOT NULL,
            encrypted_value BLOB DEFAULT '',
            path TEXT NOT NULL,
            expires_utc INTEGER NOT NULL,
            is_secure INTEGER NOT NULL,
            is_httponly INTEGER NOT NULL,
            last_access_utc INTEGER NOT NULL,
            has_expires INTEGER NOT NULL DEFAULT 1,
            is_persistent INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 1,
            samesite INTEGER NOT NULL DEFAULT -1,
            source_scheme INTEGER NOT NULL DEFAULT 0,
            source_port INTEGER NOT NULL DEFAULT -1,
            is_same_party INTEGER NOT NULL DEFAULT 0,
            last_update_utc INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (host_key, top_frame_site_key, name, path)
        )
    ''')
    
    # Конвертируем timestamp в Chrome формат (микросекунды с 1601-01-01)
    def to_chrome_time(unix_timestamp):
        # Chrome использует микросекунды с 1601-01-01
        # Unix использует секунды с 1970-01-01
        # Разница: 11644473600 секунд
        if unix_timestamp == 0:
            return 0
        chrome_epoch_diff = 11644473600
        return int((unix_timestamp + chrome_epoch_diff) * 1000000)
    
    # Мапинг sameSite значений
    samesite_map = {
        'no_restriction': 0,
        'lax': 1,
        'strict': 2,
        'unspecified': -1
    }
    
    # Импортируем каждую cookie
    imported = 0
    skipped = 0
    
    for cookie in cookies:
        try:
            host_key = cookie['domain']
            if host_key.startswith('.'):
                # Для domain cookies Chrome хранит с точкой
                pass
            else:
                # Для host-only cookies
                host_key = cookie['domain']
            
            name = cookie['name']
            value = cookie['value']
            path = cookie['path']
            
            # Конвертируем expirationDate
            expires_utc = 0
            if 'expirationDate' in cookie and cookie['expirationDate']:
                expires_utc = to_chrome_time(cookie['expirationDate'])
            
            is_secure = 1 if cookie.get('secure', False) else 0
            is_httponly = 1 if cookie.get('httpOnly', False) else 0
            
            # SameSite
            samesite = samesite_map.get(cookie.get('sameSite', 'unspecified'), -1)
            
            # Текущее время
            now = to_chrome_time(datetime.now().timestamp())
            
            # Удаляем существующую cookie если есть
            cursor.execute('''
                DELETE FROM cookies 
                WHERE host_key = ? AND name = ? AND path = ?
            ''', (host_key, name, path))
            
            # Проверяем какие колонки есть в таблице
            cursor.execute("PRAGMA table_info(cookies)")
            columns = {col[1] for col in cursor.fetchall()}
            
            # Вставляем новую cookie с учетом доступных колонок
            if 'is_same_party' in columns:
                cursor.execute('''
                    INSERT INTO cookies (
                        creation_utc, host_key, top_frame_site_key, name, value,
                        encrypted_value, path, expires_utc, is_secure, is_httponly,
                        last_access_utc, has_expires, is_persistent, priority,
                        samesite, source_scheme, source_port, is_same_party, last_update_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    now,  # creation_utc
                    host_key,  # host_key
                    '',  # top_frame_site_key
                    name,  # name
                    value,  # value
                    b'',  # encrypted_value
                    path,  # path
                    expires_utc,  # expires_utc
                    is_secure,  # is_secure
                    is_httponly,  # is_httponly
                    now,  # last_access_utc
                    1 if expires_utc > 0 else 0,  # has_expires
                    1 if expires_utc > 0 else 0,  # is_persistent
                    1,  # priority
                    samesite,  # samesite
                    2 if is_secure else 0,  # source_scheme (0=http, 2=https)
                    443 if is_secure else 80,  # source_port
                    0,  # is_same_party
                    now  # last_update_utc
                ))
            elif 'source_type' in columns:
                # Новая версия Chrome с source_type
                cursor.execute('''
                    INSERT INTO cookies (
                        creation_utc, host_key, top_frame_site_key, name, value,
                        encrypted_value, path, expires_utc, is_secure, is_httponly,
                        last_access_utc, has_expires, is_persistent, priority,
                        samesite, source_scheme, source_port, last_update_utc, 
                        source_type, has_cross_site_ancestor
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    now,  # creation_utc
                    host_key,  # host_key
                    '',  # top_frame_site_key
                    name,  # name
                    value,  # value
                    b'',  # encrypted_value
                    path,  # path
                    expires_utc,  # expires_utc
                    is_secure,  # is_secure
                    is_httponly,  # is_httponly
                    now,  # last_access_utc
                    1 if expires_utc > 0 else 0,  # has_expires
                    1 if expires_utc > 0 else 0,  # is_persistent
                    1,  # priority
                    samesite,  # samesite
                    2 if is_secure else 0,  # source_scheme (0=http, 2=https)
                    443 if is_secure else 80,  # source_port
                    now,  # last_update_utc
                    0,  # source_type (0 = HTTP)
                    0  # has_cross_site_ancestor
                ))
            else:
                # Старая версия без source_type
                cursor.execute('''
                    INSERT INTO cookies (
                        creation_utc, host_key, top_frame_site_key, name, value,
                        encrypted_value, path, expires_utc, is_secure, is_httponly,
                        last_access_utc, has_expires, is_persistent, priority,
                        samesite, source_scheme, source_port, last_update_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    now,  # creation_utc
                    host_key,  # host_key
                    '',  # top_frame_site_key
                    name,  # name
                    value,  # value
                    b'',  # encrypted_value
                    path,  # path
                    expires_utc,  # expires_utc
                    is_secure,  # is_secure
                    is_httponly,  # is_httponly
                    now,  # last_access_utc
                    1 if expires_utc > 0 else 0,  # has_expires
                    1 if expires_utc > 0 else 0,  # is_persistent
                    1,  # priority
                    samesite,  # samesite
                    2 if is_secure else 0,  # source_scheme (0=http, 2=https)
                    443 if is_secure else 80,  # source_port
                    now  # last_update_utc
                ))
            
            imported += 1
            print(f"✓ Импортирована cookie: {name} для {host_key}")
            
        except Exception as e:
            print(f"✗ Ошибка при импорте cookie {cookie.get('name', 'unknown')}: {e}")
            skipped += 1
    
    # Сохраняем изменения
    conn.commit()
    conn.close()
    
    # Копируем временную базу обратно
    shutil.copy2(temp_db_path, cookies_db_path)
    os.unlink(temp_db_path)
    
    print(f"\n✅ Импорт завершен: {imported} cookies импортировано, {skipped} пропущено")
    print(f"📁 База данных сохранена: {cookies_db_path}")
    
    return imported > 0

def main():
    # Определяем пути
    script_dir = Path(__file__).parent
    cookies_json = script_dir / "cookies.json"
    chrome_profile = script_dir / "chrome_profile"
    
    # Проверяем наличие файла cookies
    if not cookies_json.exists():
        print(f"❌ Файл {cookies_json} не найден!")
        print("Создайте файл cookies.json с экспортированными cookies")
        sys.exit(1)
    
    print("🍪 Импорт cookies в Chrome профиль")
    print(f"📄 Источник: {cookies_json}")
    print(f"📁 Профиль Chrome: {chrome_profile}")
    print()
    
    # Импортируем cookies
    success = import_cookies_to_chrome(cookies_json, chrome_profile)
    
    if success:
        print("\n✅ Cookies успешно импортированы!")
        print("\nТеперь можно запустить бота с аутентификацией")
    else:
        print("\n❌ Не удалось импортировать cookies")
        sys.exit(1)

if __name__ == "__main__":
    main()
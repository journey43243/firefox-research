"""
Модуль для извлечения и загрузки cookies Firefox.
"""

import asyncio
import sqlite3
import os
from asyncio import Task
from typing import Iterable
from datetime import datetime

from Modules.Firefox.interfaces.Strategy import StrategyABC, Generator, Metadata


class CookiesStrategy(StrategyABC):
    """
    Strategy-класс для чтения и записи данных о cookies Firefox.
    """

    def __init__(self, metadata: Metadata) -> None:
        self._logInterface = metadata.logInterface
        self._dbReadInterface = metadata.dbReadInterface
        self._dbWriteInterface = metadata.dbWriteInterface
        self._profile_id = metadata.profileId
        self._profile_path = metadata.profilePath
        
        # Путь к cookies.sqlite
        self._cookies_db_path = os.path.join(metadata.profilePath, 'cookies.sqlite')
        
        self._logInterface.Info(type(self), f"Поиск cookies.sqlite по пути: {self._cookies_db_path}")

    def _timestamp_to_datetime(self, timestamp_microseconds: int) -> str:
        """Конвертирует временную метку в строку даты."""
        if not timestamp_microseconds or timestamp_microseconds == 0:
            return ''
        try:
            timestamp_seconds = timestamp_microseconds / 1000000
            dt = datetime.fromtimestamp(timestamp_seconds)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, OSError, TypeError):
            return ''

    def _expiry_to_datetime(self, expiry_seconds: int) -> str:
        """Конвертирует время истечения в строку даты."""
        if not expiry_seconds or expiry_seconds == 0:
            return ''
        try:
            dt = datetime.fromtimestamp(expiry_seconds)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, OSError, TypeError):
            return ''

    def read(self) -> Generator[list[tuple], None, None]:
        """Читает cookies из таблицы moz_cookies."""
        yield []

    async def write(self, batch: Iterable[tuple]) -> None:
        """Записывает пакет cookies."""
        pass

    def _connect_to_cookies_db(self):
        """Создает подключение к базе cookies.sqlite."""
        if not os.path.exists(self._cookies_db_path):
            return None
        
        try:
            # Простое подключение с таймаутом
            conn = sqlite3.connect(self._cookies_db_path, timeout=5.0)
            return conn
        except sqlite3.Error as e:
            self._logInterface.Error(
                type(self),
                f'Ошибка подключения к cookies.sqlite: {e}'
            )
            return None

    async def execute(self, tasks: list[Task]) -> None:
        """
        Последовательно выполняет загрузку всех cookies.
        """
        conn = self._connect_to_cookies_db()
        if conn is None:
            self._logInterface.Warn(
                type(self),
                f'Пропускаем cookies для профиля {self._profile_id} - файл cookies.sqlite отсутствует'
            )
            return

        try:
            cursor = conn.cursor()
            
            # Проверяем существование таблицы moz_cookies
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='moz_cookies'")
            if not cursor.fetchone():
                self._logInterface.Warn(
                    type(self),
                    f'Таблица moz_cookies не найдена в cookies.sqlite для профиля {self._profile_id}'
                )
                conn.close()
                return
            
            # Читаем cookies
            # Проверяем наличие столбца baseDomain
            cursor.execute("PRAGMA table_info(moz_cookies)")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Формируем запрос
            select_fields = [
                'id', 'originAttributes', 'name', 'value', 'host', 'path',
                'expiry', 'lastAccessed', 'creationTime', 'isSecure',
                'isHttpOnly', 'inBrowserElement', 'sameSite', 'schemeMap'
            ]
            
            # Добавляем дополнительные поля если они есть
            if 'isPartitionedAttributeSet' in columns:
                select_fields.append('isPartitionedAttributeSet')
            
            if 'updateTime' in columns:
                select_fields.append('updateTime')
            
            if 'baseDomain' in columns:
                select_fields.append('baseDomain')
            
            query = f"SELECT {', '.join(select_fields)} FROM moz_cookies"
            cursor.execute(query)
            
            cookies = cursor.fetchall()
            if not cookies:
                self._logInterface.Warn(
                    type(self),
                    f'Cookies не найдены для профиля {self._profile_id}'
                )
                conn.close()
                return
            
            # Обрабатываем cookies
            cookies_data = []
            for row in cookies:
                # Индексы полей
                idx = 0
                id_val = row[idx] if idx < len(row) else 0; idx += 1
                origin_attrs = row[idx] if idx < len(row) else ''; idx += 1
                name_val = row[idx] if idx < len(row) else ''; idx += 1
                value_val = row[idx] if idx < len(row) else ''; idx += 1
                host_val = row[idx] if idx < len(row) else ''; idx += 1
                path_val = row[idx] if idx < len(row) else ''; idx += 1
                expiry_val = row[idx] if idx < len(row) else 0; idx += 1
                last_accessed_val = row[idx] if idx < len(row) else 0; idx += 1
                creation_time_val = row[idx] if idx < len(row) else 0; idx += 1
                is_secure_val = row[idx] if idx < len(row) else 0; idx += 1
                is_http_only_val = row[idx] if idx < len(row) else 0; idx += 1
                in_browser_element_val = row[idx] if idx < len(row) else 0; idx += 1
                same_site_val = row[idx] if idx < len(row) else 0; idx += 1
                scheme_map_val = row[idx] if idx < len(row) else 0; idx += 1
                
                # Дополнительные поля (могут отсутствовать)
                is_partitioned = 0
                if 'isPartitionedAttributeSet' in columns and idx < len(row):
                    is_partitioned = row[idx]; idx += 1
                
                update_time_val = 0
                if 'updateTime' in columns and idx < len(row):
                    update_time_val = row[idx]; idx += 1
                
                base_domain_val = ''
                if 'baseDomain' in columns and idx < len(row):
                    base_domain_val = row[idx] if row[idx] else ''
                
                # Если baseDomain пустой, вычисляем из host
                if not base_domain_val and host_val:
                    base_domain_val = host_val.lstrip('.')
                
                # Преобразуем временные метки
                expiry_dt = self._expiry_to_datetime(expiry_val)
                last_accessed_dt = self._timestamp_to_datetime(last_accessed_val)
                creation_dt = self._timestamp_to_datetime(creation_time_val)
                
                cookies_data.append((
                    id_val,
                    origin_attrs,
                    name_val,
                    value_val,
                    host_val,
                    path_val,
                    expiry_dt,
                    last_accessed_dt,
                    creation_dt,
                    is_secure_val,
                    is_http_only_val,
                    in_browser_element_val,
                    same_site_val,
                    scheme_map_val,
                    is_partitioned,
                    update_time_val,
                    base_domain_val,
                    self._profile_id
                ))
            
            # Записываем в базу
            if cookies_data:
                self._dbWriteInterface._cursor.executemany(
                    '''INSERT OR REPLACE INTO cookies 
                       (id, origin_attributes, name, value, host, path, expiry,
                        last_accessed, creation_time, is_secure, is_http_only,
                        in_browser_element, same_site, scheme_map, 
                        is_partitioned_attribute_set, update_time, base_domain, profile_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    cookies_data
                )
                self._dbWriteInterface.Commit()
                self._logInterface.Info(
                    type(self),
                    f'Загружено {len(cookies_data)} cookies для профиля {self._profile_id}'
                )
            
        except sqlite3.Error as e:
            self._logInterface.Error(
                type(self),
                f'Ошибка SQLite при обработке cookies: {e}'
            )
        except Exception as e:
            self._logInterface.Error(type(self), f'Ошибка при обработке cookies: {e}')
        finally:
            conn.close()
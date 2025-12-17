"""
Модуль для извлечения и загрузки кэша иконок Firefox.
"""

import asyncio
import sqlite3
import os
from asyncio import Task
from typing import Iterable

from Modules.Firefox.interfaces.Strategy import StrategyABC, Generator, Metadata


class FaviconsStrategy(StrategyABC):
    """
    Strategy-класс для чтения и записи данных о кэшированных иконках Firefox.
    """

    def __init__(self, metadata: Metadata) -> None:
        self._logInterface = metadata.logInterface
        self._dbReadInterface = metadata.dbReadInterface
        self._dbWriteInterface = metadata.dbWriteInterface
        self._profile_id = metadata.profileId
        self._profile_path = metadata.profilePath
        
        # Путь к favicons.sqlite
        self._favicons_db_path = os.path.join(metadata.profilePath, 'favicons.sqlite')
        
        self._logInterface.Info(type(self), f"Поиск favicons.sqlite по пути: {self._favicons_db_path}")

    def read(self) -> Generator[list[tuple], None, None]:
        """Читает данные об иконках."""
        yield []

    async def write(self, batch: Iterable[tuple]) -> None:
        """Записывает пакет данных."""
        pass

    def _connect_to_favicons_db(self):
        """Создает подключение к базе favicons.sqlite."""
        if not os.path.exists(self._favicons_db_path):
            return None
        
        try:
            # Простое подключение с таймаутом
            conn = sqlite3.connect(self._favicons_db_path, timeout=5.0)
            return conn
        except sqlite3.Error as e:
            self._logInterface.Error(
                type(self),
                f'Ошибка подключения к favicons.sqlite: {e}'
            )
            return None

    async def execute(self, tasks: list[Task]) -> None:
        """
        Последовательно выполняет загрузку всех пакетов данных.
        """
        conn = self._connect_to_favicons_db()
        if conn is None:
            self._logInterface.Warn(
                type(self),
                f'Пропускаем favicons для профиля {self._profile_id} - файл favicons.sqlite отсутствует'
            )
            return

        try:
            cursor = conn.cursor()
            
            # 1. Проверяем существование таблиц
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='moz_icons'")
            if not cursor.fetchone():
                self._logInterface.Warn(
                    type(self),
                    f'Таблица moz_icons не найдена в favicons.sqlite для профиля {self._profile_id}'
                )
                conn.close()
                return
            
            # 2. Чтение иконок из moz_icons
            cursor.execute('''
                SELECT id, icon_url, fixed_icon_url_hash, width, root, color, expire_ms, flags, data
                FROM moz_icons
            ''')
            
            icons = cursor.fetchall()
            if icons:
                icons_data = []
                for row in icons:
                    icons_data.append((
                        row[0] if len(row) > 0 else 0,     # id
                        row[1] if len(row) > 1 else '',    # icon_url
                        row[2] if len(row) > 2 else 0,     # fixed_icon_url_hash
                        row[3] if len(row) > 3 else 0,     # width
                        row[4] if len(row) > 4 else 0,     # root
                        row[5] if len(row) > 5 else 0,     # color
                        row[6] if len(row) > 6 else 0,     # expire_ms
                        row[7] if len(row) > 7 else 0,     # flags
                        row[8] if len(row) > 8 else b'',   # data
                        self._profile_id
                    ))
                
                self._dbWriteInterface._cursor.executemany(
                    '''INSERT OR REPLACE INTO favicons 
                       (id, icon_url, fixed_icon_url_hash, width, root, color, expire_ms, flags, data, profile_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    icons_data
                )
                self._dbWriteInterface.Commit()
                self._logInterface.Info(type(self), f'Загружено {len(icons)} иконок')
            
            # 3. Чтение страниц из moz_pages_w_icons
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='moz_pages_w_icons'")
            if cursor.fetchone():
                cursor.execute('SELECT id, page_url, page_url_hash FROM moz_pages_w_icons')
                pages = cursor.fetchall()
                
                if pages:
                    pages_data = []
                    for row in pages:
                        pages_data.append((
                            row[0] if len(row) > 0 else 0,     # id
                            row[1] if len(row) > 1 else '',    # page_url
                            row[2] if len(row) > 2 else 0,     # page_url_hash
                            self._profile_id
                        ))
                    
                    self._dbWriteInterface._cursor.executemany(
                        '''INSERT OR REPLACE INTO favicon_pages 
                           (id, page_url, page_url_hash, profile_id)
                           VALUES (?, ?, ?, ?)''',
                        pages_data
                    )
                    self._dbWriteInterface.Commit()
                    self._logInterface.Info(type(self), f'Загружено {len(pages)} страниц')
            
            # 4. Чтение связей из moz_icons_to_pages
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='moz_icons_to_pages'")
            if cursor.fetchone():
                cursor.execute('SELECT page_id, icon_id, expire_ms FROM moz_icons_to_pages')
                relations = cursor.fetchall()
                
                if relations:
                    relations_data = []
                    for row in relations:
                        relations_data.append((
                            row[0] if len(row) > 0 else 0,     # page_id
                            row[1] if len(row) > 1 else 0,     # icon_id
                            row[2] if len(row) > 2 else 0,     # expire_ms
                            self._profile_id
                        ))
                    
                    self._dbWriteInterface._cursor.executemany(
                        '''INSERT OR REPLACE INTO favicons_to_pages 
                           (page_id, icon_id, expire_ms, profile_id)
                           VALUES (?, ?, ?, ?)''',
                        relations_data
                    )
                    self._dbWriteInterface.Commit()
                    self._logInterface.Info(type(self), f'Загружено {len(relations)} связей')
            
        except sqlite3.Error as e:
            self._logInterface.Error(
                type(self),
                f'Ошибка SQLite при обработке favicons: {e}'
            )
        except Exception as e:
            self._logInterface.Error(type(self), f'Ошибка при обработке favicons: {e}')
        finally:
            conn.close()
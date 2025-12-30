"""
Модуль для извлечения и загрузки cookies Firefox.
"""
import pathlib
import sqlite3

from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable
from datetime import datetime

from Common.Routines import SQLiteDatabaseInterface
from Modules.Firefox.interfaces.Strategy import StrategyABC, Generator, Metadata

Cookie = namedtuple(
    'Cookie',
    'id origin_attributes name value host path expiry last_accessed '
    'creation_time is_secure is_http_only in_browser_element same_site '
    'scheme_map is_partitioned_attribute_set update_time base_domain profile_id'
)


class CookiesStrategy(StrategyABC):
    """
    Strategy-класс для чтения и записи данных о cookies Firefox.
    """

    def __init__(self, metadata: Metadata) -> None:
        self._logInterface = metadata.logInterface
        self.moduleName = "FirefoxCookies"
        self._dbWriteInterface = self._writeInterface(self.moduleName, metadata.logInterface, metadata.caseFolder)
        self.timestamp = self._timestamp(metadata.caseFolder)
        self._profile_id = metadata.profileId
        self._profile_path = metadata.profilePath
        self._cookies_db_path = pathlib.Path(metadata.profilePath).joinpath('cookies.sqlite')
        self._dbReadInterface = SQLiteDatabaseInterface(str(self._cookies_db_path), self._logInterface,
                                                        metadata.caseFolder, moduleRAMProcessing=False)

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

    def createDataTable(self):
        """
        Создаёт таблицу 'cookies' для хранения cookies Firefox
        и индекс по base_domain.
        """
        self._dbWriteInterface.ExecCommit(
            '''CREATE TABLE IF NOT EXISTS Data (
                id INTEGER,
                origin_attributes TEXT,
                name TEXT,
                value TEXT,
                host TEXT,
                path TEXT,
                expiry TEXT,
                last_accessed TEXT,
                creation_time TEXT,
                is_secure INTEGER,
                is_http_only INTEGER,
                in_browser_element INTEGER,
                same_site INTEGER,
                scheme_map INTEGER,
                is_partitioned_attribute_set INTEGER,
                update_time INTEGER,
                base_domain TEXT,
                profile_id INTEGER,
                PRIMARY KEY (id, profile_id)
            )'''
        )

        self._dbWriteInterface.ExecCommit(
            '''CREATE INDEX idx_cookies_base_domain ON Data (base_domain)'''
        )

        self._logInterface.Info(type(self), 'Таблица cookies создана')

    def createHeadersTables(self):
        self._dbWriteInterface.ExecCommit(
            '''CREATE TABLE IF NOT EXISTS Headers (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Name TEXT,
                Label TEXT,
                Width INTEGER,
                DataType TEXT,
                Comment TEXT
            )'''
        )

        self._dbWriteInterface.ExecCommit(
            '''INSERT INTO Headers (Name, Label, Width, DataType, Comment) VALUES
                ('id', 'ID cookie', 165, 'int', 'Уникальный идентификатор cookie'),
                ('origin_attributes', 'Origin Attributes', 175, 'string', 'Контекст происхождения cookie'),
                ('name', 'Имя', 190, 'string', 'Имя cookie'),
                ('value', 'Значение', 200, 'string', 'Значение cookie'),
                ('host', 'Хост', 185, 'string', 'Домен, к которому относится cookie'),
                ('path', 'Путь', 155, 'string', 'Путь cookie'),
                ('expiry', 'Истекает', 160, 'string', 'Дата истечения cookie'),
                ('last_accessed', 'Последний доступ', 180, 'string', 'Когда cookie был использован'),
                ('creation_time', 'Создан', 170, 'string', 'Когда cookie был создан'),
                ('is_secure', 'Secure', 150, 'int', 'Флаг Secure'),
                ('is_http_only', 'HttpOnly', 155, 'int', 'Флаг HttpOnly'),
                ('in_browser_element', 'InBrowserElement', -1, 'int', 'Флаг inBrowserElement'),
                ('same_site', 'SameSite', 160, 'int', 'Политика SameSite'),
                ('scheme_map', 'SchemeMap', -1, 'int', 'Карта схемы cookie'),
                ('is_partitioned_attribute_set', 'Partitioned', 165, 'int', 'Признак разделённого cookie'),
                ('update_time', 'UpdateTime', -1, 'int', 'Время обновления cookie'),
                ('base_domain', 'BaseDomain', 175, 'string', 'Базовый домен cookie'),
                ('profile_id', 'ID профиля', 160, 'int', 'Связанный профиль браузера')
            '''
        )

    @property
    def help(self) -> str:
        return f"{self.moduleName}: Извлечение cookies из cookies.sqlite"

    def read(self) -> Generator[list[Cookie], None, None]:
        """
        Читает cookies из cookies.sqlite пакетами по 500 строк.
        """
        try:
            # Узнаём доступные столбцы
            pragma = self._dbReadInterface.Fetch("PRAGMA table_info(moz_cookies)", commit_required=False)
            if pragma:
                columns = [col[1] for col in pragma]
            else:
                columns = []

            # Базовые поля (есть всегда)
            select_fields = [
                'id', 'originAttributes', 'name', 'value', 'host', 'path',
                'expiry', 'lastAccessed', 'creationTime',
                'isSecure', 'isHttpOnly', 'inBrowserElement',
                'sameSite', 'schemeMap'
            ]

            # Опциональные поля
            has_partitioned = 'isPartitionedAttributeSet' in columns
            has_update_time = 'updateTime' in columns
            has_base_domain = 'baseDomain' in columns

            if has_partitioned:
                select_fields.append('isPartitionedAttributeSet')
            if has_update_time:
                select_fields.append('updateTime')
            if has_base_domain:
                select_fields.append('baseDomain')

            # Выполняем запрос
            query = f"SELECT {', '.join(select_fields)} FROM moz_cookies"
            cursor = self._dbReadInterface.Fetch(query, commit_required=False)

            # Читаем пакетами
            i = 0
            while i < len(cursor):
                batch = cursor[i: i + 500]
                if not batch:
                    break

                result = []
                for row in batch:
                    # Правильная логика распаковки
                    row_list = list(row)

                    # Обязательные поля (первые 14)
                    id_val = row_list[0]
                    origin_attrs = row_list[1]
                    name_val = row_list[2]
                    value_val = row_list[3]
                    host_val = row_list[4]
                    path_val = row_list[5]
                    expiry_val = row_list[6]
                    last_accessed_val = row_list[7]
                    creation_time_val = row_list[8]
                    is_secure_val = row_list[9]
                    is_http_only_val = row_list[10]
                    in_browser_element_val = row_list[11]
                    same_site_val = row_list[12]
                    scheme_map_val = row_list[13]

                    # Обработка опциональных полей
                    is_partitioned = 0
                    update_time = 0
                    base_domain = ''

                    # Счетчик для опциональных полей
                    idx = 14

                    if has_partitioned:
                        is_partitioned = row_list[idx] if row_list[idx] is not None else 0
                        idx += 1

                    if has_update_time:
                        update_time = row_list[idx] if row_list[idx] is not None else 0
                        idx += 1

                    if has_base_domain:
                        base_domain = row_list[idx] if row_list[idx] is not None else ''
                        # Если baseDomain отсутствует — вычисляем из host
                        if not base_domain and host_val:
                            base_domain = host_val.lstrip('.')
                    elif host_val:
                        # Если поля base_domain нет в таблице, вычисляем из host
                        base_domain = host_val.lstrip('.')

                    # Формируем Cookie в правильном порядке
                    result.append(
                        Cookie(
                            id_val,
                            origin_attrs,
                            name_val,
                            value_val,
                            host_val,
                            path_val,
                            self._expiry_to_datetime(expiry_val),
                            self._timestamp_to_datetime(last_accessed_val),
                            self._timestamp_to_datetime(creation_time_val),
                            is_secure_val,
                            is_http_only_val,
                            in_browser_element_val,
                            same_site_val,
                            scheme_map_val,
                            is_partitioned,
                            update_time,
                            base_domain,
                            self._profile_id
                        )
                    )
                i += 500
                yield result
        except AttributeError:
            pass
        except sqlite3.Error as e:
            print(f"Ошибка SQLite при чтении cookies: {e}")

    def write(self, batch: Iterable[Cookie]) -> None:
        for row in batch:
            self._dbWriteInterface.ExecCommit(
                '''INSERT OR REPLACE INTO Data
                   (id, origin_attributes, name, value, host, path, expiry,
                    last_accessed, creation_time, is_secure, is_http_only,
                    in_browser_element, same_site, scheme_map,
                    is_partitioned_attribute_set, update_time, base_domain, profile_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                row
            )
        self._logInterface.Info(type(self), f'Группа из {len(batch)} cookies успешно загружена')

    def execute(self) -> None:
        self.createDataTable()
        for batch in self.read():
            self.write(batch)
        self.createInfoTable(self.timestamp)
        self.createHeadersTables()
        self._dbWriteInterface.SaveSQLiteDatabaseFromRamToFile()

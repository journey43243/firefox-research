"""Модуль стратегии чтения и записи расширений Firefox.

Содержит реализацию `ExtensionsStrategy`, предназначенную для
извлечения данных о расширениях браузера Firefox из файла
`extensions.json` профиля и записи их в выходную базу данных.
"""

import asyncio
import json
import os
import pathlib
from asyncio import Task
from collections import namedtuple
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Iterable, Generator

from Common.Routines import SQLiteDatabaseInterface
from Modules.Firefox.interfaces.Strategy import StrategyABC, Metadata

# Именованный кортеж, описывающий структуру расширения Firefox
Extension = namedtuple(
    'Extension',
    'id name version description type active user_disabled install_date '
    'update_date path source_url permissions location profile_id'
)


class ExtensionsStrategy(StrategyABC):
    """Стратегия обработки данных о расширениях Firefox.

    Стратегия читает список расширений из файла `extensions.json`
    внутри профиля Firefox, фильтрует только объекты типа "extension",
    преобразует их в структуру `Extension` и передает в модуль записи.

    Атрибуты:
        _logInterface: Интерфейс логирования.
        _dbReadInterface: Интерфейс чтения данных (не используется в этой стратегии).
        _dbWriteInterface: Интерфейс записи данных в конечную БД.
        _profile_id (int): Идентификатор профиля Firefox.
        _profile_path (str): Путь к директории профиля Firefox.
    """

    def __init__(self, metadata: Metadata) -> None:
        """Инициализирует стратегию данными из контейнера Metadata.

        Args:
            metadata (Metadata): Метаданные, включающие интерфейсы БД,
                параметры профиля и интерфейс логирования.
        """
        self._logInterface = metadata.logInterface
        self.moduleName = "FirefoxExtensions"
        self.timestamp = self._timestamp(metadata.caseFolder)
        self._dbReadInterface = metadata.dbReadInterface
        self._dbWriteInterface = self._writeInterface(self.moduleName, metadata.logInterface, metadata.caseFolder)
        self._profile_id = metadata.profileId
        self._profile_path = metadata.profilePath

    def createDataTable(self):
        """
                Создаёт таблицу 'extensions' для хранения расширений Firefox
                и соответствующие индексы по id и profile_id.
                """
        self._dbWriteInterface.ExecCommit(
            '''CREATE TABLE IF NOT EXISTS extensions (
                id TEXT PRIMARY KEY,
                name TEXT,
                version TEXT,
                description TEXT,
                type TEXT,
                active INTEGER,
                user_disabled INTEGER,
                install_date INTEGER,
                update_date INTEGER,
                path TEXT,
                source_url TEXT,
                permissions TEXT,
                location TEXT,
                profile_id INTEGER
            )'''
        )
        self._dbWriteInterface.ExecCommit('''CREATE INDEX IF NOT EXISTS idx_extensions_id ON extensions (id)''')
        self._dbWriteInterface.ExecCommit(
            '''CREATE INDEX IF NOT EXISTS idx_extensions_profile_id ON extensions (profile_id)''')
        self._logInterface.Info(type(self), 'Таблица с расширениями создана')

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
                ('id', 'ID расширения', -1, 'string', 'Уникальный идентификатор расширения'),
                ('name', 'Название', -1, 'string', 'Имя расширения'),
                ('version', 'Версия', -1, 'string', 'Версия установленного расширения'),
                ('description', 'Описание', -1, 'string', 'Описание функционала расширения'),
                ('type', 'Тип', -1, 'string', 'Тип расширения'),
                ('active', 'Активно', -1, 'int', '1 — активно, 0 — отключено'),
                ('user_disabled', 'Отключено пользователем', -1, 'int', '1 — пользователь отключил, 0 — нет'),
                ('install_date', 'Дата установки', -1, 'int', 'Время установки расширения'),
                ('update_date', 'Дата обновления', -1, 'int', 'Время последнего обновления'),
                ('path', 'Путь', -1, 'string', 'Путь к файлам расширения'),
                ('source_url', 'Источник', -1, 'string', 'URL источника расширения'),
                ('permissions', 'Разрешения', -1, 'string', 'Список разрешений расширения'),
                ('location', 'Расположение', -1, 'string', 'Где установлено расширение'),
                ('profile_id', 'ID профиля', -1, 'int', 'Связанный профиль браузера')
            '''
        )
    @property
    def help(self) -> str:
        return f"{self.moduleName}: Извлечение расширений из extensions.json"


    def read(self) -> Generator[list[Extension], None, None]:
        """Считывает расширения Firefox из файла extensions.json.

        Возвращает данные одним батчем (списком структур Extension),
        или завершает работу без возврата, если файл отсутствует.

        Returns:
            Generator[list[Extension], None, None]: Генератор, выдающий
                список найденных расширений ровно один раз.

        Notes:
            В случае отсутствия файла создается предупреждение в логах.
            Ошибки чтения JSON или структуры данных логируются.

        Raises:
            Exception: Любая ошибка чтения файла или парсинга JSON
                логируется, но не пробрасывается.
        """
        extensions_file = os.path.join(self._profile_path, 'extensions.json')
        if not os.path.exists(extensions_file):
            self._logInterface.Warn(
                type(self),
                f'Файл расширений не найден: {extensions_file}'
            )
            return

        try:
            with open(extensions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            extensions = []
            for addon in data.get('addons', []):
                if addon.get('type') != 'extension':
                    continue

                default_locale = addon.get('defaultLocale', {})
                permissions = addon.get('userPermissions', {})

                extension = Extension(
                    id=addon.get('id', ''),
                    name=default_locale.get('name', ''),
                    version=addon.get('version', ''),
                    description=default_locale.get('description', ''),
                    type=addon.get('type', ''),
                    active=1 if addon.get('active', False) else 0,
                    user_disabled=1 if addon.get('userDisabled', False) else 0,
                    install_date=addon.get('installDate', 0),
                    update_date=addon.get('updateDate', 0),
                    path=addon.get('path', ''),
                    source_url=addon.get('sourceURI', ''),
                    permissions=json.dumps(permissions) if permissions else '',
                    location=addon.get('location', ''),
                    profile_id=self._profile_id
                )
                extensions.append(extension)

            yield extensions
            self._logInterface.Info(
                type(self),
                f'Найдено {len(extensions)} расширений'
            )

        except Exception as e:
            self._logInterface.Error(
                type(self),
                f'Ошибка чтения расширений: {str(e)}'
            )

    def write(self, batch: Iterable[Extension]) -> None:
        """Записывает список расширений в выходную базу данных.

        Args:
            batch (Iterable[Extension]): Список объектов расширений,
                подготовленных к записи.

        Returns:
            None

        Notes:
            Все записи добавляются через `INSERT OR IGNORE`, что
            исключает дублирование строк.

        Raises:
            Exception: Любая ошибка записи логируется.
        """
        try:
            self._dbWriteInterface._cursor.executemany(
                '''INSERT OR IGNORE INTO extensions 
                (id, name, version, description, type, active, user_disabled, 
                 install_date, update_date, path, source_url, permissions, location, profile_id) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                batch
            )
            self._dbWriteInterface.Commit()
            self._logInterface.Info(type(self), 'Расширения записаны в БД')
        except Exception as e:
            self._logInterface.Error(
                type(self),
                f'Ошибка записи расширений: {str(e)}'
            )

    def execute(self, executor: ThreadPoolExecutor) -> None:
        self.createDataTable()
        for batch in self.read():
            if batch:  # Проверяем, что батч не пустой
                executor.submit(self.write,batch)
        self.createInfoTable(self.timestamp)
        self.createHeadersTables()
        self._dbWriteInterface.SaveSQLiteDatabaseFromRamToFile()

"""
Модуль для извлечения и загрузки кэша иконок Firefox.

Данный модуль реализует стратегию FaviconsStrategy, которая отвечает
за чтение записей из таблиц `moz_icons`, `moz_pages_w_icons` и `moz_icons_to_pages`
исходного профиля Firefox и последующую пакетную запись преобразованных данных
в результирующую БД.
"""

import asyncio
import sqlite3
from asyncio import Task
from collections import namedtuple
from typing import Iterable

from Modules.Firefox.interfaces.Strategy import StrategyABC, Generator, Metadata

Favicon = namedtuple(
    'Favicon',
    'id icon_url width height root color data profile_id'
)

FaviconPage = namedtuple(
    'FaviconPage',
    'page_url page_url_hash profile_id'
)

FaviconToPage = namedtuple(
    'FaviconToPage',
    'page_id icon_id profile_id'
)


class FaviconsStrategy(StrategyABC):
    """
    Strategy-класс для чтения и записи данных о кэшированных иконках Firefox.

    Данная стратегия реализует выгрузку информации об иконках из исходной базы Firefox
    и их последующую загрузку в результирующую базу в пакетном режиме.

    Атрибуты
    --------
    _logInterface : Any
        Интерфейс логирования, используемый для вывода диагностических сообщений.
    _dbReadInterface : Any
        Интерфейс чтения данных из исходной базы Firefox.
    _dbWriteInterface : Any
        Интерфейс записи данных в результирующую базу.
    _profile_id : int | str
        Идентификатор профиля Firefox, которому принадлежат извлекаемые записи.
    """

    def __init__(self, metadata: Metadata) -> None:
        """
        Инициализирует стратегию кэша иконок, подключая необходимые интерфейсы.

        Parameters
        ----------
        metadata : Metadata
            Контейнер с зависимостями: интерфейсы логирования, чтения,
            записи, а также идентификатор профиля.
        """
        self._logInterface = metadata.logInterface
        self._dbReadInterface = metadata.dbReadInterface
        self._dbWriteInterface = metadata.dbWriteInterface
        self._profile_id = metadata.profileId

    def read_icons(self) -> Generator[list['Favicon'], None, None]:
        """
        Читает иконки из таблицы moz_icons исходной базы Firefox пакетами по 500 строк.

        Returns
        -------
        Generator[list[Favicon], None, None]
            Генератор, возвращающий списки объектов Favicon.

        Notes
        -----
        При возникновении ошибки чтения (например, блокировки SQLite)
        выводится предупреждение и чтение прекращается.
        """
        try:
            cursor = self._dbReadInterface._cursor.execute(
                '''SELECT id, icon_url, width, height, root, color, data
                   FROM moz_icons'''
            )
            while True:
                batch = cursor.fetchmany(500)
                if not batch:
                    break
                yield [Favicon(*row, profile_id=self._profile_id) for row in batch]
        except sqlite3.OperationalError as e:
            self._logInterface.Warn(
                type(self),
                f'Иконки для профиля {self._profile_id} не могут быть считаны: {e}'
            )

    def read_pages(self) -> Generator[list['FaviconPage'], None, None]:
        """
        Читает страницы из таблицы moz_pages_w_icons пакетами по 500 строк.

        Returns
        -------
        Generator[list[FaviconPage], None, None]
            Генератор, возвращающий списки объектов FaviconPage.
        """
        try:
            cursor = self._dbReadInterface._cursor.execute(
                '''SELECT id, page_url, page_url_hash
                   FROM moz_pages_w_icons'''
            )
            while True:
                batch = cursor.fetchmany(500)
                if not batch:
                    break
                yield [FaviconPage(*row, profile_id=self._profile_id) for row in batch]
        except sqlite3.OperationalError as e:
            self._logInterface.Warn(
                type(self),
                f'Страницы иконок для профиля {self._profile_id} не могут быть считаны: {e}'
            )

    def read_icons_to_pages(self) -> Generator[list['FaviconToPage'], None, None]:
        """
        Читает связи иконок со страницами из таблицы moz_icons_to_pages пакетами по 500 строк.

        Returns
        -------
        Generator[list[FaviconToPage], None, None]
            Генератор, возвращающий списки объектов FaviconToPage.
        """
        try:
            cursor = self._dbReadInterface._cursor.execute(
                '''SELECT id, page_id, icon_id
                   FROM moz_icons_to_pages'''
            )
            while True:
                batch = cursor.fetchmany(500)
                if not batch:
                    break
                yield [FaviconToPage(*row, profile_id=self._profile_id) for row in batch]
        except sqlite3.OperationalError as e:
            self._logInterface.Warn(
                type(self),
                f'Связи иконок для профиля {self._profile_id} не могут быть считаны: {e}'
            )

    async def write_icons(self, batch: Iterable[tuple]) -> None:
        """
        Записывает пакет иконок в результирующую базу.

        Parameters
        ----------
        batch : Iterable[tuple]
            Пакет данных иконок в виде кортежей для операции INSERT OR REPLACE.
        """
        self._dbWriteInterface._cursor.executemany(
            '''INSERT OR REPLACE INTO favicons 
               (id, icon_url, width, height, root, color, data, profile_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            batch
        )
        self._dbWriteInterface.Commit()
        self._logInterface.Info(type(self), f'Группа из {len(batch)} иконок успешно загружена')

    async def write_pages(self, batch: Iterable[tuple]) -> None:
        """
        Записывает пакет страниц в результирующую базу.

        Parameters
        ----------
        batch : Iterable[tuple]
            Пакет данных страниц в виде кортежей для операции INSERT OR REPLACE.
        """
        self._dbWriteInterface._cursor.executemany(
            '''INSERT OR REPLACE INTO favicon_pages 
               (id, page_url, page_url_hash, profile_id)
               VALUES (?, ?, ?, ?)''',
            batch
        )
        self._dbWriteInterface.Commit()
        self._logInterface.Info(type(self), f'Группа из {len(batch)} страниц успешно загружена')

    async def write_icons_to_pages(self, batch: Iterable[tuple]) -> None:
        """
        Записывает пакет связей иконок со страницами в результирующую базу.

        Parameters
        ----------
        batch : Iterable[tuple]
            Пакет данных связей в виде кортежей для операции INSERT OR REPLACE.
        """
        self._dbWriteInterface._cursor.executemany(
            '''INSERT OR REPLACE INTO favicons_to_pages 
               (id, page_id, icon_id, profile_id)
               VALUES (?, ?, ?, ?)''',
            batch
        )
        self._dbWriteInterface.Commit()
        self._logInterface.Info(type(self), f'Группа из {len(batch)} связей успешно загружена')

    async def execute(self, tasks: list[Task]) -> None:
        """
        Последовательно выполняет загрузку всех пакетов данных кэша иконок.

        Чтение происходит в синхронном режиме через генераторы read_*().
        Для каждого пакета создаётся асинхронная задача записи и дожидаются
        её завершения перед переходом к следующему.

        Parameters
        ----------
        tasks : list[Task]
            Список, в который добавляются созданные задачи записи.

        Notes
        -----
        Выполнение последовательное для контроля порядка записи.
        """
        # Чтение и запись иконок
        for batch in self.read_icons():
            task = asyncio.create_task(self.write_icons(batch))
            tasks.append(task)
            await task

        # Чтение и запись страниц
        for batch in self.read_pages():
            task = asyncio.create_task(self.write_pages(batch))
            tasks.append(task)
            await task

        # Чтение и запись связей
        for batch in self.read_icons_to_pages():
            task = asyncio.create_task(self.write_icons_to_pages(batch))
            tasks.append(task)
            await task
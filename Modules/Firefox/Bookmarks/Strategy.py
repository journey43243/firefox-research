"""
Модуль для извлечения и загрузки закладок Firefox.

Данный модуль реализует стратегию BookmarksStrategy, которая отвечает
за чтение записей из таблицы `moz_bookmarks` исходного профиля Firefox
и последующую пакетную запись преобразованных данных в результирующую БД.
Стратегия работает с закладками типа 1 (обычные записи) и преобразует
временные метки Firefox в формат datetime.

Модуль используется в составе системы переноса данных профиля Firefox.
"""

import sqlite3
from collections import namedtuple
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Iterable

from Modules.Firefox.interfaces.Strategy import StrategyABC, Generator, Metadata

Bookmark = namedtuple(
    'Bookmark',
    'id type fk parent position title date_added last_modified profile_id'
)


class BookmarksStrategy(StrategyABC):
    """
    Strategy-класс для чтения и записи данных о закладках Firefox.

    Данная стратегия реализует выгрузку закладок из исходной базы Firefox
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
        Инициализирует стратегию закладок, подключая необходимые интерфейсы.

        Parameters
        ----------
        metadata : Metadata
            Контейнер с зависимостями: интерфейсы логирования, чтения,
            записи, а также идентификатор профиля.
        """
        self._logInterface = metadata.logInterface
        self._dbReadInterface = metadata.dbReadInterface
        self._dbWriteInterface = self._writeInterface("FirefoxBookmarks",metadata.logInterface,metadata.caseFolder)
        self._profile_id = metadata.profileId

    def createDataTable(self):
        """
        Создаёт таблицу 'bookmarks' для хранения закладок Firefox.
        """
        self._dbWriteInterface.ExecCommit(
            '''CREATE TABLE bookmarks (id INTEGER, type INTEGER, place INTEGER,
            parent INTEGER, position INTEGER, title TEXT,
            date_added text, last_modified text, profile_id INTEGER,
            PRIMARY KEY (id, profile_id))'''
        )
        self._logInterface.Info(type(self), 'Таблица с вкладками создана')

    def read(self) -> Generator[list['Bookmark'], None, None]:
        """
        Читает закладки из исходной базы Firefox пакетами по 500 строк.

        Returns
        -------
        Generator[list[Bookmark], None, None]
            Генератор, возвращающий списки объектов Bookmark.

        Notes
        -----
        При возникновении ошибки чтения (например, блокировки SQLite)
        выводится предупреждение и чтение прекращается.
        """
        try:
            cursor = self._dbReadInterface._cursor.execute(
                '''SELECT id, type, fk, parent, position, title, 
                          datetime(dateAdded / 1000000, 'unixepoch') as date_added,
                          datetime(lastModified / 1000000, 'unixepoch') as last_modified
                   FROM moz_bookmarks 
                   WHERE type = 1'''
            )
            while True:
                batch = cursor.fetchmany(500)
                if not batch:
                    break
                yield [Bookmark(*row, profile_id=self._profile_id) for row in batch]
        except sqlite3.OperationalError as e:
            self._logInterface.Warn(
                type(self),
                f'Закладки для профиля {self._profile_id} не могут быть считаны: {e}'
            )

    def write(self, butch: Iterable[tuple]) -> None:
        """
        Записывает пакет закладок в результирующую базу.

        Parameters
        ----------
        butch : Iterable[tuple]
            Пакет данных закладок в виде кортежей для операции INSERT OR REPLACE.

        Notes
        -----
        После записи вызывается Commit(), а также выводится информационное сообщение.
        """
        self._dbWriteInterface._cursor.executemany(
            '''INSERT OR REPLACE INTO bookmarks 
               (id, type, place, parent, position, title, date_added, last_modified, profile_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            butch
        )
        self._dbWriteInterface.Commit()
        self._logInterface.Info(type(self), f'Группа из {len(butch)} закладок успешно загружена')

    def execute(self, executor: ThreadPoolExecutor) -> None:
        self.createDataTable()
        for batch in self.read():
            executor.submit(self.write,batch)
        self._dbWriteInterface.SaveSQLiteDatabaseFromRamToFile()

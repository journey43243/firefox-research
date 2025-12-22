"""Модуль стратегии извлечения истории посещений Firefox.

Содержит реализацию `HistoryStrategy`, которая считывает историю
просмотров из таблицы `moz_places` профиля Firefox и сохраняет её
в выходную базу данных.
"""
import pathlib
import sqlite3
from collections import namedtuple
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Iterable

from Common.Routines import SQLiteDatabaseInterface
from Modules.Firefox.interfaces.Strategy import StrategyABC, Generator, Metadata

# Именованный кортеж, описывающий запись истории браузера Firefox
History = namedtuple(
    'History',
    'url title visit_count typed last_visit_date profile_id'
)


class HistoryStrategy(StrategyABC):
    """Стратегия обработки данных истории посещений (history) Firefox.

    Читает данные из таблицы `moz_places`, формирует партионные списки
    объектов `History` и передаёт их в модуль записи в БД. Конвертация
    времени последнего посещения выполняется встроенной функцией SQLite.

    Атрибуты:
        _logInterface: Интерфейс логирования.
        _dbReadInterface: Интерфейс чтения данных из базы Firefox.
        _dbWriteInterface: Интерфейс записи данных в выходную базу.
        _profile_id (int): Идентификатор активного профиля.
    """

    def __init__(self, metadata: Metadata) -> None:
        """Инициализирует стратегию на основе метаданных.

        Args:
            metadata (Metadata): Структура, содержащая интерфейсы БД,
                параметры профиля и интерфейс логирования.
        """
        self._logInterface = metadata.logInterface
        self.moduleName = "FirefoxHistory"
        self.timestamp = self._timestamp(metadata.caseFolder)
        self._dbReadInterface = metadata.dbReadInterface
        self._dbWriteInterface = self._writeInterface(self.moduleName, metadata.logInterface, metadata.caseFolder)
        self._profile_id = metadata.profileId

    def createDataTable(self):
        """
               Создаёт таблицу 'history' для хранения истории посещённых сайтов
               и индекс по URL.
               """
        self._dbWriteInterface.ExecCommit(
            '''CREATE TABLE Data (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT,
                title TEXT, visit_count INTEGER, typed INTEGER, last_visit_date text,
                profile_id INTEGER)'''
        )
        self._dbWriteInterface.ExecCommit('''CREATE INDEX idx_history_url on Data (url)''')
        self._logInterface.Info(type(self), 'Таблица с историей создана')

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
                ('id', 'ID записи', -1, 'int', 'Уникальный идентификатор записи'),
                ('url', 'URL', -1, 'string', 'Адрес посещённой страницы'),
                ('title', 'Заголовок', -1, 'string', 'Название страницы'),
                ('visit_count', 'Количество посещений', -1, 'int', 'Сколько раз страница посещалась'),
                ('typed', 'Введён вручную', -1, 'int', '1 — введён вручную, 0 — нет'),
                ('last_visit_date', 'Дата последнего визита', -1, 'string', 'Время последнего посещения'),
                ('profile_id', 'ID профиля', -1, 'int', 'Связанный профиль браузера')
            '''
        )

    @property
    def help(self) -> str:
        return f"{self.moduleName}: Извлечение истории браузера firefox из places.sqlite"

    def read(self) -> Generator[list[History], None, None]:
        """Считывает историю браузера из таблицы `moz_places`.

        Выполняет поэтапное чтение данных партиями по 500 записей
        и на каждой итерации генерирует список объектов `History`.

        Returns:
            Generator[list[History], None, None]: Генератор партий данных.

        Notes:
            Метка last_visit_date преобразуется из микросекунд в стандартный
            формат datetime через функцию SQLite.

        Raises:
            sqlite3.OperationalError: Если таблица `moz_places` отсутствует
                или повреждена. Ошибка логируется.
        """
        try:
            cursor = (self._dbReadInterface.Fetch(
                '''SELECT url, title, visit_count, typed,
                datetime(last_visit_date / 1000000, 'unixepoch') AS last_visit_date
                FROM moz_places''', commit_required=False
            ))
            i = 0
            while i < len(cursor):
                batch = cursor[i: i + 500]
                if not batch:
                    break
                i += 500
                yield [History(*row, profile_id=self._profile_id) for row in batch]
        except sqlite3.OperationalError:
            self._logInterface.Warn(
                type(self),
                f'{self._profile_id} не может быть считан (не активен)'
            )

    def write(self, butch: Iterable[tuple]) -> None:
        """Записывает партию записей истории в выходную базу данных.

        Args:
            butch (Iterable[tuple]): Итератор кортежей или структур History,
                подготовленных для записи.

        Returns:
            None

        Raises:
            Exception: Возможные ошибки записи логируются и не пробрасываются.
        """
        for row in butch:
            self._dbWriteInterface.ExecCommit(
                '''INSERT INTO Data (url, title, visit_count,
                typed, last_visit_date, profile_id)
                VALUES (?, ?, ?, ?, ?, ?)''',
                row
            )
        self._logInterface.Info(type(self), 'Группа записей успешно загружена')

    def execute(self) -> None:
        self.createDataTable()
        for batch in self.read():
            self.write(batch)
        self.createInfoTable(self.timestamp)
        self.createHeadersTables()
        self._dbWriteInterface.SaveSQLiteDatabaseFromRamToFile()

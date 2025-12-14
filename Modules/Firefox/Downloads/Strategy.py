"""Модуль реализаций стратегий извлечения данных Firefox.

Содержит класс `DownloadsStrategy`, отвечающий за чтение информации
о загрузках (`downloads`) из таблиц профиля Firefox и запись их в
выходную базу данных. Использует инфраструктуру StrategyABC.
"""

import sqlite3
from collections import namedtuple
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Iterable, Generator

from Modules.Firefox.interfaces.Strategy import StrategyABC, Metadata


# Именованный кортеж для удобства маппинга полей (tuple-поведение подходит для executemany)
Download = namedtuple("Download", "id place_id anno_attribute_id content profile_id")


class DownloadsStrategy(StrategyABC):
    """Стратегия чтения и записи сведений о загрузках из профиля Firefox.

    Стратегия предназначена для обработки значений из таблиц `moz_annos`
    и `moz_anno_attributes`, извлекая строки, связанные с загрузками
    (имя атрибута содержит подстроку `"downloads"`). Чтение выполняется
    партиями и предоставляет данные в виде генератора списков.

    Атрибуты:
        _logInterface: Интерфейс для записи логов.
        _dbReadInterface: Интерфейс чтения данных из БД Firefox.
        _dbWriteInterface: Интерфейс записи данных в выходную БД.
        _profile_id (int): Идентификатор обрабатываемого профиля.
    """

    def __init__(self, metadata: Metadata) -> None:
        """Инициализирует стратегию с необходимыми интерфейсами и параметрами.

        Args:
            metadata (Metadata): Набор интерфейсов и параметров,
                предоставляемый инфраструктурой выполнения стратегий.
        """
        self._logInterface = metadata.logInterface
        self.moduleName = "FirefoxDownloads"
        self.timestamp = self._timestamp(metadata.caseFolder)
        self._dbReadInterface = metadata.dbReadInterface
        self._dbWriteInterface = self._writeInterface(self.moduleName,metadata.logInterface,metadata.caseFolder)
        self._profile_id = metadata.profileId

    def createDataTable(self):
        """
               Создаёт таблицу 'downloads' для хранения загрузок Firefox
               и индекс по place_id.
               """
        self._dbWriteInterface.ExecCommit(
            '''CREATE TABLE downloads (id PRIMARY KEY, place_id INTEGER,
            anno_attribute_id INTEGER, content TEXT, profile_id INTEGER)'''
        )
        self._dbWriteInterface.ExecCommit('''CREATE INDEX idx_downloads_place_id on downloads (place_id)''')
        self._logInterface.Info(type(self), 'Таблица с загрузками создана')
        self._dbWriteInterface.SaveSQLiteDatabaseFromRamToFile()

    @property
    def help(self) -> str:
        return f"{self.moduleName}: Извлечение загрузок из places.sqlite"


    def read(self) -> Generator[list[Download], None, None]:
        """Читает данные о загрузках из таблиц Firefox партиями.

        Выполняет запрос к `moz_annos`, фильтруя записи по атрибутам,
        связанным с загрузками. Результат возвращается генератором:
        каждая итерация — список записей `Download`, включающий id профиля.

        Returns:
            Generator[list[Download], None, None]: Генератор партий данных.
                Партии имеют размер до 500 записей.

        Raises:
            sqlite3.OperationalError: Если нужные таблицы отсутствуют
                или база данных недоступна. Ошибка логируется и не пробрасывается.
        """
        try:
            cursor = self._dbReadInterface._cursor.execute(
                """SELECT moz_annos.id, moz_annos.place_id, moz_annos.anno_attribute_id, moz_annos.content
                   FROM moz_annos
                   WHERE moz_annos.anno_attribute_id IN (
                       SELECT id FROM moz_anno_attributes WHERE name LIKE '%downloads%')"""
            )

            while True:
                batch = cursor.fetchmany(500)
                if not batch:
                    break
                yield [Download(*row, profile_id=self._profile_id) for row in batch]

        except sqlite3.OperationalError as e:
            self._logInterface.Warn(
                type(self),
                f'Загрузки для профиля {self._profile_id} не могут быть считаны '
                f'(таблица отсутствует или БД не доступна): {e}'
            )

    def write(self, batch: Iterable[Download]) -> None:
        """Записывает партию загрузок в выходную базу данных.

        Args:
            batch (Iterable[Download]): Коллекция объектов `Download`,
                подготовленных к вставке.

        Returns:
            None

        Notes:
            Пустая партия пропускается. Запись выполняется через
            INSERT OR IGNORE для предотвращения дубликатов.

        Raises:
            Exception: Любая ошибка записи логируется, но не пробрасывается.
        """
        try:
            params = [tuple(item) for item in list(batch)]
            if not params:
                return

            self._dbWriteInterface._cursor.executemany(
                '''INSERT OR IGNORE INTO downloads (id, place_id, anno_attribute_id, content, profile_id)
                   VALUES (?, ?, ?, ?, ?)''',
                params
            )
            self._dbWriteInterface.Commit()
            self._logInterface.Info(type(self), f'Группа загрузок успешно загружена')
        except Exception as e:
            self._logInterface.Error(type(self), f'Ошибка при записи загрузок: {e}')

    def execute(self, executor: ThreadPoolExecutor) -> None:
        self.createDataTable()
        for batch in self.read():
            executor.submit(self.write,batch)
        self.createInfoTable(self.timestamp)
        self._dbWriteInterface.SaveSQLiteDatabaseFromRamToFile()

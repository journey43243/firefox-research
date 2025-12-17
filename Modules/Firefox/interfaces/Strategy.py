"""Базовые интерфейсы и структуры для стратегий обработки данных Firefox.

Содержит абстрактный базовый класс `StrategyABC`, определяющий единую
контрактную модель для всех стратегий чтения и записи данных Firefox,
а также структуру `Metadata`, включающую зависимости и параметры профиля.
"""
import pathlib
from abc import ABC, abstractmethod
from collections import namedtuple
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Generator, Iterable

from Common.Routines import SQLiteDatabaseInterface

# Метаданные, передаваемые стратегиям при инициализации
Metadata = namedtuple(
    'Metadata',
    'logInterface dbReadInterface caseFolder profileId profilePath'
)


class StrategyABC(ABC):
    """Абстрактный базовый класс стратегии чтения и записи данных.

    Стратегии, использующиеся в системе, должны реализовывать методы
    чтения данных (`read`), записи данных (`write`) и запуска (`execute`),
    который формирует асинхронные задачи на основе полученных батчей.

    Каждая дочерняя стратегия определяет собственный механизм
    извлечения и обработки данных, но интерфейс остаётся единым.
    """

    vendor: str = "LabFramework"
    moduleName: str | None = None
    _dbWriteInterface: SQLiteDatabaseInterface | None = None

    def _writeInterface(self, moduleName: str, logInterface, caseFolder: pathlib.Path) -> SQLiteDatabaseInterface:
        return SQLiteDatabaseInterface(str(caseFolder.joinpath(f"{moduleName}.sqlite")), logInterface, moduleName, True)

    def _timestamp(self, caseFolder: pathlib.Path) -> str:
        return caseFolder.parts[-1]

    @property
    @abstractmethod
    def help(self) -> str:
        pass

    @abstractmethod
    def createDataTable(self):
        pass

    def createInfoTable(self, timestamp: str) -> None:
        self._dbWriteInterface.ExecCommit(
            '''CREATE TABLE Info (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, value TEXT)'''
        )
        self._dbWriteInterface.ExecCommit(
            f'''INSERT INTO Info (key, value) VALUES ('Name', '{self.moduleName}'),
            ('Help', '{self.help}'),
            ('Timestamp', '{timestamp}'),
            ('Vendor', '{self.vendor}')
        ''')

    @abstractmethod
    def createHeadersTables(self):
        pass

    @abstractmethod
    def read(self) -> Generator[list | str, None, None]:
        """Извлекает данные из источника, возвращая их партиями.

        Returns:
            Generator[list | str, None, None]: Генератор, возвращающий
                либо список данных, либо строку состояния.

        Notes:
            Конкретные реализации могут выбирать формат данных,
            но обычно возвращают списки структурированных объектов.
        """
        pass

    @abstractmethod
    def write(self, butch: Iterable) -> None:
        pass

    @abstractmethod
    def execute(self) -> None:
        pass

"""Базовые интерфейсы и структуры для стратегий обработки данных Firefox.

Содержит абстрактный базовый класс `StrategyABC`, определяющий единую
контрактную модель для всех стратегий чтения и записи данных Firefox,
а также структуру `Metadata`, включающую зависимости и параметры профиля.
"""

from abc import ABC, abstractmethod
from asyncio import Task
from collections import namedtuple
from typing import Generator, Iterable

# Метаданные, передаваемые стратегиям при инициализации
Metadata = namedtuple(
    'Metadata',
    'logInterface dbReadInterface dbWriteInterface profileId profilePath'
)


class StrategyABC(ABC):
    """Абстрактный базовый класс стратегии чтения и записи данных.

    Стратегии, использующиеся в системе, должны реализовывать методы
    чтения данных (`read`), записи данных (`write`) и запуска (`execute`),
    который формирует асинхронные задачи на основе полученных батчей.

    Каждая дочерняя стратегия определяет собственный механизм
    извлечения и обработки данных, но интерфейс остаётся единым.
    """

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
    async def write(self, butch: Iterable) -> None:
        """Записывает партию данных в выходную систему.

        Args:
            butch (Iterable): Партия данных, подготовленная к записи.

        Returns:
            None

        Notes:
            Реализация должна сама вызывать commit (если требуется),
            а также логировать ошибки записи.
        """
        pass

    @abstractmethod
    async def execute(self, tasks: list[Task]) -> None:
        """Создаёт асинхронные задачи для запуска обработки данных.

        Args:
            tasks (list[Task]): Коллекция задач, в которую добавляются
                асинхронные операции записи данных.

        Returns:
            None

        Notes:
            Метод обычно вызывает read(), формирует батчи, и для каждого
            создаёт задачу write() через asyncio.create_task().
        """
        pass

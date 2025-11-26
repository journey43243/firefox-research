"""
Модуль абстрактного интерфейса стратегий извлечения

Этот модуль определяет абстрактный базовый класс и структуру данных
для всех стратегий извлечения данных из Firefox.

Все стратегии (профилей, истории, закладок и т.д.) должны наследоваться
от StrategyABC и переопределить три основных метода: read, write, execute.
"""

from abc import ABC, abstractmethod
from asyncio import Task
from collections import namedtuple
from typing import Generator, Iterable

# Именованный кортеж для передачи метаинформации профиля между компонентами
Metadata = namedtuple('Metadata',
                      'logInterface dbReadInterface dbWriteInterface profileId profilePath')
"""
Структура метаинформации профиля Firefox.

Содержит всю необходимую информацию для работы стратегии с конкретным профилем.

Поля:
    logInterface: Интерфейс логирования
    dbReadInterface: Подключение для чтения из places.sqlite профиля
    dbWriteInterface: Подключение для записи в выходную БД
    profileId: Уникальный ID профиля в таблице profiles
    profilePath: Полный путь к папке профиля Firefox
"""

# ################################################################
class StrategyABC(ABC):
    """
    Абстрактный базовый класс для всех стратегий извлечения данных.
    
    Определяет интерфейс, которому должны соответствовать все стратегии
    (Profiles, History, Bookmarks, Downloads, Extensions, Passwords).
    
    Каждая стратегия отвечает за извлечение одного типа данных из Firefox.
    """

    @abstractmethod
    def read(self) -> Generator[list | str, None, None]:
        """
        Читает данные из профиля Firefox.
        
        Это один из трёх основных методов стратегии.
        Должен быть генератором, возвращающим батчи данных.
        
        Yields:
            Батчи данных (списки или строки) для записи в БД
        """
        pass

    @abstractmethod
    async def write(self, butch: Iterable) -> None:
        """
        Записывает батч данных в выходную БД.
        
        Это один из трёх основных методов стратегии.
        Асинхронный метод для оптимизации при работе с БД.
        
        Args:
            butch: Итерируемая коллекция данных для записи
        """
        pass

    @abstractmethod
    async def execute(self, tasks: list[Task]) -> None:
        """
        Главный метод выполнения стратегии.
        
        Это один из трёх основных методов стратегии.
        Координирует процесс чтения и записи данных, управляет асинхронными задачами.
        
        Args:
            tasks: Список асинхронных задач для добавления новых задач
        """
        pass
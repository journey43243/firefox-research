"""
Модуль стратегии извлечения профилей Firefox

Этот модуль реализует стратегию для чтения информации о профилях Firefox
из файла profiles.ini и загрузку их в базу данных.

Профили хранятся в файле:
%APPDATA%\Mozilla\Firefox\profiles.ini
"""

import asyncio
from asyncio import Task
from typing import Generator

from Common.Routines import FileContentReader
from Modules.Firefox.interfaces.Strategy import StrategyABC

import os

class PathMixin:
    """Миксин для доступа к стандартному пути Firefox папки."""
    __folderPath = f'{os.getenv("APPDATA")}\\Mozilla\\Firefox'

    @property
    def folderPath(self):
        """Возвращает путь к папке Firefox в APPDATA."""
        return self.__folderPath

# ################################################################
class ProfilesStrategy(StrategyABC, PathMixin):
    """
    Стратегия для извлечения профилей Firefox.
    
    Читает список профилей из файла profiles.ini,  парсит их пути
    и записывает информацию в таблицу profiles выходной БД.
    
    Каждый профиль представляет отдельную конфигурацию браузера с
    собственной историей, закладками, расширениями и т.д.
    
    Атрибуты:
        _fileReader: Читатель содержимого файлов
        _logInterface: Интерфейс логирования
        _dbWriteInterface: Интерфейс для записи в БД
        __fileName: Имя файла profiles.ini
        __folderPath: Путь к папке Firefox
    """

    __fileName = 'profiles.ini'

    def __init__(self, logInterface, dbWriteInterface) -> None:
        """
        Инициализирует стратегию профилей.
        
        Args:
            logInterface: Интерфейс логирования
            dbWriteInterface: Интерфейс подключения к БД для записи
        """
        self._fileReader = FileContentReader()
        self._logInterface = logInterface
        self._dbWriteInterface = dbWriteInterface
        super().__init__()

    @property
    def fileName(self):
        """Возвращает имя файла profiles.ini."""
        return self.__fileName

    def read(self) -> Generator[str, None, None]:
        """
        Читает информацию о профилях из файла profiles.ini.
        
        Парсит файл в формате INI и извлекает пути профилей.
        Формирует полные пути до каждого профиля.
        
        Yields:
            Полный путь к папке каждого профиля
        """
        _, _, content = self._fileReader.GetTextFileContent(self.folderPath, self.fileName, includeTimestamps=False)
        profilesCnt = 0
        for _, row in content.items():
            if 'Path' in row:
                # Извлечь путь из строки "Path=Profiles/..."
                row = row[5:].replace('\n', '').replace('/', '\\')
                profilesCnt += 1
                yield self.folderPath + '\\' + row
        self._logInterface.Info(type(self), f"Считано {profilesCnt} профилей")

    async def write(self, butch: list[str]) -> None:
        """
        Записывает информацию о профилях в таблицу profiles.
        
        Args:
            butch: Список путей профилей для записи
        """
        for record in butch:
            self._dbWriteInterface.ExecCommit(
                '''INSERT INTO profiles (path) VALUES (?)''', (record, )
            )
        self._logInterface.Info(type(self), 'Все профили загружены в таблицу')

    async def execute(self, tasks: list[Task]) -> None:
        """
        Главный метод выполнения стратегии.
        
        Читает все профили и запускает асинхронную запись в БД.
        
        Args:
            tasks: Список асинхронных задач для добавления новой задачи
        """
        profiles = [profile for profile in self.read()]
        task = asyncio.create_task(self.write(profiles))
        tasks.append(task)
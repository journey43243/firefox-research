"""
Модуль для извлечения путей профилей Firefox.

Реализует стратегию чтения файла profiles.ini, расположенного в каталоге Firefox,
и выгружает пути профилей в базу данных. Используется в составе системы
извлечения данных браузера.
"""
import pathlib
from concurrent.futures import ThreadPoolExecutor
from typing import Generator

from Common.Routines import FileContentReader, SQLiteDatabaseInterface
from Modules.Firefox.interfaces.Strategy import StrategyABC

import os


class PathMixin:
    """
    Миксин, предоставляющий путь к каталогу Firefox внутри APPDATA.

    Атрибуты:
        folderPath (str): Абсолютный путь к каталогу Firefox, формируемый
        на основе переменной окружения APPDATA.
    """

    __folderPath = f"{os.getenv('APPDATA')}\\Mozilla\\Firefox"

    @property
    def folderPath(self):
        """Возвращает путь к каталогу Firefox."""
        return self.__folderPath


class ProfilesStrategy(StrategyABC, PathMixin):
    """
    Стратегия чтения списка профилей Firefox из файла profiles.ini.

    Класс реализует интерфейс StrategyABC и использует файл profiles.ini
    для извлечения путей профилей Firefox, после чего записывает их
    в базу данных.

    Атрибуты:
        _fileReader (FileContentReader): Интерфейс чтения текстовых файлов.
        _logInterface: Интерфейс логирования.
        _dbWriteInterface: Интерфейс записи в базу данных.
        __fileName (str): Имя файла, из которого извлекаются профили.
    """

    __fileName = 'profiles.ini'

    def __init__(self, logInterface, caseFolder) -> None:
        """
        Инициализирует стратегию профилей.

        Args:
            logInterface: Объект логирования.
            dbWriteInterface: Интерфейс записи в базу данных.
        """
        self._fileReader = FileContentReader()
        self._logInterface = logInterface
        self.moduleName = "FirefoxProfiles"
        self._dbWriteInterface = self._writeInterface(self.moduleName, logInterface, caseFolder)
        self.timestamp = self._timestamp(caseFolder)
        super().__init__()
        self.createDataTable()

    def createDataTable(self):
        """
        Создаёт базу 'profiles' для хранения путей профилей Firefox
        и индекс для ускоренного поиска по пути.
        """
        self._dbWriteInterface.ExecCommit(
            '''CREATE TABLE Data (ID INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT)'''
        )
        self._dbWriteInterface.ExecCommit('''CREATE INDEX idx_profiles_path on profiles (path)''')
        self._logInterface.Info(type(self), 'Таблица с профилями создана.')

    def createHeadersTables(self):
        self._dbWriteInterface.ExecCommit(
            '''CREATE TABLE Headers (ID INTEGER PRIMARY KEY AUTOINCREMENT, Name TEXT, Label TEXT, Width INTEGER, DataType TEXT, Comment TEXT)'''
        )
        self._dbWriteInterface.ExecCommit(
            '''INSERT INTO Headers (Name, Label, Width, DataType, Comment) VALUES 
            ('path', 'Путь до профиля', -1, 'string', 'Путь до профиля')'''
        )

    @property
    def help(self) -> str:
        return f"{self.moduleName}: Извлечение профилей хранящихся в profiles.ini"

    @property
    def fileName(self):
        """Возвращает имя файла с профилями Firefox."""
        return self.__fileName

    def read(self) -> Generator[str, None, None]:
        """
        Читает файл profiles.ini и генерирует пути к профилям Firefox.

        Returns:
            Generator[str, None, None]: Генератор путей к профилям.

        Поведение:
            — Извлекает содержимое файла profiles.ini.
            — Находит строки, содержащие ключ 'Path'.
            — Формирует абсолютные пути профилей.
            — Генерирует один путь за раз.
        """
        _, _, content = self._fileReader.GetTextFileContent(
            self.folderPath, self.fileName, includeTimestamps=False
        )
        profilesCnt = 0
        for _, row in content.items():
            if 'Path' in row:
                row = row[5:].replace('\n', '').replace('/', '\\')
                profilesCnt += 1
                yield self.folderPath + '\\' + row
        self._logInterface.Info(type(self), f"Считано {profilesCnt} профилей")

    def write(self, butch: list[str]) -> None:
        """
        Записывает полученные пути профилей в таблицу базы данных.

        Args:
            butch (list[str]): Список путей профилей, считанных ранее.
        """
        for record in butch:
            self._dbWriteInterface.ExecCommit(
                '''INSERT INTO Data (path) VALUES (?)''', (record,)
            )
        self._logInterface.Info(type(self), 'Все профили загружены в таблицу')

    def execute(self) -> None:
        profiles = [profile for profile in self.read()]
        self.write(profiles)
        self.createInfoTable(self.timestamp)
        self.createHeadersTables()
        self._dbWriteInterface.SaveSQLiteDatabaseFromRamToFile()

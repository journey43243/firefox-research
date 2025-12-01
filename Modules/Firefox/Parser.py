"""
Модуль запуска парсинга данных Firefox для конкретного кейса.

Содержит класс Parser, который инициализирует стратегии извлечения данных
из профилей Firefox (история, пароли, закладки, загрузки, расширения),
запускает их асинхронно и сохраняет результаты в результирующую базу данных.
"""

import asyncio

from Common.Routines import SQLiteDatabaseInterface
from Modules.Firefox.Profiles.Strategy import ProfilesStrategy
from Modules.Firefox.interfaces.Strategy import StrategyABC, Metadata
from Modules.Firefox.sqliteStarter import SQLiteStarter
from Modules.Firefox.History.Strategy import HistoryStrategy
from Modules.Firefox.Passwords.Strategy import PasswordStrategy
from Modules.Firefox.Bookmarks.Strategy import BookmarksStrategy
from Modules.Firefox.Downloads.Strategy import DownloadsStrategy
from Modules.Firefox.Extensions.Strategy import ExtensionsStrategy
from Modules.Firefox.Favicons.Strategy import FaviconsStrategy

class Parser:
    """
    Класс Parser управляет процессом извлечения данных Firefox.

    Инициализирует стратегии для разных типов данных (профили, история,
    пароли, закладки, загрузки, расширения) и выполняет их асинхронно.

    Атрибуты:
        logInterface: Интерфейс логирования.
        caseFolder (str): Путь к каталогу кейса.
        caseName (str): Название кейса.
        dbInterface: Интерфейс для работы с результирующей базой данных.
        outputFileName (str): Имя результирующего файла БД.
        outputWriter: Интерфейс записи данных.
        moduleName (str): Название модуля (Firefox).
        dbWritePath (str): Путь к результирующей базе данных.
    """

    def __init__(self, parameters: dict) -> None:
        """
        Инициализирует объект Parser с параметрами кейса.

        Parameters
        ----------
        parameters : dict
            Словарь с параметрами:
                LOG: интерфейс логирования,
                CASEFOLDER: каталог кейса,
                CASENAME: имя кейса,
                DBCONNECTION: интерфейс БД,
                OUTPUTFILENAME: имя выходного файла БД,
                OUTPUTWRITER: объект для записи данных,
                MODULENAME: название модуля.
        """
        self.logInterface = parameters['LOG']
        self.caseFolder = parameters['CASEFOLDER']
        self.caseName = parameters['CASENAME']
        self.dbInterface = parameters['DBCONNECTION']
        self.outputFileName = parameters['OUTPUTFILENAME']
        self.outputWriter = parameters['OUTPUTWRITER']
        self.moduleName = parameters['MODULENAME']
        self.dbWritePath = f'{self.caseFolder}/{self.caseName}/{self.outputFileName}'

    async def Start(self):
        """
        Основной метод запуска парсинга Firefox.

        Поведение:
            1. Проверяет соединение с результирующей базой данных.
            2. Создаёт все необходимые таблицы через SQLiteStarter.
            3. Считывает пути профилей Firefox через ProfilesStrategy.
            4. Для каждого профиля создаёт интерфейс чтения БД.
            5. Формирует объект Metadata для каждой стратегии.
            6. Асинхронно запускает стратегии History, Passwords, Bookmarks,
               Downloads и Extensions.
            7. После завершения всех задач сохраняет БД в файл.

        Returns
        -------
        dict
            Словарь с ключом moduleName и значением имени результирующей БД.
        """
        if not self.dbInterface.IsConnected():
            return

        HELP_TEXT = self.moduleName + ' Firefox Researching'
        sqlCreator = SQLiteStarter(self.logInterface, self.dbInterface)
        sqlCreator.createAllTables()
    
        profilesStrategy = ProfilesStrategy(self.logInterface, self.dbInterface)
        profiles = [profile for profile in profilesStrategy.read()]
        tasks = []
        await profilesStrategy.execute(tasks)
        if tasks: 
            await asyncio.wait(tasks)

        for id, profilePath in enumerate(profiles):
            dbReadIntreface = SQLiteDatabaseInterface(
                profilePath + r'\places.sqlite', self.logInterface, 'Firefox', False
            )
            
            dbFaviconsReadInterface = SQLiteDatabaseInterface(
                profilePath + r'\favicons.sqlite', self.logInterface, 'Firefox', False
            )

            favicons_metadata = Metadata(
                self.logInterface, dbFaviconsReadInterface, self.dbInterface, id + 1, profilePath
            )
            
            metadata = Metadata(
                self.logInterface, dbReadIntreface, self.dbInterface, id + 1, profilePath
            )
            await HistoryStrategy(metadata).execute(tasks)
            await asyncio.wait(tasks)

            for strategy in StrategyABC.__subclasses__():
                if strategy.__name__ in ['HistoryStrategy', 'ProfilesStrategy']:
                    continue
                elif strategy.__name__ == 'FaviconsStrategy':
                    await strategy(favicons_metadata).execute(tasks)
                else:
                    await strategy(metadata).execute(tasks)
                    self.logInterface.Info(type(strategy), 'отработала успешно')

        if tasks: 
            await asyncio.wait(tasks)

        self.dbInterface.SaveSQLiteDatabaseFromRamToFile()
        return {self.moduleName: self.outputWriter.GetDBName()}

"""
Модуль парсера Firefox

Этот модуль является главным обработчиком для извлечения данных из Firefox.
Координирует работу всех стратегий извлечения (профилей, истории, закладок и т.д.)
и управляет процессом загрузки данных в выходную БД.

Процесс работы:
1. Создание таблиц в выходной БД
2. Чтение и загрузка профилей Firefox
3. Для каждого профиля:
   - Открытие places.sqlite
   - Запуск всех стратегий (история, закладки, загрузки и т.д.)
   - Загрузка данных в БД
4. Сохранение БД из памяти на диск (если использовалась RAM обработка)
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

# ################################################################
class Parser:
    """
    Главный парсер для обработки данных Firefox.
    
    Этот класс управляет процессом извлечения данных из множества профилей
    Firefox, включая историю, закладки, загрузки, расширения и пароли.
    
    Использует асинхронную обработку для оптимизации производительности
    при работе с несколькими профилями.
    
    Атрибуты:
        logInterface: Интерфейс логирования
        caseFolder: Папка для сохранения результатов
        caseName: Имя текущего кейса (расследования)
        dbInterface: Интерфейс для подключения к выходной БД
        outputFileName: Имя файла результатов
        outputWriter: Писатель для вывода в БД
        moduleName: Имя модуля ("Firefox")
        dbWritePath: Полный путь к файлу БД результатов
    """

    def __init__(self, parameters: dict) -> None:
        """
        Инициализирует парсер Firefox.
        
        Args:
            parameters: Словарь параметров модуля:
                - LOG: Интерфейс логирования
                - CASEFOLDER: Папка результатов
                - CASENAME: Имя кейса
                - DBCONNECTION: Подключение к выходной БД
                - OUTPUTFILENAME: Имя файла результатов
                - OUTPUTWRITER: Писатель для БД
                - MODULENAME: Имя модуля
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
        Главный метод для запуска обработки данных Firefox.
        
        Процесс:
        1. Проверяет подключение к БД
        2. Создаёт все необходимые таблицы
        3. Читает список профилей Firefox
        4. Для каждого профиля запускает все стратегии извлечения
        5. Сохраняет данные из памяти на диск
        
        Returns:
            Словарь с результатами ({moduleName: outputFileName}) или None при ошибке
        """
        if not self.dbInterface.IsConnected():
            return

        HELP_TEXT = self.moduleName + ' Firefox Researching'
        sqlCreator = SQLiteStarter(self.logInterface, self.dbInterface)
        sqlCreator.createAllTables()

        # Загрузить профили Firefox
        profilesStrategy = ProfilesStrategy(self.logInterface, self.dbInterface)
        profiles = [profile for profile in profilesStrategy.read()]
        tasks = []
        await profilesStrategy.execute(tasks)
        if tasks: 
            await asyncio.wait(tasks)

        # Для каждого профиля запустить обработку данных
        for id, profilePath in enumerate(profiles):
            # Открыть БД places.sqlite этого профиля
            dbReadIntreface = SQLiteDatabaseInterface(profilePath + r'\places.sqlite', self.logInterface,
                                                     'Firefox', False)
            
            # Создать метаинформацию профиля
            metadata = Metadata(self.logInterface, dbReadIntreface, self.dbInterface, id + 1, profilePath)
            
            # Запустить стратегию истории (основная)
            await HistoryStrategy(metadata).execute(tasks)
            await asyncio.wait(tasks)
            
            # Запустить все остальные стратегии (они наследуют StrategyABC)
            for strategy in StrategyABC.__subclasses__():
                if strategy.__name__ in ['HistoryStrategy', 'ProfilesStrategy']:
                    continue
                else:
                    await strategy(metadata).execute(tasks)
                    self.logInterface.Info(type(strategy), 'отработала успешно')

        if tasks: 
            await asyncio.wait(tasks)

        # Сохранить БД если она была обработана в памяти
        self.dbInterface.SaveSQLiteDatabaseFromRamToFile()
        return {self.moduleName: self.outputWriter.GetDBName()}
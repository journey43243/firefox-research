"""
Модуль запуска парсинга данных Firefox для конкретного кейса.

Содержит класс Parser, который инициализирует стратегии извлечения данных
из профилей Firefox (история, пароли, закладки, загрузки, расширения),
запускает их асинхронно и сохраняет результаты в результирующую базу данных.
"""
import pathlib

from Common.Routines import SQLiteDatabaseInterface
from Modules.Firefox.Profiles.Strategy import ProfilesStrategy
from Modules.Firefox.interfaces.Strategy import StrategyABC, Metadata
from Modules.Firefox.History.Strategy import HistoryStrategy
from Modules.Firefox.Passwords.Strategy import PasswordStrategy
from Modules.Firefox.Bookmarks.Strategy import BookmarksStrategy
from Modules.Firefox.Downloads.Strategy import DownloadsStrategy
from Modules.Firefox.Extensions.Strategy import ExtensionsStrategy
from concurrent.futures import ThreadPoolExecutor


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

        profilesStrategy = ProfilesStrategy(self.logInterface, pathlib.Path(self.caseFolder).joinpath(self.caseName))
        profiles = [profile for profile in profilesStrategy.read()]

        with ThreadPoolExecutor(max_workers=5) as executor:
            profilesStrategy.execute(executor)
            for id, profilePath in enumerate(profiles):
                dbReadIntreface = SQLiteDatabaseInterface(profilePath + r'\places.sqlite', self.logInterface,
                                                          'Firefox', False)
                metadata = Metadata(self.logInterface, dbReadIntreface, pathlib.Path(self.caseFolder).joinpath(self.caseName), id + 1, profilePath)
                HistoryStrategy(metadata).execute(executor)
                for strategy in StrategyABC.__subclasses__():
                    if strategy.__name__ in ['HistoryStrategy', 'ProfilesStrategy']:
                        continue
                    else:
                        strategy(metadata).execute(executor)
                        self.logInterface.Info(type(strategy), 'отработала успешно')
            executor.shutdown(wait=True)
        pathlib.Path(pathlib.Path(self.caseFolder).joinpath(self.caseName).joinpath(self.outputWriter.GetDBName())).unlink(missing_ok=True)
        return {self.moduleName: self.outputWriter.GetDBName()}

import asyncio, time

from Common.Routines import SQLiteDatabaseInterface
from Modules.Firefox.Profiles.Strategy import ProfilesStrategy
from Modules.Firefox.interfaces.Strategy import StrategyABC, Metadata
from Modules.Firefox.sqliteStarter import SQLiteStarter
from Modules.Firefox.History.Strategy import HistoryStrategy
from Modules.Firefox.Passwords.Strategy import PasswordStrategy
from Modules.Firefox.Bookmarks.Strategy import BookmarksStrategy
from Modules.Firefox.Downloads.Strategy import DownloadsStrategy
from Modules.Firefox.Extensions.Strategy import ExtensionsStrategy

from Common.timing_decorators import time_strategy_class

# Декорируем все стратегии одной строкой
@time_strategy_class
class TimedHistoryStrategy(HistoryStrategy):
    pass

@time_strategy_class
class TimedPasswordStrategy(PasswordStrategy):
    pass

@time_strategy_class
class TimedBookmarksStrategy(BookmarksStrategy):
    pass

@time_strategy_class
class TimedDownloadsStrategy(DownloadsStrategy):
    pass

@time_strategy_class
class TimedExtensionsStrategy(ExtensionsStrategy):
    pass

@time_strategy_class
class TimedProfilesStrategy(ProfilesStrategy):
    pass

class SyncParser:

    def __init__(self, parameters: dict) -> None:
        self.logInterface = parameters['LOG']
        self.caseFolder = parameters['CASEFOLDER']
        self.caseName = parameters['CASENAME']
        self.dbInterface = parameters['DBCONNECTION']
        self.outputFileName = parameters['OUTPUTFILENAME']
        self.outputWriter = parameters['OUTPUTWRITER']
        self.moduleName = parameters['MODULENAME']
        self.dbWritePath = f'{self.caseFolder}/{self.caseName}/{self.outputFileName}'

    def Start(self):
        if not self.dbInterface.IsConnected():
            print("Ошибка: нет подключения к БД")
            return

        print("=== ЗАПУСК СИНХРОННОЙ ВЕРСИИ ПАРСЕРА FIREFOX ===")
        total_start_time = time.time()

        try:
            sqlCreator = SQLiteStarter(self.logInterface, self.dbInterface)
            sqlCreator.createAllTables()

            # Используем декорированные стратегии
            profiles_strategy = TimedProfilesStrategy(self.logInterface, self.dbInterface)
            profiles = [profile for profile in profiles_strategy.read()]
            self.execute_strategy_sync(profiles_strategy, "ProfilesStrategy")

            for id, profilePath in enumerate(profiles):
                print(f"\n--- Обработка профиля {id + 1}: {profilePath} ---")

                try:
                    dbReadInterface = SQLiteDatabaseInterface(
                        profilePath + r'\places.sqlite',
                        self.logInterface,
                        'Firefox',
                        False
                    )

                    metadata = Metadata(
                        self.logInterface,
                        dbReadInterface,
                        self.dbInterface,
                        id + 1,
                        profilePath
                    )

                    # Используем декорированные стратегии
                    strategies = [
                        (TimedHistoryStrategy(metadata), "HistoryStrategy"),
                        (TimedPasswordStrategy(metadata), "PasswordStrategy"),
                        (TimedBookmarksStrategy(metadata), "BookmarksStrategy"),
                        (TimedDownloadsStrategy(metadata), "DownloadsStrategy"),
                        (TimedExtensionsStrategy(metadata), "ExtensionsStrategy")
                    ]

                    for strategy, name in strategies:
                        self.execute_strategy_sync(strategy, f"{name}_profile_{id +1}")

                except Exception as e:
                    print(f"Ошибка при обработке профиля {profilePath}: {e}")
                    continue

            self.dbInterface.SaveSQLiteDatabaseFromRamToFile()

        except Exception as e:
            print(f"Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()

        total_end_time = time.time()
        total_execution_time = total_end_time - total_start_time

        print(f"\n=== ОБЩЕЕ ВРЕМЯ ВЫПОЛНЕНИЯ: {total_execution_time:.4f} секунд ===")

        return {self.moduleName: self.outputWriter.GetDBName()}

@time_strategy_class
class TimedSyncParser(SyncParser): pass
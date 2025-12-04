import asyncio, time
import os
from datetime import datetime

from Common.Routines import SQLiteDatabaseInterface
from Modules.Firefox.Profiles.Strategy import ProfilesStrategy
from Modules.Firefox.interfaces.Strategy import StrategyABC, Metadata
from Modules.Firefox.sqliteStarter import SQLiteStarter
from Modules.Firefox.History.Strategy import HistoryStrategy
from Modules.Firefox.Passwords.Strategy import PasswordStrategy
from Modules.Firefox.Bookmarks.Strategy import BookmarksStrategy
from Modules.Firefox.Downloads.Strategy import DownloadsStrategy
from Modules.Firefox.Extensions.Strategy import ExtensionsStrategy


class Parser:
    def __init__(self, parameters: dict) -> None:
        self.logInterface = parameters['LOG']
        self.caseFolder = parameters['CASEFOLDER']
        self.caseName = parameters['CASENAME']
        self.dbInterface = parameters['DBCONNECTION']
        self.outputFileName = parameters['OUTPUTFILENAME']
        self.outputWriter = parameters['OUTPUTWRITER']
        self.moduleName = parameters['MODULENAME']
        self.dbWritePath = f'{self.caseFolder}/{self.caseName}/{self.outputFileName}'
        self.now = os.environ.get('PROGRAM_TIME_FILENAME') or str(datetime.now()).split('.')[0].replace(':', '_')
        self.batch_stats = {}

    def _log_time(self, module_name: str, elapsed_time: float, batch_info: dict = None, error: str = None):
        """Записывает время выполнения в файл"""
        with open(f"Logs/{self.now}_time.txt", "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 50}\n")
            if error:
                f.write(f"Модуль: {module_name} (ОШИБКА)\n")
                f.write(f"Время до ошибки: {elapsed_time:.4f} секунд\n")
                f.write(f"Ошибка: {error}\n")
            else:
                f.write(f"Модуль: {module_name}\n")
                f.write(f"Время выполнения: {elapsed_time:.4f} секунд\n")

                # Добавляем информацию о батчах, если есть
                if batch_info and 'batches' in batch_info:
                    batches = batch_info['batches']
                    if batches:
                        f.write(f"\nАнализ батчей:\n")
                        f.write(f"  Количество батчей: {len(batches)}\n")
                        f.write(f"  Общее количество записей: {sum(batches)}\n")
                        f.write(f"  Средний размер батча: {sum(batches) / len(batches):.1f}\n")
                        f.write(f"  Минимальный размер: {min(batches)}\n")
                        f.write(f"  Максимальный размер: {max(batches)}\n")

                        # Анализ эффективности
                        if len(batches) > 1:
                            avg_time_per_record = elapsed_time / sum(batches)
                            f.write(f"  Среднее время на запись: {avg_time_per_record:.6f} сек/запись\n")

            f.write(f"Дата: {time.ctime()}\n")

    async def Start(self):
        if not self.dbInterface.IsConnected():
            return

        HELP_TEXT = self.moduleName + ' Firefox Researching'
        sqlCreator = SQLiteStarter(self.logInterface, self.dbInterface)
        sqlCreator.createAllTables()

        start = time.time()
        profilesStrategy = ProfilesStrategy(self.logInterface, self.dbInterface)
        profiles = [profile for profile in profilesStrategy.read()]
        profilesStrategy.execute()
        elapsed = time.time() - start
        print(f"[ProfilesStrategy] Время: {elapsed:.4f} сек")
        self._log_time('ProfilesStrategy', elapsed)

        for id, profilePath in enumerate(profiles):
            dbReadIntreface = SQLiteDatabaseInterface(profilePath + r'\places.sqlite', self.logInterface,
                                                      'Firefox', False)
            metadata = Metadata(self.logInterface, dbReadIntreface, self.dbInterface, id + 1, profilePath)

            start = time.time()
            HistoryStrategy(metadata).execute()
            elapsed = time.time() - start
            print(f"[HistoryStrategy] Время: {elapsed:.4f} сек")
            self._log_time('HistoryStrategy', elapsed)

            for strategy in StrategyABC.__subclasses__():
                if strategy.__name__ in ['HistoryStrategy', 'ProfilesStrategy']:
                    continue
                try:
                    # Создаем экземпляр стратегии с правильным конструктором
                    strategy_instance = strategy(metadata)
                    strategy_name = strategy.__name__

                    # Для стратегий с read() методом собираем статистику батчей
                    if hasattr(strategy_instance, 'read'):
                        start = time.time()
                        batch_sizes = []

                        # Читаем и считаем размеры батчей
                        for batch in strategy_instance.read():
                            if batch:
                                batch_sizes.append(len(batch))

                        # Выполняем стратегию
                        strategy_instance.execute()
                        elapsed = time.time() - start

                        batch_info = {'batches': batch_sizes} if batch_sizes else None

                        print(f"[{strategy_name}] Время: {elapsed:.4f} сек, "
                              f"Батчей: {len(batch_sizes)}, Записей: {sum(batch_sizes)}")

                        self._log_time(strategy_name, elapsed, batch_info)
                    else:
                        start = time.time()
                        strategy(metadata).execute()
                        elapsed = time.time() - start
                        print(f"[{strategy.__name__}] Время: {elapsed:.4f} сек")
                        self._log_time(strategy.__name__, elapsed)
                except Exception as e:
                    elapsed = time.time() - start
                    print(f"[{strategy_name}] ОШИБКА: {e}")
                    self._log_time(strategy_name, elapsed, error=str(e))
                    continue

                self.logInterface.Info(type(strategy), 'отработала успешно')
        self.dbInterface.SaveSQLiteDatabaseFromRamToFile()
        return {self.moduleName: self.outputWriter.GetDBName()}
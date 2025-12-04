import time
import os
import asyncio
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from Common.Routines import SQLiteDatabaseInterface
from Modules.Firefox.Profiles.Strategy import ProfilesStrategy
from Modules.Firefox.interfaces.Strategy import StrategyABC, Metadata
from Modules.Firefox.sqliteStarter import SQLiteStarter
from Modules.Firefox.History.Strategy import HistoryStrategy
import statistics


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
        self.strategy_stats = {}
        self.thread_pool_size = 5

    def _log_time(self, module_name: str, elapsed_time: float, thread_pool_size: int = None,
                  batch_info: dict = None, error: str = None):
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

                if thread_pool_size:
                    f.write(f"Размер пула потоков: {thread_pool_size}\n")

                # Добавляем информацию о батчах, если есть
                if batch_info and 'batches' in batch_info:
                    batches = batch_info['batches']
                    if batches:
                        f.write(f"\nАнализ батчей:\n")
                        f.write(f"  Количество батчей: {len(batches)}\n")
                        f.write(f"  Общее количество записей: {sum(batches)}\n")
                        if len(batches) > 1:
                            f.write(f"  Средний размер батча: {statistics.mean(batches):.1f}\n")
                            f.write(f"  Минимальный размер: {min(batches)}\n")
                            f.write(f"  Максимальный размер: {max(batches)}\n")

                            # Анализ эффективности
                            avg_time_per_record = elapsed_time / sum(batches) if sum(batches) > 0 else 0
                            f.write(f"  Среднее время на запись: {avg_time_per_record:.6f} сек/запись\n")

            f.write(f"Дата: {time.ctime()}\n")

    def _run_async_in_thread(self, async_func, *args, **kwargs):
        """Запускает асинхронную функцию в отдельном потоке с event loop"""
        try:
            # Создаем новый event loop для этого потока
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Запускаем асинхронную функцию
                result = loop.run_until_complete(async_func(*args, **kwargs))
                return result
            finally:
                loop.close()
        except RuntimeError:
            # Если уже есть event loop в этом потоке
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(async_func(*args, **kwargs))

    async def Start(self):
        if not self.dbInterface.IsConnected():
            return

        HELP_TEXT = self.moduleName + ' Firefox Researching'
        sqlCreator = SQLiteStarter(self.logInterface, self.dbInterface)
        sqlCreator.createAllTables()

        profilesStrategy = ProfilesStrategy(self.logInterface, self.dbInterface)
        profiles = [profile for profile in profilesStrategy.read()]

        with ThreadPoolExecutor(max_workers=self.thread_pool_size) as executor:
            # ProfilesStrategy - проверяем, асинхронная ли она
            start = time.time()
            if asyncio.iscoroutinefunction(profilesStrategy.execute):
                # Если асинхронная, запускаем в потоке
                future = executor.submit(self._run_async_in_thread, profilesStrategy.execute, executor)
                future.result()
            else:
                # Если синхронная, запускаем напрямую
                profilesStrategy.execute(executor)
            elapsed = time.time() - start
            print(f"[ProfilesStrategy] Время: {elapsed:.4f} сек, Потоков: {self.thread_pool_size}")
            self._log_time('ProfilesStrategy', elapsed, self.thread_pool_size)
            self.strategy_stats['ProfilesStrategy'] = {
                'time': elapsed,
                'thread_pool_size': self.thread_pool_size
            }

            for id, profilePath in enumerate(profiles):
                dbReadInterface = SQLiteDatabaseInterface(profilePath + r'\places.sqlite', self.logInterface,
                                                          'Firefox', False)
                metadata = Metadata(self.logInterface, dbReadInterface, self.dbInterface, id + 1, profilePath)

                # HistoryStrategy
                start = time.time()
                if asyncio.iscoroutinefunction(HistoryStrategy.execute):
                    history_instance = HistoryStrategy(metadata)
                    future = executor.submit(self._run_async_in_thread, history_instance.execute, executor)
                    future.result()
                else:
                    HistoryStrategy(metadata).execute(executor)
                elapsed = time.time() - start
                print(f"[HistoryStrategy] Время: {elapsed:.4f} сек, Потоков: {self.thread_pool_size}")
                self._log_time('HistoryStrategy', elapsed, self.thread_pool_size)
                self.strategy_stats['HistoryStrategy'] = {
                    'time': elapsed,
                    'thread_pool_size': self.thread_pool_size
                }

                for strategy_class in StrategyABC.__subclasses__():
                    if strategy_class.__name__ in ['HistoryStrategy', 'ProfilesStrategy']:
                        continue

                    strategy_name = strategy_class.__name__
                    try:
                        # Создаем экземпляр стратегии
                        strategy_instance = strategy_class(metadata)

                        # Собираем статистику батчей
                        batch_sizes = []
                        if hasattr(strategy_instance, 'read'):
                            for batch in strategy_instance.read():
                                if batch:
                                    batch_sizes.append(len(batch))

                        # Выполняем стратегию с проверкой на асинхронность
                        start = time.time()

                        if asyncio.iscoroutinefunction(strategy_instance.execute):
                            # Для асинхронных стратегий запускаем в отдельном потоке
                            future = executor.submit(self._run_async_in_thread, strategy_instance.execute, executor)
                            future.result()
                        else:
                            # Для синхронных стратегий
                            strategy_instance.execute(executor)

                        elapsed = time.time() - start

                        batch_info = {'batches': batch_sizes} if batch_sizes else None

                        print(f"[{strategy_name}] Время: {elapsed:.4f} сек, "
                              f"Потоков: {self.thread_pool_size}, "
                              f"Батчей: {len(batch_sizes)}, "
                              f"Записей: {sum(batch_sizes) if batch_sizes else 0}")

                        self._log_time(strategy_name, elapsed, self.thread_pool_size, batch_info)

                        # Сохраняем статистику
                        self.strategy_stats[strategy_name] = {
                            'time': elapsed,
                            'thread_pool_size': self.thread_pool_size,
                            'batch_count': len(batch_sizes),
                            'record_count': sum(batch_sizes) if batch_sizes else 0
                        }

                    except Exception as e:
                        elapsed = time.time() - start if 'start' in locals() else 0
                        print(f"[{strategy_name}] ОШИБКА: {e}")
                        self._log_time(strategy_name, elapsed, self.thread_pool_size, error=str(e))
                        continue

                    self.logInterface.Info(strategy_class, 'отработала успешно')

            executor.shutdown(wait=True)

        self.dbInterface.SaveSQLiteDatabaseFromRamToFile()
        return {self.moduleName: self.outputWriter.GetDBName()}
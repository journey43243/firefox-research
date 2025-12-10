"""Модуль стратегии извлечения истории посещений Firefox.

Содержит реализацию `HistoryStrategy`, которая считывает историю
просмотров из таблицы `moz_places` профиля Firefox и сохраняет её
в выходную базу данных.
"""

import sqlite3
from collections import namedtuple
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Iterable

from Modules.Firefox.interfaces.Strategy import StrategyABC, Generator, Metadata

# Именованный кортеж, описывающий запись истории браузера Firefox
History = namedtuple(
    'History',
    'url title visit_count typed last_visit_date profile_id'
)


class HistoryStrategy(StrategyABC):
    """Стратегия обработки данных истории посещений (history) Firefox.

    Читает данные из таблицы `moz_places`, формирует партионные списки
    объектов `History` и передаёт их в модуль записи в БД. Конвертация
    времени последнего посещения выполняется встроенной функцией SQLite.

    Атрибуты:
        _logInterface: Интерфейс логирования.
        _dbReadInterface: Интерфейс чтения данных из базы Firefox.
        _dbWriteInterface: Интерфейс записи данных в выходную базу.
        _profile_id (int): Идентификатор активного профиля.
    """

    def __init__(self, metadata: Metadata) -> None:
        """Инициализирует стратегию на основе метаданных.

        Args:
            metadata (Metadata): Структура, содержащая интерфейсы БД,
                параметры профиля и интерфейс логирования.
        """
        self._logInterface = metadata.logInterface
        self._dbReadInterface = metadata.dbReadInterface
        self._dbWriteInterface = metadata.dbWriteInterface
        self._profile_id = metadata.profileId

    def read(self) -> Generator[list[History], None, None]:
        """Считывает историю браузера из таблицы `moz_places`.

        Выполняет поэтапное чтение данных партиями по 500 записей
        и на каждой итерации генерирует список объектов `History`.

        Returns:
            Generator[list[History], None, None]: Генератор партий данных.

        Notes:
            Метка last_visit_date преобразуется из микросекунд в стандартный
            формат datetime через функцию SQLite.

        Raises:
            sqlite3.OperationalError: Если таблица `moz_places` отсутствует
                или повреждена. Ошибка логируется.
        """
        try:
            cursor = self._dbReadInterface._cursor.execute(
                '''SELECT url, title, visit_count, typed,
                datetime(last_visit_date / 1000000, 'unixepoch') AS last_visit_date
                FROM moz_places'''
            )
            while True:
                batch = cursor.fetchmany(500)
                if not batch:
                    break
                yield [History(*row, profile_id=self._profile_id) for row in batch]
        except sqlite3.OperationalError:
            self._logInterface.Warn(
                type(self),
                f'{self._profile_id} не может быть считан (не активен)'
            )

    async def write(self, butch: Iterable[tuple]) -> None:
        """Записывает партию записей истории в выходную базу данных.

        Args:
            butch (Iterable[tuple]): Итератор кортежей или структур History,
                подготовленных для записи.

        Returns:
            None

        Raises:
            Exception: Возможные ошибки записи логируются и не пробрасываются.
        """
        self._dbWriteInterface._cursor.executemany(
            '''INSERT INTO history (url, title, visit_count,
            typed, last_visit_date, profile_id)
            VALUES (?, ?, ?, ?, ?, ?)''',
            butch
        )
        self._dbWriteInterface.Commit()
        self._logInterface.Info(type(self), 'Группа записей успешно загружена')

    def execute(self, executor: ThreadPoolExecutor) -> None:
        for batch in self.read():
            self.write(batch)
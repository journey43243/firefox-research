import asyncio
import sqlite3
from asyncio import Task
from collections import namedtuple
from concurrent.futures.thread import ThreadPoolExecutor
from importlib.metadata import metadata
from typing import Iterable, Generator

from Modules.Firefox.interfaces.Strategy import StrategyABC, Metadata


# Именованный кортеж для удобства маппинга полей (tuple-поведение подходит для executemany)
Download = namedtuple("Download", "id place_id anno_attribute_id content profile_id")


class DownloadsStrategy(StrategyABC):
    """Извлекает загрузки из профиля Firefox и записывает их в выходную БД.

    Поддерживает данные в `moz_annos` (аннотации с именем, содержащим 'downloads').
    При отсутствии таблиц возвращает пустой генератор.
    """

    def __init__(self, metadata: Metadata) -> None:
        self._logInterface = metadata.logInterface
        self._dbReadInterface = metadata.dbReadInterface
        self._dbWriteInterface = metadata.dbWriteInterface
        self._profile_id = metadata.profileId

    def read(self) -> Generator[list[Download], None, None]:
        try:
            cursor = self._dbReadInterface._cursor.execute(
                """SELECT moz_annos.id, moz_annos.place_id, moz_annos.anno_attribute_id, moz_annos.content
                   FROM moz_annos
                   WHERE moz_annos.anno_attribute_id IN (
                       SELECT id FROM moz_anno_attributes WHERE name LIKE '%downloads%')"""
            )

            while True:
                batch = cursor.fetchmany(500)
                if not batch:
                    break
                yield [Download(*row, profile_id=self._profile_id) for row in batch]

        except sqlite3.OperationalError as e:
            self._logInterface.Warn(type(self),
                                    f'Загрузки для профиля {self._profile_id} не могут быть считаны (таблица отсутствует или БД не доступна): {e}')

    def write(self, batch: Iterable[Download]) -> None:
        try:
            params = [tuple(item) for item in list(batch)]
            if not params:
                return

            self._dbWriteInterface._cursor.executemany(
                '''INSERT OR IGNORE INTO downloads (id, place_id, anno_attribute_id, content, profile_id)
                   VALUES (?, ?, ?, ?, ?)''',
                params
            )
            self._dbWriteInterface.Commit()
            self._logInterface.Info(type(self), f'Группа загрузок успешно загружена')
        except Exception as e:
            self._logInterface.Error(type(self), f'Ошибка при записи загрузок: {e}')

    def execute(self, executor: ThreadPoolExecutor) -> None:
        for batch in self.read():
            executor.submit(self.write,batch)
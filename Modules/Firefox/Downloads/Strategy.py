import asyncio
import sqlite3
from asyncio import Task
from collections import namedtuple
from typing import Iterable, Generator

from Modules.Firefox.interfaces.Strategy import StrategyABC


# Именованный кортеж для удобства маппинга полей
Download = namedtuple(
    "Download",
    "id place_id anno_attribute_id content profile_id"
)


class DownloadsStrategy(StrategyABC):
    """
    Стратегия извлечения и записи истории загрузок Firefox.
    """

    def __init__(self, logInterface, dbReadInterface, dbWriteInterface, profile_id) -> None:
        self._logInterface = logInterface
        self._dbReadInterface = dbReadInterface
        self._dbWriteInterface = dbWriteInterface
        self._profile_id = profile_id

    def read(self) -> Generator[list[Download], None, None]:
        """
        Извлекает загрузки из базы профиля Firefox.
        Возвращает генератор списков Download по 500 записей.
        """
        try:
            cursor = self._dbReadInterface._cursor

            # Проверяем, какая таблица существует
            tables = cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            ).fetchall()
            table_names = {t[0] for t in tables}

            if "moz_annos" in table_names and "moz_anno_attributes" in table_names:
                query = """
                    SELECT moz_annos.id,
                           moz_annos.place_id,
                           moz_annos.anno_attribute_id,
                           moz_annos.content
                    FROM moz_annos
                    WHERE moz_annos.anno_attribute_id IN (
                        SELECT id FROM moz_anno_attributes WHERE name LIKE '%downloads%'
                    )
                """
            else:
                self._logInterface.Warn(
                    type(self),
                    f"Профиль {self._profile_id}: таблицы загрузок не найдены"
                )
                return

            cursor.execute(query)

            while True:
                batch = cursor.fetchmany(500)
                if not batch:
                    break
                yield [Download(*row, profile_id=self._profile_id) for row in batch]

        except sqlite3.OperationalError as e:
            self._logInterface.Warn(
                type(self),
                f"Профиль {self._profile_id} не удалось прочитать данные: {e}"
            )

    async def write(self, batch: Iterable[Download]) -> None:
        """
        Сохраняет партию записей о загрузках в выходную базу.
        """
        try:
            batch_list = list(batch)
            batch_count = len(batch_list)
            
            self._dbWriteInterface._cursor.executemany(
                """
                INSERT INTO downloads (id, place_id, anno_attribute_id, content, profile_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                batch_list
            )
            self._dbWriteInterface.Commit()
            self._logInterface.Info(type(self), f"Пакет из {batch_count} записей успешно загружен.")
        except Exception as e:
            self._logInterface.Warn(type(self), f"Ошибка записи: {e}")

    async def execute(self, tasks: list[Task]) -> None:
        """
        Создает асинхронные задачи для записи данных порциями.
        """
        for batch in self.read():
            task = asyncio.create_task(self.write(batch))
            tasks.append(task)
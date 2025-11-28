"""
Модуль стратегии извлечения загрузок Firefox

Этот модуль реализует стратегию для чтения истории загрузок файлов
из места places.sqlite каждого профиля Firefox.

Таблица: moz_annos (аннотации)
Аннотации с names, содержащими 'downloads', хранят информацию о загрузках в JSON.
"""

import asyncio
import sqlite3
from asyncio import Task
from collections import namedtuple
from importlib.metadata import metadata
from typing import Iterable, Generator

from Modules.Firefox.interfaces.Strategy import StrategyABC, Metadata

# Именованный кортеж для маппинга полей загрузок
Download = namedtuple("Download", "id place_id anno_attribute_id content profile_id")

class DownloadsStrategy(StrategyABC):
    """
    Стратегия для извлечения истории загрузок из Firefox.
    
    Читает таблицу moz_annos и извлекает аннотации, связанные с загрузками.
    Информация о загрузках хранится в JSON формате в поле content.
    
    Извлекаются данные о:
    - ID загруженного файла
    - Состоянии загрузки
    - Времени завершения
    - Размере файла
    
    Данные читаются батчами по 500 записей.
    """

    def __init__(self, metadata: Metadata) -> None:
        """
        Инициализирует стратегию загрузок.
        
        Args:
            metadata: Именованный кортеж с метаинформацией профиля
        """
        self._logInterface = metadata.logInterface
        self._dbReadInterface = metadata.dbReadInterface
        self._dbWriteInterface = metadata.dbWriteInterface
        self._profile_id = metadata.profileId

    def read(self) -> Generator[list[Download], None, None]:
        """
        Читает загрузки из places.sqlite.
        
        Ищет аннотации с названиями, содержащими 'downloads', и извлекает
        связанные данные о загрузках.
        
        Yields:
            Батчи по 500 записей загрузок
        
        Raises:
            sqlite3.OperationalError: Если таблица не доступна (профиль не активен)
        """
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

    async def write(self, batch: Iterable[Download]) -> None:
        """
        Записывает батч загрузок в таблицу downloads.
        
        Использует INSERT OR IGNORE для пропуска дубликатов.
        
        Args:
            batch: Итерируемая коллекция загрузок для записи
        """
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

    async def execute(self, tasks: list[Task]) -> None:
        """
        Главный метод выполнения стратегии.
        
        Читает все батчи загрузок и запускает асинхронную запись каждого батча.
        
        Args:
            tasks: Список асинхронных задач для добавления новых задач
        """
        for batch in self.read():
            task = asyncio.create_task(self.write(batch))
            tasks.append(task)
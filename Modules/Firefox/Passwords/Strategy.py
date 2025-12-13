"""
Модуль для извлечения и загрузки паролей Firefox.

Данный модуль реализует стратегию PasswordStrategy, отвечающую за
дешифровку, чтение и последующую пакетную загрузку сохранённых
паролей Firefox из профиля пользователя.

Чтение выполняется через PasswordService, который обрабатывает
ключи, мастер-пароль (если есть) и расшифровывает записи из logins.json.
Пароли записываются в результирующую базу данных пакетами.
"""

import asyncio
import pathlib
from asyncio import Task
from collections import namedtuple
from typing import Iterable

from Common.Routines import SQLiteDatabaseInterface
from Modules.Firefox.Passwords.PasswordService import PasswordService
from Modules.Firefox.interfaces.Strategy import StrategyABC, Generator, Metadata

Password = namedtuple('Password', 'url user password profile_id')


class PasswordStrategy(StrategyABC):
    """
    Strategy-класс для чтения и записи паролей Firefox.

    Стратегия использует PasswordService для расшифровки и получения списка
    паролей из профиля браузера, после чего загружает их в БД пакетами.
    """

    def __init__(self, metadata: Metadata) -> None:
        """
        Инициализация стратегии, подключение сервисов и интерфейсов.

        Parameters
        ----------
        metadata : Metadata
            Объект, содержащий ссылки на интерфейсы логирования,
            чтения БД, записи БД, путь профиля и идентификатор профиля.
        """
        self._logInterface = metadata.logInterface
        self._dbReadInterface = metadata.dbReadInterface
        self._dbWriteInterface = self._writeInterface("FirefoxPasswords", metadata.logInterface, metadata.caseFolder)
        self._profile_id = metadata.profileId
        self._profile_path = metadata.profilePath
        self._service = PasswordService(self._profile_path, self._logInterface)

    def createDataTable(self):
        """
               Создаёт таблицу 'passwords' для хранения паролей Firefox
               и индексы по URL и пользователю.
               """
        self._dbWriteInterface.ExecCommit(
            '''CREATE TABLE IF NOT EXISTS passwords (
                url TEXT,
                user TEXT,
                password TEXT,
                profile_id INTEGER,
                UNIQUE(url, user, password)
            )'''
        )
        self._dbWriteInterface.ExecCommit('''CREATE INDEX idx_url_profile_id ON passwords(url, user)''')
        self._logInterface.Info(type(self), 'Таблица с паролями успешно создана')
        self._dbWriteInterface.SaveSQLiteDatabaseFromRamToFile()


    def read(self) -> Generator[list[tuple[str, str, str, int]], None, None]:
        """
        Читает и дешифрует пароли профиля Firefox, возвращая их пакетами.

        Returns
        -------
        Generator[list[tuple]], None, None
            Пакеты кортежей (url, user, password, profile_id).

        Notes
        -----
        Если пароли отсутствуют или произошла ошибка — выдаётся предупреждение.
        """
        try:
            all_pw = self._service.get_passwords()
            if not all_pw:
                self._logInterface.Warn(type(self), 'Пароли не найдены')
                return

            batch_size = 500
            batch: list[tuple[str, str, str, int]] = []

            for rec in all_pw:
                batch.append((rec['url'], rec['user'], rec['password'], self._profile_id))
                if len(batch) >= batch_size:
                    yield batch
                    batch = []

            if batch:
                yield batch

            self._logInterface.Info(type(self), f'Найдено {len(all_pw)} паролей')

        except Exception as e:
            self._logInterface.Warn(type(self), f'Ошибка при чтении паролей: {e}')

    def write(self, batch: Iterable[tuple]) -> None:
        """
        Записывает пакет паролей в результирующую БД.

        Parameters
        ----------
        batch : Iterable[tuple]
            Список кортежей для записи.
        """
        cursor = self._dbWriteInterface._cursor
        conn = self._dbWriteInterface._connection
        try:
            conn.execute("BEGIN")
            cursor.executemany(
                '''INSERT OR IGNORE INTO passwords 
                   (url, user, password, profile_id) 
                   VALUES (?, ?, ?, ?)''',
                batch
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            self._logInterface.Error(type(self), f"Ошибка записи батча: {e}")
        else:
            self._logInterface.Info(type(self), f'Группа записей успешно загружена')

    def execute(self, tasks: list[Task]) -> None:
        """
        Запускает процесс извлечения и записи паролей.

        Для каждого пакета создаётся асинхронная задача write().

        Parameters
        ----------
        tasks : list[Task]
            Список, в который добавляются созданные задачи.
        """
        self.createDataTable()
        for batch in self.read():
            task = asyncio.create_task(self.write(batch))
            tasks.append(task)

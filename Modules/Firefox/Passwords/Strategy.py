import asyncio
from asyncio import Task
from collections import namedtuple
from typing import Iterable
from Modules.Firefox.Passwords.PasswordService import PasswordService
from Modules.Firefox.interfaces.Strategy import StrategyABC, Generator

Password = namedtuple('Password', 'url user password')

class PasswordStrategy(StrategyABC):

    def __init__(self, logInterface, dbReadInterface, dbWriteInterface, profile_path) -> None:
        self._logInterface = logInterface
        self._dbReadInterface = dbReadInterface
        self._dbWriteInterface = dbWriteInterface
        self._profile_path = profile_path
        self._service = PasswordService(profile_path)

    def read(self) -> Generator[list[tuple[str, str, str]], None, None]:
        try:
            all_pw = self._service.get_passwords()
            if not all_pw:
                self._logInterface.Warn(type(self), 'Пароли не найдены')
                return
            batch_size = 500
            batch: list[tuple[str, str, str]] = []
            for rec in all_pw:
                batch.append((rec['url'], rec['user'], rec['password']))
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
            if batch:
                yield batch
            self._logInterface.Info(type(self), f'Найдено {len(all_pw)} паролей')
        except Exception as e:
            self._logInterface.Warn(type(self), f'Ошибка при чтении паролей: {e}')

    async def write(self, butch: Iterable[tuple]) -> None:
        cursor = self._dbWriteInterface._cursor
        conn = self._dbWriteInterface._connection
        try:
            conn.execute("BEGIN")
            cursor.executemany(
                '''INSERT OR IGNORE INTO passwords (url, user, password) VALUES (?, ?, ?)''',
                butch
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            self._logInterface.Error(type(self), f"Ошибка записи батча: {e}")
        else:
            self._logInterface.Info(type(self), f'Группа записей успешно загружена')

    async def execute(self, tasks: list[Task]) -> None:
        for batch in self.read():
            task = asyncio.create_task(self.write(batch))
            tasks.append(task)

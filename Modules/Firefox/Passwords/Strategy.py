import asyncio
from asyncio import Task
from collections import namedtuple
from collections.abc import Iterable
from Modules.Firefox.Passwords.PasswordService import MozillaInteraction, Exit
from Modules.Firefox.interfaces.Strategy import StrategyABC, Generator

Password = namedtuple(
    'Password',
    'url user password',
)


class PasswordStrategy(StrategyABC):
    """
    Strategy для чтения/дешифрации паролей Firefox с помощью PasswordService.
    Использует переданные интерфейсы для чтения и записи.
    """

    def __init__(self, logInterface, dbReadInterface, dbWriteInterface, profile_id):
        self._logInterface = logInterface
        self._dbReadInterface = dbReadInterface
        self._dbWriteInterface = dbWriteInterface
        self._profile_id = profile_id
        self._moz = MozillaInteraction(non_fatal_decryption=True)

    def read(self) -> Generator[list[tuple[str, str, str]], None, None]:
        """
        Генератор, который возвращает батчи расшифрованных паролей:
        [(url, user, password), ...]
        """
        try:
            self._moz.load_profile(self._profile_id)
            self._moz.authenticate(interactive=True)
            pwstore = self._moz.decrypt_passwords()
            if not pwstore:
                self._logInterface.Warn(type(self), f'{self._profile_id}: пароли не найдены в профиле')
                return
            self._logInterface.Info(type(self), f'{self._profile_id}: найдено {len(pwstore)} паролей')

            batch_size = 500
            batch: list[tuple[str, str, str]] = []
            for rec in pwstore:
                url = rec.get('url', '')
                user = rec.get('user', '')
                password = rec.get('password', '')
                batch.append((url, user, password))
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
            if batch:
                yield batch
        except Exit as e:
            self._logInterface.Warn(type(self), f'{self._profile_id} не может быть считан: {getattr(e, "exitcode", e)}')
        finally:
            try:
                self._moz.unload_profile()
            except Exception:
                pass

    async def write(self, butch: Iterable[tuple]) -> None:
        """
        Асинхронная запись батча в БД через переданный интерфейс.
        """
        self._dbWriteInterface._cursor.executemany(
            '''INSERT INTO passwords (url, user, password) VALUES (?, ?, ?)''',
            butch
        )
        self._dbWriteInterface.Commit()
        self._logInterface.Info(type(self), f'{self._profile_id}: Группа записей успешно загружена')

    async def execute(self, tasks: list[Task]) -> None:
        """
        Чтение и запись батчей паролей.
        """
        for batch in self.read():
            task = asyncio.create_task(self.write(batch))
            tasks.append(task)
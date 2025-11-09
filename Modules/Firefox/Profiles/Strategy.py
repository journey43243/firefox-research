import asyncio
from asyncio import Task
from typing import Generator

from Common.Routines import FileContentReader
from Modules.Firefox.interfaces.Strategy import StrategyABC

import os

class PathMixin:
    __folderPath = f'{os.getenv('APPDATA')}\\Mozilla\\Firefox'

    @property
    def folderPath(self):
        return self.__folderPath

class ProfilesStrategy(StrategyABC, PathMixin):

    __fileName = 'profiles.ini'

    def __init__(self, logInterface, dbWriteInterface) -> None:
        self._fileReader = FileContentReader()
        self._logInterface = logInterface
        self._dbWriteInterface = dbWriteInterface
        super().__init__()

    @property
    def fileName(self):
        return self.__fileName

    def read(self) -> Generator[str, None, None]:
        _, _, content = self._fileReader.GetTextFileContent(self.folderPath, self.fileName,includeTimestamps=False)
        profilesCnt = 0
        for _, row in content.items():
            if 'Path' in row:
                row = row[5:].replace('\n', '').replace('/', '\\')
                profilesCnt += 1
                yield self.folderPath + '\\' + row
        self._logInterface.Info(type(self), f"Считано {profilesCnt} профилей")

    async def write(self, butch: list[str]) -> None:
        for record in butch:
            self._dbWriteInterface.ExecCommit(
                '''INSERT INTO profiles (path) VALUES (?)''', (record, )
            )
        self._logInterface.Info(type(self),'Все профили загружены в таблицу')

    async def execute(self, tasks: list[Task]) -> None:
        profiles = [profile for profile in self.read()]
        task = asyncio.create_task(self.write(profiles))
        tasks.append(task)
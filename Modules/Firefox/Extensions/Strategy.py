import asyncio
import json
import os
from asyncio import Task
from collections import namedtuple
from typing import Iterable, Generator

from Modules.Firefox.interfaces.Strategy import StrategyABC, Metadata

Extension = namedtuple(
    'Extension',
    'id name version description type active user_disabled install_date update_date path source_url permissions location profile_id'
)

class ExtensionsStrategy(StrategyABC):

    def __init__(self, metadata: Metadata) -> None:
        self._logInterface = metadata.logInterface
        self._dbReadInterface = metadata.dbReadInterface
        self._dbWriteInterface = metadata.dbWriteInterface
        self._profile_id = metadata.profileId
        self._profile_path = metadata.profilePath

    def read(self) -> Generator[list[Extension], None, None]:
        #Чтение расширений из файла extensions.json профиля
        extensions_file = os.path.join(self._profile_path, 'extensions.json')
        if not os.path.exists(extensions_file):
            self._logInterface.Warn(type(self), f'Файл расширений не найден: {extensions_file}')
            return

        try:
            with open(extensions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            extensions = []
            for addon in data.get('addons', []):
                # Берем только расширения (type == 'extension')
                if addon.get('type') != 'extension':
                    continue

                default_locale = addon.get('defaultLocale', {})
                permissions = addon.get('userPermissions', {})
                
                extension = Extension(
                    id=addon.get('id', ''),
                    name=default_locale.get('name', ''),
                    version=addon.get('version', ''),
                    description=default_locale.get('description', ''),
                    type=addon.get('type', ''),
                    active=1 if addon.get('active', False) else 0,
                    user_disabled=1 if addon.get('userDisabled', False) else 0,
                    install_date=addon.get('installDate', 0),
                    update_date=addon.get('updateDate', 0),
                    path=addon.get('path', ''),
                    source_url=addon.get('sourceURI', ''),
                    permissions=json.dumps(permissions) if permissions else '',
                    location=addon.get('location', ''),
                    profile_id=self._profile_id
                )
                extensions.append(extension)

            # Возвращаем одним батчем
            yield extensions
            self._logInterface.Info(type(self), f'Найдено {len(extensions)} расширений')

        except Exception as e:
            self._logInterface.Error(type(self), f'Ошибка чтения расширений: {str(e)}')

    async def write(self, batch: Iterable[Extension]) -> None:
        #Запись расширений в базу данных
        try:
            self._dbWriteInterface._cursor.executemany(
                '''INSERT OR IGNORE INTO extensions 
                (id, name, version, description, type, active, user_disabled, 
                 install_date, update_date, path, source_url, permissions, location, profile_id) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                batch
            )
            self._dbWriteInterface.Commit()
            self._logInterface.Info(type(self), 'Расширения записаны в БД')
        except Exception as e:
            self._logInterface.Error(type(self), f'Ошибка записи расширений: {str(e)}')

    async def execute(self, tasks: list[Task]) -> None:
        for batch in self.read():
            if batch:  # Проверяем, что батч не пустой
                task = asyncio.create_task(self.write(batch))
                tasks.append(task)
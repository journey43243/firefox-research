"""
Модуль стратегии извлечения расширений Firefox

Этот модуль реализует стратегию для чтения установленных расширений (аддонов)
из файла extensions.json каждого профиля Firefox.

Файл: %профиль%/extensions.json
Содержит JSON с информацией о всех установленных дополнениях браузера.
"""

import asyncio
import json
import os
from asyncio import Task
from collections import namedtuple
from typing import Iterable, Generator

from Modules.Firefox.interfaces.Strategy import StrategyABC, Metadata

# Именованный кортеж для маппинга полей расширений
Extension = namedtuple(
    'Extension',
    'id name version description type active user_disabled install_date update_date path source_url permissions location profile_id'
)

class ExtensionsStrategy(StrategyABC):
    """
    Стратегия для извлечения расширений из Firefox.
    
    Читает файл extensions.json профиля и извлекает информацию об
    установленных расширениях, включая:
    - ID расширения
    - Имя и описание
    - Версию
    - Статус активности
    - Дату установки
    - Разрешения (permissions)
    
    Извлекаются только расширения (type == 'extension'), не другие типы аддонов.
    """

    def __init__(self, metadata: Metadata) -> None:
        """
        Инициализирует стратегию расширений.
        
        Args:
            metadata: Именованный кортеж с метаинформацией профиля
        """
        self._logInterface = metadata.logInterface
        self._dbReadInterface = metadata.dbReadInterface
        self._dbWriteInterface = metadata.dbWriteInterface
        self._profile_id = metadata.profileId
        self._profile_path = metadata.profilePath

    def read(self) -> Generator[list[Extension], None, None]:
        """
        Читает расширения из файла extensions.json профиля.
        
        Парсит JSON и извлекает информацию о каждом расширении.
        Фильтрует по type == 'extension' (только расширения, не темы и т.д.).
        
        Yields:
            Батч со всеми найденными расширениями (не поддерживается батчинг)
        
        Warns:
            Если файл extensions.json не найден или при ошибке парсинга JSON
        """
        # Чтение расширений из файла extensions.json профиля
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
        """
        Записывает расширения в таблицу extensions.
        
        Использует INSERT OR IGNORE для пропуска дубликатов.
        
        Args:
            batch: Итерируемая коллекция расширений для записи
        """
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
        """
        Главный метод выполнения стратегии.
        
        Читает все расширения и запускает асинхронную запись.
        
        Args:
            tasks: Список асинхронных задач для добавления новых задач
        """
        for batch in self.read():
            if batch:  # Проверяем, что батч не пустой
                task = asyncio.create_task(self.write(batch))
                tasks.append(task)
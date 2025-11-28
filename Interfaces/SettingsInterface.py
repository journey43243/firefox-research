# -*- coding: utf-8 -*-
"""
Модуль интерфейса управления настройками приложения

Этот модуль предоставляет интерфейс для чтения и работы с файлом настроек
приложения (Settings.json). Обеспечивает централизованный доступ ко всем
параметрам конфигурации приложения.

Если файл настроек содержит ошибки, автоматически используются значения по умолчанию.
"""

import json
from typing import Any, Dict, NoReturn

# ################################################################
class SettingsInterface():
    """
    Интерфейс для управления настройками приложения.
    
    Читает параметры из JSON файла Settings.json и предоставляет методы
    для безопасного доступа к значениям параметров.
    
    Атрибуты:
        __settingsFileName: Имя файла настроек (Settings.json)
        __settings: Словарь с параметрами
        __log: Объект логирования для записи ошибок
    """
    
    def __init__(self, logInterface):
        """
        Инициализирует интерфейс настроек.
        
        Читает файл Settings.json из текущей директории.
        При ошибке JSON устанавливает значения по умолчанию.
        
        Args:
            logInterface: Объект LogInterface для логирования ошибок
        """
        self.__settingsFileName: str = 'Settings.json'
        self.__settings: dict = {}
        self.__log = logInterface
        
        # Инициализировать настройки
        self.__ReadSettings()
        
    def __ReadSettings(self) -> NoReturn:
        """
        Читает параметры из файла Settings.json.
        
        При ошибке парсинга JSON устанавливает значения по умолчанию:
        - CaseFolder: 'Cases' (папка для сохранения результатов)
        - TemporaryFilesFolder: 'Temp' (папка для временных файлов)
        """
        with open(self.__settingsFileName, 'rb') as f:
            try:
                self.__settings = json.load(f)
            except json.decoder.JSONDecodeError as e:
                message = f'Файл настроек содержит ошибки: {e}'
                self.__log.Error('SettingsInterface', message)
                
                # Установить значения по умолчанию
                self.__settings['CaseFolder'] = 'Cases'
                self.__settings['TemporaryFilesFolder'] = 'Temp'

    def GetSettings(self) -> Dict:
        """
        Возвращает полный словарь параметров.
        
        Returns:
            Словарь со всеми параметрами приложения
        """
        return self.__settings
    
    def GetSettingValueByName(self, parameterName: str) -> Any:
        """
        Возвращает значение параметра по имени.
        
        Args:
            parameterName: Имя параметра
        
        Returns:
            Значение параметра или None если параметр не найден
        """
        return self.__settings.get(parameterName)
    
# -*- coding: utf-8 -*-
"""
Модуль извлечения данных MuiCache (Multilingual User Interface Cache)

Этот модуль обрабатывает записи реестра Windows из веток MuiCache,
которые содержат информацию о локализованных названиях приложений,
библиотек и ресурсов в соответствии с языком системы.

MuiCache хранит дружественные названия (FriendlyName) и названия производителей
(ApplicationCompany) для исполняемых файлов и библиотек, которые были запущены
на компьютере.

Типовые расположения:
    Windows XP:
        HKU\SID\Software\Microsoft\Windows\ShellNoRoam\MUICache
    
    Windows Vista/7/8/8.1/10:
        HKU\SID\Software\Classes\Local Settings\MuiCache\<BYTE>\B1A07F78
        HKU\SID\Software\Classes\Local Settings\ImmutableMuiCache\Strings\B1A07F78 (Win8.1+)
        HKU\SID\Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache

Эти данные полезны для судебно-технического анализа (forensics):
- История приложений, запущенных на компьютере
- Дружественные названия приложений
- Информация о производителях ПО
- Параметры и расширенные атрибуты приложений
"""
import re, regipy, os
from abc import ABCMeta, abstractmethod
from typing import Tuple, Optional, Awaitable, NoReturn, Callable, Any, List, Dict

#----------------------------------------------------------------------
class _MuiCacheParser():
    """
    Абстрактный парсер для извлечения данных MuiCache.
    
    Основная логика обработки реестра Windows и преобразования данных.
    Содержит методы для:
    - Чтения веток MuiCache различных версий Windows
    - Парсинга путей к приложениям и параметров
    - Извлечения названий компаний и описаний
    - Записи данных в выходную БД
    
    Атрибуты:
        _storage (str): Путь к папке Source с исходными данными
        _rfh (Any): Обработчик файлов реестра Windows
        _wr (Any): Интерфейс для записи данных
        _db (Any): Подключение к БД для SQL операций
        _record (dict): Текущая запись для записи в БД
        _profileList (list): Список профилей пользователей
    """
    __metaclass__ = ABCMeta
    def __init__(self, parserParameters: dict, recordFields: dict):
        """
        Инициализирует парсер MuiCache.
        
        Args:
            parserParameters (dict): Параметры модуля от Solver
            recordFields (dict): Определение полей для таблицы БД
        """
        # Входные параметры
        self._redrawUI: Callable = parserParameters.get('UIREDRAW')
        self._rfh: regipy.registry.RegistryHive = parserParameters.get('REGISTRYFILEHANDLER')
        self._wr: Any = parserParameters.get('OUTPUTWRITER')
        self._db: Any = parserParameters.get('DBCONNECTION')
        self._standaloneFiles: bool = True  # ! оставлять как True
        self._storage: str = parserParameters.get('STORAGE')
        
        self._profileList: list = None
        
        # Инициализация словаря записей в БД с типами по умолчанию
        self._record: dict = {}
        for k, v in recordFields.items():
            if v == 'TEXT':
                self._record[k] = ''
            elif v == 'INTEGER' or v == 'INTEGER UNSIGNED':
                self._record[k] = 0
            else:
                self._record[k] = ''
                
    def SetUserProfilesList(self, userProfilesList: list) -> NoReturn:
        """
        Устанавливает список профилей пользователей для обработки.
        
        Args:
            userProfilesList (list): Список профилей (SID: userInfo pairs)
        """
        self._profileList = userProfilesList
    
    @abstractmethod
    async def _GetInfo(self, data) -> NoReturn:
        """Абстрактный метод для извлечения информации из реестра (переопределяется подклассом)."""
        pass

    def _CleanRecord(self) -> NoReturn:
        """
        Сбрасывает данные текущей записи перед обработкой новой.
        
        Очищает поля: Name, Company, Parameter, Value
        """
        self._record['Name'] = ''
        self._record['Company'] = ''
        self._record['Parameter'] = ''
        self._record['Value'] = ''
            
    async def Start(self) -> NoReturn:
        """
        Главный асинхронный метод для запуска парсера.
        
        Координирует процесс извлечения данных:
        1. Итерирует по всем профилям пользователей (если не standalone)
        2. Для каждого профиля вызывает _GetInfo()
        3. Обрабатывает все данные из реестра
        """
        if not self._standaloneFiles:
            if self._profileList is not None:
                for sid, userInfo in self._profileList.items():
                    await self._GetInfo(userInfo)
        else:
            await self._GetInfo(None)
            
#----------------------------------------------------------------------
class _MuiCacheParser_V1(_MuiCacheParser):
    """
    Версионный парсер для Windows XP и Server 2003.
    
    В этих ОС MuiCache находится в более простой структуре под ShellNoRoam.
    Содержит локализованные названия приложений и системных компонентов.
    """
    def __init__(self, parserParameters, recordFields):
        """
        Инициализирует парсер V1 для Windows XP/Server2003.
        
        Args:
            parserParameters (dict): Параметры модуля
            recordFields (dict): Определение полей БД
        """
        super().__init__(parserParameters, recordFields)
        
    async def _GetInfo(self, data) -> NoReturn:
        """
        Извлекает данные MuiCache из Windows XP.
        
        В Windows XP расположение:
            HKU\SID\Software\Microsoft\Windows\ShellNoRoam\MUICache            
        
        Эта ветка содержит переводы имен приложений и системных файлов,
        где каждое значение - это путь к файлу с параметром и локализованным названием.
        
        Процесс парсинга:
        1. Открывает файл ntuser.dat пользователя
        2. Читает ветку MUICache из реестра
        3. Для каждого значения парсит путь и параметр (разделены на ",-")
        4. Записывает в БД информацию о приложении
        """
        ntUserDatPath:str = None
        
        if data is None:
            self._record['UserName'] == ''
            ntUserDatPath = os.path.join(self._storage,'ntuser.dat')    
        
        await self._redrawUI('Пользователи Windows: MUICache пользователя ' + self._record['UserName'],1)
        
        if ntUserDatPath is not None:
            self._rfh.SetStorageRegistryFileFullPath(ntUserDatPath)
            ntUserDatReg = self._rfh.GetRegistryHandle()
        
            # Получение данных и запись в БД
            if ntUserDatReg is not None:
                # Заполнить источник информации
                self._record['DataSource'] = ntUserDatPath
                
                # Обработать ключи реестра
                try:
                    for item in ntUserDatReg.get_key('\\Software\\Microsoft\\Windows\\ShellNoRoam\\MUICache').get_values():
                        
                        rawName = item.name
                        if rawName == 'LangID':
                            continue
                        # Определить нет ли utf-16le вместо utf-8
                        # Убрать @ и " и обернуть слэши для проверки через re
                        rawName = rawName.replace('@','').replace('"','').replace(';','')
                       
                        try:
                            self._record['Parameter'] = rawName.rsplit(',-',1)[1]
                        except IndexError:
                            self._record['Parameter'] = ''
                    
                        try:
                            self._record['Name'] = rawName.rsplit(',-',1)[0]
                        except IndexError:
                            self._record['Name'] = rawName
                            
                        self._record['Value'] = item.value
                    
                        if rawName is not None and self._record['Value'] is not None:
                            info = (self._record['UserName'],
                                self._record['Name'],
                                self._record['Company'],
                                self._record['Parameter'],
                                self._record['Value'],
                                self._record['DataSource'])
        
                            self._wr.WriteRecord(info)
                            
                        # Сбросить значения
                        self._CleanRecord()
                
                except regipy.RegistryKeyNotFoundException:
                    pass # нет ключей
                except regipy.RegistryKeyNotFoundException:
                    pass # нет такой ветки

        await self._redrawUI('Пользователи Windows: MUICache пользователя ' + self._record['UserName'],100)        

#----------------------------------------------------------------------
class _MuiCacheParser_V2(_MuiCacheParser):
    """
    Версионный парсер для Windows Vista, 7, 8, 8.1, 10 и Server 2008+.
    
    В этих ОС MuiCache имеет более сложную структуру с несколькими ветками:
    - Local Settings\MuiCache - основные записи о приложениях
    - Local Settings\ImmutableMuiCache (Win8.1+) - неизменяемые записи
    - Local Settings\Software\Microsoft\Windows\Shell\MuiCache - расширенные атрибуты
    
    Поддерживает выделение информации о компании (ApplicationCompany) и приложении.
    """
    def __init__(self, parserParameters, recordFields):
        """
        Инициализирует парсер V2 для Windows Vista/7/8/8.1/10.
        
        Args:
            parserParameters (dict): Параметры модуля
            recordFields (dict): Определение полей БД
        """
        super().__init__(parserParameters, recordFields)
             
    async def _GetInfo(self, data) -> NoReturn:
        """
        Извлекает данные MuiCache из Windows Vista/7/8/8.1/10.
        
        В этих версиях MuiCache расположен в:
            HKU\SID\Software\Classes\Local Settings\MuiCache\<BYTE>\B1A07F78
            HKU\SID\Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache
        
        Также в Win8.1:
            HKU\SID\Software\Classes\Local Settings\ImmutableMuiCache\Strings\B1A07F78
        
        Процесс парсинга состоит из двух частей:
        
        Часть 1 (MuiCache):
        - Читает основные записи о приложениях и системных компонентах
        - Парсит пути и параметры
        - Значения в виде локализованных названий
        
        Часть 2 (Shell\MuiCache):
        - Читает расширенные атрибуты приложений
        - Обрабатывает FriendlyAppName и ApplicationCompany
        - ApplicationCompany обновляет существующие записи в БД
        
        Источник данных: UsrClass.dat (хранит информацию о классах файлов)
        """
        pathKey:str = ''
        ntUserDatPath:str = None
        usrClassDatPath:str = None
        
        if data is None:
            self._record['UserName'] == ''
            ntUserDatPath = os.path.join(self._storage,'ntuser.dat')
            usrClassDatPath = os.path.join(self._storage,'UsrClass.dat')
            
        
        if usrClassDatPath is not None:
            self._rfh.SetStorageRegistryFileFullPath(usrClassDatPath)    
            usrClassDatReg = self._rfh.GetRegistryHandle()
        
            # Получение данных и запись в БД
            if usrClassDatReg is not None:
                # Заполнить источник информации
                self._record['DataSource'] = usrClassDatPath
                
                # Обработать ключи реестра
                try:
                    # Первая часть
                    for item in usrClassDatReg.get_key('\\Local Settings\\MuiCache').iter_subkeys():
                        pathKey = item.name 
                        break
                
                    for item in usrClassDatReg.get_key('\\Local Settings\\MuiCache\\' + pathKey + '\\B1A07F78').get_values():
                        rawName = item.name
                        if rawName == 'LangID' or rawName == 'LanguageList':
                            continue
                    
                        # Определить нет ли utf-16le вместо utf-8
                        # Убрать @ и " и обернуть слэши для проверки через re
                        rawName = rawName.replace('@','').replace('"','').replace(';','')
                    
                        try:
                            self._record['Parameter'] = rawName.rsplit(',-',1)[1]
                        except IndexError:
                            self._record['Parameter'] = ''
                    
                        try:
                            self._record['Name'] = rawName.rsplit(',-',1)[0]
                        except IndexError:
                            self._record['Name'] = rawName
                    
                        self._record['Value'] = item.value
                    
                        if rawName is not None and self._record['Value'] is not None:
                            info = (self._record['UserName'],
                                    self._record['Name'],
                                    self._record['Company'],
                                    self._record['Parameter'],
                                    self._record['Value'],
                                    self._record['DataSource'])
        
                            self._wr.WriteRecord(info)
                        
                        # Сбросить значения
                        self._CleanRecord()
                
                except regipy.NoRegistrySubkeysException:
                    pass # нет ключей
                except regipy.RegistryKeyNotFoundException:
                    pass # нет такой ветки
                except regipy.exceptions.RegistryParsingException:
                    pass # кривой реестр
                
                # Вторая часть
                try:
                    for item in usrClassDatReg.get_key('\\Local Settings\\Software\\Microsoft\\Windows\\Shell\\MuiCache').get_values():
                        
                        rawName = item.name
                        if rawName == 'LangID' or rawName == 'LanguageList':
                            continue
                        
                        # Убрать @ и " и обернуть слэши для проверки через re
                        rawName = rawName.replace('@','').replace('"','').replace(';','')
                    
                        try:
                            self._record['Parameter'] = rawName.rsplit(',-',1)[1]
                        except IndexError:
                            self._record['Parameter'] = ''
                    
                        try:
                            self._record['Name'] = rawName.rsplit(',-',1)[0]
                        except IndexError:
                            self._record['Name'] = rawName
                        
                        if self._record['Name'].endswith('.FriendlyAppName'):
                            self._record['Name'] = self._record['Name'].rsplit('.FriendlyAppName',1)[0]
                        elif self._record['Name'].endswith('.ApplicationCompany'):
                            self.__UpdateRecordCompanyValue(self._record['Name'].rsplit('.ApplicationCompany',1)[0],item.value)
                            self._CleanRecord()
                            continue

                        self._record['Value'] = item.value
                    
                        if rawName is not None and self._record['Value'] is not None:
                            info = (self._record['UserName'],
                                   self._record['Name'],
                                   self._record['Company'],
                                   self._record['Parameter'],
                                   self._record['Value'],
                                   self._record['DataSource'])
                           
                            self._wr.WriteRecord(info)
                        
                        # Сбросить значения
                        self._CleanRecord()
                
                except regipy.RegistryKeyNotFoundException:
                    pass
                
                except regipy.NoRegistrySubkeysException:
                    pass
                except regipy.exceptions.RegistryParsingException:
                    pass # кривой реестр

            
        await self._redrawUI('Пользователи Windows: MUICache пользователя ' + self._record['UserName'],100)
        
    
    def __UpdateRecordCompanyValue(self, softwareName, value) -> NoReturn:
        """
        Обновляет значение компании для существующей записи в БД.
        
        Используется при обработке ApplicationCompany параметров.
        Выполняет UPDATE запрос для установки компании по названию ПО.
        
        Args:
            softwareName (str): Название приложения для поиска в БД
            value (str): Новое значение компании (производителя)
        """
        query = 'UPDATE Data SET Company = ? WHERE Name = ?;'
        self._db.ExecCommit(query, (str(value), str(softwareName)))
        
#----------------------------------------------------------------------
class Parser():
    """
    Главный класс парсера для модуля MuiCache.
    
    Отвечает за:
    1. Определение версии Windows
    2. Выбор правильного парсера (V1 для WinXP, V2 для Vista+)
    3. Создание таблиц БД с 6 полями
    4. Запись результатов
    5. Формирование финального БД с индексами и метаинформацией
    
    Таблица хранит 6 основных полей:
    - UserName: Имя пользователя
    - Name: Полный путь к приложению или его имя
    - Company: Производитель ПО (заполняется из ApplicationCompany)
    - Parameter: Параметр или расширение
    - Value: Локализованное название или описание
    - DataSource: Источник данных (ntuser.dat или UsrClass.dat)
    """
    def __init__(self, parameters: dict):
        """
        Инициализирует главный парсер MuiCache.
        
        Args:
            parameters (dict): Параметры от Solver (STORAGE, OUTPUTWRITER, DBCONNECTION, MODULENAME, CASENAME)
        """  
        self.__parameters: dict = parameters 

        self.__recordFields: dict = {
            'UserName': 'TEXT',
            'Name': 'TEXT',
            'Company': 'TEXT',
            'Parameter': 'TEXT',
            'Value': 'TEXT',
            'DataSource': 'TEXT'
         }
              
        osVersion: str = '10'
        # Парсинг версии ОС (формат: "7__1" для Windows 7 SP1)
        if osVersion.find('__') != -1:
            self.__osVersion, self.__osRelease = osVersion.split('__')
        else:
            self.__osVersion = osVersion
        
        # Выбор парсера в зависимости от версии ОС
        if self.__osVersion in ['XP', 'Server2003']:
            self.__muiCacheParser: Any = _MuiCacheParser_V1(parameters, self.__recordFields)
        else:
            self.__muiCacheParser: Any = _MuiCacheParser_V2(parameters, self.__recordFields)   
            
    async def Start(self) -> Dict:
        """
        Главный асинхронный метод для запуска модуля.
        
        Процесс выполнения:
        1. Получает параметры (STORAGE, OUTPUTWRITER, DBCONNECTION, MODULENAME)
        2. Проверяет соединение с БД
        3. Определяет структуру таблицы (поля и типы)
        4. Создает таблицы в БД
        5. Запускает парсер для извлечения данных
        6. Удаляет временные таблицы
        7. Создает индексы для быстрого поиска
        8. Записывает метаинформацию
        9. Закрывает вывод
        
        Создаваемые таблицы в БД:
        - Data: Основная таблица с 6 полями для хранения информации о приложениях
        - Info: Метаинформация о датасете (название, версия, timestamp)
        - Headers: Описание колонок (название, ярлык, ширина)
        
        Индексы:
        - По каждому полю для оптимизации поиска
        
        Returns:
            Dict: {moduleName: outputFileName} - путь к созданному файлу БД
        """
        storage: str = self.__parameters.get('STORAGE')
        outputWriter: Any = self.__parameters.get('OUTPUTWRITER')
        
        # Проверка соединения с БД перед началом работы
        if not self.__parameters.get('DBCONNECTION').IsConnected():
            return  # Модуль не может обрабатывать информацию - нет соединения с БД вывода
        
        # Определение структуры таблицы: (Имя колонки: (Label, Width, Type, Help))
        fields: dict = {
            'UserName': ('Имя пользователя', 140, 'string', 'Имя пользователя'),
            'Name': ('Полный путь / Название', 430, 'string', 'Полный путь / Название'),
            'Company': ('Производитель ПО', 150, 'string', 'Производитель ПО'),
            'Parameter': ('Параметр', -1, 'string', 'Параметр'),
            'Value': ('Описание', 430, 'string', 'Описание'),
            'DataSource': ('Источник данных', 230, 'string', 'Источник данных')
        }
        
        # Справочный текст о модуле (выводится в UI)
        HELP_TEXT: str = self.__parameters.get('MODULENAME') + """:
        Списки задания имени программы/библиотеки/иного ресурса 
        в соответствии с языком системы
                        
        Извлекается из веток:
        Windows XP:  
        HKU\\<SID>\\Software\\Microsoft\\Windows\\ShellNoRoam\\MUICache

        Windows 7, 8, 8.1, 10:  
        HKU\\<SID>\\Software\\Classes\\Local Settings\\MuiCache\\<BYTE>\\B1A07F78
        HKU\\<SID>_Classes\\Local Settings\\Software\\Microsoft\\Windows\\Shell\\MuiCache

        Переменные среды извлекаются из:
        HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SecEdit\\EnvironmentVariables
                
        """
    
        # Метаинформация о датасете
        infoTableData: dict = {
            'Name': self.__parameters.get('MODULENAME'),
            'Help': HELP_TEXT,
            'Timestamp': self.__parameters.get('CASENAME'),  # Время начала обработки - имя case
            'Vendor': 'LabFramework'
        }
        
        # Задать параметры вывода и создать таблицы
        outputWriter.SetFields(fields, self.__recordFields)
        outputWriter.CreateDatabaseTables()

        # Обработать профили и записать данные
        if self.__muiCacheParser is not None:
            self.__muiCacheParser.SetUserProfilesList(self.__parameters.get('USERPROFILES', {}))
            await self.__muiCacheParser.Start()

            # Удалить временные таблицы
            outputWriter.RemoveTempTables()
        
            # Создать индексы для быстрого поиска
            await outputWriter.CreateDatabaseIndexes(self.__parameters.get('MODULENAME'))
        
            # Завершить формирование БД (записать метаинформацию)
            outputWriter.SetInfo(infoTableData)
            outputWriter.WriteMeta()
            # Закрыть соединение БД
            await outputWriter.CloseOutput()
            
        return {self.__parameters.get('MODULENAME'): outputWriter.GetDBName()}


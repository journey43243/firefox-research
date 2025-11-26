# -*- coding: utf-8 -*-
"""
Модуль утилит для работы с файлами, реестром и базами данных

Этот модуль содержит набор вспомогательных классов и функций для:
- Работы с реестром Windows (чтение и парсинг)
- Конвертирования различных форматов временных меток (FILETIME, Unix, Cocoa)
- Чтения содержимого файлов (текстовые, бинарные, SQLite)
- Работы с базами данных SQLite (создание, чтение, запись)

Используется в качестве центрального модуля утилит по всему приложению.
"""

import os, io, re, regipy, shutil
import sqlite3
from enum import IntEnum
from construct import core
from abc import ABCMeta, abstractmethod
from typing import Any, AnyStr, List, Tuple, Dict, NoReturn, Optional
from datetime import datetime, timedelta, tzinfo 
from calendar import timegm

# ################################################################
# Константы для работы с временными форматами
# ################################################################

# Microsoft FILETIME: количество 100-наносекундных интервалов с 1.1.1601
UNIX_EPOCH_AS_FILETIME: int = 116444736000000000  # 1.1.1970 в FILETIME

# Разница между UnixEpoch и форматом Cocoa/WebKit (секунды с 1.1.2001)
COCOA_AT_UNIXEPOCH: int = 978307200

# Константы для работы со 100-наносекундными интервалами
HUNDREDS_OF_NANOSECONDS: int = 10000000
NANOSECONDS_DELIMITER: float = 1000000000.

# ################################################################
# КЛАССЫ ДЛЯ РАБОТЫ С РЕЕСТРОМ WINDOWS
# ################################################################
# Абстрактный обработчик файла-улья реестра
class _AbstractRegistryFileHandler():
    """
    Абстрактный базовый класс для работы с файлами реестра Windows.
    
    Этот класс определяет интерфейс для обработки файлов-ульев реестра Windows.
    Основная задача - управление копированием, загрузкой и удалением файлов реестра.
    
    Атрибуты:
        _fcr: Объект FileContentReader для работы с содержимым файлов
        _tempFolder: Путь к временной папке для хранения копий реестра
        _log: Объект логирования для записи событий
        _regHandle: Хэндл открытого файла реестра (regipy.registry.RegistryHive)
        _regFileFullPath: Полный путь к скопированному файлу реестра
        _storageRegFileFullPath: Полный путь к исходному файлу реестра
    """
    __metaclass__ = ABCMeta
    
    def __init__(self, tempFolder: str, log: Any):
        """
        Инициализирует абстрактный обработчик реестра.
        
        Args:
            tempFolder: Путь к временной папке для работы
            log: Объект для логирования (LogInterface)
        """
        # Входные параметры
        self._fcr: Any = FileContentReader()
        self._tempFolder: str = tempFolder
        self._log: Any = log
                
        self._regHandle: regipy.registry.RegistryHive = None
        self._regFileFullPath: str = None
        self._storageRegFileFullPath: str = None
        
    def __del__(self):
        """Деструктор: очищает ресурсы при удалении объекта."""
        self._regHandle = None
        self._storageRegFileFullPath = None
        
    def SetStorageRegistryFileFullPath(self, fullPath) -> NoReturn:
        """
        Устанавливает путь к исходному файлу реестра для обработки.
        
        Args:
            fullPath: Полный путь к файлу реестра в хранилище
        """
        self._storageRegFileFullPath = fullPath
    
    @abstractmethod
    def GetRegistryHandle(self):
        """
        Абстрактный метод для получения хэндла реестра.
        
        Подклассы должны переопределить этот метод для специфичной логики
        получения и обработки файла реестра.
        """
        pass

    def GetRegistryPath(self) -> AnyStr:
        """
        Возвращает полный путь к скопированному файлу реестра.
        
        Returns:
            Полный путь к локальной копии файла реестра
        """
        return self._regFileFullPath
        
    def _RemoveRegistryFile(self):
        """
        Удаляет временный файл реестра после обработки.
        
        Этот метод удаляет скопированный файл реестра из временной папки
        после того как его содержимое было загружено в памяти.
        """
        if self._regFileFullPath is not None:
            try:
                os.remove(self._regFileFullPath)
            except OSError as e:
                message = f'Файл не может быть удален: {e}!'
                self._log.Warn(f'_AbstractRegistryFileHandler._RemoveRegistryFile: ', message)

# ################################################################
# Обработчик файла-улья без изменений
# ################################################################
class RegistryFileHandler(_AbstractRegistryFileHandler):
    """
    Конкретная реализация обработчика файла реестра.
    
    Этот класс реализует логику для безопасной работы с файлами реестра:
    1. Копирует файл реестра из хранилища во временную папку
    2. Открывает скопированный файл с помощью regipy
    3. Удаляет временный файл (содержимое остаётся в памяти)
    
    Это позволяет избежать блокировки файла ОС и работать с ним безопасно.
    """
    
    def __init__(self, tempFolder: str, log: Any):
        """
        Инициализирует обработчик файла реестра.
        
        Args:
            tempFolder: Путь к временной папке
            log: Объект логирования
        """
        super().__init__(tempFolder, log)
             
    def GetRegistryHandle(self) -> Optional[regipy.registry.RegistryHive]:
        """
        Получает хэндл файла реестра.
        
        Процесс:
            1. Копирует файл реестра во временную папку
            2. Открывает скопированный файл с помощью regipy
            3. Удаляет временный файл (содержимое в памяти)
        
        Returns:
            Хэндл открытого файла реестра или None при ошибке
        """
        if self._storageRegFileFullPath is not None:
            # Сделать копию во временный каталог
            regFileName: str = self._storageRegFileFullPath.rsplit('\\', 1)[1]
            self._regFileFullPath = os.path.join(self._tempFolder, regFileName)
            shutil.copy(self._storageRegFileFullPath, self._regFileFullPath)
            
            # Передать файл реестра на вход regipy и получить хэндл
            try:
                self._regHandle = regipy.registry.RegistryHive(self._regFileFullPath)
            except (FileNotFoundError, PermissionError, BaseException):
                self._regHandle = None
                
        else:
            self._regHandle = None
            
        # Удалить копию файла реестра - содержимое считано в оперативку
        self._RemoveRegistryFile()     

        return self._regHandle

# ################################################################
# КЛАССЫ ДЛЯ РАБОТЫ С ВРЕМЕННЫМИ МЕТКАМИ
# ################################################################
# ################################################################
# КЛАССЫ ДЛЯ РАБОТЫ С ВРЕМЕННЫМИ МЕТКАМИ
# ################################################################
class UTC(tzinfo):
    """
    Класс, представляющий часовой пояс UTC (координированное универсальное время).
    
    Используется для создания объектов datetime с явным указанием UTC
    вместо локального времени.
    """
    
    def utcoffset(self, dt: datetime) -> timedelta:
        """Возвращает смещение UTC от GMT (всегда 0)."""
        return timedelta(0)

    def tzname(self, dt: datetime) -> AnyStr:
        """Возвращает наименование часового пояса."""
        return "UTC"

    def dst(self, dt: datetime) -> timedelta:
        """Возвращает смещение для летнего времени (в UTC нет)."""
        return timedelta(0)

# ################################################################
class FixedOffset(tzinfo):
    """
    Класс для представления фиксированного часового пояса.
    
    Используется для работы с временными метками в конкретных часовых поясах.
    Создаёт объект tzinfo на основе смещения в минутах от UTC.
    
    Пример:
        tz = FixedOffset(300, 'MSK')  # Московское время (UTC+5)
    """
    
    def __init__(self, offset: int, name: str):
        """
        Инициализирует часовой пояс.
        
        Args:
            offset: Смещение в минутах от UTC (положительное для восточнее UTC)
            name: Наименование часового пояса
        """
        if offset >= 0:
            self.__offset = timedelta(minutes=offset)
        else:
            self.__offset = timedelta(days=-1, minutes=24*60-abs(offset))
        self.__name = name
        
    def utcoffset(self, dt: datetime = None) -> timedelta:
        """Возвращает смещение этого часового пояса."""
        return self.__offset
    
    def tzname(self, dt: str = '') -> AnyStr:
        """Возвращает наименование часового пояса."""
        return self.__name
    
    def dst(self, dt = None) -> timedelta:
        """Возвращает смещение для летнего времени (не поддерживается)."""
        return timedelta(0)

# ################################################################
class TimeConverter():
    """
    Статический класс для конвертирования временных меток между различными форматами.
    
    Поддерживаемые форматы:
    - Unix timestamp: Секунды с 1.1.1970 UTC
    - FILETIME: 100-наносекундные интервалы с 1.1.1601 UTC (формат Windows)
    - Cocoa/WebKit: Секунды с 1.1.2001 UTC (формат macOS/iOS)
    - ISO format: Строка в формате ISO 8601
    - Software format: Кастомный формат приложения (YYYY.MM.DD HH:MM:SS)
    """
    
    @staticmethod
    def UnixTimestampToDatetime(unixTimestamp: int, addMicroseconds: bool = False) -> datetime:
        """
        Конвертирует Unix timestamp в объект datetime.
        
        Args:
            unixTimestamp: Количество секунд с 1.1.1970 UTC
            addMicroseconds: Если True, рассматривает микросекунды в timestamp
        
        Returns:
            Объект datetime с часовым поясом UTC
        """
        if not addMicroseconds:
            dtObj = datetime.fromtimestamp(unixTimestamp, UTC())
            return dtObj
        else:
            ts, micro = divmod(unixTimestamp, 1000000)
            dtObj = datetime.fromtimestamp(ts, UTC())
            dtObj.replace(microsecond=micro)
            return dtObj
    
    @staticmethod
    def DatetimeToFILETIME(datetimeObject) -> int:
        """
        Конвертирует объект datetime в FILETIME формат (Windows).
        
        FILETIME это 100-наносекундные интервалы с 1.1.1601 UTC.
        Если datetime без часового пояса, предполагается UTC.
        
        Примеры:
            DatetimeToFILETIME(datetime(2009, 7, 25, 23, 0))
            # 128930364000000000
            
            DatetimeToFILETIME(datetime(1970, 1, 1, 0, 0, tzinfo=UTC()))
            # 116444736000000000
        
        Args:
            datetimeObject: Объект datetime для конвертирования
        
        Returns:
            Число в формате FILETIME
        """
        if (datetimeObject.tzinfo is None) or (datetimeObject.tzinfo.utcoffset(datetimeObject) is None):
            datetimeObject = datetimeObject.replace(tzinfo=UTC())
        ft = UNIX_EPOCH_AS_FILETIME + (timegm(datetimeObject.timetuple()) * HUNDREDS_OF_NANOSECONDS)
        return ft + (datetimeObject.microsecond * 10)
    
    @staticmethod
    def FILETIMEToDatetime(FTtimestamp, tzInfoStruct=None) -> datetime:
        """
        Конвертирует FILETIME (Windows) в объект datetime.
        
        Конвертирует число FILETIME в объект Python datetime.
        Результирующий объект без часового пояса, но эквивалентен UTC.
        
        Примеры:
            FILETIMEToDatetime(116444736000000000)
            # datetime(1970, 1, 1, 0, 0)
            
            FILETIMEToDatetime(128930364000000000)
            # datetime(2009, 7, 25, 23, 0)
        
        Args:
            FTtimestamp: Число в формате FILETIME
            tzInfoStruct: Опциональная информация о часовом поясе
        
        Returns:
            Объект datetime
        """
        # Получить секунды и остаток в терминах Unix epoch
        (s, ns100) = divmod(FTtimestamp - UNIX_EPOCH_AS_FILETIME, HUNDREDS_OF_NANOSECONDS)
        # Конвертировать в объект datetime
        try:
            if tzInfoStruct is not None:
                dt = datetime.fromtimestamp(s, tz=tzInfoStruct)
            else:
                dt = datetime.fromtimestamp(s, tz=UTC())
        except OSError:
            dt = datetime.fromtimestamp(UNIX_EPOCH_AS_FILETIME, tz=UTC())
        # Добавить остаток как микросекунды
        dt = dt.replace(microsecond=(ns100 // 10))
        return dt
        
    @staticmethod
    def CocoaTimeToFILETIME(cocoaTimestamp,nanoSec=False) -> int:
        # ВО Cocoa это количество секунд(наносекунд) с 00:00 01.01.2001
        # cocoaDateTimeBase = datetime(2001,1,1)
        # unixDateTimeBase = datetime(1970,1,1)
        # delta = cocoaDateTimeBase - unixDateTimeBase
        delta = timedelta(seconds=COCOA_AT_UNIXEPOCH)

        if cocoaTimestamp not in (0, None, ''):
            if type(cocoaTimestamp) == str or\
                type(cocoaTimestamp) == float:
                cocoaTimestamp = int(cocoaTimestamp)
    
            if nanoSec:
                cocoaTimestamp = int(float(cocoaTimestamp)/NANOSECONDS_DELIMITER)
   
            cocoaDateTimeObj = datetime.fromtimestamp(timestamp=cocoaTimestamp,tz=UTC()) + delta

            return TimeConverter.DatetimeToFILETIME(cocoaDateTimeObj)
    
   
    @staticmethod
    def GetTimeInISOFormat(dt) -> AnyStr:
        """Конвертирует datetime в ISO 8601 формат."""
        return dt.isoformat()
    
    @staticmethod
    def GetTimeInSoftwareFormat(dt,microseconds=False) -> AnyStr:
        """Конвертирует datetime в формат приложения (YYYY.MM.DD HH:MM:SS)."""
        if not microseconds:
            return '{y}.{m}.{d} {HH}:{MM}:{SS}'.format(d = dt.day if dt.day > 9 else '0'+str(dt.day),
                                                       m = dt.month if dt.month > 9 else '0'+str(dt.month),
                                                       y = dt.year,
                                                       HH = dt.hour if dt.hour > 9 else '0'+str(dt.hour),
                                                       MM = dt.minute if dt.minute > 9 else '0'+str(dt.minute),
                                                       SS = dt.second if dt.second > 9 else '0'+str(dt.second))
        else:
            return '{y}.{m}.{d} {HH}:{MM}:{SS}.{mS}'.format(d = dt.day if dt.day > 9 else '0'+str(dt.day),
                                                            m = dt.month if dt.month > 9 else '0'+str(dt.month),
                                                            y = dt.year,
                                                            HH = dt.hour if dt.hour > 9 else '0'+str(dt.hour),
                                                            MM = dt.minute if dt.minute > 9 else '0'+str(dt.minute),
                                                            SS = dt.second if dt.second > 9 else '0'+str(dt.second),
                                                            mS = dt.microsecond)   

# ################################################################
# КЛАСС ДЛЯ РАБОТЫ С ФАЙЛАМИ
# ################################################################
class FileContentReader():
    """
    Статический класс для чтения содержимого различных типов файлов.
    
    Предоставляет методы для:
    - Проверки существования файлов
    - Чтения содержимого текстовых файлов (с кодировкой)
    - Чтения бинарного содержимого
    - Чтения файлов SQLite базы данных (включая WAL и SHM файлы)
    - Получения временных меток файлов (CREATE, MODIFY, ACCESS)
    """
    
    @staticmethod
    def IsExists(fullPath: str) -> bool:
        """
        Проверяет существование файла по указанному пути.
        
        Args:
            fullPath: Полный путь к файлу
        
        Returns:
            True если файл существует, False иначе
        """
        try:
            return os.path.exists(fullPath)
        except FileNotFoundError:
            return False
    
    @staticmethod
    def ListDir(folderFullPath: str) -> List:
        """
        Получает список файлов и папок в указанной директории.
        
        Args:
            folderFullPath: Полный путь к директории
        
        Returns:
            Список имён файлов и папок, или пустой список если папка не найдена
        """
        try:
            return os.listdir(folderFullPath)
        except FileNotFoundError:
            return []
    
    @staticmethod
    def GetSQLiteDBFileContent(folderPath: str, fileName: str = '', includeTimestamps: bool = True) -> Tuple:
        """
        Читает содержимое файла SQLite базы данных вместе с WAL и SHM файлами.
        
        SQLite может использовать дополнительные файлы:
        - .wal (Write-Ahead Log): Журнал для незафиксированных изменений
        - .shm (Shared Memory): Память для координации доступа
        
        Args:
            folderPath: Путь к папке с БД
            fileName: Имя файла БД (если пусто, используется folderPath как полный путь)
            includeTimestamps: Если True, получить временные метки файла
        
        Returns:
            Кортеж (timestamps_dict, dbFilePath, dbContent, shmContent, walContent)
            где timestamps_dict содержит 'CREATE', 'MODIFY', 'ACCESS'
        """
        result: tuple = None
        dbFilePath: str = None
        shmFilePath: str = None
        walFilePath: str = None
        dbContent: bytes = None
        shmContent: bytes = None
        walContent: bytes = None
        createTimeStampUTC:int = None
        modifyTimeStampUTC:int = None
        accessTimeStampUTC:int = None
               
        # Сформировать пути до файлов
        if fileName != '':
            dbFilePath = os.path.join(folderPath,fileName)
            shmFileName = f'{fileName}-shm'
            walFileName = f'{fileName}-wal'
            shmFilePath = os.path.join(folderPath,shmFileName) 
            walFilePath = os.path.join(folderPath,walFileName)
        else:
            dbFilePath = folderPath              
            shmFilePath = f'{folderPath}-shm'
            walFilePath = f'{folderPath}-wal'
            
        if includeTimestamps:
            try:
                # Получить временные отметки файла
                unixCTime = os.stat(dbFilePath).st_ctime
                unixMTime = os.stat(dbFilePath).st_mtime
                unixATime = os.stat(dbFilePath).st_atime
                createTimeStampUTC = TimeConverter.DatetimeToFILETIME(TimeConverter.UnixTimestampToDatetime(unixCTime))
                modifyTimeStampUTC = TimeConverter.DatetimeToFILETIME(TimeConverter.UnixTimestampToDatetime(unixMTime))
                accessTimeStampUTC = TimeConverter.DatetimeToFILETIME(TimeConverter.UnixTimestampToDatetime(unixATime))
            except FileNotFoundError:
                pass
            
        with open(dbFilePath,'rb') as dbf:
            try:
                dbContent = dbf.read()
            except FileNotFoundError:
                pass
        
        with open(shmFilePath,'rb') as shmf:
            try:
                shmContent = shmf.read()
            except FileNotFoundError:
                pass
        
        with open(walFilePath,'rb') as walf:
            try:
                walContent = walf.read()
            except FileNotFoundError:
                pass

   
        return ({'CREATE':createTimeStampUTC,
                   'MODIFY':modifyTimeStampUTC,
                   'ACCESS':accessTimeStampUTC},
                   dbFilePath,
                   dbContent,
                   shmContent,
                   walContent)
        
    @staticmethod
    def GetTextFileContent(folderPath:str,fileName:str='',encoding:str='utf-8',includeTimestamps:bool=True) -> Tuple:
        result:tuple = None 
        content:bytes = None
        createTimeStampUTC:int = None
        modifyTimeStampUTC:int = None
        accessTimeStampUTC:int = None
        records:dict = {}
        
        # Сформировать пути до файлов
        if fileName != '':
            filePath = os.path.join(folderPath,fileName)
        else:
            filePath = folderPath
        
        
        if includeTimestamps:
            try:
                # Получить временные отметки файла
                unixCTime = os.stat(filePath).st_ctime
                unixMTime = os.stat(filePath).st_mtime
                unixATime = os.stat(filePath).st_atime
                createTimeStampUTC = TimeConverter.DatetimeToFILETIME(TimeConverter.UnixTimestampToDatetime(unixCTime))
                modifyTimeStampUTC = TimeConverter.DatetimeToFILETIME(TimeConverter.UnixTimestampToDatetime(unixMTime))
                accessTimeStampUTC = TimeConverter.DatetimeToFILETIME(TimeConverter.UnixTimestampToDatetime(unixATime))
            except FileNotFoundError:
                pass
            
        with open(filePath,'rb') as f:
            try:
                content = f.read()
            except FileNotFoundError:
                pass
        
        if content is not None:
            # Буферизировать массив байт
            bufferedWrapper = io.TextIOWrapper(
                                    buffer = io.BytesIO(content),
                                    encoding = encoding,
                                    errors = 'ignore',
                                    line_buffering=True)
            
            # !!!! Костыль через словарь сделан в целях ускорения
            # !!!! Простое переключение элементов списка
            # !!!! работает в 3 раза дольше чем переключение ключа словаря
            buffLen = len(bufferedWrapper.readlines())
            bufferedWrapper.seek(0)
            for i in range(0,buffLen):
                readStr = bufferedWrapper.readline()
                if readStr != '':
                    records[i] = readStr
                if i >= buffLen:
                    break
                 
        return ({'CREATE':createTimeStampUTC,
                   'MODIFY':modifyTimeStampUTC,
                   'ACCESS':accessTimeStampUTC},
                   filePath,
                   records)
    
    @staticmethod
    def GetBinaryFileContent(folderPath:str,fileName:str='',includeTimestamps:bool=True) -> Tuple:
        result:tuple = None 
        content:bytes = None
        createTimeStampUTC:int = None
        modifyTimeStampUTC:int = None
        accessTimeStampUTC:int = None
        
        # Сформировать пути до файлов
        if fileName != '':
            filePath = os.path.join(folderPath,fileName)
        else:
            filePath = folderPath
        
        
        if includeTimestamps:
            try:
                # Получить временные отметки файла
                unixCTime = os.stat(filePath).st_ctime
                unixMTime = os.stat(filePath).st_mtime
                unixATime = os.stat(filePath).st_atime
                createTimeStampUTC = TimeConverter.DatetimeToFILETIME(TimeConverter.UnixTimestampToDatetime(unixCTime))
                modifyTimeStampUTC = TimeConverter.DatetimeToFILETIME(TimeConverter.UnixTimestampToDatetime(unixMTime))
                accessTimeStampUTC = TimeConverter.DatetimeToFILETIME(TimeConverter.UnixTimestampToDatetime(unixATime))
            except FileNotFoundError:
                pass
            
        with open(filePath,'rb') as f:
            try:
                content = f.read()
            except FileNotFoundError:
                pass
                 
        return ({'CREATE': createTimeStampUTC,
                'MODIFY': modifyTimeStampUTC,
                'ACCESS': accessTimeStampUTC},
                filePath,
                content)

# ################################################################
# КЛАССЫ ДЛЯ РАБОТЫ С SQLITE
# ################################################################
class SQLiteRAMProcessing(IntEnum):
    """
    Перечисление для управления обработкой SQLite базы данных в памяти.
    
    Значения:
        allowRAM (0): Разрешить обработку в оперативной памяти для ускорения
        noRAM (1): Всегда работать с файлом на диске (медленнее но экономнее по памяти)
    """
    allowRAM = 0  # Использовать RAM для обработки
    noRAM = 1  # Использовать только диск

# ################################################################
class _AbstractDatabaseClass():
    """
    Абстрактный базовый класс для работы с базами данных.
    
    Определяет минимальный интерфейс для операций с БД, который должны
    реализовать все конкретные классы для работы с различными типами БД.
    
    Эта абстрактная граница позволяет легко менять реализацию БД без
    изменения кода, который их использует.
    
    Атрибуты:
        _log (Any): Интерфейс для логирования ошибок
        _connection (sqlite3.Connection): Подключение к БД (будет инициализировано подклассом)
        _cursor (sqlite3.Cursor): Курсор для выполнения запросов
        _dbPath (str): Путь к файлу БД
        _cwd (str): Текущая рабочая директория
    """
    __metaclass__ = ABCMeta
    def __init__(self, dbPath, log):
        """
        Инициализирует абстрактный базовый класс БД.
        
        Args:
            dbPath (str): Путь к файлу БД или ':memory:' для БД в памяти
            log (Any): Интерфейс логирования для регистрации ошибок
        """
        self._log: Any = log
        self._connection: sqlite3.Connection = None
        self._cursor: sqlite3.Cursor = None
        self._dbPath: str = dbPath
        self._cwd: str = os.getcwd()
        
    @abstractmethod
    def __SetConnection(self) -> NoReturn:
        """Устанавливает подключение к БД (переопределяется подклассом)."""
        pass
    
    @abstractmethod
    def _SetCursor(self) -> NoReturn:
        """Создает курсор для выполнения запросов (переопределяется подклассом)."""
        pass
    
    @abstractmethod
    def ExecCommit(self, query: str, params: Any = '') -> NoReturn:
        """Выполняет SQL запрос и немедленно коммитит изменения."""
        pass
    
    @abstractmethod
    def Exec(self, query: str, params: Any = '') -> NoReturn:
        """Выполняет SQL запрос без коммита."""
        pass
    
    @abstractmethod    
    def Fetch(self, query: str, params: Any = '') -> List:
        """Выполняет SELECT запрос и возвращает все результаты."""
        pass
    
    @abstractmethod
    def Commit(self) -> NoReturn:
        """Коммитит все накопленные изменения."""
        pass
    
    @abstractmethod    
    def CloseConnection(self) -> NoReturn:
        """Закрывает подключение к БД."""
        pass
    
    def GetDatabasePath(self) -> AnyStr:
        """
        Возвращает путь к файлу БД.
        
        Returns:
            AnyStr: Путь к файлу БД
        """
        return self._dbPath

#----------------------------------------------------------------
class _AbstractLocalDatabaseClass(_AbstractDatabaseClass):
    """
    Абстрактный класс для локальных БД SQLite.
    
    Расширяет _AbstractDatabaseClass добавляя функциональность специфичную
    для работы с локальными файловыми БД SQLite:
    - PRAGMA настройки (foreign keys, journal mode, регистрозависимость)
    - Пользовательские SQL функции (LOWER, REGEXP)
    - Вспомогательные методы для проверки и создания структуры
    
    Этот класс все еще абстрактный и содержит реализацию общих операций,
    а конкретные подклассы переопределяют методы подключения.
    """
    __metaclass__ = ABCMeta
    def __init__(self, dbPath, log):
        """
        Инициализирует абстрактный локальный класс БД.
        
        Args:
            dbPath (str): Путь к файлу SQLite БД
            log (Any): Интерфейс логирования
        """
        super().__init__(dbPath, log)
     
    @abstractmethod
    def __SetConnection(self) -> NoReturn:
        """Подклассы должны реализовать создание подключения."""
        pass
    
    @abstractmethod
    def _SetCursor(self) -> NoReturn:
        """Подклассы должны реализовать создание курсора."""
        pass
    
    @abstractmethod
    def _SwitchOnForeignKeys(self) -> NoReturn:
        """Подклассы должны реализовать включение ограничений FK."""
        pass
   
    @abstractmethod
    def _SwitchOnCaseInsensitiveLike(self) -> NoReturn:
        """Подклассы должны реализовать настройку регистрозависимости LIKE."""
        pass
    
    def _RegExp(self, expr, item) -> Optional[re.Match]:
        """
        Вспомогательная функция для использования регулярных выражений в SQL.
        
        Используется через PRAGMA для добавления функции REGEXP() в SQL.
        Позволяет писать запросы типа: SELECT * WHERE field REGEXP 'pattern'
        
        Args:
            expr (str): Регулярное выражение (без учета регистра)
            item (Any): Строка для проверки
        
        Returns:
            Optional[re.Match]: Match объект если совпадение найдено, иначе None
        """
        reg = re.compile(expr, flags=re.I)
        return reg.search(str(item)) is not None
    
    def _Lower(self, value) -> AnyStr:
        """
        Вспомогательная функция для преобразования к нижнему регистру.
        
        Используется через PRAGMA для добавления функции LOWER() в SQL.
        
        Args:
            value (Any): Значение для преобразования
        
        Returns:
            AnyStr: Строка в нижнем регистре
        """
        return str(value).lower()
        
    def _AddLowerFunction(self) -> NoReturn:
        """
        Регистрирует пользовательскую функцию LOWER() в SQLite.
        
        После вызова этого метода можно использовать в SQL запросах:
            SELECT * WHERE LOWER(column) = 'lowercase'
        """
        if self._connection is not None:
            self._connection.create_function("LOWER", 1, self._Lower)
         
    def _AddRegExpSearch(self) -> NoReturn:
        """
        Регистрирует пользовательскую функцию REGEXP() в SQLite.
        
        После вызова этого метода можно использовать в SQL запросах:
            SELECT * WHERE column REGEXP 'pattern'
        """
        if self._connection is not None:
            self._connection.create_function("REGEXP", 2, self._RegExp)
    
    def ExecCommit(self, query: str, params: Any = '') -> NoReturn:
        """
        Выполняет SQL запрос и немедленно коммитит.
        
        Полезно для атомарных операций (INSERT, UPDATE, DELETE).
        
        Args:
            query (str): SQL запрос
            params (Any): Параметры для подстановки (защита от SQL injection)
        """
        try:
            self._cursor.execute(query, params)
            self._connection.commit()
        except sqlite3.OperationalError as e:
            message = f'Ошибка запроса к БД: {e}'
            self._log.Warn('_AbstractLocalDatabaseClass', message)
        
    def Fetch(self, query: str, params: Any = '') -> List:
        """
        Выполняет SELECT запрос и возвращает все результаты.
        
        Args:
            query (str): SQL SELECT запрос
            params (Any): Параметры для подстановки
        
        Returns:
            List: Список кортежей с результатами запроса, или пустой список при ошибке
        """
        try:
            self._cursor.execute(query, params)
            self._connection.commit()    
            return self._cursor.fetchall()
        except (sqlite3.OperationalError, sqlite3.ProgrammingError) as e:
            message = f'Ошибка запроса к БД: {e}'
            self._log.Warn('_AbstractLocalDatabaseClass', message)
            return []

    def Exec(self, query: str, params: Any = '') -> NoReturn:
        """
        Выполняет SQL запрос без коммита.
        
        Используется когда нужно выполнить несколько запросов перед коммитом
        или когда коммит будет выполнен позже.
        
        Args:
            query (str): SQL запрос
            params (Any): Параметры для подстановки
        """
        self._cursor.execute(query, params)
        
    def Commit(self) -> NoReturn:
        """
        Явно коммитит все накопленные изменения.
        
        Используется после серии Exec() вызовов.
        """
        self._connection.commit()
        
    @abstractmethod    
    def CloseConnection(self) -> NoReturn:
        """Подклассы должны реализовать закрытие подключения."""
        pass
    
    def _CheckCreateFolders(self) -> NoReturn:
        """
        Проверяет наличие всех необходимых каталогов для сохранения БД.
        
        Автоматически создает директории Cases/[CaseName]/ если их нет.
        Используется перед созданием БД на диске.
        
        Разбирает путь _dbPath на части:
        - Cases: Корневой каталог для всех дел
        - [CaseName]: Подкаталог для конкретного дела
        - [FileName]: Имя файла БД
        """
        itemsList = self._dbPath.rsplit('\\', 2)
        cases = itemsList[0]
        case = itemsList[1]

        # Проверяем последовательно каталоги
        if cases.find(':\\') == -1:
            cwdCases = os.path.join(self._cwd, cases)
            if not os.path.exists(cwdCases):                    
                os.mkdir(cwdCases)
            cwdCasesCase = os.path.join(cwdCases, case)
            if not os.path.exists(cwdCasesCase):                    
                os.mkdir(cwdCasesCase)
            
        else:
            cwdCases = cases
            if not os.path.exists(cwdCases):                    
                os.mkdir(cwdCases)
            cwdCasesCase = os.path.join(cwdCases,case)
            if not os.path.exists(cwdCasesCase):                    
                os.mkdir(cwdCasesCase)

#----------------------------------------------------------------
# Интерфейс для работы с имеющимися SQLite - только чтение
class SQLiteDatabaseInterfaceReader(_AbstractLocalDatabaseClass):
    """
    Интерфейс для чтения данных из существующей БД SQLite.
    
    Открывает существующую БД в режиме только чтения с необходимыми
    настройками для быстрого и безопасного доступа:
    - Foreign keys включены для целостности
    - Режим только чтения (query_only)
    - Case-insensitive LIKE для поисков
    - Пользовательские функции (REGEXP, LOWER)
    
    Предоставляет методы для извлечения информации о данных:
    - GetInfo(): Метаинформация о датасете
    - GetHeaders(): Описание колонок
    - GetRecordIdCache(): ID всех записей
    - IsRecords(): Проверка наличия данных
    """
    def __init__(self, dbPath, log): 
        """
        Инициализирует читатель БД.
        
        Args:
            dbPath (str): Путь к существующему файлу SQLite
            log (Any): Интерфейс логирования
        """
        super().__init__(dbPath, log)
               
        # Установить соединение из настроек и курсор        
        self._connection = self.__SetConnection()
        
        if self._connection is not None:
            self._cursor = self._SetCursor()
            self._SwitchOnForeignKeys()
            self._AddRegExpSearch()
            self._AddLowerFunction()
            self.__SwitchOnReadOnlyMode()
            self._SwitchOnCaseInsensitiveLike()
     

    def IsConnected(self) -> bool:
        """
        Проверяет, установлено ли подключение к БД.
        
        Returns:
            bool: True если подключение активно, иначе False
        """
        if self._connection is not None:
            return True
        else: 
            return False
    
    def _SetCursor(self) -> Optional[sqlite3.Cursor]:
        """
        Создает курсор для выполнения запросов.
        
        Returns:
            Optional[sqlite3.Cursor]: Новый курсор или None при ошибке
        """
        return self._connection.cursor()
    
    def __SetConnection(self) -> Optional[sqlite3.Connection]:
        """
        Устанавливает подключение к существующей БД SQLite.
        
        Returns:
            Optional[sqlite3.Connection]: Подключение или None при ошибке
        """
        try:
            if self._dbPath is not None:
                return sqlite3.connect(self._dbPath)
            else:
                # Ошибка задания параметров подключения к БД
                message = 'Имя файла БД задано неверно!'
                self._log.Error('DatabaseInterface.SQLiteDatabaseInterfaceReader.__SetConnection', message)
                return None
        except sqlite3.OperationalError:
                # Ошибка задания параметров подключения к БД
                message = 'Ошибка создания подключения к БД SQLite!'
                self._log.Error('DatabaseInterface.SQLiteDatabaseInterfaceReader.__SetConnection', message)
                return None
   
    def _SwitchOnForeignKeys(self) -> NoReturn:
        """Включает проверку ограничений внешних ключей."""
        self.ExecCommit('PRAGMA foreign_keys=on;', '')
        
    def __SwitchOnReadOnlyMode(self) -> NoReturn:
        """Переводит соединение в режим только чтения для безопасности."""
        self.ExecCommit('PRAGMA query_only=ON;', '')
        
    def _SwitchOnCaseInsensitiveLike(self) -> NoReturn:
        """Переводит оператор LIKE в режим, независимый от регистра."""
        self.ExecCommit('PRAGMA case_sensitive_like=off;', '')
        
    def _SwitchOnJournalModeMemory(self) -> NoReturn:
        """Устанавливает журнал транзакций в памяти (для производительности)."""
        self.ExecCommit('PRAGMA journal_mode=MEMORY;', '')    
                
    def GetInfo(self) -> Dict:
        """
        Читает метаинформацию о датасете из таблицы Info.
        
        Returns:
            Dict: Словарь с ключом Key и значением Value из таблицы Info
        """
        info = {}
        query = str('SELECT Key,Value FROM Info;')
        result = self.Fetch(query)
        for item in result:
            info.update({item[0]: item[1]})        
        return info
    
    def GetHeaders(self) -> List:
        """
        Читает описание колонок из таблицы Headers.
        
        Returns:
            List: Список кортежей (Name, Label, Width) для каждой колонки
        """
        query = 'SELECT Name,Label,Width FROM Headers;'
        return self.Fetch(query)
               
    def GetAmountOfRecords(self) -> int:
        """
        Возвращает общее количество записей в таблице Data.
        
        Returns:
            int: Количество записей
        """
        return self.Fetch('SELECT count(ID) FROM Data;')[0][0]
    
    def GetRecordIdCache(self) -> List:
        """
        Получает ID всех записей в порядке возрастания.
        
        Полезно для итерации по всем записям без загрузки самих данных.
        
        Returns:
            List: Список ID записей от меньшего к большему
        """
        return self.Fetch('SELECT ID FROM Data ORDER BY ID ASC;') 
        
    def IsRecords(self) -> bool:
        """
        Проверяет, содержит ли таблица Data какие-либо записи.
        
        Returns:
            bool: True если есть записи, иначе False
        """
        query = 'SELECT count(*) FROM Data;'
        try:
            rows = self.Fetch(query, '')[0][0]
            # Если есть данные
            if rows > 0:
                return True
            else:
                return False
        except IndexError:
            return False
        
    def CloseConnection(self) -> NoReturn:
        """
        Закрывает подключение к БД.
        
        После вызова этого метода подключение становится недействительным.
        """
        if self._connection is not None:
            self._connection.close()
            self._connection = None

#----------------------------------------------------------------
# Интерфейс для работы с новыми SQLite - чтение и запись
class SQLiteDatabaseInterface(SQLiteDatabaseInterfaceReader):
    """
    Полнофункциональный интерфейс для создания и работы с БД SQLite.
    
    Расширяет SQLiteDatabaseInterfaceReader добавляя возможности записи.
    Поддерживает две стратегии обработки:
    
    1. RAM Processing (внутри памяти):
       - Быстрая работа с данными
       - БД хранится в памяти (':memory:')
       - Результаты сохраняются на диск в конце (SaveSQLiteDatabaseFromRamToFile)
    
    2. Disk Processing (файловое хранилище):
       - БД сохраняется на диск сразу
       - Экономнее по памяти
       - Медленнее при большом объеме данных
    
    Используется модулями (Firefox, CompatibilityAssistant) для сохранения
    результатов извлечения.
    """
    def __init__(self, dbPath: str, log: Any, moduleName: str, moduleRAMProcessing: bool): 
        """
        Инициализирует интерфейс БД для чтения и записи.
        
        Args:
            dbPath (str): Путь к файлу БД (используется только если не RAM processing)
            log (Any): Интерфейс логирования
            moduleName (str): Имя модуля (для логирования)
            moduleRAMProcessing (bool): True для обработки в памяти, False для диска
        """
        super().__init__(dbPath, log)
        self.__moduleName: str = moduleName
        
        self._RAMProcessing: bool = moduleRAMProcessing
        # Установить соединение из настроек и курсор        
        self._connection = self.__SetConnection()
        
        if self._connection is not None:
            self._cursor = self._SetCursor()
            self._SwitchOnForeignKeys()
            self._AddRegExpSearch()
            self._AddLowerFunction()
            self.__SwitchOnAutoVacuum()
            self._SwitchOnCaseInsensitiveLike()

        
    def RemoveTempTables(self, tempTables: list) -> NoReturn:
        """
        Удаляет временные таблицы из БД.
        
        Используется для очистки после обработки данных.
        
        Args:
            tempTables (list): Список имен таблиц для удаления
        """
        for table in tempTables:
            self.ExecCommit(f'DROP TABLE {table};')
    
    def IsRAMAllocated(self):
        """
        Проверяет, используется ли обработка в памяти.
        
        Returns:
            bool: True если БД находится в памяти, иначе False
        """
        return self._RAMProcessing
    
    def __SetConnection(self) -> Optional[sqlite3.Connection]:
        """
        Устанавливает подключение в зависимости от режима обработки.
        
        Если RAMProcessing=True, создает БД в памяти (':memory:').
        Если RAMProcessing=False, создает файловую БД на диске.
        При ошибке создания каталога попытается создать папки.
        
        Returns:
            Optional[sqlite3.Connection]: Подключение или None при ошибке
        """
        # Установить соединение в зависимости от потребностей модуля в RAM
        if self._RAMProcessing:
            return sqlite3.connect(':memory:')
      
        else: 
            if self._dbPath is not None:
                try:
                    conn = sqlite3.connect(self._dbPath)
                except sqlite3.OperationalError: # ошибка подключения, проверить наличие каталога
                    try:
                        self._CheckCreateFolders()
                        conn = sqlite3.connect(database=self._dbPath,
                                                   timeout=3.0)  
                    except sqlite3.OperationalError: # нет БД      
                        conn = None
                    return conn
            else:
                # Ошибка задания параметров подключения к файлу БД
                message = 'Ошибка создания подключения к БД SQLite: Имя файла для сохранения БД задано неверно!'
                self._log.Error('DatabaseInterface.SQLiteDatabaseInterface.__SetConnection', message)
                return None

    def __SwitchOnAutoVacuum(self) -> NoReturn:
        """
        Включает автоматическую оптимизацию пространства БД.
        
        PRAGMA auto_vacuum=1 автоматически сокращает размер БД при удалении данных.
        """
        self.ExecCommit('PRAGMA auto_vacuum=1;', '')
               
    def IsDatabaseDumpAllowed(self) -> bool:
        """
        Проверяет, разрешено ли сохранение БД в файл.
        
        Returns:
            bool: True (заглушка, всегда разрешено)
        """
        return True  
      
    def SaveSQLiteDatabaseFromRamToFile(self) -> NoReturn:
        """
        Сохраняет БД из памяти на диск.
        
        Используется только когда RAMProcessing=True.
        Если БД уже на диске (RAMProcessing=False), метод ничего не делает.
        
        Процесс:
        1. Проверяет, что БД действительно в памяти
        2. Создает необходимые каталоги на диске
        3. Создает файловое подключение
        4. Копирует БД из памяти на диск через backup()
        5. Закрывает файловое подключение
        """
        if not self._RAMProcessing:
            # Если и так не в памяти обрабатывает данные
            return

        if self._connection is not None:
            self._CheckCreateFolders()
            fileDBConnection = sqlite3.connect(self._dbPath)
            self._connection.backup(fileDBConnection)
            fileDBConnection.close()
 

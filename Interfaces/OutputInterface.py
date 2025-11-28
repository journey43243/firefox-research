# -*- coding: utf-8 -*-
"""
Модуль интерфейса вывода данных

Этот модуль предоставляет абстрактные классы и конкретные реализации для
вывода данных в различные хранилища (в первую очередь SQLite БД).

Система написана с использованием абстрактного класса для разделения логики
вывода от деталей реализации хранилища.
"""

from abc import ABCMeta, abstractmethod
import itertools, sqlite3
from typing import Any, AnyStr, List, Tuple, Dict, NoReturn, Optional

# ################################################################
# Абстрактный класс для вывода информации
# ################################################################
class _AbstractOutputWriter():
    """
    Абстрактный базовый класс для записи данных в хранилище.
    
    Определяет интерфейс для вывода структурированных данных.
    Подклассы должны переопределить WriteMeta() для конкретного формата.
    
    Атрибуты:
        _caseName: Имя кейса (расследования)
        _caseFolder: Папка с результатами кейсов
        _moduleName: Имя модуля, который выводит данные
        _fieldsDescription: Описание полей таблицы
        _recordFields: Типы полей записи
        _fields: Кортеж имён полей
        _info: Метаинформация о данных
    """
    __metaclass__ = ABCMeta
    
    def __init__(self, paths: dict):
        """
        Инициализирует абстрактный писатель.
        
        Args:
            paths: Словарь с параметрами:
                - CASENAME: Имя кейса
                - CASEFOLDER: Папка с кейсами
                - MODULENAME: Имя модуля
        """
        self._caseName: str = paths.get('CASENAME', '')
        self._caseFolder: str = paths.get('CASEFOLDER', '')
        self._moduleName: str = paths.get('MODULENAME', '')
        
        self._fieldsDescription: dict = None
        self._recordFields: dict = None
        self._fieldsStr: str = ''
        self._fields: tuple = None
        
        self._info: dict = None
        
    def SetFields(self, fieldsDescription: dict, recordFields: dict) -> NoReturn:
        """
        Устанавливает описание и типы полей данных.
        
        Args:
            fieldsDescription: Словарь с описанием каждого поля
            recordFields: Словарь с типами данных полей
        """
        self._fieldsDescription = fieldsDescription
        self._recordFields = recordFields
        self._fieldsStr = ','.join(tuple(recordFields.keys()))
        self._fields = tuple(recordFields.keys())
        
    def SetInfo(self, info: dict) -> NoReturn:
        """
        Устанавливает метаинформацию о данных.
        
        Args:
            info: Словарь с метаинформацией
        """
        self._info = info
     
    @abstractmethod
    def WriteMeta(self) -> NoReturn:
        """
        Абстрактный метод для записи метаинформации.
        
        Подклассы должны переопределить этот метод для записи
        метаданных в конкретное хранилище.
        """
        pass

# ################################################################
# Конкретная реализация для SQLite БД
# ################################################################
class SQLiteDBOutputWriter(_AbstractOutputWriter):
    """
    Писатель для вывода данных в SQLite базу данных.
    
    Реализует логику для создания таблиц, записи записей и создания
    индексов в SQLite БД. Поддерживает временные таблицы для промежуточных
    данных и их удаление после обработки.
    
    Атрибуты:
        _dbConnection: Подключение к SQLite БД
        _dbName: Имя файла БД
        _tempTables: Список временных таблиц для удаления
    """
    
    def __init__(self, paths: dict):
        """
        Инициализирует писателя для SQLite.
        
        Args:
            paths: Словарь с параметрами (см. _AbstractOutputWriter)
                   плюс DBNAME: Имя файла базы данных
        """
        super().__init__(paths)
        self._dbConnection: sqlite3.Connection = None
        self._dbName: str = paths.get('DBNAME', '')
        self._tempTables: list = []
        
    def SetDBConnection(self, conn: sqlite3.Connection) -> NoReturn:
        """
        Устанавливает подключение к базе данных.
        
        Args:
            conn: Объект подключения SQLiteDatabase Interface
        """
        self._dbConnection = conn
    
    def GetDBName(self) -> AnyStr:
        """
        Возвращает имя файла базы данных.
        
        Returns:
            Имя файла БД
        """
        return self._dbName
    
    def GetDBConnection(self) -> Optional[sqlite3.Connection]:
        """
        Возвращает подключение к базе данных.
        
        Returns:
            Объект подключения или None
        """
        return self._dbConnection
    
    def AddTempTable(self, tableName: str) -> NoReturn:
        """
        Добавляет имя временной таблицы в список для удаления.
        
        Args:
            tableName: Имя таблицы для удаления
        """
        self._tempTables.append(tableName)
    
    def RemoveTempTables(self) -> NoReturn:
        """Удаляет все временные таблицы из БД."""
        for table in self._tempTables:
            query = str('DROP TABLE ' + str(table) + ';')
            self._dbConnection.ExecCommit(query)
        self._tempTables.clear()
        
    def CommitRecords(self) -> NoReturn:
        """Фиксирует все текущие изменения в БД."""
        self._dbConnection.Commit()

    def CreateDatabaseTables(self) -> NoReturn:
        """
        Создаёт необходимые таблицы в БД.
        
        Создаёт три таблицы:
        1. Data: Основная таблица с данными
        2. Headers: Описание колонок
        3. Info: Метаинформация о данных
        """
        # Cоздать таблицы в БД
        if self._dbConnection is None:
            return

        # Таблица данных с динамическими полями
        query = 'CREATE TABLE IF NOT EXISTS Data (ID INTEGER PRIMARY KEY AUTOINCREMENT, '
        for k, v in self._recordFields.items():
            query = f'{query}{k} {v},'
        
        query = query.rstrip(',')
        query = f'{query});'

        self._dbConnection.ExecCommit(query, '') 
        
        # Таблица заголовков полей (описание колонок)
        self._dbConnection.ExecCommit(
                    'CREATE TABLE IF NOT EXISTS Headers ('
                    'ID INTEGER PRIMARY KEY AUTOINCREMENT, '
                    'Name TEXT NOT NULL, '
                    'Label TEXT, '
                    'Width INTEGER, '
                    'DataType TEXT, '
                    'Comment TEXT)', '')
        
        # Таблица с информацией о массиве данных
        self._dbConnection.ExecCommit(
                    'CREATE TABLE IF NOT EXISTS Info ('
                    'ID INTEGER PRIMARY KEY AUTOINCREMENT, '
                    'Key TEXT NOT NULL, '
                    'Value TEXT)', '')
        

    async def CreateDatabaseIndexes(self, moduleName: str) -> NoReturn:
        """
        Создаёт индексы на колонки для ускорения поиска.
        
        Индексы создаются на все поля основной таблицы.
        
        Args:
            moduleName: Имя модуля (для логирования)
        """
        if self._dbConnection is None:
            return
        
        # Создать индексы
        lenKeys = len(tuple(self._recordFields.keys()))
        if self._dbConnection.IsRecords():
            for i, key in enumerate(self._recordFields.keys()):
                self._dbConnection.ExecCommit(f'CREATE INDEX idx_{key.lower()} ON Data({key});')

            
    def UpdateDataSource(self, prevDS: str, checkResult: Any, autoCommit: bool = False) -> NoReturn:
        """
        Обновляет источник данных для существующей записи.
        
        Args:
            prevDS: Предыдущее значение источника
            checkResult: Результат проверки (индекс и новый источник)
            autoCommit: Автоматически зафиксировать изменения
        """
        if self._dbConnection is None:
            return

        if checkResult is not None:
            idx = checkResult[0]
            source = checkResult[1]
            # Объединить источники и удалить дубли
            newSource = ',\n'.join(set(list(itertools.chain.from_iterable([prevDS.split(',\n'), source.split(',\n')]))))

            updQuery = f'UPDATE Data Set DataSource = "{newSource}" WHERE ID = {idx};'
    
            if autoCommit is False:
                self._dbConnection.Exec(updQuery)
            else:
                self._dbConnection.ExecCommit(updQuery)
        
                
    def WriteRecord(self, recordInfo: tuple, autoCommit: bool = False) -> NoReturn:
        """
        Записывает одну запись в таблицу Data.
        
        Args:
            recordInfo: Кортеж с данными записи (должен соответствовать порядку полей)
            autoCommit: Автоматически зафиксировать изменения
        """
        if self._dbConnection is None:
            return

        query = str('INSERT INTO Data('
                    f'{self._fieldsStr}'
                    ') VALUES (' +
                    str('?,' * len(self._recordFields.keys())).rstrip(',') + 
                    ');')

        if autoCommit is False:
            self._dbConnection.Exec(query, recordInfo)
        else:
            self._dbConnection.ExecCommit(query, recordInfo)
       
    def WriteMeta(self) -> NoReturn:
        """
        Записывает метаинформацию в таблицы Headers и Info.
        
        Заполняет таблицы с описанием полей и параметрами выводимых данных.
        """
        if self._dbConnection is None:
            return
        
        # Заполнить таблицы Headers и Info
        for key in self._fieldsDescription.keys():
            headersQuery = str('INSERT INTO Headers('
                           'Name,Label,Width,DataType,Comment) '
                           f'VALUES("{str(key)}",'
                           f'"{self._fieldsDescription[key][0]}",'
                           f'{self._fieldsDescription[key][1]},'
                           f'"{self._fieldsDescription[key][2]}",'
                           f'"{self._fieldsDescription[key][3]}");')

            self._dbConnection.ExecCommit(headersQuery)

        for key in self._info.keys():
            infoQuery = str('INSERT INTO Info(Key,Value) VALUES('
                            f'"{str(key)}",'
                            f'"{str(self._info.get(key))}");')

            self._dbConnection.ExecCommit(infoQuery)
           
            
    async def CloseOutput(self) -> NoReturn:   #!!!! Д.б. async coroutine
        # Закрыть соединение с БД с учетом, что она могла быть в памяти
        if self._dbConnection.IsConnected():
            self.CommitRecords()
            if self._dbConnection.IsDatabaseDumpAllowed():  
                if self._dbConnection.IsRecords():
                    if self._dbConnection.IsRAMAllocated():
                        self._dbConnection.SaveSQLiteDatabaseFromRamToFile()
                    self._dbConnection.CloseConnection()
                else:
                    self._dbConnection.CloseConnection()

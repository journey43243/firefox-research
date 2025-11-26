# -*- coding: utf-8 -*-
"""
Модуль динамической загрузки и координации модулей обработки

Этот модуль содержит класс Solver, который отвечает за динамическую загрузку
модулей обработки данных (Firefox, CompatibilityAssistant и т.д.) из директории
Modules/ и координирует их выполнение.

Solver является архитектурным связующим звеном между главным интерфейсом приложения
(Interface) и отдельными модулями обработки. Он:
1. Открывает все поддиректории Modules/
2. Для каждого модуля динамически загружает Parser.py
3. Создает подключение БД и интерфейс вывода
4. Запускает асинхронный метод Start() модуля
5. Сохраняет результаты в отдельные файлы SQLite

Типичный поток вызовов:
    Interface.Run() → Solver.__init__() → Solver.Start() → _ProcessTask() → Parser.Start() → Strategies
"""
import importlib, os
import importlib.util as util


from typing import Optional, Callable, Any, List, NoReturn, Awaitable

from Common.Routines import FileContentReader, SQLiteDatabaseInterface, RegistryFileHandler
from Interfaces.OutputInterface import SQLiteDBOutputWriter

#----------------------------------------------------------------
class Solver():
    """
    Динамический загрузчик и координатор модулей обработки.
    
    Отвечает за:
    - Обнаружение всех модулей в директории Modules/
    - Динамическую загрузку файлов Parser.py из каждого модуля
    - Создание БД и интерфейсов вывода для каждого модуля
    - Асинхронное выполнение каждого модуля
    - Сбор результатов
    
    Параметры для модулей (передаются в Parser):
    - TEMP: Каталог временных файлов
    - LOG: Интерфейс логирования
    - CASEFOLDER: Каталог с делами
    - CASENAME: Имя текущего дела (временная метка)
    - UIREDRAW: Callback для обновления UI
    - STORAGE: Путь к источнику данных (Source/)
    - REGISTRYFILEHANDLER: Обработчик реестра Windows
    - MODULENAME: Имя модуля
    - OUTPUTFILENAME: Имя файла результатов (модуль_result.sqlite)
    - RAMPROCESSING: Флаг использования обработки в оперативной памяти
    - DBCONNECTION: Подключение к БД для записи результатов
    - OUTPUTWRITER: Интерфейс для записи данных
    """   
    def __init__(self, settings: dict, appStartDateTime: str, interfaces: dict, dataSourcePath: str, outputFileName: str):
        """
        Инициализирует Solver с параметрами приложения и окружением.
        
        Args:
            settings (dict): Словарь с параметрами из Settings.json
                - 'CaseFolder': Директория для сохранения результатов дел
                - 'TemporaryFilesFolder': Директория временных файлов
            appStartDateTime (str): Временная метка запуска приложения (используется как имя дела)
            interfaces (dict): Словарь интерфейсов приложения
                - 'LOGGER': Интерфейс для логирования
            dataSourcePath (str): Путь к папке Source с исходными данными
            outputFileName (str): Базовое имя для файлов результатов
        """  
        self._cwd: str = os.getcwd()
        
        # Настройки приложения из Settings.json
        self._settings: dict = settings
        
        # Асинхронный метод для обновления UI (может переопределяться)
        self._redrawUIMethod: Awaitable = self.RedrawUI
        
        # Интерфейс для логирования информации и ошибок
        self._log: Any = interfaces.get('LOGGER')
        
        # Утилита для чтения содержимого файлов
        self._fcr: FileContentReader = FileContentReader()
        
        # Каталог для временных файлов (из Settings.json, обычно 'Temp')
        self._tempFolder: str = self._settings.get('TemporaryFilesFolder')
        
        # Обработчик для работы с файлами реестра Windows
        self._rfh: Any = RegistryFileHandler(self._tempFolder, self._log)

        # Имя текущего дела (case) - обычно временная метка запуска
        self._caseName: str = appStartDateTime
        
        # Каталог, где сохраняются результаты дел (обычно 'Cases')
        self._caseFolder: str = self._settings.get('CaseFolder')
        
        # Базовая часть имени файла результатов (обычно 'result.sqlite')
        self._outputFileNameBasePart: str = outputFileName
        
        
        # Словарь параметров, которые будут переданы каждому модулю
        # Модули могут расширять этот словарь своими параметрами
        self._moduleParameters: dict = {
            'TEMP': self._tempFolder,
            'LOG': self._log,
            'CASEFOLDER': self._caseFolder,
            'CASENAME': self._caseName,
            'UIREDRAW': self._redrawUIMethod,
            'STORAGE': dataSourcePath,
            'REGISTRYFILEHANDLER': self._rfh
        }
    
    async def RedrawUI(self, message: str, percent: int) -> NoReturn:
        """
        Callback для обновления пользовательского интерфейса.
        
        Переопределяется модулями для вывода информации о ходе выполнения.
        В базовой реализации просто выводит в консоль.
        
        Args:
            message (str): Сообщение о текущем статусе
            percent (int): Процент выполнения (0-100)
        """
        print(message,percent)
        
    async def _ProcessTask(self, modulePath: str, moduleName: str) -> Optional[List]:
        """
        Динамически загружает и выполняет модуль обработки.
        
        Этот приватный метод отвечает за:
        1. Динамическую загрузку Parser.py из модуля (используя importlib.util)
        2. Создание экземпляра класса Parser с параметрами модуля
        3. Асинхронный вызов метода Parser.Start()
        4. Обработку ошибок импорта и модуля
        
        Args:
            modulePath (str): Полный путь к директории модуля (например, Modules/Firefox)
            moduleName (str): Имя файла модуля (обычно 'Parser.py')
        
        Returns:
            Optional[List]: Результаты работы модуля (словарь с outputFileName) или None при ошибке
            
        Raises:
            ImportError: Если при импорте модуля возникла ошибка зависимостей
            ModuleNotFoundError: Если модуль Parser.py не найден
        """
        # Загрузить модуль
        try:
            spec = util.spec_from_file_location(name='Parser', location=os.path.join(modulePath,moduleName))
            if spec is not None: # если модуль найден
                module = util.module_from_spec(spec)
                execResult = spec.loader.exec_module(module)
                moduleInstance = module.Parser(self._moduleParameters)
                output = await moduleInstance.Start()
                return output
            else:
                return None
                
        except ImportError as ie:
            message = f'Импорт внутри динамического модуля завершился ошибкой: {ie}!'
            self._log.Error(f'Solver.ProcessTask: {os.path.join(modulePath,moduleName)}',message)
            return None
        
        except ModuleNotFoundError as mnfe:
            message = f'Ошибка импорта - модуль не найден: {mnfe} !'
            self._log.Error(f'Solver.ProcessTask: {os.path.join(modulePath,moduleName)}',message)
            return None
            

    async def Start(self) -> NoReturn:
        """
        Главный асинхронный метод выполнения Solver.
        
        Процесс выполнения:
        1. Получает список всех поддиректорий в Modules/
        2. Для каждого модуля:
           a. Обновляет параметры модуля (MODULENAME, OUTPUTFILENAME)
           b. Создает SQLiteDatabaseInterface для результатов
           c. Создает SQLiteDBOutputWriter интерфейс
           d. Вызывает _ProcessTask для загрузки и запуска Parser
           e. Вызывает UI callback с результатом
        3. Каждый модуль сохраняет результаты в отдельный SQLite файл
        
        Поток данных:
            Modules/Firefox/Parser.py → SQLiteDBOutputWriter → Cases/[CaseName]/Firefox_result.sqlite
            Modules/CompatibilityAssistant/Parser.py → ... → Cases/[CaseName]/CompatibilityAssistant_result.sqlite
        """
        modulesPath:str = os.path.join(self._cwd,'Modules')
        
        modules:list = self._fcr.ListDir(modulesPath)
        for item in modules:
            moduleFullPath = os.path.join(self._cwd,'Modules',item)
        
            # Параметры модуля   
            self._moduleParameters.update({'MODULENAME':item})
            self._moduleParameters.update({'OUTPUTFILENAME':f'{item}_{self._outputFileNameBasePart}'})
            self._moduleParameters.update({'RAMPROCESSING':True})
        
            # Соединение с БД и интерфейс вывода информации
            dbConnection = SQLiteDatabaseInterface(
                os.path.join(self._caseFolder,self._caseName,self._moduleParameters['OUTPUTFILENAME']),
                self._log,
                item,
                self._moduleParameters['RAMPROCESSING']
                )
            
            outputWriter = SQLiteDBOutputWriter(
                {'DBNAME':self._moduleParameters['OUTPUTFILENAME'],
                'CASENAME':self._moduleParameters.get('CASENAME'),
                'CASEFOLDER':self._moduleParameters.get('CASEFOLDER'),
                'MODULENAME':item}
                )
            
            outputWriter.SetDBConnection(dbConnection)

            self._moduleParameters.update({'DBCONNECTION':dbConnection})
            self._moduleParameters.update({'OUTPUTWRITER':outputWriter})
            
            moduleResult = await self._ProcessTask(moduleFullPath,'Parser.py')
            
            await self._redrawUIMethod(f'Завершена работа модуля: {moduleResult}',100)
        
        
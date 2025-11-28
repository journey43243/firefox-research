# -*- coding: utf-8 -*-
"""
Модуль интерфейса логирования

Этот модуль предоставляет единый интерфейс для логирования всех событий,
ошибок и предупреждений приложения. Использует встроенный модуль logging
для записи сообщений в файл с временными метками и уровнями серьёзности.

Все сообщения логируются в файл с именем, соответствующим времени запуска
приложения для удобства отладки и анализа работы.
"""

import os
import logging
import traceback

# ################################################################
class LogInterface():
    """
    Интерфейс логирования приложения.
    
    Обеспечивает единую точку для логирования событий во всём приложении.
    Записывает все сообщения в файл с форматированием (время, уровень, источник, сообщение).
    
    Атрибуты:
        __logPath: Полный путь к файлу логов
    """
    
    def __init__(self, appStartDateTime: str):
        """
        Инициализирует интерфейс логирования.
        
        Создаёт файл логов в папке Logs с именем, основанным на времени запуска.
        Все логирующие методы используют этот файл для записи.
        
        Args:
            appStartDateTime: Строка с временем запуска приложения (используется в имени файла)
        """
        self.__logPath = os.path.join(os.getcwd(), 'Logs', f'{appStartDateTime}.log')  
        logging.basicConfig(level=logging.INFO,
                            filename=self.__logPath,
                            filemode='w',
                            format='%(asctime)s___%(levelname)s___%(message)s')

    def Error(self, sourceName, message):
        """
        Логирует ошибку.
        
        Args:
            sourceName: Имя компонента, который выдал ошибку
            message: Текст ошибки
        """
        logging.error(f'{sourceName}: {message}')
        
    def Warn(self, sourceName, message):
        """
        Логирует предупреждение.
        
        Args:
            sourceName: Имя компонента, который выдал предупреждение
            message: Текст предупреждения
        """
        logging.warning(f'{sourceName}: {message}')
        
    def Info(self, sourceName, message):
        """
        Логирует информационное сообщение.
        
        Args:
            sourceName: Имя компонента, который выдал сообщение
            message: Текст сообщения
        """
        logging.info(f'{sourceName}: {message}')
            
    @staticmethod
    def DeathRattle(exc_type, exc_value, exc_traceback):
        """
        Обработчик непойманных исключений приложения.
        
        Вызывается при возникновении необработанного исключения.
        Логирует полную информацию об ошибке и выводит её на консоль.
        
        Args:
            exc_type: Тип исключения
            exc_value: Значение исключения
            exc_traceback: Трассировка стека вызовов
        """
        logging.error('UNCAUGHT EXCEPTION IN MODULE!',
                      exc_info=(exc_type, exc_value, exc_traceback))
        
        print('UNCAUGHT EXCEPTION IN MODULE!')
        print((exc_type, exc_value))
        print(''.join(traceback.format_tb(exc_traceback)))
        
# -*- coding: utf-8 -*-
"""
Определение структуры SACP для разбора бинарных данных

Структура SACP (Signature ACCP) используется в ветке Store реестра Windows 8.1+
для хранения информации о совместимости приложений с временными метками.

Формат структуры (всего 48 байт):
    Офсет  | Размер | Тип        | Описание
    -------|--------|------------|------------------------------------------
    0-3    | 4      | uint32     | Сигнатура: 0x53 0x41 0x43 0x50 (SACP)
    4-43   | 40     | uint8[40]  | Неопределенные данные (не полностью изучены)
    44-51  | 8      | uint64     | Временная метка в формате FILETIME (UTC)

Пример использования:
    import ctypes
    value = bytearray(item.value)
    sacpStruct = SACPStructure.from_buffer_copy(value)
    timestamp = sacpStruct.timestamp  # FILETIME (100-ns intervals from 1601-01-01)
"""
import ctypes


class SACPStructure(ctypes.Structure):
    """
    Структура для парсинга бинарного формата SACP из реестра Windows.
    
    Используется ctypes для прямого отображения памяти на Python объект.
    
    Параметры ctypes:
        _pack_ = 1: Отключает выравнивание полей, работает как #pragma pack(1) в C
        _fields_: Определение полей структуры (имя, тип)
    
    Поля:
        signature (uint32): Сигнатура SACP для проверки целостности (0x40435341)
        smth1 (uint8[40]): Неизвестные данные (пока не полностью изучены разработчиками)
        timestamp (uint64): Временная метка в формате FILETIME (100-наносекундные интервалы от 1601-01-01)
    
    Пример парсинга:
        >>> value = bytearray(item.value)
        >>> sacpStruct = SACPStructure.from_buffer_copy(value)
        >>> print(f"Сигнатура: 0x{sacpStruct.signature:08X}")
        Сигнатура: 0x40435341
        >>> print(f"Временная метка: {sacpStruct.timestamp}")
        Временная метка: 132145678901234567
    """
    _pack_ = 1  # Убирает выравнивание полей структуры (как #pragma pack(1) в C)
    _fields_ = [
        ("signature", ctypes.c_uint),          # Сигнатура SACP (4 байта): 0x40435341
        ("smth1", ctypes.c_ubyte * 40),        # Неизвестные данные (40 байт)
        ("timestamp", ctypes.c_ulonglong)      # Временная метка FILETIME (8 байт)
    ]
    
    """
    Примечание: Структура может содержать дополнительные поля, которые еще не изучены.
    Если при парсинге возникают странные значения, это может быть связано с
    неполным пониманием структуры в новых версиях Windows.
    """ 


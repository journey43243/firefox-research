"""
Модуль сервиса расшифровки паролей Firefox

Этот модуль реализует функциональность для расшифровки паролей, хранящихся
в Firefox. Использует NSS (Network Security Services) для работы с криптографией.

NSS - это библиотека, которую использует Firefox для шифрования чувствительных данных.
На Windows требуется nss3.dll, на Linux требуется libnss3.so
"""

import os
import sys
import json
import ctypes as ct
from base64 import b64decode
from getpass import getpass
from typing import List, Dict, Optional, Any

from Common.Routines import SQLiteDatabaseInterfaceReader

# ################################################################
class SECItem(ct.Structure):
    """
    Структура NSS для представления элемента безопасности.
    
    Используется для передачи данных в функции NSS.
    
    Атрибуты:
        type: Тип элемента
        data: Указатель на данные
        len: Длина данных
    """
    _fields_ = [("type", ct.c_uint), ("data", ct.c_char_p), ("len", ct.c_uint)]

    def decode_data(self):
        """
        Декодирует данные из структуры в строку.
        
        Пытается декодировать как UTF-8, при ошибке использует 'replace' стратегию.
        
        Returns:
            Декодированная строка или байты при ошибке декодирования
        """
        _bytes = ct.string_at(self.data, self.len)
        try:
            return _bytes.decode("utf-8")
        except Exception:
            return _bytes.decode(errors="replace")

# ################################################################
class NSSWrapper:
    """
    Обёртка для взаимодействия с NSS библиотекой Firefox.
    
    Загружает nss3.dll/libnss3.so, инициализирует профиль и выполняет
    расшифровку паролей. Обрабатывает кроссплатформенность.
    
    На Windows: ищет nss3.dll в папке Firefox
    На Linux: ищет libnss3.so в стандартных местоположениях
    На macOS: ищет libnss3.dylib в папке Firefox.app
    """
    
    def __init__(self):
        """
        Инициализирует обёртку NSS.
        
        Загружает соответствующую NSS библиотеку для текущей ОС и устанавливает
        прототипы функций.
        
        Raises:
            RuntimeError: Если NSS библиотека не найдена
        """
        self.lib = self._load_lib()
        self._setup_prototypes()

    def _load_lib(self) -> ct.CDLL:
        """
        Загружает NSS библиотеку для текущей ОС.
        
        Проверяет стандартные местоположения для каждой ОС.
        
        Returns:
            Загруженная CDLL библиотека
        
        Raises:
            RuntimeError: Если библиотека не найдена ни в одном местоположении
        """
        candidates = []
        if sys.platform.startswith("win"):
            candidates += [
                r"C:\Program Files\Mozilla Firefox\nss3.dll",
                r"C:\Program Files (x86)\Mozilla Firefox\nss3.dll",
            ]
        elif sys.platform == "darwin":
            candidates += ["/Applications/Firefox.app/Contents/MacOS/libnss3.dylib"]
        else:
            candidates += ["/usr/lib/libnss3.so", "/usr/lib64/libnss3.so"]

        for c in candidates:
            if os.path.isfile(c):
                try:
                    return ct.CDLL(c)
                except OSError:
                    continue

        raise RuntimeError("Could not load NSS library (nss3.dll/libnss3.so not found)")

    def _setup_prototypes(self):
        """
        Устанавливает прототипы функций NSS.
        
        Определяет типы аргументов и возвращаемых значений для всех
        используемых функций NSS.
        """
        self.lib.NSS_Init.argtypes = [ct.c_char_p]
        self.lib.NSS_Init.restype = ct.c_int

        self.lib.NSS_Shutdown.argtypes = []
        self.lib.NSS_Shutdown.restype = ct.c_int

        self.lib.PK11_GetInternalKeySlot.argtypes = []
        self.lib.PK11_GetInternalKeySlot.restype = ct.c_void_p

        self.lib.PK11_FreeSlot.argtypes = [ct.c_void_p]
        self.lib.PK11_FreeSlot.restype = None

        self.lib.PK11_NeedLogin.argtypes = [ct.c_void_p]
        self.lib.PK11_NeedLogin.restype = ct.c_int

        self.lib.PK11_CheckUserPassword.argtypes = [ct.c_void_p, ct.c_char_p]
        self.lib.PK11_CheckUserPassword.restype = ct.c_int

        self.lib.PK11SDR_Decrypt.argtypes = [ct.POINTER(SECItem), ct.POINTER(SECItem), ct.c_void_p]
        self.lib.PK11SDR_Decrypt.restype = ct.c_int

        self.lib.SECITEM_ZfreeItem.argtypes = [ct.POINTER(SECItem), ct.c_int]
        self.lib.SECITEM_ZfreeItem.restype = None

    def init_profile(self, path: str):
        """
        Инициализирует NSS с профилем Firefox.
        
        Args:
            path: Путь к папке профиля Firefox
        
        Raises:
            RuntimeError: Если инициализация не удалась
        """
        rc = self.lib.NSS_Init(f"sql:{path}".encode())
        if rc:
            raise RuntimeError(f"NSS_Init failed: {rc}")

    def shutdown(self):
        """Завершает работу NSS."""
        try:
            self.lib.NSS_Shutdown()
        except Exception:
            pass

    def authenticate(self, interactive=True):
        """
        Проходит аутентификацию в NSS (вводит главный пароль если требуется).
        
        Args:
            interactive: Если True, запрашивает пароль с консоли, иначе использует пустой
        
        Raises:
            RuntimeError: Если не удалось получить слот ключей или неверный пароль
        """
        slot = self.lib.PK11_GetInternalKeySlot()
        if not slot:
            raise RuntimeError("Cannot get key slot")

        try:
            if self.lib.PK11_NeedLogin(slot):
                pw = getpass("Primary Password: ") if interactive else ""
                rc = self.lib.PK11_CheckUserPassword(slot, pw.encode("utf-8"))
                if rc:
                    raise RuntimeError("Primary password incorrect")
        finally:
            self.lib.PK11_FreeSlot(slot)

    def decrypt_b64(self, b64text: str) -> str:
        """
        Расшифровывает зашифрованный текст в base64 формате.
        
        Args:
            b64text: Зашифрованный текст в base64
        
        Returns:
            Расшифрованный текст или "***decrypt_failed***" при ошибке
        """
        raw = b64decode(b64text)
        inp = SECItem(0, raw, len(raw))
        out = SECItem(0, None, 0)
        rc = self.lib.PK11SDR_Decrypt(ct.byref(inp), ct.byref(out), None)
        if rc:
            return "***decrypt_failed***"
        try:
            return out.decode_data()
        finally:
            self.lib.SECITEM_ZfreeItem(ct.byref(out), 0)

# ################################################################
class PasswordService:
    """
    Сервис для извлечения и расшифровки паролей Firefox.
    
    Использует NSS для расшифровки паролей, хранящихся в logins.json
    или signons.sqlite. Поддерживает оба формата для совместимости.
    """
    
    def __init__(self, profile_path: str, log: Any):
        """
        Инициализирует сервис паролей.
        
        Args:
            profile_path: Путь к папке профиля Firefox
            log: Интерфейс логирования
        """
        self.profile_path = profile_path
        self.nss = NSSWrapper()
        self._logger = log

    def _read_logins_json(self) -> Optional[List[Dict]]:
        """
        Читает пароли из файла logins.json (современный формат).
        
        Это основной формат хранения паролей в современном Firefox.
        Файл содержит JSON с массивом logins.
        
        Returns:
            Список логинов из файла или None если файл не существует
        """
        path = os.path.join(self.profile_path, "logins.json")
        if not os.path.isfile(path):
            return None
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("logins", [])

    def _read_signons_sqlite(self) -> Optional[List[Dict]]:
        """
        Читает пароли из файла signons.sqlite (старый формат).
        
        Это использовалось в старых версиях Firefox для хранения паролей.
        Более не используется, но включен для поддержки совместимости.
        
        Returns:
            Список логинов из таблицы moz_logins или None если файл не существует
        """
        path = os.path.join(self.profile_path, "signons.sqlite")
        if not os.path.isfile(path):
            return None
        db = SQLiteDatabaseInterfaceReader(path, self._logger)
        try:
            rows = db.Fetch("SELECT hostname, encryptedUsername, encryptedPassword FROM moz_logins")
        except Exception as e:
            self._log.Warn("ReaderClass", f"Ошибка чтения signons.sqlite: {e}")
            rows = []
        finally:
            db.CloseConnection()
        return [{"hostname": h, "encryptedUsername": u, "encryptedPassword": p} for h, u, p in rows]

    def get_passwords(self) -> List[Dict[str, str]]:
        """
        Получает и расшифровывает все пароли из профиля Firefox.
        
        Пытается прочитать из logins.json, если не найден - из signons.sqlite.
        Все пароли расшифровываются с использованием NSS.
        
        Returns:
            Список словарей с полями: url, user, password
            Если пароль не удалось расшифровать, содержит '***decrypt_failed***'
        """
        self.nss.init_profile(self.profile_path)
        self.nss.authenticate(interactive=False)

        logins = self._read_logins_json() or self._read_signons_sqlite()
        if not logins:
            return []

        result = []
        for item in logins:
            url = item.get("hostname", "")
            user = self.nss.decrypt_b64(item.get("encryptedUsername", "")) or ""
            pwd = self.nss.decrypt_b64(item.get("encryptedPassword", "")) or ""
            result.append({"url": url, "user": user, "password": pwd})

        self.nss.shutdown()
        return result

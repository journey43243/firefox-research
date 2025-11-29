"""
Модуль для работы с системой безопасности NSS и извлечения сохранённых паролей Firefox.

Содержит обёртку NSSWrapper для инициализации NSS, проверки пароля,
дешифрования строк PKCS#11 и освобождения структур SECItem.

Также включает PasswordService — сервис высокого уровня, который читает
пароли из `logins.json` или старого `signons.sqlite`, расшифровывает их
через NSS и возвращает список паролей с полями: url, user, password.
"""

import os
import sys
import json
import ctypes as ct
from base64 import b64decode
from getpass import getpass
from typing import List, Dict, Optional, Any

from Common.Routines import SQLiteDatabaseInterfaceReader


class SECItem(ct.Structure):
    """
    C-структура SECItem, используемая библиотекой NSS
    для представления бинарных буферов.

    Fields
    ------
    type : c_uint
        Тип SECItem.
    data : c_char_p
        Указатель на данные.
    len : c_uint
        Длина данных в байтах.
    """

    _fields_ = [("type", ct.c_uint), ("data", ct.c_char_p), ("len", ct.c_uint)]

    def decode_data(self):
        """
        Декодирует содержимое SECItem как UTF-8 строку.

        Returns
        -------
        str
            Декодированная строка. Если декодирование невозможно —
            возврат с заменой ошибочных символов.
        """
        _bytes = ct.string_at(self.data, self.len)
        try:
            return _bytes.decode("utf-8")
        except Exception:
            return _bytes.decode(errors="replace")


class NSSWrapper:
    """
    Обёртка над NSS (Network Security Services), предоставляющая функции
    инициализации профиля, проверки мастер-пароля, дешифрования строк
    PKCS#11 и освобождения ресурсов.

    Позволяет работать с данными Firefox, зашифрованными
    стандартными средствами NSS.
    """

    def __init__(self):
        """Загружает библиотеку NSS и настраивает прототипы функций."""
        self.lib = self._load_lib()
        self._setup_prototypes()

    def _load_lib(self) -> ct.CDLL:
        """
        Ищет и загружает динамическую библиотеку NSS для текущей платформы.

        Returns
        -------
        CDLL
            Загруженная библиотека NSS.

        Raises
        ------
        RuntimeError
            Если библиотека не найдена или не удалось загрузить.
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
        """Настраивает сигнатуры функций библиотеки NSS."""
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
        Инициализирует NSS-профиль Firefox.

        Parameters
        ----------
        path : str
            Путь к профилю Firefox.

        Raises
        ------
        RuntimeError
            Если NSS сообщает об ошибке инициализации.
        """
        rc = self.lib.NSS_Init(f"sql:{path}".encode())
        if rc:
            raise RuntimeError(f"NSS_Init failed: {rc}")

    def shutdown(self):
        """Корректно завершает работу NSS."""
        try:
            self.lib.NSS_Shutdown()
        except Exception:
            pass

    def authenticate(self, interactive=True):
        """
        Аутентифицирует пользователя в NSS (при наличии мастер-пароля).

        Parameters
        ----------
        interactive : bool
            Если True — запрашивает пароль у пользователя,
            иначе — пытается выполнить проверку пустым паролем.

        Raises
        ------
        RuntimeError
            Если не удалось получить слот или пароль указан неверно.
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
        Дешифрует строку Base64, зашифрованную средствами Firefox/NSS.

        Parameters
        ----------
        b64text : str
            Base64-строка с зашифрованными данными.

        Returns
        -------
        str
            Расшифрованная строка или "***decrypt_failed***" при ошибке.
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


class PasswordService:
    """
    Высокоуровневый сервис для чтения и расшифровки паролей Firefox.

    Поддерживает форматы:
    * logins.json — современный формат
    * signons.sqlite — устаревший формат старых версий Firefox
    """

    def __init__(self, profile_path: str, log: Any):
        """
        Инициализирует сервис и обёртку NSS.

        Parameters
        ----------
        profile_path : str
            Путь к профилю Firefox.
        log : Any
            Интерфейс логирования, совместимый с Logger.
        """
        self.profile_path = profile_path
        self.nss = NSSWrapper()
        self._logger = log

    def _read_logins_json(self) -> Optional[List[Dict]]:
        """
        Считывает пароли из logins.json, если файл существует.

        Returns
        -------
        list[dict] | None
            Список записей или None, если файла нет.
        """
        path = os.path.join(self.profile_path, "logins.json")
        if not os.path.isfile(path):
            return None
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("logins", [])

    def _read_signons_sqlite(self) -> Optional[List[Dict]]:
        """
        Считывает пароли из устаревшего signons.sqlite.

        Returns
        -------
        list[dict] | None
            Список расшифровываемых записей.
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
        Извлекает и расшифровывает пароли профиля Firefox.

        Returns
        -------
        list[dict]
            Список словарей с ключами:
            * url — сайт
            * user — имя пользователя
            * password — пароль
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

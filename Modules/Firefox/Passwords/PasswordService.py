import os
import sys
import json
import ctypes as ct
import sqlite3
from base64 import b64decode
from configparser import ConfigParser
from getpass import getpass
from typing import List, Dict, Optional


class SECItem(ct.Structure):
    _fields_ = [("type", ct.c_uint), ("data", ct.c_char_p), ("len", ct.c_uint)]

    def decode_data(self):
        _bytes = ct.string_at(self.data, self.len)
        try:
            return _bytes.decode("utf-8")
        except Exception:
            return _bytes.decode(errors="replace")


class NSSWrapper:
    def __init__(self):
        self.lib = self._load_lib()
        self._setup_prototypes()

    def _load_lib(self) -> ct.CDLL:
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
        rc = self.lib.NSS_Init(f"sql:{path}".encode())
        if rc:
            raise RuntimeError(f"NSS_Init failed: {rc}")

    def shutdown(self):
        try:
            self.lib.NSS_Shutdown()
        except Exception:
            pass

    def authenticate(self, interactive=True):
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
    def __init__(self, profile_path: str):
        self.profile_path = profile_path
        self.nss = NSSWrapper()

    def _read_logins_json(self) -> Optional[List[Dict]]:
        path = os.path.join(self.profile_path, "logins.json")
        if not os.path.isfile(path):
            return None
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("logins", [])

    def _read_signons_sqlite(self) -> Optional[List[Dict]]:
        path = os.path.join(self.profile_path, "signons.sqlite")
        if not os.path.isfile(path):
            return None
        con = sqlite3.connect(path)
        cur = con.cursor()
        cur.execute("SELECT hostname, encryptedUsername, encryptedPassword FROM moz_logins")
        rows = cur.fetchall()
        con.close()
        return [{"hostname": h, "encryptedUsername": u, "encryptedPassword": p} for h, u, p in rows]

    def get_passwords(self) -> List[Dict[str, str]]:
        """Возвращает список паролей с полями: url, user, password"""
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

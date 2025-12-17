"""
Модуль SQLiteStarter обеспечивает создание и удаление всех таблиц
результирующей базы данных для парсинга Firefox.

Класс SQLiteStarter предоставляет методы для создания таблиц:
profiles, history, downloads, bookmarks, passwords, extensions.
Также поддерживает удаление временных таблиц.
"""

from Common.Routines import SQLiteDatabaseInterface
from Interfaces.LogInterface import LogInterface


class SQLiteStarter:
    """
    Класс для инициализации структуры базы данных для хранения данных Firefox.

    Атрибуты:
        logInterface (LogInterface): Интерфейс логирования.
        dbInterface (SQLiteDatabaseInterface): Интерфейс работы с SQLite.
    """

    def __init__(self, logInterface: LogInterface, dbInterface: SQLiteDatabaseInterface) -> None:
        """
        Инициализирует объект SQLiteStarter.

        Parameters
        ----------
        logInterface : LogInterface
            Интерфейс логирования.
        dbInterface : SQLiteDatabaseInterface
            Интерфейс работы с базой данных.
        """
        self.logInterface = logInterface
        self.dbInterface = dbInterface

    def dropAllTables(self):
        """
        Удаляет все временные таблицы базы данных, определённые
        методами класса, начинающимися с 'create' и заканчивающимися на 'Table'.
        """
        namesList = []
        for name in dir(self):
            if name.startswith('create') and name.endswith('Table'):
                tableName = name.replace('create', '').replace('Table', '')
                namesList.append(tableName.lower())
        self.dbInterface.RemoveTempTables(namesList)

    def createAllTables(self):
        """
        Создаёт все таблицы базы данных, определённые методами класса,
        начинающимися с 'create' и заканчивающимися на 'Table'.
        """
        for methodName in dir(self):
            if methodName.startswith('create') and methodName.endswith('Table'):
                method = getattr(self, methodName)
                if callable(method):
                    method()

    def createProfilesTable(self) -> None:
        """
        Создаёт таблицу 'profiles' для хранения путей профилей Firefox
        и индекс для ускоренного поиска по пути.
        """
        self.dbInterface.ExecCommit(
            '''CREATE TABLE IF NOT EXISTS profiles (id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT)'''
        )
        self.dbInterface.ExecCommit('''CREATE INDEX IF NOT EXISTS idx_profiles_path on profiles (path)''')
        self.logInterface.Info(type(self), 'Таблица с профилями создана.')

    def createHistoryTable(self) -> None:
        """
        Создаёт таблицу 'history' для хранения истории посещённых сайтов
        и индекс по URL.
        """
        self.dbInterface.ExecCommit(
            '''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT,
                title TEXT, visit_count INTEGER, typed INTEGER, last_visit_date text,
                profile_id INTEGER, FOREIGN KEY(profile_id) REFERENCES profiles(id))'''
        )
        self.dbInterface.ExecCommit('''CREATE INDEX IF NOT EXISTS idx_history_url on history (url)''')
        self.logInterface.Info(type(self), 'Таблица с историей создана')

    def createDownloadsTable(self) -> None:
        """
        Создаёт таблицу 'downloads' для хранения загрузок Firefox
        и индекс по place_id.
        """
        self.dbInterface.ExecCommit(
            '''CREATE TABLE IF NOT EXISTS downloads (id PRIMARY KEY, place_id INTEGER,
            anno_attribute_id INTEGER, content TEXT, profile_id INTEGER,
            FOREIGN KEY(place_id) REFERENCES history(id))'''
        )
        self.dbInterface.ExecCommit('''CREATE INDEX IF NOT EXISTS idx_downloads_place_id on downloads (place_id)''')
        self.logInterface.Info(type(self), 'Таблица с загрузками создана')

    def createBookmarksTable(self) -> None:
        """
        Создаёт таблицу 'bookmarks' для хранения закладок Firefox.
        """
        self.dbInterface.ExecCommit(
            '''CREATE TABLE IF NOT EXISTS bookmarks (id INTEGER, type INTEGER, place INTEGER,
            parent INTEGER, position INTEGER, title TEXT,
            date_added text, last_modified text, profile_id INTEGER,
            PRIMARY KEY (id, profile_id))'''
        )
        self.logInterface.Info(type(self), 'Таблица с вкладками создана')

    def createPasswordsTable(self) -> None:
        """
        Создаёт таблицу 'passwords' для хранения паролей Firefox
        и индексы по URL и пользователю.
        """
        self.dbInterface.ExecCommit(
            '''CREATE TABLE IF NOT EXISTS passwords (
                url TEXT,
                user TEXT,
                password TEXT,
                profile_id INTEGER, FOREIGN KEY(profile_id) REFERENCES profiles(id),
                UNIQUE(url, user, password)
            )'''
        )
        self.dbInterface.ExecCommit('''CREATE INDEX IF NOT EXISTS idx_url_profile_id ON passwords(url, user)''')
        self.logInterface.Info(type(self), 'Таблица с паролями успешно создана')

    def createExtensionsTable(self) -> None:
        """
        Создаёт таблицу 'extensions' для хранения расширений Firefox
        и соответствующие индексы по id и profile_id.
        """
        self.dbInterface.ExecCommit(
            '''CREATE TABLE IF NOT EXISTS extensions (
                id TEXT PRIMARY KEY,
                name TEXT,
                version TEXT,
                description TEXT,
                type TEXT,
                active INTEGER,
                user_disabled INTEGER,
                install_date INTEGER,
                update_date INTEGER,
                path TEXT,
                source_url TEXT,
                permissions TEXT,
                location TEXT,
                profile_id INTEGER,
                FOREIGN KEY(profile_id) REFERENCES profiles(id)
            )'''
        )
        self.dbInterface.ExecCommit('''CREATE INDEX IF NOT EXISTS idx_extensions_id ON extensions (id)''')
        self.dbInterface.ExecCommit('''CREATE INDEX IF NOT EXISTS idx_extensions_profile_id ON extensions (profile_id)''')
        self.logInterface.Info(type(self), 'Таблица с расширениями создана')
        
    def createFaviconsTable(self) -> None:
        """
        Создаёт таблицы для хранения кэшированных иконок Firefox.
        """
        # Таблица иконок (реальная структура из favicons.sqlite)
        self.dbInterface.ExecCommit(
            '''CREATE TABLE IF NOT EXISTS favicons (
                id INTEGER PRIMARY KEY,
                icon_url TEXT,
                fixed_icon_url_hash INTEGER,
                width INTEGER,
                root INTEGER,
                color INTEGER,
                expire_ms INTEGER,
                flags INTEGER,
                data BLOB,
                profile_id INTEGER,
                FOREIGN KEY(profile_id) REFERENCES profiles(id)
            )'''
        )
        
        # Таблица страниц с иконками
        self.dbInterface.ExecCommit(
            '''CREATE TABLE IF NOT EXISTS favicon_pages (
                id INTEGER PRIMARY KEY,
                page_url TEXT,
                page_url_hash INTEGER,
                profile_id INTEGER,
                FOREIGN KEY(profile_id) REFERENCES profiles(id)
            )'''
        )
        
        # Таблица связей иконок со страницами (реальная структура)
        self.dbInterface.ExecCommit(
            '''CREATE TABLE IF NOT EXISTS favicons_to_pages (
                page_id INTEGER,
                icon_id INTEGER,
                expire_ms INTEGER,
                profile_id INTEGER,
                PRIMARY KEY (page_id, icon_id, profile_id),
                FOREIGN KEY(page_id) REFERENCES favicon_pages(id),
                FOREIGN KEY(icon_id) REFERENCES favicons(id),
                FOREIGN KEY(profile_id) REFERENCES profiles(id)
            )'''
        )
        
        # Создание индексов для ускорения поиска
        self.dbInterface.ExecCommit('''CREATE INDEX IF NOT EXISTS idx_favicons_icon_url ON favicons (icon_url)''')
        self.dbInterface.ExecCommit('''CREATE INDEX IF NOT EXISTS idx_favicon_pages_url ON favicon_pages (page_url)''')
        self.dbInterface.ExecCommit('''CREATE INDEX IF NOT EXISTS idx_favicons_to_pages_ids ON favicons_to_pages (page_id, icon_id)''')
        
        self.logInterface.Info(type(self), 'Таблицы с кэшем иконок созданы')

    def createCookiesTable(self) -> None:
        """
        Создаёт таблицу 'cookies' для хранения cookies Firefox.
        """
        self.dbInterface.ExecCommit(
            '''CREATE TABLE IF NOT EXISTS cookies (
                id INTEGER PRIMARY KEY,
                origin_attributes TEXT,
                name TEXT NOT NULL,
                value TEXT,
                host TEXT NOT NULL,
                path TEXT NOT NULL,
                expiry INTEGER,
                last_accessed INTEGER,
                creation_time INTEGER,
                is_secure INTEGER,
                is_http_only INTEGER,
                in_browser_element INTEGER,
                same_site INTEGER,
                scheme_map INTEGER,
                is_partitioned_attribute_set INTEGER,
                update_time INTEGER,
                base_domain TEXT,
                profile_id INTEGER,
                FOREIGN KEY(profile_id) REFERENCES profiles(id)
            )'''
        )
        
        # Создание индексов для ускорения поиска
        self.dbInterface.ExecCommit('''CREATE INDEX IF NOT EXISTS idx_cookies_host ON cookies (host)''')
        self.dbInterface.ExecCommit('''CREATE INDEX IF NOT EXISTS idx_cookies_name ON cookies (name)''')
        self.dbInterface.ExecCommit('''CREATE INDEX IF NOT EXISTS idx_cookies_base_domain ON cookies (base_domain)''')
        self.dbInterface.ExecCommit('''CREATE INDEX IF NOT EXISTS idx_cookies_profile_id ON cookies (profile_id)''')
        
        self.logInterface.Info(type(self), 'Таблица с cookies создана')

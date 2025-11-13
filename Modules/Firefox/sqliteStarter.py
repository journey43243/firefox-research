from Common.Routines import SQLiteDatabaseInterface
from Interfaces.LogInterface import LogInterface


class SQLiteStarter:

    def __init__(self, logInterface: LogInterface, dbInterface: SQLiteDatabaseInterface) -> None:
        self.logInterface = logInterface
        self.dbInterface = dbInterface

    def dropAllTables(self):
        namesList = []
        for name in dir(self):
            if name.startswith('create') and name.endswith('Table'):
                tableName = name.replace('create', '').replace('Table', '')
                namesList.append(tableName.lower())
        self.dbInterface.RemoveTempTables(namesList)

    def createAllTables(self):
        for methodName in dir(self):
            if methodName.startswith('create') and methodName.endswith('Table'):
                method = getattr(self, methodName)
                if callable(method):
                    method()


    def createProfilesTable(self) -> None:
        self.dbInterface.ExecCommit(
            '''CREATE TABLE profiles (id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT)
            '''
        )
        self.dbInterface.ExecCommit('''CREATE INDEX idx_profiles_path on profiles (path)''')
        self.logInterface.Info(type(self), 'Таблица с профилями создана.')
    def createHistoryTable(self) -> None:
        self.dbInterface.ExecCommit(
            '''CREATE TABLE history (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT,
                title TEXT, visit_count INTEGER, typed INTEGER, last_visit_date text,
                profile_id INTEGER, FOREIGN KEY(profile_id) REFERENCES profiles(id))
            '''
        )
        self.dbInterface.ExecCommit('''CREATE INDEX idx_history_url on history (url)''')
        self.logInterface.Info(type(self), 'Таблица с историей создана')
    def createDownloadsTable(self) -> None:
        self.dbInterface.ExecCommit(
            '''CREATE TABLE downloads (id PRIMARY KEY, place_id INTEGER,
            anno_attribute_id INTEGER, content TEXT, profile_id INTEGER ,FOREIGN KEY(place_id) REFERENCES history(id))'''
        )
        self.dbInterface.ExecCommit('''CREATE INDEX idx_downloads_place_id on downloads (place_id)''')
        self.logInterface.Info(type(self), 'Таблица с загрузками создана')
    def createBookmarksTable(self) -> None:
        self.dbInterface.ExecCommit(
            '''CREATE TABLE bookmarks (id INTEGER PRIMARY KEY, type INTEGER,
            place INTEGER, parent INTEGER, position INTEGER, title TEXT,
            date_added text, last_modified text, FOREIGN KEY(place) REFERENCES history(id))'''
        )
        self.logInterface.Info(type(self), 'Таблица с вкладками создана')
    def createExtensionsTable(self) -> None:
        self.dbInterface.ExecCommit(
            '''CREATE TABLE extensions (id TEXT PRIMARY KEY, name TEXT,
            description TEXT, homepage_url TEXT, creator TEXT, active BOOLEAN,
            install_date text, path TEXT, source_uri TEXT, root_uri TEXT,
            profile_id INTEGER, FOREIGN KEY(profile_id) REFERENCES profiles(id))'''
        )
        self.logInterface.Info(type(self), 'Таблица с расширениями создана')

    def createPasswordsTable(self) -> None:
        self.dbInterface.ExecCommit(
            '''CREATE TABLE IF NOT EXISTS passwords (
                url TEXT,
                user TEXT,
                password TEXT,
                UNIQUE(url, user, password)
            );'''
        )
        self.dbInterface.ExecCommit('''CREATE INDEX idx_url_profile_id ON passwords(url, user)''')
        self.logInterface.Info(type(self), 'Таблица с паролями успешно создана')
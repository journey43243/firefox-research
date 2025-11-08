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
            '''CREATE TABLE profiles (id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT)'''
        )
        self.logInterface.Info(type(self), 'Таблица с профилями создана.')
    def createHistoryTable(self) -> None:
        self.dbInterface.ExecCommit(
            '''CREATE TABLE history (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT,
                title TEXT, visit_count INTEGER, typed INTEGER, last_visit_date INTEGER,
                profile_id INTEGER, FOREIGN KEY(profile_id) REFERENCES profiles(id))
            '''
        )
        self.logInterface.Info(type(self), 'Таблица с историей создана')
    def createDownloadsTable(self) -> None:
        self.dbInterface.ExecCommit(
            '''CREATE TABLE downloads (id PRIMARY KEY, place_id INTEGER,
            anno_attribute_id INTEGER, content TEXT, FOREIGN KEY(place_id) REFERENCES history(id))'''
        )
        self.logInterface.Info(type(self), 'Таблица с загрузками создана')
    def createBookmarksTable(self) -> None:
        self.dbInterface.ExecCommit(
            '''CREATE TABLE bookmarks (id INTEGER PRIMARY KEY, type INTEGER,
            place INTEGER, parent INTEGER, position INTEGER, title TEXT,
            dateAdded INTEGER, lastModified INTEGER, FOREIGN KEY(place) REFERENCES history(id))'''
        )
        self.logInterface.Info(type(self), 'Таблица с вкладками создана')
    def createExtensionsTable(self) -> None:
        self.dbInterface.ExecCommit(
            '''CREATE TABLE extensions (id TEXT PRIMARY KEY, name TEXT,
            description TEXT, homepageURL TEXT, creator TEXT, active BOOLEAN,
            install_date INTEGER, path TEXT, source_uri TEXT, root_uri TEXT'''
        )
        self.logInterface.Info(type(self), 'Таблица с расширениями создана')
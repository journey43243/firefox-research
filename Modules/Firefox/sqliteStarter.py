"""
Модуль создателя таблиц SQLite для Firefox данных

Этот модуль предоставляет класс для автоматического создания всех
необходимых таблиц в выходной SQLite БД на основе данных Firefox.

Использует паттерн конвенции (convention over configuration) для
автоматического поиска методов создания таблиц.
"""

from Common.Routines import SQLiteDatabaseInterface
from Interfaces.LogInterface import LogInterface

# ################################################################
class SQLiteStarter:
    """
    Создатель таблиц SQLite для данных Firefox.
    
    Этот класс содержит методы для создания всех необходимых таблиц
    в выходной БД. Использует автоматическое обнаружение методов,
    начинающихся с 'create' и заканчивающихся на 'Table'.
    
    Таблицы:
    - profiles: Список профилей Firefox
    - history: История посещений сайтов
    - bookmarks: Сохранённые закладки
    - downloads: История загрузок
    - passwords: Сохранённые пароли
    - extensions: Установленные расширения
    
    Атрибуты:
        logInterface: Интерфейс логирования
        dbInterface: Интерфейс подключения к БД
    """

    def __init__(self, logInterface: LogInterface, dbInterface: SQLiteDatabaseInterface) -> None:
        """
        Инициализирует создатель таблиц.
        
        Args:
            logInterface: Интерфейс логирования
            dbInterface: Интерфейс подключения к выходной БД
        """
        self.logInterface = logInterface
        self.dbInterface = dbInterface

    def dropAllTables(self):
        """
        Удаляет все таблицы, созданные этим классом.
        
        Автоматически находит методы createXyzTable и удаляет соответствующие таблицы.
        """
        namesList = []
        for name in dir(self):
            if name.startswith('create') and name.endswith('Table'):
                tableName = name.replace('create', '').replace('Table', '')
                namesList.append(tableName.lower())
        self.dbInterface.RemoveTempTables(namesList)

    def createAllTables(self):
        """
        Создаёт все таблицы, для которых есть методы createXyzTable.
        
        Использует рефлексию для автоматического обнаружения и вызова
        методов создания таблиц.
        """
        for methodName in dir(self):
            if methodName.startswith('create') and methodName.endswith('Table'):
                method = getattr(self, methodName)
                if callable(method):
                    method()

    # ################################################################
    # Методы создания таблиц
    # ################################################################

    def createProfilesTable(self) -> None:
        """
        Создаёт таблицу для хранения информации о профилях Firefox.
        
        Таблица: profiles
        Поля:
        - id: Уникальный идентификатор профиля
        - path: Полный путь к папке профиля
        """
        self.dbInterface.ExecCommit(
            '''CREATE TABLE profiles (id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT)
            '''
        )
        self.dbInterface.ExecCommit('''CREATE INDEX idx_profiles_path on profiles (path)''')
        self.logInterface.Info(type(self), 'Таблица с профилями создана.')

    def createHistoryTable(self) -> None:
        """
        Создаёт таблицу для хранения истории посещений.
        
        Таблица: history
        Поля:
        - id: Уникальный идентификатор записи
        - url: URL посещённой страницы
        - title: Название страницы
        - visit_count: Количество посещений
        - typed: 1 если URL введён вручную, 0 если переход по ссылке
        - last_visit_date: Дата последнего посещения
        - profile_id: ID профиля (внешний ключ)
        """
        self.dbInterface.ExecCommit(
            '''CREATE TABLE history (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT,
                title TEXT, visit_count INTEGER, typed INTEGER, last_visit_date text,
                profile_id INTEGER, FOREIGN KEY(profile_id) REFERENCES profiles(id))
            '''
        )
        self.dbInterface.ExecCommit('''CREATE INDEX idx_history_url on history (url)''')
        self.logInterface.Info(type(self), 'Таблица с историей создана')

    def createDownloadsTable(self) -> None:
        """
        Создаёт таблицу для хранения истории загрузок.
        
        Таблица: downloads
        Поля:
        - id: ID загрузки
        - place_id: ID места (внешний ключ на history)
        - anno_attribute_id: ID атрибута аннотации
        - content: JSON содержимое с деталями загрузки
        - profile_id: ID профиля (внешний ключ)
        """
        self.dbInterface.ExecCommit(
            '''CREATE TABLE downloads (id PRIMARY KEY, place_id INTEGER,
            anno_attribute_id INTEGER, content TEXT, profile_id INTEGER ,FOREIGN KEY(place_id) REFERENCES history(id))'''
        )
        self.dbInterface.ExecCommit('''CREATE INDEX idx_downloads_place_id on downloads (place_id)''')
        self.logInterface.Info(type(self), 'Таблица с загрузками создана')

    def createBookmarksTable(self) -> None:
        """
        Создаёт таблицу для хранения закладок.
        
        Таблица: bookmarks
        Поля:
        - id: Уникальный ID закладки
        - type: Тип (1=URL, 2=папка, 3=разделитель)
        - place: ID связанного места (URL)
        - parent: ID родительской папки
        - position: Позиция в иерархии
        - title: Название закладки
        - date_added: Дата добавления
        - last_modified: Дата последнего изменения
        - profile_id: ID профиля (внешний ключ)
        """
        self.dbInterface.ExecCommit(
            '''CREATE TABLE bookmarks (id INTEGER, type INTEGER, place INTEGER,
            parent INTEGER, position INTEGER, title TEXT,
            date_added text, last_modified text, profile_id INTEGER,
            PRIMARY KEY (id, profile_id))'''
        )
        self.logInterface.Info(type(self), 'Таблица с вкладками создана')

    def createPasswordsTable(self) -> None:
        """
        Создаёт таблицу для хранения сохранённых паролей.
        
        Таблица: passwords
        Поля:
        - url: URL сайта для этого пароля
        - user: Имя пользователя/логин
        - password: Расшифрованный пароль
        - profile_id: ID профиля (внешний ключ)
        
        Ограничение UNIQUE предотвращает дубликаты одинаковых паролей
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
        self.dbInterface.ExecCommit('''CREATE INDEX idx_url_profile_id ON passwords(url, user)''')
        self.logInterface.Info(type(self), 'Таблица с паролями успешно создана')

    def createExtensionsTable(self) -> None:
        """
        Создаёт таблицу для хранения установленных расширений.
        
        Таблица: extensions
        Поля:
        - id: Уникальный ID расширения
        - name: Название расширения
        - version: Версия
        - description: Описание
        - type: Тип ("extension", "theme" и т.д.)
        - active: 1 если активно, 0 если отключено
        - user_disabled: 1 если отключено пользователем
        - install_date: Дата установки (миллисекунды)
        - update_date: Дата обновления
        - path: Путь к папке расширения
        - source_url: URL источника
        - permissions: JSON список разрешений
        - location: Место установки
        - profile_id: ID профиля (внешний ключ)
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
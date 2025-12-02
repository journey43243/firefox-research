# -*- coding: utf-8 -*-
"""
Тестовый модуль Firefox.
Создаёт таблицы через sqliteStarter и заполняет мок-данными.
В таблицу Data пишет количество записей в каждой таблице.
В таблицу Info краткую сводку о назначении БД.
В таблицу Headers заголовки.

Пример запуска:
    python firefox_module.py --profiles 20 --history 50000 --downloads 10000
"""

from typing import Dict
import random
import argparse

def parse_mock_counts():
    parser = argparse.ArgumentParser(description="Set mock counts for Firefox test module")
    parser.add_argument("--profiles", type=int, default=10, help="Number of profiles")
    parser.add_argument("--history", type=int, default=100000, help="Number of history entries")
    parser.add_argument("--downloads", type=int, default=5000, help="Number of downloads")
    parser.add_argument("--bookmarks", type=int, default=3000, help="Number of bookmarks")
    parser.add_argument("--passwords", type=int, default=1000, help="Number of passwords")
    parser.add_argument("--extensions", type=int, default=150, help="Number of extensions")

    args = parser.parse_args()
    return {
        "profiles": args.profiles,
        "history": args.history,
        "downloads": args.downloads,
        "bookmarks": args.bookmarks,
        "passwords": args.passwords,
        "extensions": args.extensions
    }

class Parser:
    def __init__(self, parameters: dict):
        self.parameters = parameters
        self.log = parameters["LOG"]
        self.db = parameters["DBCONNECTION"]
        self.outputWriter = parameters["OUTPUTWRITER"]
        self.moduleName = parameters["MODULENAME"]

        # Сколько записей создавать для каждой таблицы
        self.mock_counts = parameters.get("MOCK_COUNTS") or parse_mock_counts()

    async def Start(self) -> Dict:
        if not self.db.IsConnected():
            raise SystemExit("Ошибка: база данных не подключена!")

        # ---------------------------------------------------------------
        # 1. Создаём Firefox таблицы через sqliteStarter модуля FireFox
        # ---------------------------------------------------------------
        from Modules.Firefox.sqliteStarter import SQLiteStarter
        sql = SQLiteStarter(self.log, self.db)
        sql.createAllTables()

        # -----------------------------------------
        # 2. Мокируем данные для каждой таблицы
        # -----------------------------------------

        # Profiles
        for i in range(self.mock_counts["profiles"]):
            self.db.ExecCommit(
                "INSERT INTO profiles (id, path) VALUES (?, ?);",
                (i+1, f"C:/Users/User{i+1}/AppData/Roaming/Firefox/Profile{i+1}")
            )

        # History
        for i in range(self.mock_counts["history"]):
            self.db.ExecCommit(
                """INSERT INTO history
                   (id, url, title, visit_count, typed, last_visit_date, profile_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?);""",
                (i+1,
                 f"https://example{i+1}.com",
                 f"Title{i+1}",
                 random.randint(1, 10),
                 random.randint(0, 1),
                 f"2025-01-{(i % 28) + 1:02d} 12:00:00",
                 (i % self.mock_counts["profiles"]) + 1)
            )

        # Downloads
        for i in range(self.mock_counts["downloads"]):
            self.db.ExecCommit(
                """INSERT INTO downloads
                   (id, place_id, anno_attribute_id, content, profile_id)
                   VALUES (?, ?, ?, ?, ?);""",
                (i+1,
                 (i % self.mock_counts["history"]) + 1,
                 100+i,
                 f"file{i+1}.txt",
                 (i % self.mock_counts["profiles"]) + 1)
            )

        # Bookmarks
        for i in range(self.mock_counts["bookmarks"]):
            self.db.ExecCommit(
                """INSERT INTO bookmarks
                   (id, type, place, parent, position, title, date_added, last_modified, profile_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (i+1, 1, (i % self.mock_counts["history"]) + 1, 0, i,
                 f"Bookmark{i+1}",
                 f"2025-01-{(i % 28) + 1:02d}",
                 f"2025-01-{(i % 28) + 1:02d}",
                 (i % self.mock_counts["profiles"]) + 1)
            )

        # Passwords
        for i in range(self.mock_counts["passwords"]):
            self.db.ExecCommit(
                """INSERT INTO passwords
                   (url, user, password, profile_id)
                   VALUES (?, ?, ?, ?);""",
                (f"https://example{i+1}.com",
                 f"user{i+1}",
                 f"pass{i+1}",
                 (i % self.mock_counts["profiles"]) + 1)
            )

        # Extensions
        for i in range(self.mock_counts["extensions"]):
            self.db.ExecCommit(
                """INSERT INTO extensions
                   (id, name, version, description, type, active, user_disabled, install_date, update_date,
                    path, source_url, permissions, location, profile_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (f"ext{i+1}",
                 f"Extension{i+1}",
                 f"{i+1}.0",
                 f"Description{i+1}",
                 "extension",
                 1,
                 0,
                 0,
                 0,
                 f"/path/to/ext{i+1}",
                 f"https://source{i+1}.com",
                 "all",
                 "local",
                 (i % self.mock_counts["profiles"]) + 1)
            )

        # -----------------------------------------
        # 3. Вставляем в Data только количество записей каждой таблицы
        # -----------------------------------------
        data_fields = {
            'TableName': ('Название таблицы', 200, 'string', ''),
            'Count': ('Количество записей', 100, 'int', '')
        }

        record_fields = {
            'TableName': 'TEXT',
            'Count': 'INTEGER'
        }

        self.outputWriter.SetFields(data_fields, record_fields)
        self.outputWriter.CreateDatabaseTables()

        for table, count in self.mock_counts.items():
            self.outputWriter.WriteRecord((table, count))

        # -----------------------------------------
        # 4. Завершение формирования БД
        # -----------------------------------------
        infoTableData = {
            'Name': self.moduleName,
            'Help': f"{self.moduleName}: Тестовый модуль Firefox",
            'Timestamp': self.parameters["CASENAME"],
            'Vendor': 'PythonCustomFramework'
        }

        self.outputWriter.RemoveTempTables()
        await self.outputWriter.CreateDatabaseIndexes(self.moduleName)
        self.outputWriter.SetInfo(infoTableData)
        self.outputWriter.WriteMeta()

        if self.db.IsRAMAllocated():
            self.db.SaveSQLiteDatabaseFromRamToFile()

        self.db.CloseConnection()

        return {self.moduleName: self.db.GetDatabasePath()}

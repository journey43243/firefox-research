import asyncio
import datetime

from Common.Routines import SQLiteDatabaseInterface, FileContentReader
from Interfaces.LogInterface import LogInterface
from Modules.Firefox.Profiles.ProfilesReader import ProfilesReader
from Modules.Firefox.Profiles.ProfilesWriter import ProfilesWriter
from Modules.Firefox.sqliteStarter import SQLiteStarter
from Modules.Firefox.History.HistoryReader import HistoryReader
from Modules.Firefox.History.HistoryWriter import HistoryWriter


class Parser:

    def __init__(self, parameters:dict)-> None:
        print(parameters)
        self.logInterface = parameters['LOG']
        self.caseFolder = parameters['CASEFOLDER']
        self.caseName = parameters['CASENAME']
        self.dbInterface = parameters['DBCONNECTION']
        self.outputFileName = parameters['OUTPUTFILENAME']
        self.outputWriter = parameters['OUTPUTWRITER']
        self.dbWritePath = f'{self.caseFolder}/{self.caseName}/{self.outputFileName}'

    async def Start(self):
        if not self.dbInterface.IsConnected():
            return

        profiles = ProfilesReader(self.logInterface, FileContentReader()).getProfiles()
        sqlCreator = SQLiteStarter(self.logInterface, self.dbInterface)
        sqlCreator.createAllTables()
        ProfilesWriter(self.logInterface, self.dbInterface).insertProfiles(profiles)
        historyWriter = HistoryWriter(self.logInterface, self.dbInterface)
        tasks = []
        for id, profilePath in enumerate(profiles):
            dbIntrefaceRead = SQLiteDatabaseInterface(profilePath + '\places.sqlite', self.logInterface,
                                                      'Firefox', False)
            historyReader = HistoryReader(self.logInterface, dbIntrefaceRead, id + 1)
            for batch in historyReader.read():
                task = asyncio.create_task(historyWriter.write(batch))
                tasks.append(task)
        if tasks: await asyncio.wait(tasks)
        self.dbInterface.SaveSQLiteDatabaseFromRamToFile()

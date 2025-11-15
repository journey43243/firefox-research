import asyncio

from Common.Routines import SQLiteDatabaseInterface
from Modules.Firefox.Profiles.Strategy import ProfilesStrategy
from Modules.Firefox.interfaces.Strategy import StrategyABC, Metadata
from Modules.Firefox.sqliteStarter import SQLiteStarter
from Modules.Firefox.History.Strategy import HistoryStrategy
from Modules.Firefox.Passwords.Strategy import PasswordStrategy
from Modules.Firefox.Extensions.Strategy import ExtensionsStrategy

class Parser:
    def __init__(self, parameters: dict) -> None:
        self.logInterface = parameters['LOG']
        self.caseFolder = parameters['CASEFOLDER']
        self.caseName = parameters['CASENAME']
        self.dbInterface = parameters['DBCONNECTION']
        self.outputFileName = parameters['OUTPUTFILENAME']
        self.outputWriter = parameters['OUTPUTWRITER']
        self.moduleName = parameters['MODULENAME']
        self.dbWritePath = f'{self.caseFolder}/{self.caseName}/{self.outputFileName}'

    async def Start(self):
        if not self.dbInterface.IsConnected():
            return

        HELP_TEXT = self.moduleName + ' Firefox Researching'
        sqlCreator = SQLiteStarter(self.logInterface, self.dbInterface)
        sqlCreator.createAllTables()

        profilesStrategy = ProfilesStrategy(self.logInterface, self.dbInterface)
        profiles = [profile for profile in profilesStrategy.read()]
        tasks = []
        await profilesStrategy.execute(tasks)
        if tasks: 
            await asyncio.wait(tasks)

        for id, profilePath in enumerate(profiles):
            dbReadInterface = SQLiteDatabaseInterface(
                profilePath + r'\places.sqlite', 
                self.logInterface,
                'Firefox', 
                False
            )
            metadata = Metadata(
                self.logInterface, 
                dbReadInterface, 
                self.dbInterface, 
                id + 1, 
                profilePath
            )
            
            await HistoryStrategy(metadata).execute(tasks)
            await asyncio.wait(tasks)
            
            for strategy in StrategyABC.__subclasses__():
                if strategy.__name__ in ['HistoryStrategy', 'ProfilesStrategy', 'ExtensionsStrategy']:
                    continue
                else:
                    await strategy(metadata).execute(tasks)
                    self.logInterface.Info(type(strategy), 'отработала успешно')
            
            await ExtensionsStrategy(metadata).execute(tasks)
            self.logInterface.Info(ExtensionsStrategy.__name__, 'отработала успешно')

        if tasks: 
            await asyncio.wait(tasks)

        self.dbInterface.SaveSQLiteDatabaseFromRamToFile()
        return {self.moduleName: self.outputWriter.GetDBName()}
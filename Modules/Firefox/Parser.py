import asyncio

from Common.Routines import SQLiteDatabaseInterface
from Modules.Firefox.Profiles.Strategy import ProfilesStrategy
from Modules.Firefox.interfaces.Strategy import StrategyABC
from Modules.Firefox.sqliteStarter import SQLiteStarter
from Modules.Firefox.History.Strategy import HistoryStrategy

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
        if tasks: await asyncio.wait(tasks)


        for id, profilePath in enumerate(profiles):
            dbReadIntreface = SQLiteDatabaseInterface(profilePath + r'\places.sqlite', self.logInterface,
                                                      'Firefox', False)
            await HistoryStrategy(self.logInterface, dbReadIntreface, self.dbInterface, id + 1).execute(tasks)
            for strategy in StrategyABC.__subclasses__():
                if strategy.__name__ in ['HistoryStrategy', 'ProfilesStrategy']:
                    continue
                elif strategy.__name__ == 'PasswordStrategy':
                    await strategy(self.logInterface, dbReadIntreface, self.dbInterface, profilePath).execute(tasks)
                    self.logInterface.Info(type(strategy), 'отработала успешно')
                else:
                    await strategy(self.logInterface, dbReadIntreface, self.dbInterface, id + 1).execute(tasks)
                    self.logInterface.Info(type(strategy), 'отработала успешно')



        if tasks: await asyncio.wait(tasks)

        self.dbInterface.SaveSQLiteDatabaseFromRamToFile()
        return {self.moduleName: self.outputWriter.GetDBName()}

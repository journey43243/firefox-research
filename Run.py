# -*- coding: utf-8 -*-
"""
Точка входа

"""

import sys,asyncio
from Common.Codes import ExitCode
from Interfaces.Main import Interface
from typing import NoReturn


#--------------------------------------------------------------------------------
class ExitStatus():
    def __init__(self):
        self.status:int = ExitCode.Ok.value

#--------------------------------------------------------------------------------
def main() -> NoReturn:
    exitStatus:ExitStatus = ExitStatus()
    loop:'asyncio.windows_events.ProactorEventLoop' = asyncio.get_event_loop()
    appEntryPoint:Interface = Interface()
    # Обеспечиваем асинхронный цикл работы
    try:
        loop.run_until_complete(appEntryPoint.Run(exitStatus))
        sys.exit(exitStatus.status)
    except asyncio.exceptions.CancelledError:
        sys.exit(ExitCode.AsyncStartError.value)


from Common.timing_decorators import time_strategy_class


async def run_firefox_timed():
    """Запуск Firefox с замерами времени (async версия)"""
    print("=== ЗАПУСК ASYNC FIREFOX С ТАЙМИНГОМ ===")

    import os
    os.makedirs('Cases/FirefoxTimed', exist_ok=True)
    os.makedirs('Logs', exist_ok=True)

    class SimpleLogger:
        def Info(self, source, msg): print(f"INFO: {msg}")

        def Warn(self, source, msg): print(f"WARN: {msg}")

        def Error(self, source, msg): print(f"ERROR: {msg}")

    from Common.Routines import SQLiteDatabaseInterface

    parameters = {
        'LOG': SimpleLogger(),
        'CASEFOLDER': 'Cases',
        'CASENAME': 'FirefoxTimed',
        'DBCONNECTION': SQLiteDatabaseInterface('Cases/FirefoxTimed/timed.db', SimpleLogger(), 'Firefox', True),
        'OUTPUTFILENAME': 'timed.db',
        'OUTPUTWRITER': type('', (), {'GetDBName': lambda: 'timed.db'})(),
        'MODULENAME': 'Firefox'
    }

    from Modules.Firefox.Parser import TimedParser
    parser = TimedParser(parameters)
    result = await parser.Start()
    print(f"Результат: {result}")


def run_firefox_sync_timed():
    """Запуск Firefox с замерами времени (sync версия)"""
    print("=== ЗАПУСК SYNC FIREFOX С ТАЙМИНГОМ ===")

    import os
    os.makedirs('Cases/FirefoxSyncTimed', exist_ok=True)
    os.makedirs('Logs', exist_ok=True)

    class SimpleLogger:
        def Info(self, source, msg): print(f"INFO: {msg}")

        def Warn(self, source, msg): print(f"WARN: {msg}")

        def Error(self, source, msg): print(f"ERROR: {msg}")

    from Common.Routines import SQLiteDatabaseInterface

    parameters = {
        'LOG': SimpleLogger(),
        'CASEFOLDER': 'Cases',
        'CASENAME': 'FirefoxSyncTimed',
        'DBCONNECTION': SQLiteDatabaseInterface('Cases/FirefoxSyncTimed/sync_timed.db', SimpleLogger(), 'Firefox',
                                                True),
        'OUTPUTFILENAME': 'sync_timed.db',
        'OUTPUTWRITER': type('', (), {'GetDBName': lambda: 'sync_timed.db'})(),
        'MODULENAME': 'Firefox'
    }

    from Modules.Firefox.SyncParser import TimedSyncParser

    parser = TimedSyncParser(parameters)
    result = parser.Start()
    print(f"Результат: {result}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == '--timed-async':
            asyncio.run(run_firefox_timed())
        elif sys.argv[1] == '--timed-sync':
            run_firefox_sync_timed()
        else:
            main()
    else:
        main()
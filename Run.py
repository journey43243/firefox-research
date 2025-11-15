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
    # Исправленная строка - создаем новый event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    appEntryPoint:Interface = Interface()
    # Обеспечиваем асинхронный цикл работы
    try:
        loop.run_until_complete(appEntryPoint.Run(exitStatus)) 
        sys.exit(exitStatus.status)
    except asyncio.exceptions.CancelledError:
        sys.exit(ExitCode.AsyncStartError.value)
    finally:
        loop.close()

if __name__ == '__main__': 
    main()
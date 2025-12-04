# -*- coding: utf-8 -*-
"""
Точка входа

"""

import sys,asyncio
import os
from Common.Codes import ExitCode
from Interfaces.Main import Interface
from typing import NoReturn
from Common.timing_decorators import time_program_execution
from datetime import datetime


#--------------------------------------------------------------------------------
class ExitStatus():
    def __init__(self):
        self.status:int = ExitCode.Ok.value

#--------------------------------------------------------------------------------
async def run_program(exitStatus: ExitStatus) -> None:
    """Основная асинхронная функция запуска программы"""
    appEntryPoint: Interface = Interface()
    await appEntryPoint.Run(exitStatus)

time_filename = str(datetime.now()).split('.')[0].replace(':', '_')
os.environ['PROGRAM_TIME_FILENAME'] = time_filename

@time_program_execution(log_filename=time_filename)
async def run_program_timed(exitStatus: ExitStatus) -> None:
    """Версия с замером времени"""
    appEntryPoint: Interface = Interface()
    await appEntryPoint.Run(exitStatus)

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


def main_timed() -> NoReturn:
    """Запуск с замером времени"""
    exitStatus: ExitStatus = ExitStatus()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(run_program_timed(exitStatus))
        sys.exit(exitStatus.status)
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(ExitCode.ControlParametersError.value)
    finally:
        loop.close()

if __name__ == '__main__':
    if '--timed' in sys.argv:
        main_timed()
    else:
        main()
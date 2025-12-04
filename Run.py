# -*- coding: utf-8 -*-
"""
Точка входа

"""

import sys, asyncio
import os
from Common.Codes import ExitCode
from Interfaces.Main import Interface
from typing import NoReturn
from Common.timing_decorators import time_program_execution
from datetime import datetime


# --------------------------------------------------------------------------------
class ExitStatus():
    def __init__(self):
        self.status: int = ExitCode.Ok.value


# --------------------------------------------------------------------------------
def main() -> NoReturn:
    """Обычный запуск программы без замера времени"""
    exitStatus: ExitStatus = ExitStatus()
    loop: 'asyncio.windows_events.ProactorEventLoop' = asyncio.get_event_loop()
    appEntryPoint: Interface = Interface()

    # Обеспечиваем асинхронный цикл работы
    try:
        loop.run_until_complete(appEntryPoint.Run(exitStatus))
        sys.exit(exitStatus.status)
    except asyncio.exceptions.CancelledError:
        sys.exit(ExitCode.AsyncStartError.value)


# --------------------------------------------------------------------------------
def main_timed() -> NoReturn:
    """Запуск программы с замером времени и аналитикой производительности"""
    exitStatus: ExitStatus = ExitStatus()

    try:
        # Создаем имя файла для логов аналитики
        time_filename = str(datetime.now()).split('.')[0].replace(':', '_')
        os.environ['PROGRAM_TIME_FILENAME'] = time_filename

        # Настраиваем асинхронный цикл
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.get_event_loop()

        # Декорируем функцию запуска с замером времени
        @time_program_execution(log_filename=time_filename)
        async def timed_execution():
            appEntryPoint: Interface = Interface()
            return await appEntryPoint.Run(exitStatus)

        # Выполняем программу с замером времени
        loop.run_until_complete(timed_execution())
        sys.exit(exitStatus.status)

    except asyncio.exceptions.CancelledError:
        sys.exit(ExitCode.AsyncStartError.value)
    except Exception as e:
        print(f"Ошибка при выполнении программы: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(ExitCode.ControlParametersError.value)
    finally:
        if 'loop' in locals():
            loop.close()


# --------------------------------------------------------------------------------
if __name__ == '__main__':
    if '--timed' in sys.argv or '--analytics' in sys.argv:
        main_timed()
    else:
        main()
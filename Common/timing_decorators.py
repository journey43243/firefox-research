from functools import wraps
import time
from datetime import datetime
import asyncio



def time_program_execution(log_filename: str = None):
    """Декоратор для замера времени выполнения всей программы"""

    def decorator(func):
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            print("ЗАПУСК ПРОГРАММЫ...")
            start_time = time.time()

            result = func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time

            # Определяем имя файла
            if log_filename:
                filename = log_filename
            else:
                filename = str(datetime.now()).split('.')[0].replace(':', '_')

            print(f"ОБЩЕЕ ВРЕМЯ ВЫПОЛНЕНИЯ ПРОГРАММЫ:")
            print(f"{'=' * 50}")
            print(f"Время: {execution_time:.4f} секунд")

            # Записываем основную информацию в файл
            with open(f"Logs/{filename}_time.txt", "a", encoding="utf-8") as f:
                f.write(f"\n{'=' * 50}\n")
                f.write(f"Время выполнения программы: {execution_time:.4f} секунд\n")
                f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

            return result

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            print("ЗАПУСК ПРОГРАММЫ...")
            start_time = time.time()

            result = await func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time

            if log_filename:
                filename = log_filename
            else:
                filename = str(datetime.now()).split('.')[0].replace(':', '_')

            print(f"ОБЩЕЕ ВРЕМЯ ВЫПОЛНЕНИЯ ПРОГРАММЫ:")
            print(f"Время: {execution_time:.4f} секунд")

            # Записываем основную информацию в файл
            with open(f"Logs/{filename}_time.txt", "a", encoding="utf-8") as f:
                f.write(f"\n{'=' * 50}\n")
                f.write(f"Время выполнения программы: {execution_time:.4f} секунд\n")
                f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            return result

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator






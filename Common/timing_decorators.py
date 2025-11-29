# Common/timing_decorators.py
import time
from functools import wraps
import asyncio


def time_method(func):
    """Универсальный декоратор для замера времени async и sync методов"""

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        print(f"🚀 Начал выполнение {func.__name__}")
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"✅ Метод {func.__name__} выполнился за {execution_time:.4f} секунд")
        return result

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        print(f"🚀 Начал выполнение {func.__name__}")
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"✅ Метод {func.__name__} выполнился за {execution_time:.4f} секунд")
        return result

    # Возвращаем async или sync обертку в зависимости от типа функции
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


def time_strategy_class(cls):
    """Универсальный декоратор класса для async и sync стратегий"""
    print(f"🎯 ДЕКОРИРУЕМ КЛАСС: {cls.__name__}")

    class TimedClass(cls):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            print(f"🔧 СОЗДАН ЭКЗЕМПЛЯР: {cls.__name__}")

            # Декорируем read и write независимо от их типа (async/sync)
            if hasattr(self, 'read'):
                print(f"  📖 ДЕКОРИРУЕМ READ В {cls.__name__}")
                self.read = time_method(self.read)
            if hasattr(self, 'write'):
                print(f"  📝 ДЕКОРИРУЕМ WRITE В {cls.__name__}")
                self.write = time_method(self.write)
            if hasattr(self, 'execute'):
                print(f"  ⚡ ДЕКОРИРУЕМ EXECUTE В {cls.__name__}")
                self.execute = time_method(self.execute)

    TimedClass.__name__ = f"Timed{cls.__name__}"
    return TimedClass
@echo off
REM Получаем расширение файла
set "ext=%~x1"

REM Если .py, прогоняем через doxypypy
if /I "%ext%"==".py" (
    doxypypy -a -c "%~1"
) else (
    REM Для других файлов (например .dox) просто выводим содержимое
    type "%~1"
)

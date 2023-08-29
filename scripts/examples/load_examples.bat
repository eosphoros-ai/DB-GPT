@echo off
setlocal

:: Get script location and set working directory
for %%i in (%0) do set SCRIPT_LOCATION=%%~dpi
cd %SCRIPT_LOCATION%
cd ..
cd ..
set WORK_DIR=%CD%

:: Check if sqlite3 is installed
where sqlite3 >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo sqlite3 not found, please install sqlite3
    exit /b 1
)

:: Default file paths
set DEFAULT_DB_FILE=DB-GPT\pilot\data\default_sqlite.db
set DEFAULT_SQL_FILE=DB-GPT\docker\examples\sqls\*_sqlite.sql
set DB_FILE=%WORK_DIR%\pilot\data\default_sqlite.db
set SQL_FILE=

:argLoop
if "%1"=="" goto argDone
if "%1"=="-d" goto setDBFile
if "%1"=="--db-file" goto setDBFile
if "%1"=="-f" goto setSQLFile
if "%1"=="--sql-file" goto setSQLFile
if "%1"=="-h" goto printUsage
if "%1"=="--help" goto printUsage
goto argError

:setDBFile
shift
set DB_FILE=%1
shift
goto argLoop

:setSQLFile
shift
set SQL_FILE=%1
shift
goto argLoop

:argError
echo Invalid argument: %1
goto printUsage

:printUsage
echo USAGE: %0 [--db-file sqlite db file] [--sql-file sql file path to run]
echo   [-d^|--db-file sqlite db file path] default: %DEFAULT_DB_FILE%
echo   [-f^|--sql-file sqlite file to run] default: %DEFAULT_SQL_FILE%
echo   [-h^|--help] Usage message
exit /b 0

:argDone


if "%SQL_FILE%"=="" (
    if not exist "%WORK_DIR%\pilot\data" mkdir "%WORK_DIR%\pilot\data"
    for %%f in (%WORK_DIR%\docker\examples\sqls\*_sqlite.sql) do (
        echo execute sql file: %%f
        sqlite3 "%DB_FILE%" < "%%f"
    )
) else (
    echo Execute SQL file %SQL_FILE%
    sqlite3 "%DB_FILE%" < "%SQL_FILE%"
)

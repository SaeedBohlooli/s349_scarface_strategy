:: start cmd /k python ..\scripts\charts_ver1.py

set CMD="python ..\scripts\charts_ver1.py"

set PROGRAM=python.exe
set PORTFOLIO=p107
set KEY_1=charts_ver1
set KEY_2=charts_ver1

wmic process where "name='%PROGRAM%' and CommandLine like '%%%KEY_1%%%' and CommandLine like '%%%KEY_2%%%' " get ProcessId | findstr [0-9] >nul

:: for debugging
:: wmic process where "name='node.exe' " get ProcessId,CommandLine

if %errorlevel%==0 (
    echo We already running for %PROGRAM% %KEY_1% %KEY_2% %CMD%
    echo === Running process ===
    wmic process where "name='%PROGRAM%' and CommandLine like '%%%KEY_1%%%' and CommandLine like '%%%KEY_2%%%' " get ProcessId,CommandLine
) else (
    echo Starting program %CMD%
    start cmd /k %CMD%
)
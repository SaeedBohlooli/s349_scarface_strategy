:: start cmd /k python ..\trading_utils\watchdog_ibgateway.py

set CMD="python ..\trading_utils\watchdog_ibgateway.py"

set PROGRAM=python.exe
set PORTFOLIO=p107
set KEY_1=watchdog_ibgateway
set KEY_2=watchdog_ibgateway

wmic process where "name='%PROGRAM%' and CommandLine like '%%%KEY_1%%%' and CommandLine like '%%%KEY_2%%%' " get ProcessId | findstr [0-9] >nul

:: for debugging
:: wmic process where "name='node.exe' " get ProcessId,CommandLine

if %errorlevel%==0 (
    echo We already running for %PROGRAM% %KEY_1% %KEY_2% %CMD%
    echo === Running process ===
    wmic process where "name='%PROGRAM%' and CommandLine like '%%%KEY_1%%%' and CommandLine like '%%%KEY_2%%%' " get ProcessId,CommandLine
) else (
    echo Starting program %CMD%
    :: start cmd /k python ..\trading_utils\watchdog_ibgateway.py
    start cmd /k %CMD%

)
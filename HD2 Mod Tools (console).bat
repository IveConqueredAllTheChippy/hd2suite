@echo off
rem HD2 Mod Tools - the same start as "HD2 Mod Tools.exe", but with this console window open,
rem so that error messages can be read. It runs:   python -B -I hd2suite\app.py
rem   -B  write no .pyc files      -I  ignore PYTHON* environment variables and user site-packages
setlocal
cd /d "%~dp0"
echo Folder: "%CD%"
if exist "python\python.exe" goto bundled

echo No folder "python" here, so the Python installed on this PC is used:  py -3
echo.
py -3 -B -I "hd2suite\app.py" %*
goto done

:bundled
echo Using the Python in this folder:  python\python.exe
echo.
"python\python.exe" -B -I "hd2suite\app.py" %*

:done
echo.
echo The program ended with code %ERRORLEVEL% (0 = no error). Error details, if any: hd2suite\error.log
pause

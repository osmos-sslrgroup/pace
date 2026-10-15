@echo off
echo Starting Build Process...
call venv\Scripts\activate.bat
echo Installing dependencies and Pyinstaller...
pip install -r requirements.txt pyinstaller
echo Running PyInstaller...
pyinstaller --clean PACE.spec
echo.
echo Build complete! Executable is located in the dist\PACE\ folder (if directory build) or dist\PACE.exe (if one-file).
pause

@echo off
cd /d %~dp0
py -m PyInstaller --noconfirm --clean --onefile --windowed --name ApexElite launcher.py
if not exist releases mkdir releases
copy /Y dist\ApexElite.exe releases\ApexElite.exe >nul
powershell -NoProfile -Command "Compress-Archive -Path 'releases\\ApexElite.exe' -DestinationPath 'releases\\ApexElite-Windows-x64.zip' -Force"
echo Build complete.
echo EXE: %cd%\releases\ApexElite.exe
echo ZIP: %cd%\releases\ApexElite-Windows-x64.zip

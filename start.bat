@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo WiiMotionSteamVR startup
set "ROOT=%~dp0"
set "PKG=%ROOT%driver\wiimotionsteamvr"
set "BRIDGE=%PKG%\bin\win64\wii_bridge.exe"
if not exist "%PKG%\bin\win64\driver_wiimotionsteamvr.dll" (
  echo ERROR: SteamVR driver DLL is missing.
  echo Build the Windows x64 package with scripts\build-windows.ps1 or download a release package.
  pause & exit /b 1
)
if not exist "%BRIDGE%" (
  echo ERROR: HID bridge executable is missing: "%BRIDGE%"
  echo Build the packaged bridge using scripts\build-windows.ps1.
  pause & exit /b 1
)
set "VRPATHREG="
if not exist "%ROOT%scripts\find-steamvr.ps1" (
  echo ERROR: SteamVR discovery helper is missing: "%ROOT%scripts\find-steamvr.ps1"
  echo Re-extract the complete release ZIP. Do not copy start.bat alone.
  pause & exit /b 1
)
for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\find-steamvr.ps1" 2^>^&1`) do set "VRPATHREG=%%I"
if not defined VRPATHREG (
  echo ERROR: SteamVR was not found in Steam or its registered libraries.
  echo Install SteamVR through Steam, then run this file again.
  pause & exit /b 1
)
if not exist "%VRPATHREG%" (
  echo ERROR: SteamVR discovery returned a path that does not exist: "%VRPATHREG%"
  echo Check the Steam library and rerun start.bat.
  pause & exit /b 1
)
for %%I in ("%VRPATHREG%") do set "VRBIN=%%~dpI"
"%VRPATHREG%" | find /i "%PKG%" >nul
if errorlevel 1 (
  echo SteamVR driver is not installed. Install now? [Y/N]
  choice /c YN /n
  if errorlevel 2 exit /b 0
  "%VRPATHREG%" adddriver "%PKG%"
  if errorlevel 1 (echo ERROR: vrpathreg could not register the driver. Check SteamVR path and permissions.& pause & exit /b 1)
)
echo Starting HID bridge. Pair the Wii Remote in Windows Bluetooth settings first.
start "WiiMotionSteamVR HID Bridge" /b "%BRIDGE%" --config "%ROOT%config\config.json"
timeout /t 2 /nobreak >nul
tasklist /fi "imagename eq wii_bridge.exe" | find /i "wii_bridge.exe" >nul
if errorlevel 1 (echo ERROR: HID bridge failed to start. Check logs\bridge.log.& pause & exit /b 1)
tasklist /fi "imagename eq vrserver.exe" | find /i "vrserver.exe" >nul
if errorlevel 1 (
  if exist "%VRBIN%vrstartup.exe" start "SteamVR" "%VRBIN%vrstartup.exe"
)
echo HID bridge is running. SteamVR will enumerate WiiRemotePlus-R and WiiNunchuk-L.
pause

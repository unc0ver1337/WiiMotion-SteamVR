@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo WiiMotionSteamVR startup
set "ROOT=%~dp0"
set "PKG=%ROOT%driver\wiimotionsteamvr"
set "BRIDGE=%PKG%\bin\win64\wii_bridge.exe"
if not exist "%PKG%\bin\win64\driver_wiimotion.dll" (
  echo ERROR: SteamVR driver DLL is missing.
  echo Build the Windows x64 package with scripts\build-windows.ps1 or download a release package.
  pause & exit /b 1
)
if not exist "%BRIDGE%" (
  echo ERROR: HID bridge executable is missing: %BRIDGE%
  echo Build the packaged bridge using scripts\build-windows.ps1.
  pause & exit /b 1
)
set "STEAM="
for /f "tokens=2,*" %%A in ('reg query "HKCU\Software\Valve\Steam" /v SteamPath 2^>nul ^| find /i "SteamPath"') do set "STEAM=%%B"
if not defined STEAM for /f "tokens=2,*" %%A in ('reg query "HKLM\SOFTWARE\WOW6432Node\Valve\Steam" /v InstallPath 2^>nul ^| find /i "InstallPath"') do set "STEAM=%%B"
if not defined STEAM (echo ERROR: Steam install path not found. Install Steam or repair its registry entry.& pause & exit /b 1)
set "VRPATHREG=%STEAM%\steamapps\common\SteamVR\bin\win64\vrpathreg.exe"
if not exist "%VRPATHREG%" (echo ERROR: SteamVR not found. Install SteamVR through Steam.& pause & exit /b 1)
"%VRPATHREG%" | find /i "wiimotionsteamvr" >nul
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
  set "STEAMVR=%STEAM%\steamapps\common\SteamVR\bin\win64\vrstartup.exe"
  if exist "%STEAMVR%" start "SteamVR" "%STEAMVR%"
)
echo HID bridge is running. SteamVR will enumerate WiiRemotePlus-R and WiiNunchuk-L.
pause

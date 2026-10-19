@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%~dp0"
set "STEAM="
for /f "tokens=2,*" %%A in ('reg query "HKCU\Software\Valve\Steam" /v SteamPath 2^>nul ^| find /i "SteamPath"') do set "STEAM=%%B"
if not defined STEAM for /f "tokens=2,*" %%A in ('reg query "HKLM\SOFTWARE\WOW6432Node\Valve\Steam" /v InstallPath 2^>nul ^| find /i "InstallPath"') do set "STEAM=%%B"
if not defined STEAM (echo ERROR: Steam path not found; nothing was removed.& pause & exit /b 1)
set "VRPATHREG=%STEAM%\steamapps\common\SteamVR\bin\win64\vrpathreg.exe"
taskkill /im wii_bridge.exe /f >nul 2>&1
if exist "%VRPATHREG%" (
  "%VRPATHREG%" removedriver "%ROOT%driver\wiimotionsteamvr"
  if errorlevel 1 echo WARNING: driver deregistration reported an error.
) else echo WARNING: SteamVR vrpathreg not found; registration may remain.
echo Driver registration removal attempted. No SteamVR files or user configuration were deleted.
echo Build outputs can be removed manually after SteamVR stops.
pause

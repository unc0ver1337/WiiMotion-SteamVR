@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%~dp0"
set "VRPATHREG="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\find-steamvr.ps1"`) do set "VRPATHREG=%%I"
if not defined VRPATHREG (echo ERROR: SteamVR was not found; driver registration was not changed.& pause & exit /b 1)
taskkill /im wii_bridge.exe /f >nul 2>&1
if exist "%VRPATHREG%" (
  "%VRPATHREG%" removedriver "%ROOT%driver\wiimotionsteamvr"
  if errorlevel 1 echo WARNING: driver deregistration reported an error.
) else echo WARNING: SteamVR vrpathreg not found; registration may remain.
echo Driver registration removal attempted. No SteamVR files or user configuration were deleted.
echo Build outputs can be removed manually after SteamVR stops.
pause

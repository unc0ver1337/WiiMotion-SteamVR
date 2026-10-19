$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $root 'work\openvr\headers\openvr_driver.h'))) { & (Join-Path $PSScriptRoot 'fetch-openvr.ps1') }
python -m pip install --disable-pip-version-check -r (Join-Path $root 'bridge\requirements.txt')
python -m pip install --disable-pip-version-check pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --name wii_bridge --distpath (Join-Path $root 'dist\wii_bridge') (Join-Path $root 'bridge\src\wii_bridge.py')
cmake -S $root -B (Join-Path $root 'build') -A x64 -DOPENVR_ROOT=(Join-Path $root 'work\openvr')
cmake --build (Join-Path $root 'build') --config Release
if ($LASTEXITCODE -ne 0) { throw 'Windows x64 build failed.' }
New-Item -ItemType Directory -Force (Join-Path $root 'build\package\driver\wiimotionsteamvr\bin\win64') | Out-Null
Copy-Item (Join-Path $root 'dist\wii_bridge\wii_bridge.exe') (Join-Path $root 'build\package\driver\wiimotionsteamvr\bin\win64\wii_bridge.exe') -Force

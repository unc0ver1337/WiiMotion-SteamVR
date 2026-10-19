$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $root 'work\openvr'
if (Test-Path (Join-Path $dest 'headers\openvr_driver.h')) { Write-Host "OpenVR SDK present at $dest"; exit 0 }
New-Item -ItemType Directory -Force $dest | Out-Null
git init $dest
git -C $dest remote add origin https://github.com/ValveSoftware/openvr.git
git -C $dest fetch --depth 1 origin 0924064316de3effbcd1acf1e309182a2deb1c05
if ($LASTEXITCODE -ne 0) { throw 'Could not obtain the pinned official Valve OpenVR SDK revision.' }
git -C $dest checkout FETCH_HEAD

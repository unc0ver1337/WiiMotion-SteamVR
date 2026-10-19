# WiiMotion-SteamVR 1.0

Windows x64 SteamVR driver for one Wii Remote Plus and connected original Nunchuk. Creates two virtual Vive controllers. Includes packaged HID bridge: no Python installation required.

## Run

1. Extract the complete release ZIP to a permanent directory, including scripts/.
2. Pair Wii Remote Plus via Windows Bluetooth; connect Nunchuk and keep both still during calibration.
3. Run start.bat and accept driver registration. Restart SteamVR after installation or updating.
4. Hold 1 and 2 together once with both hands in the desired neutral pose to recenter.

B: right trigger; A: right grip; D-pad: held right trackpad; Plus: right menu; Minus: left menu. 1: left System; 2: right System. Nunchuk Z: left trigger; C: left grip; stick: left trackpad. System events remain active during the recenter chord.

## Tracking

Wii Remote orientation uses MotionPlus quaternion integration and gravity correction; yaw drifts. Nunchuk tilt uses its accelerometer and has no independent yaw. Both use a virtual forearm model relative to the HMD, not measured positional 6DoF. Translating the hand without rotating it is not tracked.

Orientation smoothing uses normalized quaternion interpolation with hemisphere correction: time constants 25 ms right and 45 ms left. Position smoothing uses 35 ms. These are filter settings, not measured total latency. Recenter bypasses orientation smoothing; buttons are not smoothed.

## Validation

Windows x64 MSVC and PyInstaller builds run in GitHub Actions with 10 synthetic protocol/math tests. Both devices and Vive bindings have loaded in the local SteamVR runtime. The user confirmed the preceding tracking version works. Final smoothing and chord behavior still require user validation; no measured latency or exhaustive game compatibility is claimed.

## Configuration and removal

config/config.json controls bridge retry, logging, stick deadzone and gyro sensitivity/gravity correction. Native hand offsets, mapping and filter constants currently use compiled defaults; other legacy config fields are not active. Run uninstall.bat from the installed package to remove its driver registration.

## Build

Visual Studio 2022 C++ tools, CMake 3.20+, Python 3.12 and Git are required. Run scripts/build-windows.ps1. CI packages the full release directory. Tests: python -m unittest discover -s tests -v.

## License

MIT project code. OpenVR headers are fetched from Valve at a pinned revision. hidapi uses its upstream BSD license; PyInstaller uses GPL with bootloader exception. Nintendo, HTC Vive and SteamVR belong to their respective owners.

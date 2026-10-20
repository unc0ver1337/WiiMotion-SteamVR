# WiiMotion-SteamVR 2.0

Windows x64 driver for an ordinary Nintendo Wii Remote with an original wired Nunchuk. One Bluetooth HID connection creates two virtual Vive controllers. Python and compilation are not required for the release ZIP.

## Version 2 changes

Gyroscope decoding, integration, bias calibration and MotionPlus activation have been removed. Both hands use the same accelerometer tilt, virtual arm and smoothing pipeline. Standard Nunchuk C/Z and 10-bit acceleration decoding replaces passthrough decoding. IPC v3 is 48 bytes and rejects older bridge formats. MotionPlus hardware is not required; Wii Remote Plus may work in ordinary remote mode, which needs hardware verification.

## Install and start

1. Extract the complete ZIP to a permanent directory. Keep scripts/, config/ and driver/ with start.bat.
2. Pair the Wii Remote in Windows Bluetooth settings and connect the Nunchuk. Disconnect an external MotionPlus attachment if present.
3. Run start.bat. Accept driver registration when prompted. Restart SteamVR after installing/updating the driver.
4. Hold both hands in a comfortable neutral pose and press 1+2 together to recenter.
5. SteamVR uses Vive Controller bindings. Per-game bindings may require adjustment.

Do not delete or move the registered directory without running uninstall.bat first. Stop the bridge with Ctrl+C in its console. Only one bridge instance can own the HID device.

## Controls

B: right trigger. A: right grip. D-pad: right trackpad direction and held click. Plus: right menu. Minus: left menu. 1: right System. 2: left System. 1+2: recenter both hands. Nunchuk Z: left trigger; C: left grip; stick: left trackpad, clicked while outside the deadzone. System events remain active with the recenter chord.

## Tracking and configuration

Both accelerometers measure gravity-relative tilt. Neither provides independent yaw or measured position. Position is a virtual forearm relative to the HMD; moving a hand without tilting is not tracked. Fast acceleration can distort tilt. Orientation uses 28 ms and position 22 ms exponential filter time constants, not measured total latency.

config/config.json has only active settings: logging_level, retry_seconds and stick_deadzone (fraction of axis range). Invalid values are clamped or use safe defaults. Bridge logs are under driver/wiimotionsteamvr/logs. A disconnected bridge clears controls after 250 ms; missing Nunchuk inputs reset after 500 ms.

## Removal and troubleshooting

Run uninstall.bat in the registered directory. It deregisters only that path; files can then be deleted after SteamVR closes. If controllers are absent, check SteamVR logs/vrserver.txt for the registered path and DLL load errors, ensure the add-on is enabled, and restart SteamVR. If no HID is found, verify Bluetooth pairing and close other Wii tools. If Nunchuk is absent, reconnect its plug and restart the bridge. Do not use an old 1.x bridge with the 2.0 DLL.

## Build and tests

Visual Studio 2022 C++ tools, CMake 3.20+, Git and Python 3.12 are required. Run scripts/build-windows.ps1. CI on windows-2022 builds MSVC x64 DLL, packages PyInstaller bridge and uploads the ZIP. Run python -m unittest discover -s tests -v.

Automated tests cover the ordinary Nunchuk bit layout, buttons, report validity, initialization ACK errors, VID/PID discovery, IPC v3 and disconnect controls. Ordinary Wii Remote hardware integration and per-game compatibility must be checked on hardware; previous 1.x passthrough hardware results do not validate this new protocol mode.

## License

MIT project code. Official OpenVR headers are fetched at a pinned Valve revision. hidapi uses its upstream BSD license; PyInstaller has a bootloader exception. No Hydra resources or Sixense SDK are used. Protocol reference: https://wiibrew.org/wiki/Wiimote/Extension_Controllers/Nunchuck

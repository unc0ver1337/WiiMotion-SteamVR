# WiiMotion-SteamVR

Windows SteamVR external driver and HID bridge for one Wii Remote Plus with a connected Nunchuk. It registers two `TrackedDeviceClass_Controller` devices: Wii Remote Plus as right hand and Nunchuk as left hand.

## Status

This repository contains a source implementation and Windows CI build. The current development environment has no MSVC/Windows SDK, SteamVR runtime, Bluetooth Wii Remote, or Nunchuk, so a local DLL build and hardware/runtime validation have not been performed. Check the Actions artifact before treating a package as a working release.

## Hardware and tracking limits

- Windows 10/11 x64; Nintendo Wii Remote Plus, MotionPlus and an original Nunchuk; Bluetooth HID.
- MotionPlus and Nunchuk use the `0x37` report and the Nunchuk passthrough bit layout.
- Remote orientation is a quaternion integration of gyro rates with low gain gravity correction for pitch/roll. Yaw has no absolute reference and drifts.
- The Nunchuk has no gyro. Its orientation cannot provide independent 3DoF tracking; its virtual controller follows HMD orientation while its gravity samples are reported over IPC for further two axis tilt estimation.
- Positions are fixed offsets transformed by the current raw HMD pose. They are emulated, not measured 6DoF.
- No positional accelerometer integration is used.

## Install and run

1. Download and extract the Windows x64 Actions artifact or release package. Keep `start.bat`, `uninstall.bat`, `config`, and `driver` in one directory.
2. Pair the Wii Remote Plus in Windows Bluetooth settings, then connect the Nunchuk to its extension socket.
3. Start SteamVR once so it finishes installation. Run `start.bat`; it finds Steam from the registry, checks `vrpathreg`, and asks before adding this external driver.
4. In SteamVR Controller Settings, load or create bindings for **WiiMotionSteamVR Controller**. The profile defines trackpad, trigger, grip and menu components.
5. Stop with Ctrl+C in the bridge console. Run `uninstall.bat` to remove only this external driver registration.

## Source build

Install Visual Studio 2022 C++ build tools, CMake 3.20+, Git, and Python 3.12. Run `scripts\build-windows.ps1` from PowerShell. It fetches Valve's OpenVR headers, builds the HID bridge with PyInstaller and compiles the x64 server driver. Run automated tests with `python -m unittest discover -s tests -v`.

## Configuration and diagnostics

Defaults live in `config/config.json`. The bridge logs discovery and sensor errors to its console. HID reports include a monotonic timestamp and sequence number; SteamVR rejects stale data and clears inputs after 250 ms. Configurable position offsets, binding remaps, gravity fusion tuning and persistent file logging are not yet wired into runtime behavior.

## Known implementation gaps

- Per-hand `input_profile` bindings need validation against the current SteamVR input schema; game bindings may need to be created manually.
- The current input components update trackpad axes but do not yet expose the standard pose component/profile interaction expected by every game.
- Configurable offsets are not loaded by the native driver; safe fixed HMD-relative offsets are used.
- Recenter is currently level-triggered while Home is held and resets the integrated orientation directly.
- Nunchuk gravity vector is transported but not yet used to rotate its virtual controller.
- Start/uninstall batches are source scripts and require package layout validation on a SteamVR Windows machine.
- Hardware tests, SteamVR runtime tests, latency measurements and a Windows build are pending. CI must successfully execute before calling this a release.

## License

Project code: MIT. The OpenVR SDK is fetched from Valve's official repository during build and is not vendored. `hidapi` is distributed under its upstream BSD license; PyInstaller is GPLv2 with a bootloader exception. Nintendo and SteamVR are trademarks of their owners.

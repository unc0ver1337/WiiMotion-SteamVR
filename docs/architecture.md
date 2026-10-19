# Architecture

`bridge/src/wii_bridge.py` exclusively opens the Nintendo HID device and performs MotionPlus/Nunchuk initialization, report decoding, bias calibration, quaternion integration and reconnect. It publishes fixed-size version 1 frames over a local Windows named pipe (`\\.\pipe\WiiMotionSteamVR`). Each frame has sequence, monotonic timestamp, connection flags, buttons, quaternion, Nunchuk gravity vector and stick state.

`driver/src/driver.cpp` implements Valve OpenVR's `IServerTrackedDeviceProvider` and two `ITrackedDeviceServerDriver` objects. The provider starts a separate pipe reader. SteamVR's `RunFrame` never waits for Bluetooth or pipe I/O; it consumes the latest frame and clears stale controls. Devices have stable serials and role hints.

The driver's frame loop reads the raw HMD pose and transforms fixed shoulder/hand offsets into SteamVR world coordinates. The right controller combines HMD world orientation with the remote gyro orientation; the left follows HMD orientation because Nunchuk has no gyro.

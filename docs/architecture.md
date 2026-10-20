# Architecture 2.0

One hidapi connection reads 0x37 (buttons, remote acceleration and standard extension data). Initialization writes only A400F0=55 and A400FB=00, with acknowledgements. No MotionPlus activation or alternating gyro decoding exists.

A worker serves a 48-byte version-3 Named Pipe frame: header, sequence and monotonic timestamp, flags/buttons, normalized Nunchuk gravity vector, stick, C/Z and raw 8-bit remote acceleration. Native SteamVR input updates use a separate pipe reader and reject stale frames after 250 ms. Both hands share tilt-to-quaternion, recenter, smoothing and virtual forearm code.

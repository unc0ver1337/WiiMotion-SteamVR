# Installation

Use a successful Windows x64 CI artifact. Extract its full folder layout, pair the Wii Remote in Windows Bluetooth settings, connect the Nunchuk, then run `start.bat`. Driver registration uses SteamVR's `vrpathreg.exe adddriver`; removal uses `removedriver` with the matching driver directory. Steam is found via its registry entry, not a fixed drive path. No administrator elevation is requested.

Run SteamVR, inspect its system report and `logs\vrserver.txt` if devices do not appear. The bridge and driver must run in the same Windows user session because the named pipe is local.

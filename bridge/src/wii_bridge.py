"""Wii Remote + standard Nunchuk HID bridge for WiiMotionSteamVR (Windows)."""
from __future__ import annotations
import ctypes
import json
import argparse
import logging
import math
import os
import struct
import threading
import time
from pathlib import Path

VID, PIDS, REPORT = 0x057E, (0x0306, 0x0330), 0x37
PIPE = r"\\.\pipe\WiiMotionSteamVR"
FRAME = struct.Struct("<IHHQIH H fff ff B3B")
MAGIC, VERSION, CONNECTED, HAS_NUNCHUK = 0x31534D57, 3, 1, 2
log = logging.getLogger("WiiMotionSteamVR")

def decode_buttons(report: bytes) -> int:
    return ((report[1] << 8) | report[2]) & 0x1F9F

def extension_payload(report: bytes):
    if not report or report[0] != REPORT or len(report) < 22:
        return None
    d = report[16:22]
    if d == bytes(6) or d == bytes([255]) * 6:
        return None
    return d

def decode_nunchuk(d: bytes):
    ax=(d[2]<<2)|((d[5]>>2)&3)
    ay=(d[3]<<2)|((d[5]>>4)&3)
    az=(d[4]<<2)|((d[5]>>6)&3)
    return d[0],d[1],ax,ay,az,not bool(d[5]&2),not bool(d[5]&1)

def axis(raw, center=128, dz=7):
    delta=raw-center
    if abs(delta)<=dz: return 0.
    span=(128 if delta<0 else 127)-dz
    return max(-1.,min(1.,(delta-math.copysign(dz,delta))/span))

def gravity_direction(ax,ay,az):
    n=math.sqrt(ax*ax+ay*ay+az*az)
    if n<20 or n>900: return (0.,0.,0.)
    return (ax/n,ay/n,az/n)

def pack_frame(seq, flags, timestamp, buttons, accel, stick, nc_buttons, remote_accel=(128,128,128)):
    return FRAME.pack(MAGIC,VERSION,FRAME.size,timestamp,seq,flags,buttons,
                      *accel,*stick,nc_buttons,*(int(v) for v in remote_accel))

def report_devices(hid):
    return [d for d in hid.enumerate(VID,0) if d.get("product_id") in PIDS]

def write_report(remote, payload):
    if remote.write(bytes(payload)) <= 0: raise OSError("HID write failed")

def write_register(remote,address,value):
    write_report(remote,[0x16,*address.to_bytes(4,"big"),1,value,*([0]*15)])
    deadline=time.monotonic()+2
    while time.monotonic()<deadline:
        r=remote.read(64,100)
        if r and r[0]==0x22 and len(r)>=5 and r[3]==0x16:
            if r[4]: raise RuntimeError(f"Register {address:08X} error {r[4]}")
            return
    raise TimeoutError(f"Register {address:08X} acknowledgement timed out")

def initialize(remote):
    write_register(remote,0x04A400F0,0x55); time.sleep(.1)
    write_register(remote,0x04A400FB,0)
    write_report(remote,[0x12,0x04,REPORT])

class PipeServer:
    """Single-client, message-mode Windows pipe. A mutex limits the bridge to one instance."""
    def __init__(self): self.handle=None
    def serve(self, stop, latest):
        if os.name!="nt": raise RuntimeError("Wii HID bridge requires Windows")
        from ctypes import wintypes
        k=ctypes.WinDLL("kernel32",use_last_error=True)
        k.CreateNamedPipeW.restype=wintypes.HANDLE
        k.CreateNamedPipeW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID]
        k.ConnectNamedPipe.argtypes=[wintypes.HANDLE,wintypes.LPVOID]
        k.WriteFile.argtypes=[wintypes.HANDLE,wintypes.LPCVOID,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),wintypes.LPVOID]
        k.DisconnectNamedPipe.argtypes=[wintypes.HANDLE]
        k.CloseHandle.argtypes=[wintypes.HANDLE]
        while not stop.is_set():
            h=k.CreateNamedPipeW(PIPE,0x00000002,0x00000000,1,4096,4096,1000,None)
            if h==wintypes.HANDLE(-1).value: raise ctypes.WinError(ctypes.get_last_error())
            self.handle=h
            connected=k.ConnectNamedPipe(h,None) or ctypes.get_last_error()==535
            if connected:
                while not stop.is_set():
                    packet=latest()
                    written=wintypes.DWORD()
                    if not k.WriteFile(h,packet,len(packet),ctypes.byref(written),None): break
                    stop.wait(.004)
                k.DisconnectNamedPipe(h)
            k.CloseHandle(h); self.handle=None
    def close(self):
        if self.handle:
            k=ctypes.WinDLL("kernel32"); k.CancelIoEx.argtypes=[ctypes.c_void_p,ctypes.c_void_p];k.CloseHandle.argtypes=[ctypes.c_void_p]
            k.CancelIoEx(self.handle,None); k.CloseHandle(self.handle)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--config",type=Path); args=parser.parse_args()
    base=Path(sys.argv[0]).resolve().parents[2] if getattr(sys,"frozen",False) else Path(__file__).resolve().parents[2]
    config_path=args.config or (base/"config/config.json")
    cfg={"logging_level":"INFO","retry_seconds":3.,"stick_deadzone":.08}
    try:
        loaded=json.loads(config_path.read_text(encoding="utf-8-sig"))
        if not isinstance(loaded,dict): raise ValueError("configuration must be an object")
        cfg["logging_level"]=str(loaded.get("logging_level","INFO"))
        for key,low,high in (("retry_seconds",1.,30.),("stick_deadzone",0.,.45)):
            value=float(loaded.get(key,cfg[key]))
            if not math.isfinite(value): raise ValueError(key+" must be finite")
            cfg[key]=max(low,min(high,value))
    except (OSError,ValueError,TypeError) as exc:
        print("Invalid/missing configuration; using safe defaults:",exc)
    log_dir=base/"logs"; log_dir.mkdir(exist_ok=True)
    logging.basicConfig(level=getattr(logging,str(cfg.get("logging_level","INFO")).upper(),logging.INFO),format="%(asctime)s %(levelname)s %(message)s",handlers=[logging.FileHandler(log_dir/"bridge.log",encoding="utf-8"),logging.StreamHandler()])
    import hid
    mutex=None
    if os.name=="nt":
        kernel=ctypes.WinDLL("kernel32",use_last_error=True)
        kernel.CreateMutexW.restype=ctypes.c_void_p
        kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p]
        mutex=kernel.CreateMutexW(None,False,"Local\\WiiMotionSteamVR-HID")
        if not mutex: raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error()==183: raise RuntimeError("Another WiiMotionSteamVR bridge already owns the HID device")
    latest_lock=threading.Lock(); latest_packet=pack_frame(0,0,0,0,(0,1,0),(0,0),0)
    def get_latest():
        with latest_lock:return latest_packet
    stop=threading.Event(); pipe=PipeServer()
    threading.Thread(target=pipe.serve,args=(stop,get_latest),daemon=True).start()
    seq=0; remote=None
    try:
        while True:
            try:
                devices=report_devices(hid)
                if not devices:
                    log.warning("Wii Remote not found; pair it in Windows Bluetooth settings")
                    time.sleep(max(1.,float(cfg.get("retry_seconds",3)))); continue
                # Enumeration is VID/PID filtered; a process-wide mutex prevents a second bridge opening HID.
                remote=hid.device(); remote.open_path(devices[0]["path"]); remote.set_nonblocking(False)
                log.info("Connected Wii Remote PID 0x%04X",devices[0]["product_id"])
                initialize(remote); log.info("WiiMotion 2.0: ordinary Wii Remote + Nunchuk, accelerometer-only tracking")
                nunchuk=(128,128,512,512,512,False,False); nc_seen=0
                last=time.monotonic(); reported_nunchuk=False
                nunchuk_wait=last; reported_missing_nunchuk=False
                while True:
                    report=remote.read(64,100); now=time.monotonic()
                    if report and report[0] in (0x20,0x30,0x31): write_report(remote,[0x12,0x04,REPORT])
                    d=extension_payload(report)
                    if not report or report[0]!=REPORT or len(report)<22:
                        if now-last>1.0: raise RuntimeError("No valid Wii Remote reports for one second; reconnecting")
                        continue
                    last=now; buttons=decode_buttons(report)
                    if d is not None:
                        nunchuk=decode_nunchuk(d); nc_seen=now
                        if not reported_nunchuk:
                            log.info("Standard Nunchuk packets detected"); reported_nunchuk=True
                    if not reported_nunchuk and not reported_missing_nunchuk and now-nunchuk_wait>3:
                        log.warning("Nunchuk not detected; check the extension connector and initialization")
                        reported_missing_nunchuk=True
                    sx,sy,ax,ay,az,c,z=nunchuk
                    if now-nc_seen>.5: sx=sy=128;ax=ay=az=512;c=z=False
                    nc_buttons=int(c)|(int(z)<<1)
                    flags=CONNECTED|(HAS_NUNCHUK if now-nc_seen<.5 else 0)
                    dz=min(.45,max(0.,float(cfg.get("stick_deadzone",.08))))
                    packet=pack_frame(seq,flags,time.perf_counter_ns(),buttons,gravity_direction(ax-512,ay-512,az-512),(axis(sx,dz=dz*127),axis(sy,dz=dz*127)),nc_buttons,report[3:6])
                    seq=(seq+1)&0xffffffff
                    with latest_lock:latest_packet=packet
                    if now-last>1.0: raise RuntimeError("No valid Wii Remote reports for one second; reconnecting")
            except KeyboardInterrupt:
                break
            except Exception as exc:
                log.exception("HID connection lost or initialization failed: %s",exc)
            finally:
                if remote:
                    try: remote.close()
                    except Exception: pass
                    remote=None
                with latest_lock: latest_packet=pack_frame(seq,0,0,0,(0,0,0),(0,0),0)
            time.sleep(max(1.,float(cfg.get("retry_seconds",3))))
    except KeyboardInterrupt: pass
    finally:
        stop.set();pipe.close()
        if remote:
            try: remote.close()
            except Exception: pass
        if mutex:
            kernel=ctypes.WinDLL("kernel32");kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(mutex)

if __name__=="__main__":
    import sys
    try: main()
    except Exception as e:
        log.exception("Bridge stopped: %s",e)
        input("Press Enter to close...")

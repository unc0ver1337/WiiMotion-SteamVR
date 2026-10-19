"""Wii MotionPlus + Nunchuk HID bridge for WiiMotionSteamVR (Windows)."""
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
FRAME = struct.Struct("<IHHQIH H ffff fff ff B3x")
MAGIC, VERSION, CONNECTED, HAS_NUNCHUK = 0x31534D57, 1, 1, 2
log = logging.getLogger("WiiMotionSteamVR")

def decode_buttons(report: bytes) -> int:
    return ((report[1] << 8) | report[2]) & 0x1F9F

def extension_payload(report: bytes):
    if not report or report[0] != REPORT or len(report) < 22:
        return None
    d = report[16:22]
    if (d[5] & 1) or d == bytes(6) or d == bytes([255]) * 6:
        return None
    return d

def decode_gyro(d: bytes):
    return ((d[0] | ((d[3] & 0xFC) << 6), d[2] | ((d[5] & 0xFC) << 6),
             d[1] | ((d[4] & 0xFC) << 6)),
            (bool(d[3] & 2), bool(d[3] & 1), bool(d[4] & 2)))

def decode_nunchuk(d: bytes):
    ax=(d[2]<<2)|((d[5]&0x10)>>3); ay=(d[3]<<2)|((d[5]&0x20)>>4)
    az=((d[4]&0xFE)<<2)|((d[5]&0xC0)>>5)
    return d[0], d[1], ax, ay, az, not bool(d[5]&8), not bool(d[5]&4)

class Quaternion:
    def __init__(self): self.w,self.x,self.y,self.z=1.,0.,0.,0.
    def reset(self): self.w,self.x,self.y,self.z=1.,0.,0.,0.
    def set(self,values): self.w,self.x,self.y,self.z=values
    def multiply(self,b):
        a=(self.w,self.x,self.y,self.z)
        self.w=a[0]*b[0]-a[1]*b[1]-a[2]*b[2]-a[3]*b[3]
        self.x=a[0]*b[1]+a[1]*b[0]+a[2]*b[3]-a[3]*b[2]
        self.y=a[0]*b[2]-a[1]*b[3]+a[2]*b[0]+a[3]*b[1]
        self.z=a[0]*b[3]+a[1]*b[2]-a[2]*b[1]+a[3]*b[0]
        n=math.sqrt(self.w**2+self.x**2+self.y**2+self.z**2) or 1
        self.w,self.x,self.y,self.z=(v/n for v in (self.w,self.x,self.y,self.z))
    def integrate(self, rates, dt):
        mag=math.sqrt(sum(v*v for v in rates))
        if mag < 1e-9 or dt <= 0 or dt > .1: return
        h=mag*dt/2; s=math.sin(h)/mag
        self.multiply((math.cos(h),*(v*s for v in rates)))
    def rotate(self,v):
        w,x,y,z=self.w,self.x,self.y,self.z; a,b,c=v
        return ((1-2*(y*y+z*z))*a+2*(x*y-w*z)*b+2*(x*z+w*y)*c,
                2*(x*y+w*z)*a+(1-2*(x*x+z*z))*b+2*(y*z-w*x)*c,
                2*(x*z-w*y)*a+2*(y*z+w*x)*b+(1-2*(x*x+y*y))*c)
    @staticmethod
    def from_to(a,b):
        dot=sum(x*y for x,y in zip(a,b))
        if dot < -0.999999: return (0.,1.,0.,0.)
        q=(1+dot,a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
        n=math.sqrt(sum(x*x for x in q)) or 1
        return tuple(x/n for x in q)

class Gyro:
    def __init__(self,gravity_gain=.015,sensitivity=1.,max_rate=12.):
        self.bias=[0.,0.,0.]; self.count=0; self.ready=False; self.q=Quaternion(); self.last=None
        self.samples=[];self.accel_sum=[0.,0.,0.];self.accel_count=0
        self.gravity_gain=min(.1,max(0.,float(gravity_gain)));self.sensitivity=min(4.,max(.1,float(sensitivity)));self.max_rate=min(20.,max(2.,float(max_rate)))
    def update(self,d,now,accel):
        raw,slow=decode_gyro(d)
        if any(v<1000 or v>15000 for v in raw): return False
        if not self.ready:
            if all(slow):
                self.samples.append(raw);self.samples=self.samples[-5:]
                stable=len(self.samples)==5 and all(max(c)-min(c)<=30 for c in zip(*self.samples))
                if stable:
                    self.count+=1
                    for i,v in enumerate(raw): self.bias[i]+=(v-self.bias[i])/self.count
                    av=[float(v-128) for v in accel];an=math.sqrt(sum(v*v for v in av))
                    if 15<=an<=110:
                        for i,v in enumerate(av):self.accel_sum[i]+=v
                        self.accel_count+=1
                    if self.count>=60:
                        self.ready=True
                        if self.accel_count:
                            av=[v/self.accel_count for v in self.accel_sum];n=math.sqrt(sum(v*v for v in av))
                            if n>0:self.q.set(Quaternion.from_to(tuple(v/n for v in av),(0.,1.,0.)))
            self.last=now; return True
        dt=now-self.last if self.last is not None else 0; self.last=now
        if not 0<dt<.1: return True
        rates=[(v-b)/13.768*(1 if s else 2000/440)*math.pi/180*self.sensitivity for v,b,s in zip(raw,self.bias,slow)]
        rates=(rates[1],-rates[2],-rates[0]); mag=math.sqrt(sum(v*v for v in rates))
        if mag>self.max_rate: rates=[v*self.max_rate/mag for v in rates]
        self.q.integrate(rates,dt)
        av=tuple(float(v-128) for v in accel);an=math.sqrt(sum(v*v for v in av))
        if self.gravity_gain and 15<=an<=110:
            aw=self.q.rotate(tuple(v/an for v in av));ex,ey,ez=-aw[2],0.,aw[0]
            en=math.sqrt(ex*ex+ey*ey+ez*ez)
            if en>1e-6:
                angle=self.gravity_gain*dt*en/2;scale=math.sin(angle)/en
                corr=(math.cos(angle),ex*scale,ey*scale,ez*scale)
                q=self.q;self.q.set((corr[0]*q.w-corr[1]*q.x-corr[2]*q.y-corr[3]*q.z,
                    corr[0]*q.x+corr[1]*q.w+corr[2]*q.z-corr[3]*q.y,
                    corr[0]*q.y-corr[1]*q.z+corr[2]*q.w+corr[3]*q.x,
                    corr[0]*q.z+corr[1]*q.y-corr[2]*q.x+corr[3]*q.w))
                n=math.sqrt(sum(v*v for v in (self.q.w,self.q.x,self.q.y,self.q.z))) or 1
                self.q.set(tuple(v/n for v in (self.q.w,self.q.x,self.q.y,self.q.z)))
        if all(slow) and mag<.035:
            for i,v in enumerate(raw): self.bias[i]+=(v-self.bias[i])*.0002
        return True
    def recenter(self): self.q.reset()

def axis(raw, center=128, dz=7):
    delta=raw-center
    if abs(delta)<=dz: return 0.
    span=(128 if delta<0 else 127)-dz
    return max(-1.,min(1.,(delta-math.copysign(dz,delta))/span))

def gravity_direction(ax,ay,az):
    n=math.sqrt(ax*ax+ay*ay+az*az)
    if n<20 or n>900: return (0.,0.,0.)
    return (ax/n,ay/n,az/n)

def pack_frame(seq, flags, timestamp, buttons, q, accel, stick, nc_buttons):
    return FRAME.pack(MAGIC,VERSION,FRAME.size,timestamp,seq,flags,buttons,
                      q.w,q.x,q.y,q.z,*accel,*stick,nc_buttons)

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
    write_register(remote,0x04A600F0,0x55); time.sleep(.1)
    write_register(remote,0x04A600FE,5); time.sleep(.2)
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
    cfg=json.loads(config_path.read_text(encoding="utf-8"))
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
    latest_lock=threading.Lock(); latest_packet=pack_frame(0,0,0,0,Quaternion(),(0,1,0),(0,0),0)
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
                initialize(remote); log.info("MotionPlus initialized; collecting bias while waiting for valid 0x37 gyro packets")
                nunchuk=(128,128,512,512,512,False,False); nc_seen=0
                gcfg=cfg.get("gyro",{})
                gyro=Gyro(gcfg.get("gravity_correction",.015),gcfg.get("sensitivity",1.),gcfg.get("max_rate_rad_s",12.))
                last=lastgyro=time.monotonic(); reported_nunchuk=False; reported_calibration=False
                nunchuk_wait=last; reported_missing_nunchuk=False; previous_buttons=0
                while True:
                    report=remote.read(64,100); now=time.monotonic()
                    if report and report[0] in (0x20,0x30,0x31): write_report(remote,[0x12,0x04,REPORT])
                    d=extension_payload(report)
                    if not report or report[0]!=REPORT or len(report)<22:
                        if now-lastgyro>1.0: raise RuntimeError("No valid MotionPlus gyro packets for one second; retrying device")
                        continue
                    last=now; buttons=decode_buttons(report)
                    if (buttons & 3)==3 and (previous_buttons & 3)!=3: gyro.recenter()
                    previous_buttons=buttons
                    if d is not None and d[5]&2:
                        accel=tuple(float(v) for v in report[3:6])
                        if gyro.update(d,now,accel): lastgyro=now
                    elif d is not None:
                        nunchuk=decode_nunchuk(d); nc_seen=now
                        if not reported_nunchuk:
                            log.info("Nunchuk passthrough packets detected"); reported_nunchuk=True
                    if not reported_nunchuk and not reported_missing_nunchuk and now-nunchuk_wait>3:
                        log.warning("Nunchuk passthrough not detected; check the extension connector and initialization")
                        reported_missing_nunchuk=True
                    if now-last>.3: buttons=0; nunchuk=(128,128,512,512,512,False,False)
                    sx,sy,ax,ay,az,c,z=nunchuk
                    if now-nc_seen>.5: c=z=False
                    nc_buttons=int(c)|(int(z)<<1)
                    flags=CONNECTED|(HAS_NUNCHUK if now-nc_seen<.5 else 0)
                    dz=min(.45,max(0.,float(cfg.get("stick_deadzone",.08))))
                    packet=pack_frame(seq,flags,time.perf_counter_ns(),buttons,gyro.q,gravity_direction(ax-512,ay-512,az-512),(axis(sx,dz=dz),axis(sy,dz=dz)),nc_buttons)
                    seq=(seq+1)&0xffffffff
                    with latest_lock:latest_packet=packet
                    if gyro.ready and not reported_calibration:
                        log.info("Gyroscope bias calibrated");reported_calibration=True
                    if now-lastgyro>1.0: raise RuntimeError("No valid MotionPlus gyro packets for one second; retrying device")
            except KeyboardInterrupt:
                break
            except Exception as exc:
                log.exception("HID connection lost or initialization failed: %s",exc)
            finally:
                if remote:
                    try: remote.close()
                    except Exception: pass
                    remote=None
                with latest_lock: latest_packet=pack_frame(seq,0,0,0,Quaternion(),(0,0,0),(0,0),0)
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

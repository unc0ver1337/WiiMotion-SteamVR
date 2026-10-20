import importlib.util,sys,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location("bridge",Path(__file__).resolve().parents[1]/"bridge/src/wii_bridge.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
def report(d,buttons=0):return bytes([0x37,buttons>>8,buttons&255,*([128]*3),*([0]*10),*d])
class Tests(unittest.TestCase):
    def test_report_length(self):
        for r in (b"",bytes([0x37])+bytes(20),bytes([0x34])+bytes(21)):self.assertIsNone(b.extension_payload(r))
    def test_invalid_extension(self):
        for d in (bytes(6),bytes([255])*6):self.assertIsNone(b.extension_payload(report(d)))
    def test_standard_nunchuk_accepts_unpressed_z_bit(self):
        d=bytes([128,128,128,128,180,3]);self.assertEqual(b.extension_payload(report(d)),d)
    def test_standard_nunchuk_buttons(self):
        for bits,c,z in ((0,True,True),(1,True,False),(2,False,True),(3,False,False)):
            self.assertEqual(b.decode_nunchuk(bytes([128,128,128,128,180,bits]))[-2:],(c,z))
    def test_standard_nunchuk_all_accel_low_bits(self):
        self.assertEqual(b.decode_nunchuk(bytes([10,20,100,120,140,0b11100111]))[:5],(10,20,401,482,563))
    def test_remote_buttons(self):self.assertEqual(b.decode_buttons(report(bytes(6),0x1f9f)),0x1f9f)
    def test_deadzone(self):
        self.assertEqual(b.axis(128),0);self.assertEqual(b.axis(131),0);self.assertEqual(b.axis(0),-1);self.assertEqual(b.axis(255),1)
    def test_gravity(self):
        self.assertEqual(b.gravity_direction(0,0,0),(0,0,0));self.assertEqual(b.gravity_direction(0,100,0),(0,1,0))
    def test_ipc_v3_roundtrip(self):
        p=b.pack_frame(7,3,123,0x44,(.1,.2,.3),(.2,-.4),2,(100,150,200));v=b.FRAME.unpack(p)
        self.assertEqual(len(p),48);self.assertEqual(v[:7],(b.MAGIC,3,48,123,7,3,0x44));self.assertEqual(v[-4:],(2,100,150,200))
    def test_disconnect_resets_controls(self):
        v=b.FRAME.unpack(b.pack_frame(0,0,0,0,(0,0,0),(0,0),0));self.assertEqual(v[5:7],(0,0));self.assertEqual(v[7:13],(0,0,0,0,0,0))
    def test_initialization_standard_registers_only(self):
        class Hid:
            def __init__(self):self.writes=[]
            def write(self,p):self.writes.append(p);return len(p)
            def read(self,*args):return [0x22,0,0,0x16,0]
        h=Hid()
        with patch.object(b.time,"sleep"):b.initialize(h)
        self.assertEqual([int.from_bytes(w[1:5],"big") for w in h.writes[:-1]],[0x04a400f0,0x04a400fb])
        self.assertEqual(h.writes[-1],bytes([0x12,4,0x37]))
    def test_write_error(self):
        class Hid:
            def write(self,p):return len(p)
            def read(self,*args):return [0x22,0,0,0x16,7]
        with self.assertRaises(RuntimeError):b.write_register(Hid(),0x04a400f0,0x55)
    def test_hid_filter(self):
        class Hid:
            def enumerate(self,*args):return [{"product_id":0x0306},{"product_id":0x0330},{"product_id":123}]
        self.assertEqual(len(b.report_devices(Hid())),2)
if __name__=="__main__":unittest.main()

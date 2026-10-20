import importlib.util, sys, unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"bridge/src/wii_bridge.py"
spec=importlib.util.spec_from_file_location("wii_bridge",P); b=importlib.util.module_from_spec(spec);sys.modules[spec.name]=b;spec.loader.exec_module(b)
def report(d,buttons=0): return bytes([0x37,(buttons>>8)&255,buttons&255,*([0]*13),*d])
def gyro(yaw=8063,pitch=8063,roll=8063,slow=(1,1,1)):
    return bytes([yaw&255,roll&255,pitch&255,((yaw>>8)<<2)|(2 if slow[0] else 0)|(1 if slow[1] else 0),((roll>>8)<<2)|(2 if slow[2] else 0),((pitch>>8)<<2)])
class BridgeTests(unittest.TestCase):
    def test_report_mode_length_and_bad_extension(self):
        self.assertIsNone(b.extension_payload(b""));self.assertIsNone(b.extension_payload(bytes([0x34])+bytes(21)))
        self.assertIsNone(b.extension_payload(bytes([0x37])+bytes(20)));self.assertIsNone(b.extension_payload(report(bytes(6))))
        self.assertIsNone(b.extension_payload(report(bytes([255])*6)))
        bad=bytearray([128,128,80,90,101,0]);bad[5]|=1;self.assertIsNone(b.extension_payload(report(bad)))
    def test_buttons_and_gyro_fields(self):
        self.assertEqual(b.decode_buttons(report(bytes([128,128,0,0,1,0]),0x0800)),0x0800)
        self.assertEqual(b.decode_gyro(gyro(9000,7500,8200))[0],(9000,7500,8200))
    def test_nunchuk_stick_accel_cz(self):
        x,y,ax,ay,az,c,z=b.decode_nunchuk(bytes([0,255,100,120,0x80,0xCC]))
        self.assertEqual((x,y),(0,255));self.assertEqual((ax,ay,az),(400,480,518));self.assertFalse(c);self.assertFalse(z)
    def test_alternating_packets_retain_nunchuk(self):
        nc=bytes([10,200,100,120,0x80,0xCC]);state=b.decode_nunchuk(nc);g=gyro()
        self.assertEqual(b.extension_payload(report(g)),g);self.assertEqual(state,b.decode_nunchuk(nc));self.assertEqual((state[0],state[1]),(10,200))
    def test_stick_deadzone(self): self.assertEqual(b.axis(128),0);self.assertEqual(b.axis(0),-1);self.assertEqual(b.axis(255),1)
    def test_accelerometer_gravity_vector(self):
        self.assertEqual(b.gravity_direction(0,0,0),(0.0,0.0,0.0))
        gx,gy,gz=b.gravity_direction(0,0,100)
        self.assertAlmostEqual(gx,0);self.assertAlmostEqual(gy,0);self.assertAlmostEqual(gz,1)
    def test_quaternion_integration_and_recenter(self):
        q=b.Quaternion()
        for _ in range(100):q.integrate((0,1,0),.01)
        self.assertAlmostEqual(sum(v*v for v in (q.w,q.x,q.y,q.z)),1,places=8);self.assertNotAlmostEqual(abs(q.w),1)
        q.reset();self.assertEqual((q.w,q.x,q.y,q.z),(1,0,0,0))
    def test_bias_calibration_and_serialization(self):
        g=b.Gyro()
        for i in range(65):g.update(gyro(8050,8100,8200),i*.01,(0,0,1024))
        self.assertTrue(g.ready)
        values=b.FRAME.unpack(b.pack_frame(5,b.CONNECTED|b.HAS_NUNCHUK,123,0x44,g.q,(0,0,1024),(.2,-.3),3))
        self.assertEqual(len(b.FRAME.pack(*values)),64);self.assertEqual((values[0],values[1],values[2],values[4],values[5],values[6]),(b.MAGIC,2,64,5,3,0x44))
    def test_gravity_initializes_tilt_without_yaw_reference(self):
        g=b.Gyro()
        for i in range(70):g.update(gyro(),i*.01,(178,128,128))
        self.assertTrue(g.ready)
        rotated=g.q.rotate((1.,0.,0.))
        self.assertAlmostEqual(rotated[0],0.,places=5);self.assertAlmostEqual(rotated[1],1.,places=5)
    def test_remote_acceleration_is_separate_from_orientation(self):
        q=b.Quaternion();q.integrate((.3,.2,-.1),.05)
        first=b.FRAME.unpack(b.pack_frame(1,b.CONNECTED,100,0,q,(0,1,0),(0,0),0,(100,150,200)))
        second=b.FRAME.unpack(b.pack_frame(2,b.CONNECTED,200,0,q,(0,1,0),(0,0),0,(200,90,120)))
        self.assertEqual(first[7:11],second[7:11])
        self.assertEqual(first[-3:],(100,150,200));self.assertEqual(second[-3:],(200,90,120))
    def test_disconnect_frame_clears_actions(self):
        values=b.FRAME.unpack(b.pack_frame(6,0,900,0,b.Quaternion(),(0,0,0),(0,0),0))
        self.assertEqual(values[5],0);self.assertEqual(values[6],0);self.assertEqual(values[-4],0);self.assertEqual(values[-3:],(128,128,128))
if __name__=="__main__":unittest.main()

#pragma once
#include "protocol.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>

namespace wms {
struct Vec3 { double x{}, y{}, z{}; };
struct Quat {
    double w{1}, x{}, y{}, z{};
    void normalize() { double n=std::sqrt(w*w+x*x+y*y+z*z); if(n>1e-12){w/=n;x/=n;y/=n;z/=n;} }
    void integrate(Vec3 omega, double dt) {
        const double a=std::sqrt(omega.x*omega.x+omega.y*omega.y+omega.z*omega.z);
        if(a<1e-9 || dt<=0) return;
        const double h=a*dt*.5, s=std::sin(h)/a;
        Quat d{std::cos(h),omega.x*s,omega.y*s,omega.z*s};
        Quat r{w*d.w-x*d.x-y*d.y-z*d.z,w*d.x+x*d.w+y*d.z-z*d.y,
               w*d.y-x*d.z+y*d.w+z*d.x,w*d.z+x*d.y-y*d.x+z*d.w};
        *this=r; normalize();
    }
    static Quat from_to(Vec3 a, Vec3 b) {
        double d=a.x*b.x+a.y*b.y+a.z*b.z;
        Quat q{1+d,a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};
        if(d < -0.999999) q={0,1,0,0};
        q.normalize(); return q;
    }
};
inline std::array<double,3> decode_gyro(const uint8_t*d) {
    return {double(d[0] | ((d[3]&0xFC)<<6)), double(d[2] | ((d[5]&0xFC)<<6)), double(d[1] | ((d[4]&0xFC)<<6))};
}
inline std::array<bool,3> decode_slow(const uint8_t*d) { return {bool(d[3]&2),bool(d[3]&1),bool(d[4]&2)}; }
inline std::array<int,6> decode_nunchuk(const uint8_t*d) {
    return {int(d[0]),int(d[1]),int((d[2]<<2)|((d[5]&0x10)>>3)),int((d[3]<<2)|((d[5]&0x20)>>4)),
            int(((d[4]&0xFE)<<2)|((d[5]&0xC0)>>5)),int((!bool(d[5]&8))|((!bool(d[5]&4))<<1))};
}
inline double deadzone(uint8_t raw,double center,double span,double dz) {
    double v=(raw-center)/span; if(std::abs(v)<=dz) return 0;
    return std::copysign(std::min(1.0,(std::abs(v)-dz)/(1-dz)),v);
}
inline bool usable_extension(const uint8_t*d) {
    bool zero=true, full=true; for(int i=0;i<6;i++){zero &= d[i]==0;full &= d[i]==255;}
    return !zero && !full && !(d[5]&1);
}
struct Fusion {
    Quat q{}; std::array<double,3> bias{}; bool calibrated{}; uint32_t stable{};
    void recenter() { q={}; }
    void update(const uint8_t*d,double dt,const uint16_t*accel=nullptr) {
        auto raw=decode_gyro(d); auto slow=decode_slow(d);
        if(!calibrated) {
            if(slow[0]&&slow[1]&&slow[2] && raw[0]>1000&&raw[1]>1000&&raw[2]>1000&&raw[0]<15000&&raw[1]<15000&&raw[2]<15000) {
                for(int i=0;i<3;i++) bias[i]+=(raw[i]-bias[i])/double(++stable);
                if(stable>=60) calibrated=true;
            }
            return;
        }
        if(dt<=0||dt>.1) return;
        double rate[3];
        for(int i=0;i<3;i++) { rate[i]=(raw[i]-bias[i])/13.768*(slow[i]?1.0:2000.0/440.0)*3.141592653589793/180.0; }
        Vec3 omega{rate[1],-rate[2],-rate[0]};
        double mag=std::sqrt(omega.x*omega.x+omega.y*omega.y+omega.z*omega.z);
        if(mag>12) { double k=12/mag; omega={omega.x*k,omega.y*k,omega.z*k}; }
        q.integrate(omega,dt);
        if(accel) {
            Vec3 a{double(accel[0]),double(accel[1]),double(accel[2])};
            double n=std::sqrt(a.x*a.x+a.y*a.y+a.z*a.z);
            if(n>100 && n<1300) {
                a={a.x/n,a.y/n,a.z/n}; Quat correction=Quat::from_to(a,{0,1,0});
                // Low-gain gravity correction; it does not constrain yaw.
                Quat c{1+(correction.w-1)*.015,correction.x*.015,correction.y*.015,correction.z*.015};c.normalize();
                Quat r{c.w*q.w-c.x*q.x-c.y*q.y-c.z*q.z,c.w*q.x+c.x*q.w+c.y*q.z-c.z*q.y,c.w*q.y-c.x*q.z+c.y*q.w+c.z*q.x,c.w*q.z+c.x*q.y-c.y*q.x+c.z*q.w};q=r;q.normalize();
            }
        }
        if(slow[0]&&slow[1]&&slow[2]&&mag<.035) for(int i=0;i<3;i++) bias[i]+=(raw[i]-bias[i])*.0002;
    }
};
}

#include <windows.h>
#include <openvr_driver.h>
#include "pipe_client.hpp"
#include "motion.hpp"
#include <array>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <memory>
#include <string>

namespace {
using namespace vr;
using Clock=std::chrono::steady_clock;
class WiiController final : public ITrackedDeviceServerDriver {
public:
    WiiController(bool right,const char* serial):right_(right),serial_(serial){}
    EVRInitError Activate(uint32_t id) override {
        id_=id; auto props=VRProperties(); container_=props->TrackedDeviceToPropertyContainer(id);
        props->SetStringProperty(container_,Prop_TrackingSystemName_String,"wiimotionsteamvr");
        props->SetStringProperty(container_,Prop_ModelNumber_String,right_?"Razer Hydra Right (Wii test)":"Razer Hydra Left (Wii test)");
        props->SetStringProperty(container_,Prop_SerialNumber_String,serial_.c_str());
        props->SetStringProperty(container_,Prop_ManufacturerName_String,"Nintendo / WiiMotionSteamVR");
        props->SetStringProperty(container_,Prop_RenderModelName_String,"{wiimotionsteamvr}hydra_controller");
        props->SetStringProperty(container_,Prop_ControllerType_String,"hydra_controller");
        props->SetInt32Property(container_,Prop_ControllerRoleHint_Int32,right_?TrackedControllerRole_RightHand:TrackedControllerRole_LeftHand);
        props->SetStringProperty(container_,Prop_InputProfilePath_String,"{wiimotionsteamvr}/input/wii_controller_profile.json");
        VRDriverInput()->CreateBooleanComponent(container_,right_?"/input/grip/click":"/input/grip/click",&grip_);
        VRDriverInput()->CreateBooleanComponent(container_,"/input/trigger/click",&trigger_);
        VRDriverInput()->CreateScalarComponent(container_,"/input/trigger/value",&triggerValue_,VRScalarType_Absolute,VRScalarUnits_NormalizedOneSided);
        VRDriverInput()->CreateBooleanComponent(container_,"/input/trackpad/click",&padClick_);
        VRDriverInput()->CreateBooleanComponent(container_,"/input/menu/click",&menu_);
        VRDriverInput()->CreateScalarComponent(container_,"/input/trackpad/x",&padX_,VRScalarType_Absolute,VRScalarUnits_NormalizedTwoSided);
        VRDriverInput()->CreateScalarComponent(container_,"/input/trackpad/y",&padY_,VRScalarType_Absolute,VRScalarUnits_NormalizedTwoSided);
        VRDriverInput()->CreateBooleanComponent(container_,"/input/system/click",&system_);
        VRDriverInput()->CreateBooleanComponent(container_,"/input/trackpad/touch",&padTouch_);
        return VRInitError_None;
    }
    void Deactivate() override { id_=k_unTrackedDeviceIndexInvalid; }
    void EnterStandby() override {}
    void* GetComponent(const char*) override { return nullptr; }
    void DebugRequest(const char*,char* out,uint32_t n) override { if(n)out[0]=0; }
    DriverPose_t GetPose() override { return pose_; }
    void update(const wms::Frame& f,bool fresh,const TrackedDevicePose_t& hmd) {
        if(id_==k_unTrackedDeviceIndexInvalid) return;
        pose_={}; pose_.poseTimeOffset=0; pose_.qWorldFromDriverRotation={1,0,0,0};
        pose_.qDriverFromHeadRotation={1,0,0,0};
        HmdQuaternion_t qh{1,0,0,0};
        const auto& m=hmd.mDeviceToAbsoluteTracking;
        if(hmd.bPoseIsValid) {
            qh=from_matrix(m);
            const double ox=right_?.28:-.28, oy=-.22, oz=-.48;
            const double rx=m.m[0][0]*ox+m.m[0][1]*oy+m.m[0][2]*oz;
            const double ry=m.m[1][0]*ox+m.m[1][1]*oy+m.m[1][2]*oz;
            const double rz=m.m[2][0]*ox+m.m[2][1]*oy+m.m[2][2]*oz;
            pose_.vecPosition[0]=m.m[0][3]+rx; pose_.vecPosition[1]=m.m[1][3]+ry; pose_.vecPosition[2]=m.m[2][3]+rz;
        } else {
            pose_.vecPosition[0]=right_?.28:-.28; pose_.vecPosition[1]=-.22; pose_.vecPosition[2]=-.48;
        }
        const HmdQuaternion_t qi{f.q_w,f.q_x,f.q_y,f.q_z};
        const bool center=fresh && ((f.buttons&3)==3);
        const bool centerEdge=center&&!centerHeld_; centerHeld_=center;
        HmdQuaternion_t hand=qi;
        if(!right_) {
            const double ax=f.nunchuk_ax,ay=f.nunchuk_ay,az=f.nunchuk_az;
            const double n=sqrt(ax*ax+ay*ay+az*az);
            if(n>.5 && (f.flags&wms::kFlagNunchuk)) {
                const double w=1.+ay/n, x=-az/n, z=ax/n;
                const double qn=sqrt(w*w+x*x+z*z);
                if(qn>1e-5) hand={w/qn,x/qn,0,z/qn}; else hand={0,1,0,0};
            } else hand={1,0,0,0};
            if(centerEdge) nunchukCenter_={hand.w,-hand.x,-hand.y,-hand.z};
            hand=multiply(nunchukCenter_,hand);
        }
        // Physical downward pitch must point the virtual wand downward.
        hand.x=-hand.x;
        const auto sampleTime=Clock::now();
        double dt=std::chrono::duration<double>(sampleTime-lastSmooth_).count(); lastSmooth_=sampleTime;
        dt=(std::max)(0.,(std::min)(.1,dt));
        const double alpha=1.-exp(-dt/(right_?.025:.045));
        if(!fresh || !smoothReady_ || centerEdge) smoothHand_=hand;
        else {
            const double dot=smoothHand_.w*hand.w+smoothHand_.x*hand.x+smoothHand_.y*hand.y+smoothHand_.z*hand.z;
            const double sign=dot<0?-1.:1.;
            smoothHand_={smoothHand_.w*(1-alpha)+sign*hand.w*alpha,
                         smoothHand_.x*(1-alpha)+sign*hand.x*alpha,
                         smoothHand_.y*(1-alpha)+sign*hand.y*alpha,
                         smoothHand_.z*(1-alpha)+sign*hand.z*alpha};
            const double n=sqrt(smoothHand_.w*smoothHand_.w+smoothHand_.x*smoothHand_.x+smoothHand_.y*smoothHand_.y+smoothHand_.z*smoothHand_.z);
            if(n>1e-9) smoothHand_={smoothHand_.w/n,smoothHand_.x/n,smoothHand_.y/n,smoothHand_.z/n};
        }
        smoothReady_=fresh; hand=smoothHand_;
        pose_.qRotation=fresh?multiply(qh,hand):qh;
        // Virtual forearm: rotation changes the endpoint around a fixed elbow.
        // This is an arm model, not measured translational tracking.
        if(fresh && hmd.bPoseIsValid) {
            const double length=.28;
            // An elbow above the wrist gives roll a lateral lever arm too.
            const double drop=.18;
            const double dx=-length*2*(hand.x*hand.z+hand.w*hand.y)
                            -drop*2*(hand.x*hand.y-hand.w*hand.z);
            const double dy=-length*2*(hand.y*hand.z-hand.w*hand.x)
                            +drop*2*(hand.x*hand.x+hand.z*hand.z);
            const double dz=length*2*(hand.x*hand.x+hand.y*hand.y)
                            -drop*2*(hand.y*hand.z+hand.w*hand.x);
            const double delta[3]={dx,dy,dz};
            for(int row=0;row<3;++row) {
                double target=pose_.vecPosition[row];
                for(int col=0;col<3;++col) target+=m.m[row][col]*delta[col];
                if(!positionReady_) filteredPosition_[row]=target;
                const double step=(1.-exp(-dt/.035))*(target-filteredPosition_[row]);
                filteredPosition_[row]+=step;
                pose_.vecPosition[row]=filteredPosition_[row];
            }
            positionReady_=true;
        } else positionReady_=false;
        pose_.result=(fresh&&hmd.bPoseIsValid)?TrackingResult_Running_OK:TrackingResult_Running_OutOfRange;
        pose_.poseIsValid=hmd.bPoseIsValid; pose_.deviceIsConnected=true; pose_.willDriftInYaw=true;
        VRServerDriverHost()->TrackedDevicePoseUpdated(id_,pose_,sizeof(pose_));
        double t=0;
        bool trigger=false,grip=false,padclick=false,menu=false;
        double x=0,y=0;
        if(fresh) {
            if(right_) {
                const auto b=f.buttons; trigger=(b&0x0004)!=0; grip=(b&0x0008)!=0;
                menu=(b&0x0010)!=0; padclick=(b&0x0f00)!=0;
                // D-pad as four digital directions, represented on trackpad axes.
                x=((b&0x0200)?1.:0.)-((b&0x0100)?1.:0.);
                y=((b&0x0800)?1.:0.)-((b&0x0400)?1.:0.);
            } else {
                menu=(f.buttons&0x1000)!=0;
                trigger=(f.nunchuk_buttons&2)!=0; grip=(f.nunchuk_buttons&1)!=0;
                x=f.stick_x; y=f.stick_y; padclick=(x*x+y*y>.001);
            }
            t=trigger?1.:0.;
        }
        VRDriverInput()->UpdateBooleanComponent(system_,fresh && (f.buttons & (right_?0x0001:0x0002)),0);
        VRDriverInput()->UpdateBooleanComponent(padTouch_,fresh && (right_?padclick:(x*x+y*y>.001)),0);
        VRDriverInput()->UpdateBooleanComponent(trigger_,trigger,0);
        VRDriverInput()->UpdateScalarComponent(triggerValue_,float(t),0);
        VRDriverInput()->UpdateBooleanComponent(grip_,grip,0);
        VRDriverInput()->UpdateBooleanComponent(padClick_,padclick,0);
        VRDriverInput()->UpdateBooleanComponent(menu_,menu,0);
        VRDriverInput()->UpdateScalarComponent(padX_,float(x),0);
        VRDriverInput()->UpdateScalarComponent(padY_,float(y),0);
    }
private:
    static HmdQuaternion_t multiply(const HmdQuaternion_t&a,const HmdQuaternion_t&b) {
        return {a.w*b.w-a.x*b.x-a.y*b.y-a.z*b.z,a.w*b.x+a.x*b.w+a.y*b.z-a.z*b.y,
                a.w*b.y-a.x*b.z+a.y*b.w+a.z*b.x,a.w*b.z+a.x*b.y-a.y*b.x+a.z*b.w};
    }
    static HmdQuaternion_t from_matrix(const HmdMatrix34_t&m) {
        HmdQuaternion_t q{};
        q.w=sqrt((std::max)(0.0,1.0+double(m.m[0][0])+double(m.m[1][1])+double(m.m[2][2])))*.5;
        q.x=sqrt((std::max)(0.0,1.0+double(m.m[0][0])-double(m.m[1][1])-double(m.m[2][2])))*.5;
        q.y=sqrt((std::max)(0.0,1.0-double(m.m[0][0])+double(m.m[1][1])-double(m.m[2][2])))*.5;
        q.z=sqrt((std::max)(0.0,1.0-double(m.m[0][0])-double(m.m[1][1])+double(m.m[2][2])))*.5;
        q.x=copysign(q.x,m.m[2][1]-m.m[1][2]);q.y=copysign(q.y,m.m[0][2]-m.m[2][0]);q.z=copysign(q.z,m.m[1][0]-m.m[0][1]);
        return q;
    }
    Clock::time_point lastSmooth_{Clock::now()}; HmdQuaternion_t smoothHand_{1,0,0,0}; bool smoothReady_{false};
    double filteredPosition_[3]{}; bool positionReady_{false};
    HmdQuaternion_t nunchukCenter_{1,0,0,0}; bool centerHeld_{false};
    bool right_; std::string serial_; uint32_t id_{k_unTrackedDeviceIndexInvalid}; PropertyContainerHandle_t container_{};
    VRInputComponentHandle_t system_{},padTouch_{},grip_{},trigger_{},triggerValue_{},padClick_{},menu_{},padX_{},padY_{};
    DriverPose_t pose_{};
};

class Provider final : public IServerTrackedDeviceProvider {
public:
    EVRInitError Init(IVRDriverContext* ctx) override {
        VR_INIT_SERVER_DRIVER_CONTEXT(ctx);
        right_=std::make_unique<WiiController>(true,"WiiRemotePlus-R");
        left_=std::make_unique<WiiController>(false,"WiiNunchuk-L");
        if(!VRServerDriverHost()->TrackedDeviceAdded("WiiRemotePlus-R",TrackedDeviceClass_Controller,right_.get()) ||
           !VRServerDriverHost()->TrackedDeviceAdded("WiiNunchuk-L",TrackedDeviceClass_Controller,left_.get())) {
            right_.reset();left_.reset();VR_CLEANUP_SERVER_DRIVER_CONTEXT();return VRInitError_Driver_Failed;
        }
        pipe_.start();return VRInitError_None;
    }
    void Cleanup() override { pipe_.stop();left_.reset();right_.reset();VR_CLEANUP_SERVER_DRIVER_CONTEXT(); }
    const char* const* GetInterfaceVersions() override { return k_InterfaceVersions; }
    void RunFrame() override {
        auto f=pipe_.latest(); const auto now=Clock::now();
        TrackedDevicePose_t hmd{}; VRServerDriverHost()->GetRawTrackedDevicePoses(0.0f,&hmd,1);
        const double age=std::chrono::duration<double>(now.time_since_epoch()).count()*1e9-double(f.timestamp_ns);
        bool fresh=f.magic==wms::kMagic && (f.flags&wms::kFlagConnected) && wms::valid(f) &&
            f.timestamp_ns!=0 && age>=0.0 && age<250000000.0;
        if(!fresh){f.buttons=0;f.nunchuk_buttons=0;f.stick_x=f.stick_y=0;f.q_w=1;f.q_x=f.q_y=f.q_z=0;}
        if(right_)right_->update(f,fresh,hmd);if(left_)left_->update(f,fresh,hmd);
    }
    bool ShouldBlockStandbyMode() override { return false; }
    void EnterStandby() override {}
    void LeaveStandby() override {}
private:
    wms::PipeClient pipe_; std::unique_ptr<WiiController> right_,left_;
};
Provider g_provider;
}

extern "C" __declspec(dllexport) void* HmdDriverFactory(const char* name,int* error) {
    if(error)*error=vr::VRInitError_None;
    if(std::strcmp(name,vr::IServerTrackedDeviceProvider_Version)==0)return &g_provider;
    if(error)*error=vr::VRInitError_Init_InterfaceNotFound;return nullptr;
}


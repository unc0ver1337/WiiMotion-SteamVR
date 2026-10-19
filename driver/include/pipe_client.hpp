#pragma once
#ifdef _WIN32
#include <windows.h>
#include "protocol.hpp"
#include <mutex>
#include <thread>
#include <atomic>
namespace wms {
class PipeClient {
public:
    PipeClient()=default; ~PipeClient(){stop();}
    void start() { running_=true; thread_=std::thread([this]{run();}); }
    void stop() { running_=false; {std::lock_guard<std::mutex> l(m_);if(pipe_!=INVALID_HANDLE_VALUE){CancelIoEx(pipe_,nullptr);CloseHandle(pipe_);pipe_=INVALID_HANDLE_VALUE;}} if(thread_.joinable()) thread_.join(); }
    Frame latest() { std::lock_guard<std::mutex> l(m_); return frame_; }
private:
    std::atomic<bool> running_{false}; std::thread thread_; std::mutex m_; HANDLE pipe_{INVALID_HANDLE_VALUE}; Frame frame_{};
    void run() {
        while(running_) {
            HANDLE h=CreateFileW(L"\\\\.\\pipe\\WiiMotionSteamVR",GENERIC_READ,0,nullptr,OPEN_EXISTING,0,nullptr);
            if(h==INVALID_HANDLE_VALUE){Sleep(250);continue;}
            {std::lock_guard<std::mutex> l(m_);pipe_=h;}
            while(running_) {
                Frame f{}; DWORD got=0; if(!ReadFile(h,&f,sizeof(f),&got,nullptr)||got!=sizeof(f)||!valid(f)) break;
                std::lock_guard<std::mutex> l(m_);frame_=f;
            }
            {std::lock_guard<std::mutex> l(m_);if(pipe_==h)pipe_=INVALID_HANDLE_VALUE;}
            CloseHandle(h);
        }
    }
};
}
#endif

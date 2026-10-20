#pragma once
#include <array>
#include <cstdint>
#include <cstring>
#include <cmath>

namespace wms {
constexpr uint32_t kMagic = 0x31534D57; // WMS1
constexpr uint16_t kVersion = 3;
constexpr uint16_t kFlagConnected = 1;
constexpr uint16_t kFlagNunchuk = 2;
#pragma pack(push, 1)
struct Frame {
    uint32_t magic{kMagic};
    uint16_t version{kVersion};
    uint16_t size{sizeof(Frame)};
    uint64_t timestamp_ns{}; // bridge monotonic clock, nanoseconds
    uint32_t sequence{};
    uint16_t flags{};
    uint16_t buttons{}; // Wii button mask, same order as status report
    float nunchuk_ax{}, nunchuk_ay{}, nunchuk_az{}; // normalized gravity direction
    float stick_x{}, stick_y{};
    uint8_t nunchuk_buttons{}; // bit0 C, bit1 Z
    uint8_t remote_accel[3]{128,128,128}; // raw Wii accelerometer, IPC v3
};
#pragma pack(pop)
static_assert(sizeof(Frame) == 48);
inline bool valid(const Frame& f) {
    if (f.magic != kMagic || f.version != kVersion || f.size != sizeof(Frame)) return false;
    const float v[] = {f.nunchuk_ax,f.nunchuk_ay,f.nunchuk_az,f.stick_x,f.stick_y};
    for (float x : v) if (!std::isfinite(x)) return false;
    return true;
}
}

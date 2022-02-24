#ifndef TENHOU_H
#define TENHOU_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <vector>
// #include <windows.h>
// #include <openssl/sha.h>
#include "SHA512.h"
#include "mt19937ar.h"
// #include "base64.h" //http://yamatyuu.net/computer/program/vc2013/base64/index.html
#define DWORD uint32_t
#define BYTE uint8_t
#define MTRAND_N 624
#define DEBUG 1

struct TenhouShuffle {
    const char *MTseed_b64 = nullptr;
    unsigned char MTseed[MTRAND_N * 4 + 1];
    DWORD RTseed[MTRAND_N];
    unsigned int yama[136];
    DWORD rnd[SHA512_DIGEST_LENGTH / sizeof(DWORD) * 9];
    DWORD src[sizeof(rnd) / sizeof(*rnd) * 2];

private:
    TenhouShuffle() = default;
public:
    inline static TenhouShuffle& instance()
    {
        static TenhouShuffle tenhou;
        return tenhou;
    }
    void init(const char* seed);
    std::vector<int> generate_yama();
};
void tenhou_yama_from_seed(const char *MTseed_b64, unsigned int yama[136]);

#endif
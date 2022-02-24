#include <stdio.h>
#include <stdlib.h>
#include <string.h>
// #include <windows.h>
// #include <openssl/sha.h>
#include "SHA512.h"
#include "mt19937ar.h"
// #include "base64.h" //http://yamatyuu.net/computer/program/vc2013/base64/index.html
#define DWORD unsigned long
#ifndef BYTE
#define BYTE unsigned char
#define
#define MTRAND_N 624
#define DEBUG 1

// http://tenhou.net/0/?log=2014021221gm-00a9-0000-23324af3&tw=0
// char MTseed_b64[] = "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";
// mjlog��ӛ����Ƥ���<SHUFFLE seed="mt19937ar-sha512-n288-base64,~> 3328����

static const char* haiDisp[34] = {
    "<1m>", "<2m>", "<3m>", "<4m>", "<5m>", "<6m>", "<7m>", "<8m>", "<9m>",
    "<1p>", "<2p>", "<3p>", "<4p>", "<5p>", "<6p>", "<7p>", "<8p>", "<9p>",
    "<1s>", "<2s>", "<3s>", "<4s>", "<5s>", "<6s>", "<7s>", "<8s>", "<9s>",
    "<�|>", "<��>", "<��>", "<��>", "<��>", "<�l>", "<��>"
};

//	base64��1���֤�6bit�΂��ˉ�Q����

inline int base64_to_6bit(int c) {
    if (c == '=')
        return 0;
    if (c == '/')
        return 63;
    if (c == '+')
        return 62;
    if (c <= '9')
        return (c - '0') + 52;
    if ('a' <= c)
        return (c - 'a') + 26;
    return (c - 'A');
}

//	base64��������src��ǥ��`�ɤ��ƥХ��ʥꂎ�ˉ�Q��dtc�˸�{
//	len��base64��������
//	��Q��ΥХ������򷵤�

inline int base64Decode(char* src, char* dtc) {
    unsigned o0, o1, o2, o3;
    char* p = dtc;
    for (int n = 0; src[n];) {
        o0 = base64_to_6bit(src[n]);
        o1 = base64_to_6bit(src[n + 1]);
        o2 = base64_to_6bit(src[n + 2]);
        o3 = base64_to_6bit(src[n + 3]);

        *p++ = (o0 << 2) | ((o1 & 0x30) >> 4);
        *p++ = ((o1 & 0xf) << 4) | ((o2 & 0x3c) >> 2);
        *p++ = ((o2 & 0x3) << 6) | o3 & 0x3f;
        n += 4;
    }
    *p = 0;
    return int(p - dtc);
}

//	�Х��ʥ������src��base64�ǥ��󥳩`�ɤ���
//	src:�Х��ʥ����� len:�Х��ʥ������L��
//	dtc:��Q��������Ф򱣴椹�륢�ɥ쥹 dtc_len:��Q��ΥХ������򱣴椹�륢�ɥ쥹

inline void base64Encode(char* src, char* dtc, int len, int* dtc_len) {
    //	6bit����base64�����֤؉�Q����Ʃ`�֥�
    //                              1         2         3         4         5         6
    //                    0123456789012345678901234567890123456789012345678901234567890123456789
    //                                    1               2               3
    //                    0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF
    const char table[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

    int n;
    int mod = len % 3;

    int adj_len = len - mod;	//	3�α���������
    char* p = dtc;
    int o0, o1, o2, o3;
    for (n = 0; n < adj_len;) {
        unsigned x = ((unsigned)src[n] << 16) + ((unsigned)src[n + 1] << 8) + unsigned(src[n + 2]);
        o0 = (x >> 18) & 0x3f;
        o1 = (x >> 12) & 0x3f;
        o2 = (x >> 6) & 0x3f;
        o3 = x & 0x3f;
        *p++ = table[o0];
        *p++ = table[o1];
        *p++ = table[o2];
        *p++ = table[o3];
        n += 3;
    }
    if (mod) {
        if (mod == 1) {
            unsigned x = (unsigned)src[n] << 16;
            o0 = (x >> 18) & 0x3f;
            o1 = (x >> 12) & 0x3f;
            *p++ = table[o0];
            *p++ = table[o1];
            *p++ = '=';
            *p++ = '=';
        }
        else if (mod == 2) {
            unsigned x = ((unsigned)src[n] << 16) + ((unsigned)src[n + 1] << 8);
            o0 = (x >> 18) & 0x3f;
            o1 = (x >> 12) & 0x3f;
            o2 = (x >> 6) & 0x3f;
            *p++ = table[o0];
            *p++ = table[o1];
            *p++ = table[o2];
            *p++ = '=';
        }
    }
    *p = 0;
    *dtc_len = int(p - dtc);
}


// ����ǥ������Q�v��
//http://torasukenote.blog120.fc2.com/page-3.html
inline int convertEndian(void* input, size_t s) {
    // ��������: void *input...����ǥ������Q����ؤΥݥ���
    // ��������: size_t    s...��Q����ΥХ�����
    int i;   // ������
    char* temp;   // ��Q�r���ä���һ�r������
    if ((temp = (char*)calloc(s, sizeof(char))) == NULL) {
        return 0;   // �I��_���Ǥ�����ʧ����
    }
    for (i = 0; i < s; i++) {   // input�ǩ`����temp��һ�r����
        temp[i] = ((char*)input)[i];
    }
    for (i = 1; i <= s; i++) {   // temp�ǩ`�����淽��ˤ���input�ش���
        ((char*)input)[i - 1] = temp[s - i];
    }
    free(temp);   // �_�������I�����
    return 1;   // �����K��
}

inline void yama_from_seed(char *MTseed_b64, BYTE yama[136]) {
    int i;

    unsigned char MTseed[MTRAND_N * 4 + 1];//4992+1(�K�˥��`��׷���ä�+1)

    base64Decode(MTseed_b64, (char*)MTseed);

    //MTseed��DWORD[]�ˉ�Q
    DWORD RTseed[MTRAND_N];//��`��MT�Υ��`��
    {
        //����
        for (i = 0; i < MTRAND_N; i++) {
            RTseed[i] = MTseed[4 * i] << 24 |
                MTseed[4 * i + 1] << 16 |
                MTseed[4 * i + 2] << 8 |
                MTseed[4 * i + 3];
        }

        //RTseed�Υ���ǥ������Q
        for (i = 0; i < sizeof(RTseed) / sizeof(*RTseed); ++i) convertEndian(&RTseed[i], sizeof(*RTseed));
    }
    //��`��MT����ڻ�
    init_by_array(RTseed, sizeof(RTseed) / sizeof(*RTseed));

    int nGame;
    for (nGame = 0; nGame < 10; nGame++) {
        //��`����MT����������+SHA512
        DWORD rnd[SHA512_DIGEST_LENGTH / sizeof(DWORD) * 9]; // 135+2���Ϥ�_��
        {
            DWORD src[sizeof(rnd) / sizeof(*rnd) * 2]; // 1024bit�gλ��512bit��hash

            //��`����MT����������
            for (i = 0; i < sizeof(src) / sizeof(*src); ++i) src[i] = genrand_int32();

            //�ϥå���Ӌ��
            for (i = 0; i < sizeof(rnd) / SHA512_DIGEST_LENGTH/*=9 */; ++i) {
                SHA512((BYTE*)src + i * SHA512_DIGEST_LENGTH * 2, SHA512_DIGEST_LENGTH * 2, (BYTE*)rnd + i * SHA512_DIGEST_LENGTH);
            }
        }

        //��ɽ����åե�
        // BYTE yama[136];
        {
            BYTE tmp_yama; // ����ޤ�108
            int tmp_index;

            for (i = 0; i < 136; ++i) yama[i] = i;
            for (i = 0; i < 136 - 1; ++i) {
                //swap(yama[i],yama[i + (rnd[i]%(136-i))]); // 1/2^32���¤��`����S��
                tmp_index = i + (rnd[i] % (136 - i));
                tmp_yama = yama[i];
                yama[i] = yama[tmp_index];
                yama[tmp_index] = tmp_yama;
            }
        }

        //��ɽ��ʾ
        printf("--------Game %d--------\r\n", nGame);
        printf("yama =\r\n");
        for (i = 0; i < 136; ++i) {
            printf("%s", haiDisp[yama[i] / 4]);
            if ((i + 1) % 17 == 0) printf("\r\n");
            if (i == 83) printf("  ");//���ƽK�˵ص�˥��ک`����Ю��
        }
        printf("\r\n");

        //���������ʾ
        int dice0 = rnd[135] % 6;
        int dice1 = rnd[136] % 6;
        printf("dice0 = %d, dice1 = %d\r\n\r\n\r\n", dice0 + 1, dice1 + 1);
        // rnd[137]��rnd[143]��δʹ��
    }
    return;
}
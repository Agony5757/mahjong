#ifndef SHA512_H
#define SHA512_H

#include <cstring>
#include <cassert>
#include <cstdint>
/* do we have sha512 header defs */
#ifndef SHA512_DIGEST_LENGTH
#define SHA512_BLOCK_LENGTH		128
#define SHA512_DIGEST_LENGTH		64
#define SHA512_DIGEST_STRING_LENGTH	(SHA512_DIGEST_LENGTH * 2 + 1)
typedef struct _SHA512_CTX {
	uint64_t	state[8];
	uint64_t	bitcount[2];
	uint8_t	buffer[SHA512_BLOCK_LENGTH];
} SHA512_CTX;
#endif /* do we have sha512 header defs */

void SHA512_Init(SHA512_CTX*);
void SHA512_Update(SHA512_CTX*, void*, size_t);
void SHA512_Final(uint8_t[SHA512_DIGEST_LENGTH], SHA512_CTX*);
unsigned char* SHA512(void* data, unsigned int data_len, unsigned char* digest);

#endif
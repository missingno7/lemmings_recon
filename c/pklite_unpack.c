#include "pklite_unpack.h"

#include <string.h>

#define EXE_SIZE 32749u
#define IMAGE_LIMIT 0x100000u
#define STREAM_OFFSET 0x2f0u
#define TABLE_OFFSET 0x2a8u
#define TABLE_SIZE 62u

static const uint8_t target_sha[32] = {
    0x5e,0x17,0x6d,0x21,0x57,0x0e,0xb4,0x74,0xf6,0x8b,0x12,0x92,0x04,0x50,0xf5,0xb4,
    0xcc,0xc2,0x5a,0x10,0xc3,0xdd,0x2a,0x47,0xe1,0x26,0xb0,0xb1,0x43,0xee,0x0b,0x8d
};

/* Small standalone SHA-256, used only for the pinned executable identity. */
static uint32_t rotr(uint32_t x, unsigned n) { return (x >> n) | (x << (32u - n)); }
static void sha256(const uint8_t *data, size_t length, uint8_t digest[32]) {
    static const uint32_t k[64] = {
        0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,0x3956c25bu,0x59f111f1u,0x923f82a4u,0xab1c5ed5u,
        0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,
        0xe49b69c1u,0xefbe4786u,0x0fc19dc6u,0x240ca1ccu,0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,
        0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,0xc6e00bf3u,0xd5a79147u,0x06ca6351u,0x14292967u,
        0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,
        0xa2bfe8a1u,0xa81a664bu,0xc24b8b70u,0xc76c51a3u,0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,
        0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,0x391c0cb3u,0x4ed8aa4au,0x5b9cca4fu,0x682e6ff3u,
        0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u
    };
    uint32_t h[8] = {0x6a09e667u,0xbb67ae85u,0x3c6ef372u,0xa54ff53au,0x510e527fu,0x9b05688cu,0x1f83d9abu,0x5be0cd19u};
    size_t total = ((length + 9u + 63u) / 64u) * 64u, block;
    for (block = 0; block < total; block += 64u) {
        uint8_t chunk[64]; uint32_t w[64], a,b,c,d,e,f,g,hh; unsigned i;
        for (i=0;i<64;i++) {
            size_t at=block+i;
            if (at < length) chunk[i]=data[at];
            else if (at==length) chunk[i]=0x80;
            else if (at>=total-8u) chunk[i]=(uint8_t)(((uint64_t)length*8u) >> ((total-1u-at)*8u));
            else chunk[i]=0;
        }
        for (i=0;i<16;i++) w[i]=((uint32_t)chunk[i*4]<<24)|((uint32_t)chunk[i*4+1]<<16)|((uint32_t)chunk[i*4+2]<<8)|chunk[i*4+3];
        for (i=16;i<64;i++) { uint32_t x=w[i-15],y=w[i-2]; w[i]=w[i-16]+(rotr(x,7)^rotr(x,18)^(x>>3))+w[i-7]+(rotr(y,17)^rotr(y,19)^(y>>10)); }
        a=h[0];b=h[1];c=h[2];d=h[3];e=h[4];f=h[5];g=h[6];hh=h[7];
        for (i=0;i<64;i++) { uint32_t t1=hh+(rotr(e,6)^rotr(e,11)^rotr(e,25))+((e&f)^((~e)&g))+k[i]+w[i]; uint32_t t2=(rotr(a,2)^rotr(a,13)^rotr(a,22))+((a&b)^(a&c)^(b&c)); hh=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2; }
        h[0]+=a;h[1]+=b;h[2]+=c;h[3]+=d;h[4]+=e;h[5]+=f;h[6]+=g;h[7]+=hh;
    }
    for (unsigned i=0;i<8;i++) { digest[i*4]=(uint8_t)(h[i]>>24);digest[i*4+1]=(uint8_t)(h[i]>>16);digest[i*4+2]=(uint8_t)(h[i]>>8);digest[i*4+3]=(uint8_t)h[i]; }
}

typedef struct Stream { const uint8_t *data; size_t size,pos; uint16_t bits; unsigned left; } Stream;
static int byte(Stream *s, uint8_t *v) { if(s->pos>=s->size)return 0;*v=s->data[s->pos++];return 1; }
static int word(Stream *s, uint16_t *v) { uint8_t a,b;if(!byte(s,&a)||!byte(s,&b))return 0;*v=(uint16_t)(a|((uint16_t)b<<8));return 1; }
static int bit(Stream *s,unsigned *v) { *v=s->bits&1u;s->bits>>=1;s->left--;if(!s->left){if(!word(s,&s->bits))return 0;s->left=16;}return 1; }
static int bits(Stream *s,unsigned n,unsigned *v) { unsigned x=0,b;while(n--){if(!bit(s,&b))return 0;x=(x<<1)|b;}*v=x;return 1; }

LmnPkliteStatus lmn_pklite_unpack(const uint8_t *exe,size_t size,uint8_t *image,size_t capacity,size_t *image_size,uint16_t *relocations,size_t relocation_capacity,size_t *relocation_count,LmnPkliteHeader *header) {
    uint8_t digest[32]; Stream s; size_t out=0,nrel=0; uint32_t segment=0; unsigned matches=0,markers=0;
    if(!exe||!image||!image_size||!relocation_count||!header||(!relocations&&relocation_capacity))return LMN_PKLITE_ARGUMENT;
    *image_size=0;*relocation_count=0;memset(header,0,sizeof(*header));
    if(size!=EXE_SIZE)return LMN_PKLITE_WRONG_IDENTITY;
    sha256(exe,size,digest);if(memcmp(digest,target_sha,32))return LMN_PKLITE_WRONG_IDENTITY;
    for(unsigned i=0;i<14;i++)header->mz[i]=(uint16_t)(exe[i*2]|((uint16_t)exe[i*2+1]<<8));
    s.data=exe;s.size=size;s.pos=STREAM_OFFSET;s.left=16;
    if(!word(&s,&s.bits))return LMN_PKLITE_MALFORMED;
    for(;;){
        unsigned control,b,b0;int length;uint8_t x;unsigned high=0;uint16_t distance;
        if(!bit(&s,&control))return LMN_PKLITE_MALFORMED;
        if(!control){if(!byte(&s,&x))return LMN_PKLITE_MALFORMED;if(out>=capacity||out>=IMAGE_LIMIT)return LMN_PKLITE_CAPACITY;image[out++]=(uint8_t)(x^s.left);continue;}
        if(!bits(&s,2,&b))return LMN_PKLITE_MALFORMED;
        if(b<2){
            if(!bit(&s,&b0)) return LMN_PKLITE_MALFORMED;
            b=(b<<1)|b0;
            if(b){if(!bit(&s,&b0))return LMN_PKLITE_MALFORMED;b=(b<<1)|b0;if(b>=5){if(!bit(&s,&b0))return LMN_PKLITE_MALFORMED;b=(b<<1)|b0;}}
            if(b<=12)length=exe[TABLE_OFFSET+b];
            else {
                if(!bits(&s,1,&b0)) return LMN_PKLITE_MALFORMED;
                b=((b&3u)<<1)|b0;
                if(b>=5){if(!bit(&s,&b0))return LMN_PKLITE_MALFORMED;b=(b<<1)|b0;}
                if(b<=12)length=exe[TABLE_OFFSET+11+b];
                else {if(!bits(&s,1,&b0))return LMN_PKLITE_MALFORMED;b=((b&3u)<<1)|b0;if(b>=5){if(!bit(&s,&b0))return LMN_PKLITE_MALFORMED;b=(b<<1)|b0;}length=exe[TABLE_OFFSET+22+b];}
                if(length==25){if(!byte(&s,&x))return LMN_PKLITE_MALFORMED;if(x==255)break;if(x==254){markers++;continue;}length+=x;}
            }
        } else length=(int)b;
        if(length!=2){if(!bit(&s,&control))return LMN_PKLITE_MALFORMED;if(!control){if(!bits(&s,3,&b))return LMN_PKLITE_MALFORMED;if(b>=2){if(!bit(&s,&b0))return LMN_PKLITE_MALFORMED;b=(b<<1)|b0;if(b>=8){if(!bit(&s,&b0))return LMN_PKLITE_MALFORMED;b=(b<<1)|b0;if(b>=23){if(!bit(&s,&b0))return LMN_PKLITE_MALFORMED;b=(b<<1)|b0;high=b&0xdfu;}else high=exe[TABLE_OFFSET+38+b];}else high=exe[TABLE_OFFSET+38+b];}else high=exe[TABLE_OFFSET+38+b];}}
        if(!byte(&s,&x)) return LMN_PKLITE_MALFORMED;
        distance=(uint16_t)((high<<8)|x);
        if(!distance||distance>out||length<2)return LMN_PKLITE_MALFORMED;
        if((size_t)length>capacity-out||(size_t)length>IMAGE_LIMIT-out)return LMN_PKLITE_CAPACITY;
        while(length--){image[out]=image[out-distance];out++;}matches++;
    }
    header->relocation_stream_offset=s.pos;
    for(;;){uint16_t count;if(!word(&s,&count))return LMN_PKLITE_MALFORMED;if(count==0xffff)break;if(!count)continue;
        if(count>relocation_capacity-nrel)return LMN_PKLITE_CAPACITY;
        for(unsigned i=0;i<count;i++){uint16_t offset;uint64_t site;if(!word(&s,&offset))return LMN_PKLITE_MALFORMED;site=(uint64_t)segment*16u+offset;if(site+2u>out||site>UINT16_MAX)return LMN_PKLITE_MALFORMED;relocations[nrel++]=(uint16_t)site;}
        segment+=0xfffu;
    }
    header->footer_offset=s.pos;
    if(!word(&s,&header->stack_ss)||!word(&s,&header->stack_sp)||!word(&s,&header->entry_cs)||!word(&s,&header->entry_ip))return LMN_PKLITE_MALFORMED;
    header->consumed_bytes=s.pos;*image_size=out;*relocation_count=nrel;(void)matches;(void)markers;
    return LMN_PKLITE_OK;
}

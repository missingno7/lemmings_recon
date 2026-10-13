"""Static DAT section decoding derived from CS:1BAF..1CB8, not a game runtime."""
from common import ROOT, BUILD, sha, write_json

class ReverseBits:
    def __init__(self, payload, valid_bits):
        if not payload or not 1 <= valid_bits <= 8:
            raise ValueError('Invalid initial bit count or empty payload')
        self.payload, self.pos = payload, len(payload)-1
        self.value, self.left = payload[-1], valid_bits
        self.checksum = self.value

    def read(self, count):
        result=0
        for _ in range(count):
            if not self.left:
                self.pos-=1
                if self.pos<0:
                    raise ValueError('Truncated reverse bitstream')
                self.value=self.payload[self.pos]
                self.checksum ^= self.value
                self.left=8
            result=(result<<1)|(self.value&1)
            self.value >>= 1
            self.left-=1
        return result

def decode_section(data):
    if len(data)<10:
        raise ValueError('Truncated DAT header')
    size=int.from_bytes(data[2:6],'big')
    packed=int.from_bytes(data[6:10],'big')
    # This bounded static extractor handles the 16-bit section domain used here.
    # The original loads the high size word then overwrites AX at1BD6; do not
    # claim support for arbitrary 32-bit lengths from the apparent file header.
    if not 0<size<=0xffff or not 10<packed<=min(len(data),0xffff):
        raise ValueError('Invalid or unsupported DAT section length')
    bits=ReverseBits(data[10:packed],data[0])
    out=bytearray(size)
    cursor=size
    tokens=[]
    while cursor:
        if bits.read(1):
            op=bits.read(2)
            if op==3:
                count=bits.read(8)+9
                distance=None
            elif op==2:
                count=bits.read(8)+1
                distance=bits.read(12)+1
            else:
                count=op+3
                distance=bits.read(op+9)+1
        elif bits.read(1):
            count,distance=2,bits.read(8)+1
        else:
            count,distance=bits.read(3)+1,None
        if count>cursor:
            raise ValueError('Token writes before output start')
        tokens.append('literal' if distance is None else f'match_{count}')
        for _ in range(count):
            cursor-=1
            if distance is None:
                out[cursor]=bits.read(8)
            else:
                source=cursor+distance
                if source>=size:
                    raise ValueError('Backreference outside decoded suffix')
                out[cursor]=out[source]
    if bits.checksum!=data[1]:
        raise ValueError('DAT XOR checksum mismatch')
    if bits.pos!=0:
        raise ValueError('Unconsumed packed payload bytes')
    return bytes(out),dict(packed_size=packed,image_size=size,image_sha256=sha(out),
                           checksum=data[1],remaining_bits=bits.left,token_count=len(tokens))

def sound_images():
    result={}
    for name in ('adlib','tandysnd'):
        data=(ROOT/'assets'/f'{name}.dat').read_bytes()
        image,meta=decode_section(data)
        if meta['packed_size']!=len(data):
            raise ValueError('Unexpected extra sound section')
        result[name]=(image,dict(meta,source=f'assets/{name}.dat',source_sha256=sha(data)))
    return result

if __name__=='__main__':
    for name,(image,meta) in sound_images().items():
        BUILD.mkdir(exist_ok=True)
        (BUILD/f'{name}.bin').write_bytes(image)
        write_json(BUILD/f'{name}-image.json',meta)
        print(name,meta)

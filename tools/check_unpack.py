"""Independent bounded oracle: execute only the original PKLITE stub.

Stop BEFORE CS:IP = load:0000. Vary DOS load segment, initial memory poison and
the DOS-supplied DF/IF; compare every decompressed byte, all relocation fixups,
entry, stack and the FLAGS handed to the game. The stub executes CLD (stub 0129),
STD (0000, backward self-move), CLD (0036) and STI before its RETF, so the game
entry receives DF=0 and IF=1 whatever DF/IF DOS supplied: original-code evidence,
not a platform assumption.
"""
import struct
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_INTR
from unicorn import x86_const as x
from unpack import ASSET, unpack, relocated

def check(load, poison, eflags=2):
    packed = ASSET.read_bytes()
    image, meta = unpack(packed)
    h = meta['packed_mz']
    psp = load - 16
    uc = Uc(UC_ARCH_X86, UC_MODE_16)
    uc.mem_map(0, 0x110000)
    uc.mem_write(0, bytes([poison]) * 0x110000)
    uc.mem_write(psp * 16, bytes(256))
    uc.mem_write(psp * 16 + 2, struct.pack('<H', 0x9000))
    uc.mem_write(load * 16, packed[h['header_paragraphs'] * 16:])
    for name, val in dict(cs=(load+h['cs']) & 0xffff, ip=h['ip'],
                          ss=load+h['ss'], sp=h['sp'], ds=psp, es=psp,
                          eflags=eflags).items():
        uc.reg_write(getattr(x, 'UC_X86_REG_' + name.upper()), val)
    reached = []
    def hook(u, address, size, _):
        if (u.reg_read(x.UC_X86_REG_CS) == load + meta['entry']['cs'] and
                u.reg_read(x.UC_X86_REG_IP) == meta['entry']['ip']):
            reached.append(u.reg_read(x.UC_X86_REG_EFLAGS))
            u.emu_stop()
    def interrupt(u, number, _):
        raise AssertionError(f'Unexpected interrupt {number:02x} in unpacker')
    uc.hook_add(UC_HOOK_CODE, hook)
    uc.hook_add(UC_HOOK_INTR, interrupt)
    start = ((load + h['cs']) & 0xffff) * 16 + h['ip']
    uc.emu_start(start, 0x10ffff, count=2_000_000)
    assert reached, 'Unpacker did not reach static entry within budget'
    actual = bytes(uc.mem_read(load * 16, len(image)))
    expected = relocated(image, meta['relocations'], load)
    if actual != expected:
        at = next(i for i, (a, b) in enumerate(zip(actual, expected)) if a != b)
        raise AssertionError(f'Unpacker differs at image:{at:05x}: {actual[at]:02x} != {expected[at]:02x}')
    assert uc.reg_read(x.UC_X86_REG_SS) == load + meta['stack']['ss']
    assert uc.reg_read(x.UC_X86_REG_SP) == meta['stack']['sp']
    assert uc.reg_read(x.UC_X86_REG_DS) == psp
    assert uc.reg_read(x.UC_X86_REG_ES) == psp
    assert (reached[0] >> 10) & 1 == 0, 'DF at game entry is not 0'
    assert (reached[0] >> 9) & 1 == 1, 'IF at game entry is not 1'
    print(f'PASS original unpacker vs static decoder: load={load:04X}, poison={poison:02X}, '
          f'DOS DF/IF={(eflags >> 10) & 1}/{(eflags >> 9) & 1} -> entry DF=0 IF=1, {len(image)} bytes')

if __name__ == '__main__':
    for load, poison, eflags in [(0x1010, 0, 0x002), (0x1213, 0xa5, 0x402),
                                 (0x2345, 0x5a, 0x202), (0x1010, 0x33, 0x602)]:
        check(load, poison, eflags)

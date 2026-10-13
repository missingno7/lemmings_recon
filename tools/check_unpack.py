"""Independent bounded oracle: execute only the original PKLITE stub.

Stop BEFORE CS:IP = load:0000. Vary DOS load segment and initial memory poison;
compare every decompressed byte, all relocation fixups, entry and stack.
"""
import struct
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_INTR
from unicorn import x86_const as x
from unpack import ASSET, unpack, relocated

def check(load, poison):
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
                          eflags=2).items():
        uc.reg_write(getattr(x, 'UC_X86_REG_' + name.upper()), val)
    reached = []
    def hook(u, address, size, _):
        if (u.reg_read(x.UC_X86_REG_CS) == load + meta['entry']['cs'] and
                u.reg_read(x.UC_X86_REG_IP) == meta['entry']['ip']):
            reached.append(True)
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
    print(f'PASS original unpacker vs static decoder: load={load:04X}, poison={poison:02X}, {len(image)} bytes')

if __name__ == '__main__':
    for load, poison in [(0x1010, 0), (0x1213, 0xa5), (0x2345, 0x5a)]:
        check(load, poison)

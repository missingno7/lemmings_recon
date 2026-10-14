"""Bounded original/native differential checks for ClearVgaBytes."""
import ctypes
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import capstone
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_INSN, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
from unicorn import x86_const as x
import dat_io as oracle
from common import ROOT, BUILD, read_json, write_json, sha
from cbuild import build
from unpack import ASSET, unpack, relocated

MEMORY_SIZE = 1 << 20
MEMORY_MASK = MEMORY_SIZE - 1
VGA_BASE = 0xa0000
VGA_END = 0xb0000
DF = 0x0400
IF = 0x0200
AF = 0x0010
ARITH = 0x08d5
DEFINED_EXIT = 0x0fc7  # XOR leaves AF undefined.
TRACE_FLAGS = 0x0fc7
MEM = ctypes.POINTER(ctypes.c_uint8)
IMAGE, ORACLE = unpack(ASSET.read_bytes())
SYMS = {row['symbol_name']: row for row in read_json(ROOT / 'metadata/symbols.json')}
ROUTINE = SYMS['ClearVgaBytes']
ENTRY = ROUTINE['address']
END = ENTRY + ROUTINE['size']
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
BRANCHES = {pc for pc, ins in INS.items()
            if ins.group(capstone.CS_GRP_JUMP) or ins.mnemonic.startswith('loop')}
EDGES = set()


class Regs(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'sp',
                 'cs', 'ds', 'es', 'ss', 'ip', 'flags')]


READ = ctypes.CFUNCTYPE(ctypes.c_uint8, ctypes.c_void_p, MEM,
                        ctypes.c_uint32, ctypes.c_uint16)
WRITE = ctypes.CFUNCTYPE(None, ctypes.c_void_p, MEM, ctypes.c_uint32,
                         ctypes.c_uint8, ctypes.c_uint16)
OUT = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint16,
                       ctypes.c_uint16, ctypes.c_uint16)


class Bus(ctypes.Structure):
    _fields_ = [('context', ctypes.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


def physical(segment, offset):
    return ((segment << 4) + (offset & 0xffff)) & MEMORY_MASK


def put16(mem, segment, offset, value):
    address = physical(segment, offset)
    mem[address] = value & 255
    mem[(address + 1) & MEMORY_MASK] = (value >> 8) & 255


class PlanarVga:
    """Documented unchained A000 mode-0 plane/latch fixture for this routine."""
    def __init__(self, seed, read_map):
        rng = random.Random(seed)
        self.planes = [bytearray(rng.randbytes(65536)) for _ in range(4)]
        self.latches = [rng.randrange(256) for _ in range(4)]
        self.seq = [rng.randrange(256) for _ in range(5)]
        self.gc = [rng.randrange(256) for _ in range(9)]
        self.seq[2] = 0x0f
        self.seq[4] = 0x06  # chain-4 and odd/even disabled; 64KiB A000 map
        self.gc[3] = 0       # no rotate or logical operation
        self.gc[4] = read_map
        self.gc[5] = 0       # write mode 0
        self.gc[6] = 0x05     # A000 64KiB map
        self.gc[8] = 0xff     # full bit mask
        self.seq_index = 0
        self.gc_index = 0

    def read(self, mem, address):
        if VGA_BASE <= address < VGA_END:
            offset = address - VGA_BASE
            if self.seq[4] & 0x08 or self.gc[6] & 0x0c != 0x04:
                raise AssertionError('Fixture requires an unchained A000 64KiB aperture')
            if self.gc[5] & 0x08:
                raise AssertionError('Fixture covers graphics-controller read mode 0 only')
            self.latches = [plane[offset] for plane in self.planes]
            value = self.latches[self.gc[4] & 3]
            mem[address] = value
            return value
        return mem[address]

    def write(self, mem, address, value):
        value &= 255
        if VGA_BASE <= address < VGA_END:
            offset = address - VGA_BASE
            if self.seq[4] & 0x08 or self.gc[6] & 0x0c != 0x04:
                raise AssertionError('Fixture requires an unchained A000 64KiB aperture')
            if self.gc[5] & 3:
                raise AssertionError('Fixture covers graphics-controller write mode 0 only')
            if self.gc[3] & 0x18:
                raise AssertionError('Fixture covers replace logical operation only')
            bit_mask = self.gc[8]
            for index, plane in enumerate(self.planes):
                if not (self.seq[2] & (1 << index)):
                    continue
                source = ((self.gc[0] >> index) & 1) * 255 \
                    if self.gc[1] & (1 << index) else value
                plane[offset] = ((source & bit_mask) |
                                 (self.latches[index] & (255 ^ bit_mask)))
        mem[address] = value

    def out(self, port, value):
        index = value & 255
        data = value >> 8
        if port == 0x3c4:
            self.seq_index = index
            if index < len(self.seq):
                self.seq[index] = data
        elif port == 0x3ce:
            self.gc_index = index
            if index < len(self.gc):
                self.gc[index] = data
        else:
            raise AssertionError(f'Unexpected word output port {port:04x}')

    def state(self):
        return (self.planes, self.latches, self.seq, self.gc,
                self.seq_index, self.gc_index)


class TracedBus:
    def __init__(self, seed, read_map, memory, return_alias=None):
        self.mem = memory
        self.vga = PlanarVga(seed, read_map)
        self.trace = []
        self.output_count = 0
        if return_alias is not None:
            offset, word = return_alias
            selected = self.vga.gc[4] & 3
            self.vga.planes[selected][offset] = word & 255
            self.vga.planes[selected][(offset + 1) & 0xffff] = word >> 8

    def read(self, address, flags):
        address &= MEMORY_MASK
        value = self.vga.read(self.mem, address)
        self.trace.append(('read', address, value, flags & TRACE_FLAGS))
        return value

    def write(self, address, value, flags):
        address &= MEMORY_MASK
        self.vga.write(self.mem, address, value)
        self.trace.append(('write', address, value & 255, flags & TRACE_FLAGS))

    def out(self, port, value, flags):
        # The first OUT precedes XOR and carries live incoming AF; later AF is
        # undefined. Other tracked bits include IF/DF and defined arithmetic flags.
        mask = 0x0fd7 if self.output_count == 0 else 0x0fc7
        self.trace.append(('out', port, value, flags & mask))
        self.output_count += 1
        self.vga.out(port, value)


def callbacks(bus):
    errors = []

    @READ
    def read(_context, _mem, address, flags):
        try:
            return bus.read(address, flags)
        except Exception as error:
            errors.append(error)
            return 0

    @WRITE
    def write(_context, _mem, address, value, flags):
        try:
            bus.write(address, value, flags)
        except Exception as error:
            errors.append(error)

    @OUT
    def out(_context, port, value, flags):
        try:
            bus.out(port, value, flags)
        except Exception as error:
            errors.append(error)

    return Bus(None, read, write, out), errors


def cases():
    out = []

    def add(name, count, di, **kw):
        out.append(dict(name=name, count=count, di=di, seed=len(out), **kw))

    add('zero-count-forward', 0, 0x2345)
    add('zero-count-reverse', 0, 0xffff, df=True)
    add('single-forward-at-ffff', 1, 0xffff)
    add('single-reverse-at-zero', 1, 0, df=True)
    add('forward-cursor-wrap', 3, 0xfffe)
    add('reverse-cursor-wrap', 3, 1, df=True)
    add('forward-planar-span', 0x120, 0x4a68)
    add('reverse-planar-span', 0x120, 0x4b87, df=True)
    add('large-rep-count', 0x2878, 0x8000)
    for df in (False, True):
        for di in (0x0000, 0xffff):
            untouched = (di + 1) & 0xffff if df else (di - 1) & 0xffff
            add(f'max-count-ffff-di-{di:04x}-df-{int(df)}', 0xffff, di,
                df=df, untouched_offset=untouched)
    add('stack-offset-ffff', 8, 0x7ffb, ss=0x7123, sp=0xffff,
        return_word=0xcafe)
    add('physical-20bit-ret-wrap', 4, 0x00fe, ss=0xffff, sp=0xffff,
        return_word=0x5aa5)
    add('vga-return-read-refreshes-latches', 1, 0x0040, ss=0xa000,
        sp=0x0020, return_word=0x5aff, read_map=2,
        vga_return_offset=0x0020)
    add('vga-live-ret-alias-is-cleared', 1, 0x0010, ss=0xa000,
        sp=0x0010, return_word=0x5aff, read_map=2,
        vga_return_offset=0x0010)
    add('stack-mirrors-write-vga-aperture', 0, 0x6fff, ss=0xa000,
        sp=0x0020, return_word=0x5aff, read_map=2,
        vga_return_offset=0x0020)
    for sp in (0x0000, 0x0001, 0x0002, 0x0003, 0x0008, 0x0009,
               0x000a, 0x000b, 0x000c, 0x000d, 0x000e, 0x000f, 0x0010):
        add(f'plain-ram-ret-and-ss-mirror-overlap-sp-{sp:04x}', 0, 0x6fff,
            ss=0x6000, sp=sp, return_word=0x5aff)
    add('ss-word-crosses-ffff-physical', 2, 0x0100, ss=0xf000,
        sp=0xffff, return_word=0x1234)
    add('incoming-if-df-and-af', 7, 0xfffc, df=True, iflag=True,
        af=True, ss=0x9fff, sp=0x0010, return_word=0x6d5c)
    return out


def prepare(case):
    rng = random.Random(0x4df8 + case['seed'])
    load = (0x1010, 0x1213, 0x2345)[case['seed'] % 3]
    mem = bytearray(rng.randbytes(MEMORY_SIZE))
    mem[load << 4:(load << 4) + len(IMAGE)] = relocated(
        IMAGE, ORACLE['relocations'], load)
    regs = {name: rng.randrange(65536) for name in oracle.REG_NAMES}
    regs.update(cs=load, ip=ENTRY, ss=case.get('ss', 0x7000),
                sp=case.get('sp', 0x8000), di=case['di'], cx=case['count'])
    flags = 2 | (rng.randrange(65536) & ARITH)
    flags = (flags | DF) if case.get('df') else (flags & ~DF)
    flags = (flags | IF) if case.get('iflag') else (flags & ~IF)
    flags = (flags | AF) if case.get('af') else (flags & ~AF)
    put16(mem, regs['ss'], regs['sp'], case.get('return_word', 0xff00))
    return mem, regs, flags


def library(mutation=0):
    lib = ctypes.CDLL(str(build(BUILD / f'vga-clear-m{mutation}-pid{os.getpid()}.dll',
                                mutation, 'vga_clear')))
    lib.lmn_clear_vga_bytes_adapter.argtypes = [MEM, ctypes.POINTER(Regs),
                                                ctypes.POINTER(Bus)]
    lib.lmn_clear_vga_bytes_adapter.restype = None
    return lib


def run_case(lib, case, collect_coverage=False):
    mem, regs, flags = prepare(case)
    c_memory = bytearray(mem)
    original_memory = bytearray(mem)
    return_alias = (case['vga_return_offset'], case['return_word']) \
        if 'vga_return_offset' in case else None
    c_bus_state = TracedBus(case.get('seed', 0) + 0x4df8,
                            case.get('read_map', 2), c_memory, return_alias)
    u_bus_state = TracedBus(case.get('seed', 0) + 0x4df8,
                            case.get('read_map', 2), original_memory, return_alias)
    c_bus, errors = callbacks(c_bus_state)
    c_regs = Regs(**regs, flags=flags)
    lib.lmn_clear_vga_bytes_adapter(
        (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(c_memory),
        ctypes.byref(c_regs), ctypes.byref(c_bus))
    if errors:
        raise errors[0]

    uc = Uc(UC_ARCH_X86, UC_MODE_16)
    uc.mem_map(0, 1 << 21)
    uc.mem_write(0, bytes(mem))
    uc.mem_write(MEMORY_SIZE, bytes(mem))
    for name, register in oracle.REG.items():
        uc.reg_write(register, regs[name])
    uc.reg_write(x.UC_X86_REG_EFLAGS, flags)
    sites = set()
    previous = None
    done = False
    actual_return = None
    original_errors = []
    def code(machine, pc, _size, _user):
        nonlocal previous, done, actual_return
        offset = pc - (regs['cs'] << 4)
        if previous == END - 1:
            done = True
            actual_return = offset & 0xffff
            machine.emu_stop()
            return
        if offset not in INS or machine.reg_read(oracle.REG['cs']) != regs['cs']:
            raise AssertionError(f"{case['name']}: original escaped to {offset & 0xffff:04x}")
        sites.add(offset)
        previous = offset

    def memory_read(machine, _access, address, size, _value, _user):
        try:
            flags_now = machine.reg_read(x.UC_X86_REG_EFLAGS)
            for index in range(size):
                linear = address + index
                byte = u_bus_state.read(linear & MEMORY_MASK, flags_now)
                machine.mem_write(linear, bytes((byte,)))
        except Exception as error:
            original_errors.append(error)

    def memory_write(machine, _access, address, size, value, _user):
        try:
            flags_now = machine.reg_read(x.UC_X86_REG_EFLAGS)
            for index in range(size):
                linear = address + index
                byte = (value >> (8 * index)) & 255
                physical_address = linear & MEMORY_MASK
                u_bus_state.write(physical_address, byte, flags_now)
                # The guest uses a 20-bit bus; keep its wrapped physical byte
                # visible even when Unicorn's linear address is above 1 MiB.
                machine.mem_write(physical_address, bytes((byte,)))
        except Exception as error:
            original_errors.append(error)

    def output(machine, port, size, value, _user):
        try:
            if size != 2:
                raise AssertionError('Expected OUT DX,AX word operation')
            u_bus_state.out(port, value, machine.reg_read(x.UC_X86_REG_EFLAGS))
        except Exception as error:
            original_errors.append(error)

    uc.hook_add(UC_HOOK_CODE, code)
    uc.hook_add(UC_HOOK_MEM_READ, memory_read, begin=0, end=(1 << 21) - 1)
    uc.hook_add(UC_HOOK_MEM_WRITE, memory_write, begin=0, end=(1 << 21) - 1)
    uc.hook_add(UC_HOOK_INSN, output, None, 1, 0, x.UC_X86_INS_OUT)
    uc.emu_start(physical(regs['cs'], ENTRY), 0, count=100000)
    if not done:
        raise AssertionError(f"{case['name']}: original exceeded the bounded run")
    if original_errors:
        raise original_errors[0]

    original_regs = {name: uc.reg_read(register) & 0xffff
                     for name, register in oracle.REG.items()}
    original_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xffff
    original_ram = bytes(uc.mem_read(0, MEMORY_SIZE))
    for name in oracle.REG_NAMES:
        got = getattr(c_regs, name)
        if got != original_regs[name]:
            raise AssertionError(f"{case['name']}: {name} C={got:04x}/"
                                 f"original={original_regs[name]:04x}")
    if (c_regs.flags ^ original_flags) & DEFINED_EXIT:
        raise AssertionError(f"{case['name']}: defined flags differ")
    if bytes(c_memory) != original_ram:
        offset = next(i for i, pair in enumerate(zip(c_memory, original_ram))
                      if pair[0] != pair[1])
        raise AssertionError(f"{case['name']}: whole RAM differs at {offset:05x}")
    if c_bus_state.vga.state() != u_bus_state.vga.state():
        raise AssertionError(f"{case['name']}: VGA planes/latches/registers differ")
    if c_bus_state.trace != u_bus_state.trace:
        mismatch = next((i for i, pair in enumerate(zip(c_bus_state.trace,
                                                        u_bus_state.trace))
                         if pair[0] != pair[1]),
                        min(len(c_bus_state.trace), len(u_bus_state.trace)))
        raise AssertionError(f"{case['name']}: ordered bus trace differs at {mismatch}; "
                             f"C={c_bus_state.trace[mismatch:mismatch+1]}, "
                             f"original={u_bus_state.trace[mismatch:mismatch+1]}")
    if c_regs.ip != actual_return:
        raise AssertionError(f"{case['name']}: adapter RET target differs")

    # Independently require all four planes to be zeroed over the REP footprint
    # when the live SS mirrors and RET do not alias the VGA aperture.
    if regs['ss'] != 0xa000:
        initial_planes = [bytearray(plane) for plane in
                          PlanarVga(case.get('seed', 0) + 0x4df8,
                                    case.get('read_map', 2)).planes]
        expected_planes = [bytearray(plane) for plane in initial_planes]
        step = -1 if flags & DF else 1
        for index in range(case['count']):
            expected_planes_offset = (case['di'] + step * index) & 0xffff
            for plane in expected_planes:
                plane[expected_planes_offset] = 0
        if c_bus_state.vga.planes != expected_planes:
            raise AssertionError(f"{case['name']}: independent all-plane clear differs")
        if 'untouched_offset' in case:
            offset = case['untouched_offset']
            for plane_index in range(4):
                if c_bus_state.vga.planes[plane_index][offset] != \
                        initial_planes[plane_index][offset]:
                    raise AssertionError(f"{case['name']}: untouched byte {offset:04x} changed in plane {plane_index}")
    if collect_coverage:
        return sites, set()
    return None


def main():
    report = BUILD / 'vga-clear-differential.json'
    report.unlink(missing_ok=True)
    if ENTRY != 0x4df8 or ROUTINE['size'] != 63:
        raise AssertionError('Unexpected ClearVgaBytes ledger boundary')
    if len(INS) != 25 or sum(ins.size for ins in INS.values()) != 63:
        raise AssertionError(f'Unexpected decoded extent: {len(INS)} sites, '
                             f'{sum(ins.size for ins in INS.values())} bytes')
    baseline = cases()
    sites = set()
    native = library()
    for case in baseline:
        seen, edges = run_case(native, case, True)
        sites |= seen
        if edges:
            raise AssertionError('Straight-line VGA clear unexpectedly branched')
    if sites != set(INS):
        raise AssertionError(f'Missing instruction sites: {sorted(set(INS) - sites)}')

    mutation_cases = {1: 'single-forward-at-ffff',
                      2: 'reverse-planar-span',
                      3: 'zero-count-forward'}
    mutations = []
    by_name = {case['name']: case for case in baseline}
    for mutation, name in mutation_cases.items():
        try:
            run_case(library(mutation), by_name[name])
        except AssertionError:
            mutations.append(dict(mutation=mutation, case=name))
        else:
            raise AssertionError(f'Compiled mutation {mutation} survived on {name}')

    paths = ('c/vga_clear.c', 'c/vga_clear.h', 'c/special_blit.h',
             'c/regs.h', 'c/lemmings_sym.h', 'tests/vga_clear.py',
             'tests/dat_io.py', 'tools/cbuild.py', 'tools/common.py',
             'tools/difftest.py', 'tools/unpack.py', 'metadata/symbols.json',
             'assets/vgalemmi.exe')
    public_cases = [{key: value for key, value in case.items()
                     if key not in ('seed', 'return_word')} | {
                         'return_word': f"{case.get('return_word', 0xff00):04x}",
                         'df': bool(case.get('df')),
                         'iflag': bool(case.get('iflag')),
                         'af_incoming': bool(case.get('af'))}
                    for case in baseline]
    write_json(report, dict(image='main', image_sha256=sha(IMAGE),
        case_count=len(baseline), cases=public_cases,
        mutation_count=len(mutations), mutations_detected=mutations,
        translated_code_bytes=sum(ins.size for ins in INS.values()),
        instruction_addresses=sorted(INS), executed_instruction_addresses=sorted(sites),
        branch_instruction_addresses=sorted(BRANCHES), branch_edges=[],
        routine=dict(name='ClearVgaBytes', start=ENTRY, end=END,
                     byte_count=END-ENTRY, bytes=IMAGE[ENTRY:END].hex(),
                     byte_sha256=sha(IMAGE[ENTRY:END]), status='bounded native translation'),
        c_sources=['c/vga_clear.c', 'c/vga_clear.h'],
        original_range=dict(start=ENTRY, end=END, decoded_bytes=END-ENTRY,
                            instruction_sites=len(INS), classification='code'),
        input_hashes={path: sha((ROOT / path).read_bytes()) for path in paths},
        device_contract='Unchained planar A000 64KiB aperture; graphics-controller read mode 0 and write mode 0; replace operation; full bit mask; sequencer map mask; device-owned planes and latches; no IRQ scheduling.',
        flag_notes='First OUT and first SS mirror retain all incoming flags; XOR AX,AX then XOR AL,AL set PF/ZF, clear CF/OF, preserve IF/DF, and leave AF undefined. REP STOSB preserves flags.',
        domain='Complete original 4DF8..4E36 routine; all 25 instruction sites; six live SS word mirrors; six ordered OUT words; ES=A000, AL=0, forward/reverse REP STOSB including zero count and 16-bit DI wrap; physical 20-bit memory; live RET read through the same bus; full RAM/registers, defined flags, VGA planes/latches/registers and ordered bus traces.'))
    print(f'PASS VGA clear C: {len(baseline)} cases, {len(sites)} instruction sites, '
          f'0 branch edges; {len(mutations)} compiled mutations detected')


if __name__ == '__main__':
    main()

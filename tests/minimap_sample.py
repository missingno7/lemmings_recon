"""Bounded 7A39 minimap-sample original/C comparisons and leaf contracts."""
import ctypes
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import capstone
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_INTR,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
from unicorn import x86_const as x
import dat_io as oracle
from common import ROOT, BUILD, read_json, write_json, sha
from cbuild import build
from unpack import ASSET, unpack, relocated


IMAGE, ORACLE = unpack(ASSET.read_bytes())
SYMS = {s['symbol_name']: s for s in read_json(ROOT / 'metadata/symbols.json')}
ROUTINE = SYMS['AccumulateMinimapSample']
ENTRY = ROUTINE['address']
END = ENTRY + ROUTINE['size']
RETURNS = {0x7A54, 0x7A59}
TARGET = SYMS['MinimapColumnBits']['address']
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {i.address: i for i in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
BRANCHES = {pc for pc, i in INS.items()
            if i.group(capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EDGES = {(pc, i.operands[0].imm & 0xffff) for pc, i in INS.items()
         if pc in BRANCHES}
EDGES |= {(pc, pc + i.size) for pc, i in INS.items()
          if pc in BRANCHES}
MEMORY_SIZE = 1 << 20
MEMORY_MASK = MEMORY_SIZE - 1
MAPPED_SIZE = 2 * MEMORY_SIZE
LOADS = (0x1010, 0x1213, 0x2345)
FLAGS_DEFINED = 0x0fd7
CF, PF, AF, ZF, SF, IF, DF, OF = 1, 4, 0x10, 0x40, 0x80, 0x200, 0x400, 0x800
ARITH = CF | PF | AF | ZF | SF | OF
REG_NAMES = oracle.REG_NAMES + ('flags',)
MEM = ctypes.POINTER(ctypes.c_uint8)
READ = ctypes.CFUNCTYPE(ctypes.c_uint8, ctypes.c_void_p, MEM,
                        ctypes.c_uint32, ctypes.c_uint16)
WRITE = ctypes.CFUNCTYPE(None, ctypes.c_void_p, MEM, ctypes.c_uint32,
                         ctypes.c_uint8, ctypes.c_uint16)
OUT = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint16,
                       ctypes.c_uint16, ctypes.c_uint16)


class Regs(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in REG_NAMES]


class RasterBus(ctypes.Structure):
    _fields_ = [('context', ctypes.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


def physical(segment, offset):
    return ((segment << 4) + (offset & 0xffff)) & MEMORY_MASK


def read_word(mem, segment, offset):
    address = physical(segment, offset)
    return mem[address] | (mem[(address + 1) & MEMORY_MASK] << 8)


def write_byte(mem, segment, offset, value):
    mem[physical(segment, offset)] = value & 0xff


def put_source(mem, segment, offset, pair):
    write_byte(mem, segment, offset, pair[0])
    write_byte(mem, segment, (offset + 1) & 0xffff, pair[1])


def even_parity(value):
    return (value & 0xff).bit_count() % 2 == 0


def cmp8_flags(flags, left, right):
    result = (left - right) & 0xff
    set_flags = 0
    if left < right:
        set_flags |= CF
    if even_parity(result):
        set_flags |= PF
    if (left ^ right ^ result) & 0x10:
        set_flags |= AF
    if result == 0:
        set_flags |= ZF
    if result & 0x80:
        set_flags |= SF
    if (left ^ right) & (left ^ result) & 0x80:
        set_flags |= OF
    return (flags & ~ARITH) | set_flags


def or8_flags(flags, value):
    set_flags = 0
    if even_parity(value):
        set_flags |= PF
    if value == 0:
        set_flags |= ZF
    if value & 0x80:
        set_flags |= SF
    # OR leaves AF undefined; retain the CMP representative and exclude AF
    # from post-OR architectural comparisons.
    return (flags & ~(CF | PF | ZF | SF | OF)) | set_flags


def expected_contract(mem, regs, flags):
    out_mem = bytearray(mem)
    pushed = (regs['sp'] - 2) & 0xffff
    oracle.put16(out_mem, regs['ss'], pushed, regs['cx'])
    first = out_mem[physical(regs['es'], regs['si'])]
    second = out_mem[physical(regs['es'], (regs['si'] + 1) & 0xffff)]
    population = (first | (second << 8)).bit_count()
    out_flags = cmp8_flags(flags, population, 8)
    if population > 8:
        address = physical(regs['cs'], regs['bx'])
        value = out_mem[address] | (regs['dx'] & 0xff)
        out_mem[address] = value
        out_flags = or8_flags(out_flags, value)
    out_regs = dict(regs)
    out_regs.update(ax=0, cx=read_word(out_mem, regs['ss'], pushed),
        dx=(population << 8) | (regs['dx'] & 0xff),
        ip=read_word(out_mem, regs['ss'], regs['sp']),
        sp=(regs['sp'] + 2) & 0xffff)
    return out_mem, out_regs, out_flags, population


def cases():
    out = []

    def add(name, pair, **kw):
        out.append(dict(name=name, pair=pair, seed=len(out), **kw))

    # Each population count executes its SHR carry/no-carry and LOOP edges.
    for count in range(17):
        value = (1 << count) - 1
        add(f'population-{count:02d}', (value >> 8, value & 0xff),
            mask=(0xa5 ^ (count * 37)) & 0xff, cx=0x6130 + count)

    # Exact SI wrap differs from reading a physical word across the boundary.
    add('si-ffff-second-byte-wrap', (0x01, 0x80), es=0x4000, si=0xffff,
        contiguous_decoy=0xff, mask=0x84)
    add('es-physical-20bit-wrap', (0x80, 0x01), es=0xffff, si=0x000f,
        mask=0x5a)
    add('stack-offset-wrap-sp-0001', (0x07, 0x80), ss=0x7000, sp=0x0001,
        mask=0xe1)
    add('stack-physical-20bit-wrap', (0x0f, 0x80), ss=0xf000, sp=0x1001,
        mask=0x81)
    add('stack-offset-wrap-sp-0000', (0x01, 0xff), ss=0x7000, sp=0x0000,
        mask=0x36)

    # PUSH CX supplies the live source bytes before either ES read.
    add('source-aliases-push-cx', (0x00, 0x00), ss=0x7000, sp=0x9000,
        source_alias_push=True, cx=0xffff, mask=0x96)

    # OR can change the live saved CX word and the caller's live RET word.
    for byte_index in (0, 1):
        target = (0xff00 - 2 + byte_index) & 0xffff
        add(f'target-aliases-saved-cx-byte-{byte_index}', (0xff, 0x01),
            cs_is_ss=True, ss=0, sp=0xff00, cx=0x1234,
            target_cursor=target, mask=0x80)
    for byte_index in (0, 1):
        add(f'target-aliases-return-byte-{byte_index}', (0xff, 0x01),
            cs_is_ss=True, ss=0, sp=0xff00,
            target_cursor=(0xff00 + byte_index) & 0xffff,
            return_word=0x1234 if byte_index == 0 else 0x1200,
            mask=0x80)

    # Exercise assorted flags, offsets and source bytes in addition to the
    # complete 0..16 population grid.
    rng = random.Random(0x7a39)
    for index in range(40):
        value = rng.randrange(1 << 16)
        add(f'random-{index:02d}', (value >> 8, value & 0xff),
            es=rng.randrange(1 << 16), si=rng.randrange(1 << 16),
            mask=rng.randrange(256), cx=rng.randrange(1 << 16))
    return out


def prepare(case):
    rng = random.Random(0x7a39 + case['seed'])
    load = LOADS[case['seed'] % len(LOADS)]
    mem = bytearray(rng.randbytes(MEMORY_SIZE))
    mem[load << 4:(load << 4) + len(IMAGE)] = relocated(
        IMAGE, ORACLE['relocations'], load)
    regs = {name: rng.randrange(1 << 16) for name in oracle.REG_NAMES}
    cs = load
    ss = case.get('ss', 0x7000)
    if case.get('cs_is_ss'):
        cs = load
        ss = cs
    sp = case.get('sp', 0x8000)
    es = case.get('ss', 0x7000) if case.get('source_alias_push') else case.get('es', 0x4000)
    si = ((sp - 2) & 0xffff) if case.get('source_alias_push') else case.get('si', 0x1234)
    bx = case.get('target_cursor', TARGET)
    regs.update(cs=cs, ip=ENTRY, ds=rng.randrange(1 << 16), es=es,
        ss=ss, sp=sp, si=si, bx=bx,
        cx=case.get('cx', rng.randrange(1 << 16)),
        dx=((rng.randrange(256) << 8) | case.get('mask',
             (rng.randrange(256)))),)
    # Keep TF clear so Unicorn's single-step INT 1 does not leave the
    # quiescent-IRQ domain; IF, DF and every arithmetic input bit still vary.
    flags = 2 | (rng.randrange(1 << 16) & 0x0ed5)

    # The target is mutable CS data in the ordinary cases. Alias cases obtain
    # its old byte from the pushed CX word or the caller's return word.
    if not case.get('cs_is_ss'):
        write_byte(mem, regs['cs'], bx, case.get('target_before', 0x35 + case['seed']))
    put_source(mem, regs['es'], si, case['pair'])
    if 'contiguous_decoy' in case:
        mem[(physical(regs['es'], si) + 1) & MEMORY_MASK] = case['contiguous_decoy']
    oracle.put16(mem, regs['ss'], regs['sp'], case.get('return_word', 0xff00))
    return mem, regs, flags


def library(mutation=0):
    lib = ctypes.CDLL(str(build(BUILD / f'minimap-sample-m{mutation}.dll',
                                mutation, 'minimap_sample')))
    lib.lmn_accumulate_minimap_sample_adapter.argtypes = [
        MEM, ctypes.POINTER(Regs), ctypes.POINTER(RasterBus)]
    lib.lmn_accumulate_minimap_sample_adapter.restype = None
    lib.lmn_accumulate_minimap_sample_core.argtypes = [
        MEM, ctypes.c_uint16, ctypes.c_uint16, ctypes.c_uint16,
        ctypes.c_uint16, ctypes.c_uint16, ctypes.c_uint16, ctypes.c_uint8,
        ctypes.c_uint16, ctypes.c_uint16, ctypes.POINTER(RasterBus)]
    lib.lmn_accumulate_minimap_sample_core.restype = ctypes.c_uint16 * 5
    # ctypes needs the declared C result structure, not a packed array.
    class Result(ctypes.Structure):
        _fields_ = [('value', ctypes.c_uint16), ('population_mask', ctypes.c_uint16),
                    ('count', ctypes.c_uint16), ('stack_offset', ctypes.c_uint16),
                    ('flags', ctypes.c_uint16)]
    lib.lmn_accumulate_minimap_sample_core.restype = Result
    return lib


def register_values(regs):
    return {name: getattr(regs, name) for name in oracle.REG_NAMES}


def run_case(lib, case):
    mem, regs, flags = prepare(case)
    expected_mem, expected_regs, expected_flags, population = expected_contract(mem, regs, flags)
    local_code = bytes(mem[(regs['cs'] << 4) + ENTRY:(regs['cs'] << 4) + END])

    # The callback bus is a complete 1 MiB RAM model and records byte order.
    bus_mem = bytearray(mem)
    bus_regs = Regs(**regs, flags=flags)
    bus_events = []
    bus_errors = []

    @READ
    def bus_read(_context, memory, address, inflags):
        try:
            address &= MEMORY_MASK
            value = memory[address]
            bus_events.append(('read', address, None, inflags & FLAGS_DEFINED))
            return value
        except Exception as error:
            bus_errors.append(error)
            return 0

    @WRITE
    def bus_write(_context, memory, address, value, inflags):
        try:
            address &= MEMORY_MASK
            memory[address] = value
            bus_events.append(('write', address, value, inflags & FLAGS_DEFINED))
        except Exception as error:
            bus_errors.append(error)

    @OUT
    def bus_out(_context, _port, _value, _inflags):
        bus_errors.append(AssertionError('sample leaf unexpectedly used a port'))

    c_bus = RasterBus(None, bus_read, bus_write, bus_out)
    lib.lmn_accumulate_minimap_sample_adapter(
        (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(bus_mem),
        ctypes.byref(bus_regs), ctypes.byref(c_bus))
    if bus_errors:
        raise bus_errors[0]

    # The optional null-bus path uses ordinary, explicitly wrapped RAM.
    direct_mem = bytearray(mem)
    direct_regs = Regs(**regs, flags=flags)
    lib.lmn_accumulate_minimap_sample_adapter(
        (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(direct_mem),
        ctypes.byref(direct_regs), None)

    # Unicorn's extra MiB mirrors the 20-bit DOS bus. Keep both views in sync
    # for data accesses that cross the physical 1 MiB boundary.
    uc = Uc(UC_ARCH_X86, UC_MODE_16)
    uc.mem_map(0, MAPPED_SIZE)
    uc.mem_write(0, bytes(mem))
    uc.mem_write(MEMORY_SIZE, bytes(mem))
    for name, register in oracle.REG.items():
        uc.reg_write(register, regs[name])
    uc.reg_write(x.UC_X86_REG_EFLAGS, flags)
    sites = set()
    edges = set()
    oracle_events = []
    previous = None
    done = False

    def code(machine, pc, _size, _user):
        nonlocal previous, done
        offset = pc - (regs['cs'] << 4)
        if previous in BRANCHES:
            edges.add((previous, offset & 0xffff))
        if previous in RETURNS:
            done = True
            machine.emu_stop()
            return
        if machine.reg_read(oracle.REG['cs']) != regs['cs'] or offset not in INS:
            raise AssertionError(f"{case['name']}: original escaped at {offset & 0xffff:04x}")
        sites.add(offset)
        previous = offset

    def memory_read(machine, _access, address, size, _value, _user):
        event_flags = machine.reg_read(x.UC_X86_REG_EFLAGS) & FLAGS_DEFINED
        for index in range(size):
            linear = address + index
            if linear >= MEMORY_SIZE:
                machine.mem_write(linear,
                    bytes(machine.mem_read(linear & MEMORY_MASK, 1)))
            oracle_events.append(('read', linear & MEMORY_MASK, None, event_flags))

    def memory_write(machine, _access, address, size, value, _user):
        event_flags = machine.reg_read(x.UC_X86_REG_EFLAGS) & FLAGS_DEFINED
        for index in range(size):
            linear = address + index
            byte = (value >> (8 * index)) & 0xff
            oracle_events.append(('write', linear & MEMORY_MASK, byte, event_flags))
            if linear >= MEMORY_SIZE:
                machine.mem_write(linear & MEMORY_MASK, bytes((byte,)))
            else:
                machine.mem_write(linear + MEMORY_SIZE, bytes((byte,)))

    def interrupt(_machine, number, _user):
        raise AssertionError(f"{case['name']}: unexpected interrupt {number}")

    uc.hook_add(UC_HOOK_CODE, code)
    uc.hook_add(UC_HOOK_MEM_READ, memory_read)
    uc.hook_add(UC_HOOK_MEM_WRITE, memory_write)
    uc.hook_add(UC_HOOK_INTR, interrupt)
    uc.emu_start(physical(regs['cs'], ENTRY), 0, count=1000)
    if not done:
        raise AssertionError(f"{case['name']}: sample leaf exceeded bounded execution")

    oracle_regs = {name: uc.reg_read(register) & 0xffff
                   for name, register in oracle.REG.items()}
    oracle_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xffff
    oracle_mem = bytes(uc.mem_read(0, MEMORY_SIZE))
    if bytes(uc.mem_read((regs['cs'] << 4) + ENTRY, END - ENTRY)) != local_code:
        raise AssertionError(f"{case['name']}: original modified executing sample code")

    for label, got_regs, got_flags, got_mem in (
            ('original contract', oracle_regs, oracle_flags, oracle_mem),
            ('C callback bus', register_values(bus_regs), bus_regs.flags, bytes(bus_mem)),
            ('C null bus', register_values(direct_regs), direct_regs.flags, bytes(direct_mem))):
        for name in oracle.REG_NAMES:
            if got_regs[name] != expected_regs[name]:
                raise AssertionError(f"{case['name']}: {label} {name}={got_regs[name]:04x}, "
                                     f"expected {expected_regs[name]:04x}")
        flag_mask = FLAGS_DEFINED if population <= 8 else FLAGS_DEFINED & ~AF
        if (got_flags ^ expected_flags) & flag_mask:
            raise AssertionError(f"{case['name']}: {label} flags {got_flags:04x}, "
                                 f"expected {expected_flags:04x}, mask {flag_mask:04x}")
        if got_mem != bytes(expected_mem):
            position = next(i for i, (a, b) in enumerate(zip(got_mem, expected_mem)) if a != b)
            raise AssertionError(f"{case['name']}: {label} whole RAM differs at {position:05x}")

    if bytes(uc.mem_read((regs['cs'] << 4) + ENTRY, END - ENTRY)) != local_code:
        raise AssertionError(f"{case['name']}: C callback bus modified executing sample code")
    if bytes(direct_mem[(regs['cs'] << 4) + ENTRY:(regs['cs'] << 4) + END]) != local_code:
        raise AssertionError(f"{case['name']}: C null bus modified executing sample code")

    if len(bus_events) != len(oracle_events):
        raise AssertionError(f"{case['name']}: ordered RAM access count differs "
                             f"({len(bus_events)} C/{len(oracle_events)} original)")
    for index, (c_event, u_event) in enumerate(zip(bus_events, oracle_events)):
        if c_event[:3] != u_event[:3]:
            raise AssertionError(f"{case['name']}: ordered RAM access {index} differs: "
                                 f"C {c_event[:3]}, original {u_event[:3]}")
        flag_mask = FLAGS_DEFINED
        # The final POP and RET observe post-OR flags; AF is undefined there.
        if population > 8 and index >= 6:
            flag_mask &= ~AF
        if (c_event[3] ^ u_event[3]) & flag_mask:
            raise AssertionError(f"{case['name']}: RAM access {index} flags differ: "
                                 f"C {c_event[3]:04x}, original {u_event[3]:04x}")

    return sites, edges, population


def exhaustive_native_populations(lib):
    """Run every 16-bit source vector through the native logical core."""
    memory = bytearray(MEMORY_SIZE)
    es, si, cs, bx, ss, sp = 0x4000, 0x0100, 0x2000, 0x0200, 0x5000, 0x9000
    source = physical(es, si)
    target = physical(cs, bx)
    stack = (sp - 2) & 0xffff
    pointer = (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(memory)
    for value in range(1 << 16):
        memory[source] = value >> 8
        memory[source + 1] = value & 0xff
        count = (value * 0x9e37 + 0x51a7) & 0xffff
        memory[physical(ss, stack)] = count & 0xff
        memory[physical(ss, stack) + 1] = count >> 8
        mask = ((value * 73) ^ (value >> 8)) & 0xff
        before = 0x0002 | ((value * 0x95) & 0x0fd5)
        memory[target] = 0x32
        result = lib.lmn_accumulate_minimap_sample_core(pointer, cs, es, ss, sp,
            si, bx, mask, count, before, None)
        population = value.bit_count()
        wanted_flags = cmp8_flags(before, population, 8)
        wanted_byte = 0x32
        if population > 8:
            wanted_byte |= mask
            wanted_flags = or8_flags(wanted_flags, wanted_byte)
        if (result.value != 0 or result.population_mask != (population << 8) | mask or
                result.count != count or result.stack_offset != sp or
                memory[target] != wanted_byte):
            raise AssertionError(f'Native exhaustive vector {value:04x} differs')
        flag_mask = FLAGS_DEFINED if population <= 8 else FLAGS_DEFINED & ~AF
        if (result.flags ^ wanted_flags) & flag_mask:
            raise AssertionError(f'Native exhaustive flags differ for {value:04x}')
    return 1 << 16


def main():
    report = BUILD / 'minimap-sample-differential.json'
    report.unlink(missing_ok=True)
    if len(INS) != 16 or sum(i.size for i in INS.values()) != 33:
        raise AssertionError('7A39 static instruction extent differs from the 33-byte leaf')
    expected_bytes = bytes.fromhex(
        '51 26 8A 24 26 8A 44 01 B9 10 00 32 F6 D1 E8 73 02 FE C6 '
        'E2 F8 80 FE 08 7F 02 59 C3 2E 08 17 59 C3')
    if IMAGE[ENTRY:END] != expected_bytes:
        raise AssertionError('Pinned 7A39 bytes differ from the reviewed leaf')

    baseline = cases()
    lib = library()
    sites = set()
    edges = set()
    populations = {}
    for case in baseline:
        got_sites, got_edges, population = run_case(lib, case)
        sites |= got_sites
        edges |= got_edges
        populations[case['name']] = population
    if sites != set(INS):
        raise AssertionError(f'Missing sample instruction sites: {set(INS) - sites}')
    if edges != EDGES:
        raise AssertionError(f'Missing sample branch edges: {EDGES - edges}')
    if populations['population-08'] != 8 or populations['population-09'] != 9:
        raise AssertionError('Threshold cases do not straddle eight')

    exhaustive_count = exhaustive_native_populations(lib)
    mutation_cases = {
        1: next(case for case in baseline if case['name'] == 'population-08'),
        2: next(case for case in baseline if case['name'] == 'si-ffff-second-byte-wrap'),
        3: next(case for case in baseline if case['name'] == 'target-aliases-saved-cx-byte-0'),
    }
    mutations = []
    for mutation, case in mutation_cases.items():
        mutant = library(mutation)
        try:
            run_case(mutant, case)
        except AssertionError:
            mutations.append(dict(mutation=mutation, case=case['name']))
        else:
            raise AssertionError(f'Sample compiled mutation {mutation} survived')

    paths = ('c/minimap_sample.c', 'c/minimap_sample.h', 'c/special_blit.h',
        'c/regs.h', 'tests/minimap_sample.py', 'tests/dat_io.py', 'tools/cbuild.py',
        'tools/unpack.py', 'tools/common.py', 'metadata/symbols.json',
        'assets/vgalemmi.exe')
    write_json(report, dict(image='main', image_sha256=sha(IMAGE),
        routine=dict(name=ROUTINE['symbol_name'], start=ENTRY, end=END),
        original_bytes=expected_bytes.hex(' ').upper(), case_count=len(baseline),
        mutation_count=len(mutations), mutations_detected=mutations,
        executed_instruction_addresses=sorted(sites), branch_edges=sorted(edges),
        translated_code_bytes=sum(i.size for i in INS.values()),
        native_exhaustive_population_vectors=exhaustive_count,
        cases=[case['name'] for case in baseline],
        input_hashes={path: sha((ROOT / path).read_bytes()) for path in paths},
        domain='Intact 7A39..7A59 near-call leaf; ES byte reads with 16-bit offset wrap; '
               'PUSH/POP CX and RET through live contiguous SS words; CS:BX OR only for '
               'population >8; full 20-bit RAM, null and callback buses, all registers, '
               'defined flags, ordered byte accesses; quiescent IRQ seam'))
    print(f'PASS minimap sample C: {len(baseline)} cases, {len(sites)} sites, '
          f'{len(edges)} branch edges, {exhaustive_count} exhaustive vectors; '
          f'{len(mutations)} compiled mutations detected')


if __name__ == '__main__':
    main()

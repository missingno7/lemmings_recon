"""Bounded original/native checks for MarkDrawingDirtyCells (9A15)."""
import ctypes
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import capstone
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INTR)
from unicorn import x86_const as x
import dat_io as oracle
from common import ROOT, BUILD, read_json, write_json, sha
from cbuild import build
from unpack import ASSET, unpack, relocated

MEMORY_SIZE = 1 << 20
MEMORY_MASK = MEMORY_SIZE - 1
MAPPED_SIZE = 2 * MEMORY_SIZE
LOADS = (0x1010, 0x1213, 0x2345)
IMAGE, ORACLE = unpack(ASSET.read_bytes())
SYMS = {row['symbol_name']: row for row in read_json(ROOT / 'metadata/symbols.json')}
ROUTINE = SYMS['MarkDrawingDirtyCells']
ENTRY = ROUTINE['address']
END = ENTRY + ROUTINE['size']
RET = END - 1
MAP_OFFSET = SYMS['DrawingDirtyCellMapOffset']['address']
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
BRANCHES = {pc for pc, ins in INS.items()
            if ins.group(capstone.CS_GRP_JUMP) or ins.mnemonic.startswith('loop')}
EDGES = {(pc, ins.operands[0].imm & 0xffff)
         for pc, ins in INS.items() if pc in BRANCHES}
EDGES |= {(pc, ins.address + ins.size)
          for pc, ins in INS.items() if pc in BRANCHES}
ARITH = 0x08d5
CF, PF, AF, ZF, SF, IF, DF, OF = 1, 4, 0x10, 0x40, 0x80, 0x200, 0x400, 0x800
FLAGS_DEFINED = CF | PF | ZF | SF | IF | DF | OF
REG_NAMES = oracle.REG_NAMES
MEM = ctypes.POINTER(ctypes.c_uint8)


class Regs(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in REG_NAMES + ('flags',)]


class DrawingDirtyCall(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('data_segment', 'stack_segment', 'stack_offset', 'left', 'top',
                 'packed_height', 'width', 'source_cursor', 'destination_cursor',
                 'control', 'flags')]


class DrawingDirtyResult(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('left', 'top', 'packed_height', 'width', 'source_cursor',
                 'destination_cursor', 'control', 'stack_offset', 'flags')]


READ = ctypes.CFUNCTYPE(ctypes.c_uint8, ctypes.c_void_p, MEM,
                        ctypes.c_uint32, ctypes.c_uint16)
WRITE = ctypes.CFUNCTYPE(None, ctypes.c_void_p, MEM, ctypes.c_uint32,
                         ctypes.c_uint8, ctypes.c_uint16)
OUT = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint16,
                       ctypes.c_uint16, ctypes.c_uint16)


class RasterBus(ctypes.Structure):
    _fields_ = [('context', ctypes.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


def physical(segment, offset):
    return ((segment << 4) + (offset & 0xffff)) & MEMORY_MASK


def put16(mem, segment, offset, value):
    address = physical(segment, offset)
    mem[address] = value & 255
    mem[(address + 1) & MEMORY_MASK] = (value >> 8) & 255


def get16(mem, segment, offset):
    address = physical(segment, offset)
    return mem[address] | (mem[(address + 1) & MEMORY_MASK] << 8)


def add_case(out, name, **fields):
    out.append(dict(name=name, seed=len(out), **fields))


def cases():
    out = []
    add_case(out, 'one-byte-normal-row', left=0x10, top=0, packed_height=8,
             width=8)
    add_case(out, 'clamp-left-below-16', left=0, top=0, packed_height=8,
             width=8)
    add_case(out, 'left-fraction-and-width-two', left=0x19, top=0,
             packed_height=8, width=9)
    add_case(out, 'top-fraction-rounds-height', left=0x10, top=1,
             packed_height=8, width=8)
    add_case(out, 'height-fraction-rounds-height', left=0x10, top=0,
             packed_height=9, width=8)
    add_case(out, 'zero-height-hits-map-bound', left=0x10, top=0,
             packed_height=0, width=8)
    add_case(out, 'zero-width-height-one-65536-stores', left=0x10, top=0,
             packed_height=8, width=0)
    add_case(out, 'zero-width-overwrites-live-stack-and-ret', left=0x10, top=0,
             packed_height=8, width=0, data_segment=0x6000, stack_segment=0x6000,
             stack_offset=0x1000, map_base=0xff00, aliases_stack=True)
    add_case(out, 'map-read-after-seven-pushes', left=0x10, top=0,
             packed_height=8, width=8, data_segment=0x6000,
             stack_segment=0x6000, stack_offset=0x0032,
             map_base=0xbeef, push_overwrites_map=True)
    add_case(out, 'live-ret-low-byte-alias', left=0x10, top=0,
             packed_height=8, width=8, stack_offset=0x9000,
             map_base=0x8fff, stack_alias=True)
    add_case(out, 'live-saved-si-alias', left=0x10, top=0,
             packed_height=8, width=8, stack_offset=0x9000,
             map_base=0x8ffd, stack_alias=True)
    add_case(out, 'live-row-si-save-alias', left=0x10, top=0,
             packed_height=8, width=8, stack_offset=0x9000,
             map_base=0x8fed, stack_alias=True)
    add_case(out, 'stack-offset-zero', left=0x10, top=0, packed_height=8,
             width=8, stack_offset=0)
    add_case(out, 'stack-offset-one-wrap', left=0x10, top=0,
             packed_height=8, width=8, stack_offset=1)
    add_case(out, 'stack-offset-ffff', left=0x10, top=0,
             packed_height=8, width=8, stack_offset=0xffff)
    add_case(out, 'physical-20-bit-wrap', left=0x10, top=0,
             packed_height=8, width=0x20, data_segment=0xffff,
             stack_segment=0xffff, map_base=0x000f)
    add_case(out, 'cl-byte-wrap-mutant', left=0x10, top=0xff99,
             packed_height=0x00f8, width=8)
    add_case(out, 'wrong-segment-mutant', left=0x10, top=0,
             packed_height=8, width=9)

    # Every incoming CL value at each top low-three-bit residue. CH is also
    # varied; the routine clears it after byte-rounding CL.
    for top_fraction in range(8):
        for cl in range(256):
            ch = (cl * 29 + top_fraction * 17) & 255
            add_case(out, f'cl-{cl:02x}-top-{top_fraction}', left=0x10,
                     top=top_fraction, packed_height=(ch << 8) | cl,
                     width=8, simple_memory=True)
    return out


def prepare(case):
    seed = 0xd115 + case['seed']
    rng = random.Random(seed)
    load = LOADS[case['seed'] % len(LOADS)]
    mem = bytearray(MEMORY_SIZE)
    image = relocated(IMAGE, ORACLE['relocations'], load)
    code_start = load << 4
    mem[code_start:code_start + len(image)] = image
    ds = case.get('data_segment', (load + 0x09a9) & 0xffff)
    ss = case.get('stack_segment', 0x7000)
    sp = case.get('stack_offset', 0x9000)
    regs = {name: rng.randrange(65536) for name in REG_NAMES}
    regs.update(cs=load, ip=ENTRY, ds=ds, ss=ss, sp=sp,
        ax=case['left'], bx=case['top'], cx=case['packed_height'],
        dx=case['width'])
    put16(mem, ds, MAP_OFFSET, case.get('map_base', 0x2000))
    if case.get('push_overwrites_map'):
        # PUSH CX stores at SS:0026 immediately before the routine reads DS:0026.
        if physical(ds, MAP_OFFSET) != physical(ss, 0x26):
            raise AssertionError('push-overwrites-map fixture does not alias DS:26')
    put16(mem, ss, sp, case.get('return_word', 0xbabe))
    flags = 2 | (rng.randrange(1 << 12) & 0x0ed5)
    if rng.randrange(2):
        flags |= IF
    if rng.randrange(2):
        flags |= DF
    else:
        flags &= ~DF
    return mem, regs, flags, load


def library(mutation=0):
    path = build(BUILD / f'drawing-dirty-m{mutation}.dll', mutation,
                 'drawing_dirty')
    lib = ctypes.CDLL(str(path))
    lib.lmn_mark_drawing_dirty_cells_core.argtypes = [
        MEM, ctypes.POINTER(DrawingDirtyCall), ctypes.POINTER(RasterBus)]
    lib.lmn_mark_drawing_dirty_cells_core.restype = DrawingDirtyResult
    lib.lmn_mark_drawing_dirty_cells_adapter.argtypes = [
        MEM, ctypes.POINTER(Regs), ctypes.POINTER(RasterBus)]
    lib.lmn_mark_drawing_dirty_cells_adapter.restype = None
    return lib


def make_bus(c_mem):
    events = []
    errors = []

    @READ
    def read(_context, _memory, address, flags):
        try:
            address &= MEMORY_MASK
            value = c_mem[address]
            events.append(('read', address, value, flags & FLAGS_DEFINED))
            return value
        except Exception as error:
            errors.append(error)
            return 0

    @WRITE
    def write(_context, _memory, address, value, flags):
        try:
            address &= MEMORY_MASK
            value &= 255
            c_mem[address] = value
            events.append(('write', address, value, flags & FLAGS_DEFINED))
        except Exception as error:
            errors.append(error)

    @OUT
    def out(_context, port, value, flags):
        errors.append(AssertionError(
            f'unexpected port output {port:04x}={value:04x} flags={flags:04x}'))

    return RasterBus(None, read, write, out), events, errors


def make_call(regs, flags):
    return DrawingDirtyCall(regs['ds'], regs['ss'], regs['sp'], regs['ax'],
        regs['bx'], regs['cx'], regs['dx'], regs['si'], regs['di'], regs['bp'],
        flags)


def run_case(lib, case, collect_coverage=False):
    mem, regs, flags, load = prepare(case)
    c_mem = bytearray(mem)
    call = make_call(regs, flags)
    bus, c_events, c_errors = make_bus(c_mem)
    c_result = lib.lmn_mark_drawing_dirty_cells_core(
        (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(c_mem), ctypes.byref(call),
        ctypes.byref(bus))
    if c_errors:
        raise c_errors[0]

    uc = Uc(UC_ARCH_X86, UC_MODE_16)
    uc.mem_map(0, MAPPED_SIZE)
    uc.mem_write(0, bytes(mem))
    uc.mem_write(MEMORY_SIZE, bytes(mem))
    for name, reg in oracle.REG.items():
        uc.reg_write(reg, regs[name])
    uc.reg_write(x.UC_X86_REG_EFLAGS, flags)
    u_events = []
    sites = set()
    edges = set()
    previous = None
    stopped_at_ret = False

    def code(machine, pc, _size, _user):
        nonlocal previous, stopped_at_ret
        offset = (pc - (regs['cs'] << 4)) & 0xffff
        if previous in BRANCHES:
            edges.add((previous, offset))
        if uc.reg_read(oracle.REG['cs']) != regs['cs'] or offset not in INS:
            raise AssertionError(f"{case['name']}: original escaped at {offset:04x}")
        sites.add(offset)
        previous = offset
        if offset == RET:
            stopped_at_ret = True
            machine.emu_stop()

    def memory_read(machine, _access, address, size, _value, _user):
        for index in range(size):
            linear = address + index
            if linear >= MEMORY_SIZE:
                machine.mem_write(linear,
                    bytes(machine.mem_read(linear & MEMORY_MASK, 1)))
            event_address = linear & MEMORY_MASK
            value = machine.mem_read(linear, 1)[0]
            event_flags = machine.reg_read(x.UC_X86_REG_EFLAGS) & FLAGS_DEFINED
            u_events.append(('read', event_address, value, event_flags))

    def memory_write(machine, _access, address, size, value, _user):
        for index in range(size):
            linear = address + index
            byte = (value >> (8 * index)) & 255
            event_flags = machine.reg_read(x.UC_X86_REG_EFLAGS) & FLAGS_DEFINED
            u_events.append(('write', linear & MEMORY_MASK, byte, event_flags))
            mirror = linear - MEMORY_SIZE if linear >= MEMORY_SIZE else linear + MEMORY_SIZE
            machine.mem_write(mirror, bytes((byte,)))

    def interrupt(_machine, number, _user):
        raise AssertionError(f"{case['name']}: unexpected interrupt {number}")

    uc.hook_add(UC_HOOK_CODE, code)
    uc.hook_add(UC_HOOK_MEM_READ, memory_read)
    uc.hook_add(UC_HOOK_MEM_WRITE, memory_write)
    uc.hook_add(UC_HOOK_INTR, interrupt)
    uc.emu_start(physical(regs['cs'], ENTRY), 0, count=2_000_000)
    if not stopped_at_ret:
        raise AssertionError(f"{case['name']}: original exceeded bounded execution")

    original_regs = {name: uc.reg_read(reg) & 0xffff
                     for name, reg in oracle.REG.items()}
    original_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xffff
    original_mem = bytes(uc.mem_read(0, MEMORY_SIZE))
    if case['name'] == 'zero-width-overwrites-live-stack-and-ret':
        if get16(original_mem, regs['ss'], regs['sp']) != 0x0101:
            raise AssertionError('full SS overwrite did not replace active RET with 0101h')
        for name in ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp'):
            if original_regs[name] != 0x0101:
                raise AssertionError(f'full SS overwrite did not restore {name}=0101h')
    expected_fields = {
        'left': original_regs['ax'], 'top': original_regs['bx'],
        'packed_height': original_regs['cx'], 'width': original_regs['dx'],
        'source_cursor': original_regs['si'],
        'destination_cursor': original_regs['di'], 'control': original_regs['bp'],
        'stack_offset': original_regs['sp']}
    for name, expected in expected_fields.items():
        got = getattr(c_result, name)
        if got != expected:
            raise AssertionError(f"{case['name']}: core {name}={got:04x}, "
                                 f"original={expected:04x}")
    if (c_result.flags ^ original_flags) & (ARITH | IF | DF):
        raise AssertionError(f"{case['name']}: core flags {c_result.flags:04x}, "
                             f"original={original_flags:04x}")
    if bytes(c_mem) != original_mem:
        position = next(i for i, (a, b) in enumerate(zip(c_mem, original_mem))
                        if a != b)
        raise AssertionError(f"{case['name']}: whole RAM differs at {position:05x}")
    if len(c_events) != len(u_events):
        raise AssertionError(f"{case['name']}: ordered RAM access count differs "
                             f"({len(c_events)} C/{len(u_events)} original)")
    for index, (c_event, u_event) in enumerate(zip(c_events, u_events)):
        if c_event != u_event:
            raise AssertionError(f"{case['name']}: ordered RAM access {index} differs: "
                                 f"C={c_event}, original={u_event}")

    if collect_coverage:
        return sites, edges, dict(case=case, mem=mem, c_mem=c_mem, regs=regs,
            flags=flags, result=c_result, original_regs=original_regs,
            original_flags=original_flags, original_mem=original_mem,
            original_events=u_events)
    return None


def check_adapter(lib, saved):
    case = saved['case']
    c_mem = bytearray(saved['mem'])
    regs = saved['regs']
    c_regs = Regs(**regs, flags=saved['flags'])
    bus, events, errors = make_bus(c_mem)
    lib.lmn_mark_drawing_dirty_cells_adapter(
        (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(c_mem), ctypes.byref(c_regs),
        ctypes.byref(bus))
    if errors:
        raise errors[0]
    expected_ip = get16(saved['original_mem'], regs['ss'], regs['sp'])
    expected_regs = dict(saved['original_regs'])
    expected_regs['ip'] = expected_ip
    expected_regs['sp'] = (expected_regs['sp'] + 2) & 0xffff
    for name in REG_NAMES:
        got = getattr(c_regs, name)
        if got != expected_regs[name]:
            raise AssertionError(f"{case['name']}: adapter {name}={got:04x}, "
                                 f"expected={expected_regs[name]:04x}")
    if (c_regs.flags ^ saved['original_flags']) & (ARITH | IF | DF):
        raise AssertionError(f"{case['name']}: adapter flags differ at RET")
    if bytes(c_mem) != saved['original_mem']:
        raise AssertionError(f"{case['name']}: adapter whole RAM differs")
    expected_events = list(saved['original_events'])
    ret_address = physical(regs['ss'], regs['sp'])
    expected_events.extend((('read', ret_address, expected_ip & 255,
                              saved['original_flags'] & FLAGS_DEFINED),
                             ('read', (ret_address + 1) & MEMORY_MASK,
                              expected_ip >> 8,
                              saved['original_flags'] & FLAGS_DEFINED)))
    if events != expected_events:
        index = next((i for i, pair in enumerate(zip(events, expected_events))
                      if pair[0] != pair[1]), min(len(events), len(expected_events)))
        raise AssertionError(f"{case['name']}: adapter bus order differs at {index}")

    # The logical core's null-bus path uses the same wrapped 20-bit RAM.
    direct_mem = bytearray(saved['mem'])
    call = make_call(regs, saved['flags'])
    direct_result = lib.lmn_mark_drawing_dirty_cells_core(
        (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(direct_mem),
        ctypes.byref(call), None)
    if bytes(direct_mem) != saved['original_mem']:
        raise AssertionError(f"{case['name']}: null-bus core whole RAM differs")
    for name in ('left', 'top', 'packed_height', 'width', 'source_cursor',
                 'destination_cursor', 'control', 'stack_offset', 'flags'):
        if getattr(direct_result, name) != getattr(saved['result'], name):
            raise AssertionError(f"{case['name']}: null-bus core {name} differs")


def main():
    report = BUILD / 'drawing-dirty-differential.json'
    report.unlink(missing_ok=True)
    baseline = cases()
    if ENTRY != 0x9a15 or ROUTINE['size'] != 122:
        raise AssertionError('Unexpected symbol-ledger extent for MarkDrawingDirtyCells')
    if len(INS) != 63 or sum(ins.size for ins in INS.values()) != 122:
        raise AssertionError(f'Unexpected decoded extent: {len(INS)} sites, '
                             f'{sum(ins.size for ins in INS.values())} bytes')

    lib = library()
    sites, edges = set(), set()
    adapter_samples = {}
    by_name = {case['name']: case for case in baseline}
    for case in baseline:
        case_sites, case_edges, saved = run_case(lib, case, True)
        sites |= case_sites
        edges |= case_edges
        if case['name'] in ('one-byte-normal-row', 'live-ret-low-byte-alias',
                            'zero-width-overwrites-live-stack-and-ret'):
            adapter_samples[case['name']] = saved
    if sites != set(INS):
        raise AssertionError(f'Missing instruction sites: {sorted(set(INS)-sites)}')
    if edges != EDGES:
        raise AssertionError(f'Missing branch edges: {sorted(EDGES-edges)}')
    for saved in adapter_samples.values():
        check_adapter(lib, saved)

    mutation_inputs = (
        (1, 'cl-byte-wrap-mutant'),
        (2, 'wrong-segment-mutant'),
        (3, 'zero-width-overwrites-live-stack-and-ret'))
    mutations = []
    for mutation, name in mutation_inputs:
        try:
            run_case(library(mutation), by_name[name])
        except AssertionError:
            mutations.append(dict(mutation=mutation, case=name))
        else:
            raise AssertionError(f'Compiled drawing-dirty mutation {mutation} survived on {name}')

    paths = ('c/drawing_dirty.c', 'c/drawing_dirty.h', 'docs/drawing-dirty.md', 'c/regs.h',
             'c/lemmings_sym.h', 'c/special_blit.h', 'tests/drawing_dirty.py',
             'tests/dat_io.py', 'tools/common.py', 'tools/cbuild.py',
             'tools/unpack.py', 'metadata/symbols.json', 'metadata/inputs.json',
             'assets/vgalemmi.exe')
    public_cases = [dict(name=case['name'], map_base=case.get('map_base', 0x2000),
        segments_alias=case.get('data_segment',
            (LOADS[case['seed'] % len(LOADS)] + 0x09a9) & 0xffff) ==
            case.get('stack_segment', 0x7000),
        physical_wrap=case.get('data_segment') == 0xffff or
                      case.get('stack_segment') == 0xffff)
        for case in baseline]
    write_json(report, dict(image='main', image_sha256=sha(IMAGE),
        case_count=len(baseline), cases=public_cases,
        mutation_count=len(mutations), mutations_detected=mutations,
        translated_code_bytes=sum(ins.size for ins in INS.values()),
        instruction_addresses=sorted(INS), instruction_sites=sorted(sites),
        branch_instruction_addresses=sorted(BRANCHES), branch_edges=sorted(edges),
        routine=dict(name=ROUTINE['symbol_name'], start=ENTRY, end=END,
                     byte_count=END-ENTRY, bytes=IMAGE[ENTRY:END].hex(),
                     byte_sha256=sha(IMAGE[ENTRY:END])),
        input_hashes={path: sha((ROOT / path).read_bytes()) for path in paths},
        fixture_domains=dict(cl_values=256, top_residues=8,
            zero_width_65536_stores=True, zero_height_bounded_by_map=True,
            read_ds_map_after_pushes=True, ds_ss_alias=True,
            live_stack_and_ret_alias=True, sp_values=[0, 1, 0xffff],
            physical_20_bit_wrap=True, bus_callbacks=True,
            null_bus_core=True, adapter_ret=True),
        flag_notes='Final flags come from CMP SI,BP on every bounded path; all '
                   'arithmetic flags are defined there. AF is excluded only from '
                   'per-access comparisons across undefined intermediates.',
        domain='Original bounded CS:9A15..9A8E and C11 core; DS:0026 map selection '
               'after seven live SS pushes, 40-byte row stride, byte-wrapped CL '
               'rounding, unsigned base+0321h bound, 16-bit zero-count loops, '
               'live SS save/RET aliases, physical 20-bit RAM and ordered byte access.'))
    print(f'PASS drawing dirty cells C: {len(baseline)} cases, {len(sites)} '
          f'instruction sites, {len(edges)} branch edges; 3 compiled mutations detected')


if __name__ == '__main__':
    main()

"""Bounded original/native checks for ClipPlanarDrawingRectangle."""
import ctypes
import os
import random
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
import capstone
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
from unicorn import x86_const as x
import dat_io as oracle
from common import ROOT, BUILD, read_json, sha, write_json
from cbuild import build
from unpack import ASSET, unpack, relocated

MEMORY_SIZE = 1 << 20
MAPPED_SIZE = 2 * MEMORY_SIZE
MEM = ctypes.POINTER(ctypes.c_uint8)
CF, PF, AF, ZF, SF, TF, IF, DF, OF = 1, 4, 0x10, 0x40, 0x80, 0x100, 0x200, 0x400, 0x800
ARITH_FLAGS = CF | PF | AF | ZF | SF | OF
LOGIC_FLAGS = CF | PF | ZF | SF | OF
CONTROL_FLAGS = TF | IF | DF
ALL_TEST_FLAGS = ARITH_FLAGS | CONTROL_FLAGS
INITIAL_DEFINED = ALL_TEST_FLAGS
IMAGE, ORACLE = unpack(ASSET.read_bytes())
SYMS = {row['symbol_name']: row for row in read_json(ROOT / 'metadata/symbols.json')}
ROUTINE = SYMS['ClipPlanarDrawingRectangle']
ENTRY = ROUTINE['address']
END = 0x9A15
RET_SITES = {0x99E7, 0x9A0B, 0x9A14}
NOP_SITE = 0x9996
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
NORMAL_INS = set(INS) - {NOP_SITE}
BRANCHES = {pc for pc, ins in INS.items()
            if ins.group(capstone.CS_GRP_JUMP)}
FIELDS = {
    'DrawingHeight': SYMS['DrawingHeight']['address'],
    'DrawingWidthPixels': SYMS['DrawingWidthPixels']['address'],
    'DrawingSourcePitchBytes': SYMS['DrawingSourcePitchBytes']['address'],
    'DrawingHorizontalSkipBytes': SYMS['DrawingHorizontalSkipBytes']['address'],
    'DrawingVerticalSkipBytes': SYMS['DrawingVerticalSkipBytes']['address'],
    'DrawingSavedHeightHighByte': SYMS['DrawingSavedHeightHighByte']['address'],
}
LOADS = (0x1010, 0x1213, 0x2345)


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
    return ((segment << 4) + offset) & 0xfffff


def put_word_at(memory, address, value):
    address &= 0xfffff
    memory[address] = value & 255
    memory[(address + 1) & 0xfffff] = (value >> 8) & 255


def put_word(memory, segment, offset, value):
    put_word_at(memory, physical(segment, offset), value)


def get_word_at(memory, address):
    address &= 0xfffff
    return memory[address] | (memory[(address + 1) & 0xfffff] << 8)


def add_case(out, name, left, top, height, width, control, **kwargs):
    out.append(dict(name=name, left=left & 0xffff, top=top & 0xffff,
                    height=height & 0xffff, width=width & 0xffff,
                    control=control & 0xffff, seed=len(out), **kwargs))


def cases():
    out = []
    # Each control shape gets an unmodified pass and a clipping/rejection path.
    add_case(out, 'control-0-zero-size-fast-pass', 3, 40, 0, 0, 0,
             screen_width=32, screen_height=24)
    add_case(out, 'horizontal-negative-two-steps', -16, 2, 5, 40, 4,
             screen_width=64, screen_height=24)
    add_case(out, 'horizontal-negative-signed-overflow-reject', -32768, 2,
             5, 32767, 4, screen_width=64, screen_height=24)
    add_case(out, 'horizontal-positive-two-steps', 8, 2, 5, 40, 4,
             screen_width=32, screen_height=24)
    add_case(out, 'horizontal-start-at-right-edge-reject', 32, 2, 5, 8, 4,
             screen_width=32, screen_height=24)
    add_case(out, 'horizontal-add-overflow-signed-jns', 0x7fff, 2, 5, 1, 4,
             screen_width=0x8000, screen_height=24)

    add_case(out, 'vertical-negative-accepted-mul', 2, -3, 8, 12, 8,
             screen_width=32, screen_height=24, pitch=80)
    add_case(out, 'vertical-negative-height-overflow-reject', 2, -8, 5, 12,
             8, screen_width=32, screen_height=24, pitch=80)
    add_case(out, 'vertical-negative-8000-signed-reject', 2, -32768, 255,
             12, 8, screen_width=32, screen_height=24, pitch=0xffff)
    add_case(out, 'vertical-top-at-height-reject', 2, 24, 4, 12, 8,
             screen_width=32, screen_height=24)
    add_case(out, 'vertical-bottom-clipped', 2, 20, 8, 12, 8,
             screen_width=32, screen_height=24)
    add_case(out, 'vertical-bottom-no-clip', 2, 4, 8, 12, 8,
             screen_width=32, screen_height=24)
    add_case(out, 'vertical-zero-width-reject-at-check', 2, 4, 8, 0, 8,
             screen_width=32, screen_height=24)
    add_case(out, 'vertical-zero-height-reject-at-check', 2, 4, 0, 12, 8,
             screen_width=32, screen_height=24)
    add_case(out, 'vertical-zero-height-kept-on-negative-top', 2, -1, 1,
             12, 8, screen_width=32, screen_height=24)
    add_case(out, 'both-controls-negative-top', -4, -2, 9, 20, 12,
             screen_width=32, screen_height=24, pitch=0x1234)
    add_case(out, 'both-controls-positive-clipped', 28, 20, 8, 20, 12,
             screen_width=32, screen_height=24, pitch=0x2345)

    # Live SS aliases: the stack save, mid-stage control reload, MUL saves,
    # saved CH byte, and the near return all observe the same physical RAM.
    add_case(out, 'ss-ds-horizontal-save-changes-control', 8, 4, 8, 40, 7,
             ds=0x6000, ss=0x6000, sp=0x66fe, screen_width=32,
             screen_height=24, horizontal_skip=7, pitch=80)
    add_case(out, 'saved-ch-byte-overwrites-saved-bp', 8, 4, 8, 24, 4,
             packed_high=8, ds=0x6000, ss=0x6000, sp=0xa94b,
             screen_width=32, screen_height=24)
    add_case(out, 'saved-ch-byte-overwrites-near-ret', 1, 2, 3, 4, 0,
             packed_high=0x80, ds=0x6000, ss=0x6000, sp=0xa949,
             screen_width=32, screen_height=24, return_word=0x5500)
    add_case(out, 'horizontal-skip-changes-near-ret', 8, 2, 5, 40, 4,
             ds=0x6000, ss=0x6000, sp=0x66fc, screen_width=32,
             screen_height=24, horizontal_skip=0x0060, return_word=0x0060)
    add_case(out, 'mul-pitch-read-before-push-and-return-alias', 0x3456, -3,
             8, 12, 8, ds=0x6000, ss=0x6000, sp=0x66fe,
             screen_width=32, screen_height=24, pitch=0x3456,
             return_word=0x7777)
    add_case(out, 'near-ret-offset-ffff-contiguous-word', 2, 4, 8, 12, 0,
             ss=0x7000, sp=0xffff, screen_width=32, screen_height=24,
             return_word=0x8899)
    add_case(out, 'near-ret-physical-20bit-wrap', 2, -3, 8, 12, 8,
             ss=0xffff, sp=0xffff, screen_width=32, screen_height=24,
             pitch=0x1001, return_word=0x9abc)
    add_case(out, 'ds-ss-physical-20bit-wrap', 2, -2, 8, 12, 12,
             ds=0xffff, ss=0xffff, sp=0x66fe, screen_width=32,
             screen_height=24, pitch=0x4321)

    # Signed comparison boundaries make JL/JGE differ from SF-only JNS/JS.
    add_case(out, 'negative-dx-wraps-positive-after-subtract', 4, 2, 5,
             0x8001, 4, screen_width=32, screen_height=24)
    add_case(out, 'negative-height-signed-boundary', 2, 0x7fff, 2, 12, 8,
             screen_width=32, screen_height=0x8000)
    add_case(out, 'positive-top-overflow-in-bottom-add', 2, 0x7fff, 8,
             12, 8, screen_width=32, screen_height=0x8000)

    # Deterministic bounded rectangles broaden register, flags, segment and
    # packed-CH coverage while keeping every clip loop finite.
    rng = random.Random(0x9967)
    for n in range(28):
        screen_width = rng.choice((24, 32, 40, 64, 0x8000))
        screen_height = rng.choice((16, 24, 32, 48, 0x8000))
        left = rng.randint(-24, 72)
        top = rng.randint(-12, 56)
        width = rng.randint(0, 48)
        height = rng.randint(0, 16)
        control = rng.choice((0, 4, 8, 12))
        add_case(out, f'random-{n:02d}', left, top, height, width, control,
                 screen_width=screen_width, screen_height=screen_height,
                 packed_high=rng.choice((0, 1, 0x7f, 0x80, 0xff)),
                 pitch=rng.randrange(65536), flags_seed=rng.randrange(1 << 16))

    # The three source mutations each have a direct witness in this set.
    add_case(out, 'mutation-horizontal-signed-ge', 0, 2, 5, 1, 4,
             screen_width=0xfff8, screen_height=24)
    add_case(out, 'mutation-vertical-signed-ge', 0, 0, 4, 8, 8,
             screen_width=32, screen_height=0x8000)
    add_case(out, 'mutation-eight-pixel-horizontal-step', 4, 2, 5, 30, 4,
             screen_width=20, screen_height=24)
    return out


CASES = cases()


def prepare(case):
    rng = random.Random(0x9967 + case['seed'])
    load = LOADS[case['seed'] % len(LOADS)]
    memory = bytearray(rng.randbytes(MEMORY_SIZE))
    image = relocated(IMAGE, ORACLE['relocations'], load)
    start = load << 4
    memory[start:start + len(image)] = image
    regs = {name: rng.randrange(65536) for name in oracle.REG_NAMES}
    regs.update(cs=load, ip=ENTRY,
                ds=case.get('ds', (load + 0x09a9) & 0xffff),
                ss=case.get('ss', 0x7000), sp=case.get('sp', 0x8000),
                ax=case['left'], bx=case['top'],
                cx=((case.get('packed_high', rng.randrange(256)) & 255) << 8) |
                   (case['height'] & 255),
                dx=case['width'], bp=case['control'],
                si=rng.randrange(65536), di=rng.randrange(65536))
    flags = 2 | (case.get('flags_seed', rng.randrange(1 << 16)) &
                 (CF | PF | AF | ZF | SF | IF | DF | OF))

    put_word(memory, regs['ds'], FIELDS['DrawingWidthPixels'],
             case['screen_width'])
    put_word(memory, regs['ds'], FIELDS['DrawingHeight'],
             case['screen_height'])
    put_word(memory, regs['ds'], FIELDS['DrawingSourcePitchBytes'],
             case.get('pitch', rng.randrange(65536)))
    put_word(memory, regs['ds'], FIELDS['DrawingHorizontalSkipBytes'],
             case.get('horizontal_skip', rng.randrange(65536)))
    put_word(memory, regs['ds'], FIELDS['DrawingVerticalSkipBytes'],
             rng.randrange(65536))
    put_word(memory, regs['ss'], regs['sp'],
             case.get('return_word', 0xff00))
    return memory, regs, flags, load


def library(mutation=0):
    path = build(BUILD / f'drawing-clip-m{mutation}-pid{os.getpid()}.dll',
                 mutation, 'drawing_clip')
    lib = ctypes.CDLL(str(path))
    lib.lmn_clip_planar_drawing_rectangle_adapter.argtypes = [
        MEM, ctypes.POINTER(Regs), ctypes.POINTER(Bus)]
    lib.lmn_clip_planar_drawing_rectangle_adapter.restype = None
    return lib


def make_bus(memory):
    events = []
    errors = []

    @READ
    def read(_context, _memory, address, flags):
        try:
            address &= 0xfffff
            value = memory[address]
            events.append(('read', address, value, flags))
            return value
        except Exception as error:
            errors.append(error)
            return 0

    @WRITE
    def write(_context, _memory, address, value, flags):
        try:
            address &= 0xfffff
            memory[address] = value
            events.append(('write', address, value, flags))
        except Exception as error:
            errors.append(error)

    bus = Bus(None, read, write, OUT())
    return bus, events, errors, (read, write)


def setter_mask(ins):
    if ins.mnemonic in ('add', 'sub', 'neg', 'cmp'):
        return ARITH_FLAGS
    if ins.mnemonic in ('and', 'test', 'xor'):
        return LOGIC_FLAGS
    if ins.mnemonic == 'mul':
        return CF | OF
    return 0


def static_branch_edges():
    """Enumerate each direct branch target and conditional fallthrough."""
    edges = set()
    for pc in BRANCHES:
        ins = INS[pc]
        target = int(ins.operands[0].imm) & 0xffff
        if target in INS:
            edges.add((pc, target))
        if ins.mnemonic != 'jmp':
            fallthrough = (pc + ins.size) & 0xffff
            if fallthrough in INS:
                edges.add((pc, fallthrough))
    return edges


EXPECTED_EDGES = static_branch_edges()


def event_mask(ins, kind, current_mask):
    # Unicorn reports the live flags on the bus before the current instruction
    # commits its arithmetic result, including an ADD memory write.
    return current_mask


def run_original(case, memory, regs, flags, load):
    machine = Uc(UC_ARCH_X86, UC_MODE_16)
    machine.mem_map(0, MAPPED_SIZE)
    machine.mem_write(0, bytes(memory))
    machine.mem_write(MEMORY_SIZE, bytes(memory))
    for name, register in oracle.REG.items():
        machine.reg_write(register, regs[name])
    machine.reg_write(x.UC_X86_REG_EFLAGS, flags)
    shadow = bytearray(memory)
    sites = set()
    edges = set()
    events = []
    previous = None
    current_pc = None
    defined_mask = INITIAL_DEFINED
    instruction_flags = {}
    done = False
    count = 0

    def code(uc, pc, _size, _user):
        nonlocal previous, current_pc, defined_mask, done, count
        offset = (pc - (regs['cs'] << 4)) & 0xffff
        if previous in RET_SITES:
            done = True
            uc.emu_stop()
            return
        if uc.reg_read(oracle.REG['cs']) != regs['cs'] or offset not in INS:
            raise AssertionError(f"{case['name']}: original escaped to {offset:04x}")
        if previous in BRANCHES:
            edges.add((previous, offset))
        if previous is not None:
            defined_mask |= setter_mask(INS[previous])
            if INS[previous].mnemonic in ('test', 'and', 'xor'):
                defined_mask = (defined_mask & ~ARITH_FLAGS) | \
                               (CONTROL_FLAGS | LOGIC_FLAGS)
            elif INS[previous].mnemonic == 'mul':
                defined_mask = (defined_mask & ~ARITH_FLAGS) | \
                               (CONTROL_FLAGS | CF | OF)
            elif INS[previous].mnemonic in ('add', 'sub', 'neg', 'cmp'):
                defined_mask = CONTROL_FLAGS | ARITH_FLAGS
        if offset == NOP_SITE:
            raise AssertionError('Unreachable 9996 NOP executed from normal entry')
        sites.add(offset)
        current_pc = offset
        instruction_flags[offset] = uc.reg_read(x.UC_X86_REG_EFLAGS)
        previous = offset
        count += 1
        if count > 100000:
            raise AssertionError(f"{case['name']}: routine exceeded instruction budget")

    def mem_read(uc, _access, address, size, _value, _user):
        ins = INS[current_pc]
        ef = instruction_flags[current_pc]
        for index in range(size):
            linear = address + index
            physical_address = linear & 0xfffff
            value = shadow[physical_address]
            events.append(('read', physical_address, value, ef,
                           event_mask(ins, 'read', defined_mask), current_pc))
            uc.mem_write(linear, bytes((value,)))

    def mem_write(uc, _access, address, size, value, _user):
        ins = INS[current_pc]
        ef = instruction_flags[current_pc]
        mask = event_mask(ins, 'write', defined_mask)
        for index in range(size):
            linear = address + index
            physical_address = linear & 0xfffff
            byte_value = (value >> (8 * index)) & 255
            events.append(('write', physical_address, byte_value, ef, mask,
                           current_pc))
            shadow[physical_address] = byte_value
            uc.mem_write(linear, bytes((byte_value,)))
            if linear != physical_address:
                uc.mem_write(physical_address, bytes((byte_value,)))

    machine.hook_add(UC_HOOK_CODE, code)
    machine.hook_add(UC_HOOK_MEM_READ, mem_read)
    machine.hook_add(UC_HOOK_MEM_WRITE, mem_write)
    machine.emu_start(physical(regs['cs'], ENTRY), 0, count=100000)
    if not done:
        raise AssertionError(f"{case['name']}: near RET did not finish")
    actual_regs = {name: machine.reg_read(register)
                   for name, register in oracle.REG.items()}
    actual_flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    return actual_regs, actual_flags, shadow, sites, edges, events, defined_mask


def mismatch(case, actual, expected, label):
    for index, (got, want) in enumerate(zip(actual, expected)):
        if got != want:
            raise AssertionError(f"{case['name']}: {label} event {index}: "
                                 f"C {got}, original {want}")
    if len(actual) != len(expected):
        raise AssertionError(f"{case['name']}: {label} count {len(actual)}, "
                             f"original {len(expected)}")


def compare(lib, case, collect=False):
    memory, regs, flags, load = prepare(case)
    c_memory = bytearray(memory)
    c_regs = Regs(**regs, flags=flags)
    bus, c_events, errors, callbacks = make_bus(c_memory)
    lib.lmn_clip_planar_drawing_rectangle_adapter(
        (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(c_memory),
        ctypes.byref(c_regs), ctypes.byref(bus))
    if errors:
        raise errors[0]

    # The fallback is a second independent RAM path through the same adapter.
    plain_memory = bytearray(memory)
    plain_regs = Regs(**regs, flags=flags)
    lib.lmn_clip_planar_drawing_rectangle_adapter(
        (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(plain_memory),
        ctypes.byref(plain_regs), None)
    if plain_memory != c_memory:
        address = next(i for i, (a, b) in enumerate(zip(plain_memory, c_memory))
                       if a != b)
        raise AssertionError(f"{case['name']}: null-bus RAM differs at {address:05x}")
    for name in oracle.REG_NAMES:
        if getattr(plain_regs, name) != getattr(c_regs, name):
            raise AssertionError(f"{case['name']}: null-bus {name} differs")
    if (plain_regs.flags ^ c_regs.flags) & ALL_TEST_FLAGS:
        raise AssertionError(f"{case['name']}: null-bus flags differ")

    original, original_flags, original_memory, sites, edges, original_events, \
        final_defined = run_original(case, memory, regs, flags, load)
    for name in oracle.REG_NAMES:
        got = getattr(c_regs, name)
        want = original[name]
        if got != want:
            raise AssertionError(f"{case['name']}: C {name}={got:04x}, "
                                 f"original={want:04x}")
    if (c_regs.flags ^ original_flags) & final_defined:
        raise AssertionError(f"{case['name']}: C defined flags "
                             f"{c_regs.flags:04x}, original {original_flags:04x}, "
                             f"mask {final_defined:04x}")
    if c_memory != original_memory:
        address = next(i for i, (a, b) in enumerate(zip(c_memory, original_memory))
                       if a != b)
        raise AssertionError(f"{case['name']}: whole RAM differs at {address:05x}")

    c_simple = [(kind, address, value) for kind, address, value, _flags in c_events]
    original_simple = [(kind, address, value)
                       for kind, address, value, _flags, _mask, _pc in original_events]
    mismatch(case, c_simple, original_simple, 'ordered byte access')
    for index, (actual, expected) in enumerate(zip(c_events, original_events)):
        c_flags = actual[3]
        original_flags_at_access = expected[3]
        mask = expected[4]
        if (c_flags ^ original_flags_at_access) & mask:
            raise AssertionError(
                f"{case['name']}: bus flags event {index} at {expected[5]:04x} "
                f"mask {mask:04x}: C {c_flags:04x}, original "
                f"{original_flags_at_access:04x}")
    if len(c_events) != len(original_events):
        raise AssertionError(f"{case['name']}: access count differs")
    if collect:
        return sites, edges
    return None


def main():
    report_path = BUILD / 'drawing-clip-differential.json'
    report_path.unlink(missing_ok=True)
    native = library(0)
    all_sites = set()
    all_edges = set()
    for case in CASES:
        sites, edges = compare(native, case, collect=True)
        all_sites.update(sites)
        all_edges.update(edges)

    missing = NORMAL_INS - all_sites
    extra_sites = all_sites - NORMAL_INS
    if missing or extra_sites or len(NORMAL_INS) != 73:
        raise AssertionError('Normal-entry site coverage differs: missing=' +
            ', '.join(f'{pc:04x}' for pc in sorted(missing)) + '; extra=' +
            ', '.join(f'{pc:04x}' for pc in sorted(extra_sites)) +
            f'; expected 73 sites, decoded {len(NORMAL_INS)}')
    if NOP_SITE in all_sites:
        raise AssertionError('9996 NOP unexpectedly executed')
    if len(EXPECTED_EDGES) != 29 or all_edges != EXPECTED_EDGES:
        raise AssertionError(f'Branch-edge coverage differs: missing='
            f'{sorted(EXPECTED_EDGES-all_edges)}, extra='
            f'{sorted(all_edges-EXPECTED_EDGES)}, expected {len(EXPECTED_EDGES)}')

    mutant_count = 0
    witnesses = {
        1: 'mutation-horizontal-signed-ge',
        2: 'mutation-vertical-signed-ge',
        3: 'mutation-eight-pixel-horizontal-step',
    }
    for mutation, name in witnesses.items():
        mutant = library(mutation)
        case = next(case for case in CASES if case['name'] == name)
        try:
            compare(mutant, case)
        except AssertionError:
            mutant_count += 1
        else:
            raise AssertionError(f'CLIP_MUTATION={mutation} survived {name}')

    if mutant_count != 3:
        raise AssertionError(f'Only {mutant_count} of three mutants were detected')
    paths = (
        'c/drawing_clip.c', 'c/drawing_clip.h', 'c/regs.h',
        'c/special_blit.h', 'c/lemmings_sym.h', 'tests/drawing_clip.py',
        'tests/dat_io.py', 'tools/common.py', 'tools/cbuild.py',
        'tools/difftest.py', 'tools/coverage.py', 'tools/unpack.py',
        'metadata/symbols.json', 'assets/vgalemmi.exe',
        'docs/drawing-clip.md',
    )
    routine_bytes = IMAGE[ENTRY:END]
    mutations = [
        dict(mutation=1, case='mutation-horizontal-signed-ge'),
        dict(mutation=2, case='mutation-vertical-signed-ge'),
        dict(mutation=3, case='mutation-eight-pixel-horizontal-step'),
    ]
    write_json(report_path, dict(
        image='main', image_sha256=sha(IMAGE), case_count=len(CASES),
        cases=[case['name'] for case in CASES],
        mutation_count=mutant_count, mutations_detected=mutations,
        instruction_addresses=sorted(INS), instruction_sites=sorted(all_sites),
        executed_instruction_addresses=sorted(all_sites),
        branch_instruction_addresses=sorted(BRANCHES),
        branch_edges=sorted(all_edges), translated_code_bytes=173,
        routine=dict(name=ROUTINE['symbol_name'], start=ENTRY, end=END,
                     byte_count=len(routine_bytes), bytes=routine_bytes.hex(),
                     byte_sha256=sha(routine_bytes)),
        native_code_ranges=[[ENTRY, NOP_SITE], [NOP_SITE + 1, END]],
        unexecuted_nop_9996=True,
        fixture_domains=dict(controls=[0, 4, 8, 12], screen_width_cases=[20, 24,
                32, 40, 64, 0x8000, 0xfff8], screen_height_cases=[16, 24, 32,
                48, 0x8000], deterministic_random_cases=28,
            loads=[f'{load:04x}' for load in LOADS], flags_mask=ALL_TEST_FLAGS,
            physical_ram_bytes=MEMORY_SIZE, physical_20_bit_wrap=True,
            segment_offset_wrap=True, word_bytes_physically_contiguous=True,
            ds_ss_alias=True, live_ds_fields=True, live_stack_and_return_aliases=True,
            stack_offset_values=[0xa949, 0xa94b, 0x66fc, 0x66fe, 0xffff],
            raster_bus_callback_ram=True, null_bus_ram=True,
            adapter_near_return=True),
        quirks=[
            'Signed JL/JGE boundaries coexist with sign-only JNS/JS tests.',
            'All clipping arithmetic wraps at 16 bits; horizontal clipping advances one byte per 8 pixels.',
            'CH is saved and restored through live DS:A949, and BP is reloaded through live SS between stages.',
            'DS fields are read at each original access; DS and SS aliases can change later control flow.',
            'Vertical MUL adds only the low product word; MUL defines CF/OF while temporary AX/DX saves use live SS.',
            'Only the nonnegative vertical path performs the zero-width/zero-height rejection checks.',
            'The body leaves the near-return word for the adapter; physical word bytes are contiguous across offset FFFF.',
        ],
        domain='Bounded CS:9967..9A14 routine execution with constructed RAM, '
               'all-register/defined-flag, full-memory and ordered byte-access '
               'differential checks; this does not establish VGA behavior or '
               'reachability outside the identified leaf.',
        input_hashes={path: sha((ROOT / path).read_bytes()) for path in paths},
    ))
    print(f'PASS drawing clip C: {len(CASES)} cases, {len(all_sites)} instruction '
          f'sites, {len(all_edges)} branch edges; {mutant_count} compiled mutations detected')


if __name__ == '__main__':
    main()

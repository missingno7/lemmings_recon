"""Original-only contract checks for level initializer prefix 36B9..3741.

The independent field model below reads and writes one canonical RAM/VGA image.
It does not call reconstructed C and it does not model later level setup.
"""
import ast
import gc
import hashlib
import random
import struct
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import terrain_drawing as piece
from aligned_masked import TraceDevice
from bounded_process import run_bounded
from common import ROOT, BUILD, read_json, sha, write_json
from drawing_caller_oracle import original
from minimap_vga import VGA_BASE, VGA_END
from resources import decode_section, section_spans
from unpack import ASSET, relocated


START = 0x36B9
END = 0x3742
HEADER_OFF = 0x0FCB
HEADER_SIZE = 0x20
PREFIX_BYTES = END - START
DECODED = tuple(piece.MD.disasm(piece.IMAGE[START:END], START))
INS = {instruction.address: instruction for instruction in DECODED}
ARITH_MASK = 0x08D5
SHIFT_MASK = 0x08C5
FULL_FLAGS = 0x0FD7
SHIFT_FLAGS = 0x0FC7
EVENT_LIMIT = 512
VGA_EVENT_LIMIT = 512

BYTE_FIELDS = (
    (0x00, (0x0064, 0x0067)),
    (0x02, (0x0047,)),
    (0x04, (0x0044,)),
    (0x06, (0x20A7,)),
    (0x08, (0x006A,)),
    (0x0A, (0x006D,)),
    (0x0C, (0x0070,)),
    (0x0E, (0x0073,)),
    (0x10, (0x0076,)),
    (0x12, (0x0079,)),
    (0x14, (0x007C,)),
    (0x16, (0x007F,)),
)
OUTPUT_OFFSETS = tuple(sorted({offset for _, outputs in BYTE_FIELDS
                               for offset in outputs} | {0x0000, 0x0002}))
INPUTS = tuple(sorted({
    'tests/level_header_contract.py',
    'tests/drawing_caller_oracle.py', 'tests/terrain_drawing.py',
    'tests/drawing_render.py', 'tests/drawing_bitmap.py',
    'tests/drawing_aligned_render.py', 'tests/drawing_masked_render.py',
    'tests/drawing_shifted_render.py', 'tests/aligned_masked.py',
    'tests/aligned_read_mask.py', 'tests/dat_io.py', 'tests/dat_io_c.py',
    'tests/special_blit.py', 'tests/resource_rle.py',
    'tests/minimap_vga.py', 'tools/bounded_process.py', 'tools/cbuild.py',
    'tools/common.py',
    'tools/resources.py', 'tools/unpack.py', 'metadata/symbols.json',
    'src/game_code.asm', 'src/level_initialize.asm', 'src/program.asm',
    'docs/level-initialize-frontier.md',
    'docs/level-header-ownership.md', 'docs/level-header-contract.md',
    'assets/vgalemmi.exe',
    *(f'assets/level{group:03d}.dat' for group in range(10)),
    *(f'assets/{path.name}'
      for path in sorted((ROOT / 'assets').glob('ground*o.dat'))),
}))


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def dependency_paths():
    """Include the local Python import closure, even for indirect fixture imports."""
    paths = set(INPUTS)
    pending = [ROOT / path for path in paths if path.endswith('.py')]
    while pending:
        path = pending.pop()
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                     else [node.module] if isinstance(node, ast.ImportFrom) else [])
            for name in names:
                if not name:
                    continue
                for directory in ('tests', 'tools'):
                    candidate = ROOT / directory / (name.split('.')[0] + '.py')
                    if candidate.is_file():
                        relative = candidate.relative_to(ROOT).as_posix()
                        if relative not in paths:
                            paths.add(relative)
                            pending.append(candidate)
    return sorted(paths)


def physical(segment, offset):
    return ((segment << 4) + (offset & 0xFFFF)) & 0xFFFFF


def initial_flags(seed, *, df, iff):
    flags = 0x0002 | ((seed * 0x135 + 0x055) & ARITH_MASK)
    flags |= 0x0400 if df else 0
    flags |= 0x0200 if iff else 0
    return flags & 0xFFFF


def add16_flags(flags, left, right):
    total = left + right
    value = total & 0xFFFF
    status = 0
    if total > 0xFFFF:
        status |= 0x0001
    if (value & 0xFF).bit_count() % 2 == 0:
        status |= 0x0004
    if (left ^ right ^ value) & 0x0010:
        status |= 0x0010
    if value == 0:
        status |= 0x0040
    if value & 0x8000:
        status |= 0x0080
    if (~(left ^ right) & (left ^ value) & 0x8000) != 0:
        status |= 0x0800
    return ((flags & ~ARITH_MASK) | status) & 0xFFFF, value


def shr1_flags(flags, value):
    result = (value >> 1) & 0xFFFF
    status = value & 1
    if (result & 0xFF).bit_count() % 2 == 0:
        status |= 0x0004
    if result == 0:
        status |= 0x0040
    if result & 0x8000:
        status |= 0x0080
    # For a one-bit SHR, OF is the pre-shift sign bit. AF is undefined and
    # deliberately left out of SHIFT_MASK comparisons.
    if value & 0x8000:
        status |= 0x0800
    return ((flags & ~SHIFT_MASK) | status) & 0xFFFF, result


def pinned_headers():
    result = []
    for group in range(10):
        path = ROOT / 'assets' / f'level{group:03d}.dat'
        packed = path.read_bytes()
        spans = section_spans(packed)
        require(len(spans) == 8,
                f'{path.name}: expected eight pinned LEVEL sections, got {len(spans)}')
        for section, (start, end) in enumerate(spans):
            image, _meta = decode_section(packed[start:end])
            require(len(image) >= HEADER_SIZE,
                    f'{path.name} section {section}: short level header')
            result.append(dict(
                name=f'level-{group:03d}-{section:02d}', seed=len(result),
                header=image[:HEADER_SIZE], source=f'assets/level{group:03d}.dat',
                section=section))
    require(len(result) == 80, f'expected 80 pinned level headers, got {len(result)}')
    return result


def synthetic_cases():
    words = (0xA17F, 0xB283, 0xC385, 0xD4E7, 0xE50A, 0xF60B,
             0x8712, 0x9823, 0xA934, 0xBA45, 0xCB56, 0xDC67, 0xFFF4)

    def make_header(view_word, time_word=0xD4E7):
        values = (*words[:3], time_word, *words[4:12], view_word)
        return b''.join(value.to_bytes(2, 'big') for value in values) + bytes(6)

    result = [
        dict(name='poisoned-high-bytes-and-byte-store-widths', seed=80,
             header=make_header(words[-1]), ds=0x5000, df=0, iff=1),
        dict(name='view-add-wrap-final-carry-one-vga-ds', seed=81,
             header=make_header(0xFFF4), ds=0xA000, df=1, iff=0,
             expect_view_carry=1),
        dict(name='view-add-wrap-final-carry-zero-segment-wrap', seed=82,
             header=make_header(0xFFF0), ds=0xFFFF, df=0, iff=1,
             expect_view_carry=0),
        dict(name='vga-backed-header-and-output-bus', seed=83,
             header=make_header(0x9A65), ds=0xA000, df=1, iff=1),
    ]
    for view, time in ((0, 0), (7, 0xFFFF), (0x7FEF, 0x7FCF),
                       (0x7FF0, 0x7FD0), (0x7FFF, 0x7FFF),
                       (0x8000, 0x8000), (0xFFEF, 0xFFCF),
                       (0xFFFF, 0xFFD0)):
        seed = 80 + len(result)
        result.append(dict(name=f'add-boundaries-view-{view:04x}-time-{time:04x}',
                           seed=seed, header=make_header(view, time),
                           ds=0x5000, df=seed & 1, iff=(seed >> 1) & 1))
    return result


def all_cases():
    result = []
    for case in pinned_headers():
        case['ds'] = 0x5000
        case['df'] = (case['seed'] >> 0) & 1
        case['iff'] = (case['seed'] >> 1) & 1
        result.append(case)
    result.extend(synthetic_cases())
    return result


def prepare(case):
    seed = case['seed']
    rng = random.Random(0x36B9A7 + seed)
    load = (0x1010, 0x1213, 0x2345)[seed % 3]
    ds = case['ds']
    memory = bytearray(rng.randbytes(1 << 20))
    loaded = relocated(piece.IMAGE, piece.ORACLE['relocations'], load)
    memory[load << 4:(load << 4) + len(loaded)] = loaded

    for index, value in enumerate(case['header']):
        memory[physical(ds, HEADER_OFF + index)] = value

    # Every output begins with nonzero poison. Byte destinations retain their
    # adjacent high bytes; the two word destinations must replace both bytes.
    for index, offset in enumerate(OUTPUT_OFFSETS):
        at = physical(ds, offset)
        memory[at] = (0xD3 + index * 17 + seed) & 0xFF
        memory[(at + 1) & 0xFFFFF] = (0x6B + index * 29 + seed) & 0xFF

    registers = {name: rng.randrange(0x10000) for name in piece.oracle.REG_NAMES}
    registers.update(cs=load, ip=START, ds=ds, es=0x6800,
                     ss=0x7A00, sp=0x8F20)
    flags = initial_flags(seed, df=case['df'], iff=case['iff'])
    return memory, registers, flags


def prime_vga_source(device, case):
    if not VGA_BASE <= (case['ds'] << 4) < VGA_END:
        return
    # The aperture's read map is plane zero. Seed every plane identically so
    # the input header is also visible through the whole VGA latch model.
    for index, value in enumerate(case['header'][:0x1A]):
        offset = (HEADER_OFF + index) & 0xFFFF
        for plane in device.vga.planes:
            plane[offset] = value


def expected_trace_digest(events):
    digest = hashlib.sha256()
    kinds = {'read': 0, 'write': 1}
    for kind, address, value, _flags, _mask in events:
        digest.update(struct.pack('<BIH', kinds[kind], address & 0xFFFFFFFF,
                                  value & 0xFFFF))
    return digest.hexdigest()


def model(case, device, initial_registers, initial_flags):
    ds = case['ds']
    events = []

    def read_byte(offset, flags, mask):
        address = physical(ds, offset)
        value = device.vga.read(device.memory, address, flags)
        events.append(('read', address, value, flags, mask))
        return value

    def write_byte(offset, value, flags, mask):
        address = physical(ds, offset)
        value &= 0xFF
        device.vga.write(device.memory, address, value, flags)
        events.append(('write', address, value, flags, mask))

    def read_be_word(offset, flags, mask):
        high = read_byte(HEADER_OFF + offset, flags, mask)
        low = read_byte(HEADER_OFF + offset + 1, flags, mask)
        return (high << 8) | low

    flags = initial_flags
    mask = FULL_FLAGS
    for offset, outputs in BYTE_FIELDS:
        value = read_be_word(offset, flags, mask)
        if offset == 0x06:
            flags, value = add16_flags(flags, value, 0x0030)
        for output in outputs:
            write_byte(output, value, flags, mask)

    view = read_be_word(0x18, flags, mask)
    flags, view = add16_flags(flags, view, 0x0010)
    write_byte(0x0000, view, flags, mask)
    write_byte(0x0001, view >> 8, flags, mask)
    shift_states = {}
    for pc in (0x3739, 0x373B, 0x373D):
        shift_states[pc] = (view, flags, mask)
        flags, view = shr1_flags(flags, view)
        mask = SHIFT_FLAGS
    shift_states[0x373F] = (view, flags, mask)
    write_byte(0x0002, view, flags, mask)
    write_byte(0x0003, view >> 8, flags, mask)

    expected_registers = dict(initial_registers)
    expected_registers.update(ax=view, di=HEADER_OFF, ip=END)
    return expected_registers, flags, mask, events, view, shift_states


def event_values(trace):
    return [struct.unpack_from('<H', trace, offset)[0]
            for offset in range(0, len(trace), 2)]


def check_bus_trace(case, expected, actual):
    actual.events.check(case['name'])
    require(actual.events.count == len(expected),
            f"{case['name']}: bus event count {actual.events.count} != {len(expected)}")
    require(actual.events.digest.hexdigest() == expected_trace_digest(expected),
            f"{case['name']}: ordered byte read/store trace differs from field model")
    actual_masks = event_values(actual.events.mask_bytes)
    actual_flags = event_values(actual.events.flag_bytes)
    expected_masks = [event[4] for event in expected]
    require(actual_masks == expected_masks,
            f"{case['name']}: instruction-defined flag masks differ")
    for index, (event, observed) in enumerate(zip(expected, actual_flags)):
        require(((event[3] ^ observed) & event[4]) == 0,
                f"{case['name']}: event {index} has different defined flags")


def check_vga_trace(case, expected, actual):
    expected_vga = [
        (kind, address - VGA_BASE, value, flags & mask, mask)
        for kind, address, value, flags, mask in expected
        if VGA_BASE <= address < VGA_END
    ]
    observed_vga = actual.vga.trace
    require(len(observed_vga) == len(expected_vga),
            f"{case['name']}: VGA bus event count differs")
    for index, (observed, want) in enumerate(zip(observed_vga, expected_vga)):
        kind, address, value, flags = observed
        exp_kind, exp_address, exp_value, exp_flags, mask = want
        require((kind, address, value) == (exp_kind, exp_address, exp_value),
                f"{case['name']}: VGA event {index} differs")
        require(((flags ^ exp_flags) & mask) == 0,
                f"{case['name']}: VGA event {index} defined flags differ")


def verify_case(case):
    memory, registers, flags = prepare(case)
    model_device = TraceDevice(bytearray(memory), 0xA000 + case['seed'], read_map=0)
    original_device = TraceDevice(bytearray(memory), 0xA000 + case['seed'], read_map=0)
    prime_vga_source(model_device, case)
    prime_vga_source(original_device, case)

    expected_registers, expected_flags, expected_mask, events, view, shift_states = model(
        case, model_device, registers, flags)
    observed_shifts = set()

    def observe(pc, machine, _device):
        if pc in shift_states:
            value, status, defined = shift_states[pc]
            require(machine.reg_read(piece.oracle.REG['ax']) == value,
                    f"{case['name']}: AX before {pc:04x} differs")
            observed = machine.reg_read(piece.x.UC_X86_REG_EFLAGS)
            require(((observed ^ status) & defined) == 0,
                    f"{case['name']}: defined flags before {pc:04x} differ")
            observed_shifts.add(pc)

    actual, mask, sites, edges, boundary, _child, _body = original(
        case, original_device, registers, flags, instructions=INS, far_calls=set(),
        continuations=(END,), max_steps=64, observe=observe)
    require(observed_shifts == set(shift_states),
            f"{case['name']}: missing individual SHR phase observations")

    require(boundary == ('continuation', registers['cs'], END),
            f"{case['name']}: unexpected boundary {boundary!r}")
    require(mask == expected_mask == SHIFT_FLAGS,
            f"{case['name']}: final defined-flag mask {mask:#x} != {expected_mask:#x}")
    require(sites == set(INS),
            f"{case['name']}: original executed {len(sites)} sites, expected {len(INS)}")
    require(not edges, f"{case['name']}: unexpected control-flow edges {edges!r}")
    for name, value in expected_registers.items():
        require(actual[name] == value,
                f"{case['name']}: {name.upper()} {actual[name]:04x} != {value:04x}")
    require(((actual['flags'] ^ expected_flags) & expected_mask) == 0,
            f"{case['name']}: final defined flags differ")
    require(original_device.memory == model_device.memory,
            f"{case['name']}: canonical RAM image differs from field model")
    require(original_device.vga.state() == model_device.vga.state(),
            f"{case['name']}: VGA plane/latch/register state differs")
    check_bus_trace(case, events, original_device)
    check_vga_trace(case, events, original_device)

    if 'expect_view_carry' in case:
        require((actual['flags'] & 1) == case['expect_view_carry'],
                f"{case['name']}: final SHR carry mismatch")
        require((actual['flags'] & 0x0800) == 0,
                f"{case['name']}: final SHR overflow should be zero")
        require(not (mask & 0x0010),
                f"{case['name']}: AF unexpectedly reported defined after SHR")
    return dict(name=case['name'], sites=len(sites), bus_events=len(events),
                vga_events=len(original_device.vga.trace),
                ds=case['ds'], df=case['df'], iff=case['iff'],
                final_ax=view, final_flags=actual['flags'] & expected_mask,
                original_boundary=list(boundary))


def validate_static_extent():
    require(END - START == 137, 'unexpected initializer prefix byte extent')
    require(len(INS) == 47, f'unexpected decoded site count: {len(INS)}')
    cursor = START
    for instruction in DECODED:
        require(instruction.address == cursor,
                f"decode gap at {cursor:04x}, got {instruction.address:04x}")
        cursor += instruction.size
    require(cursor == END, f'decode did not end at {END:04x}')
    require(not any(i.mnemonic.startswith('call') or i.mnemonic.startswith('j')
                    for i in DECODED),
            'prefix unexpectedly contains a call or branch')
    symbols = {row['symbol_name']: row
               for row in read_json(ROOT / 'metadata/symbols.json')}
    require(symbols['LoadedLevelRecord']['address'] == HEADER_OFF,
            'LoadedLevelRecord address no longer matches the prefix contract')


def worker():
    piece.common.MAX_BUS_EVENTS = EVENT_LIMIT
    piece.common.MAX_VGA_EVENTS = VGA_EVENT_LIMIT
    validate_static_extent()
    paths = dependency_paths()
    hashes = {path: sha((ROOT / path).read_bytes()) for path in paths}
    results = []
    for case in all_cases():
        results.append(verify_case(case))
        gc.collect()

    require(hashes == {path: sha((ROOT / path).read_bytes()) for path in paths},
            'Header contract inputs changed during execution')
    report = dict(
        evidence_kind='original-only-level-header-prefix',
        c_coverage_claimed=False,
        prefix=dict(start=f'{START:04X}', end_exclusive=f'{END:04X}',
                    decoded_bytes=PREFIX_BYTES, decoded_sites=len(INS),
                    executed_original_sites=sorted(f'{site:04X}' for site in INS)),
        case_count=len(results), cases=results, input_sha256=hashes)
    write_json(BUILD / 'level-header-contract-original.json', report)
    print(f"original-only level-header contract: {len(results)} cases, "
          f'{PREFIX_BYTES} bytes / {len(INS)} sites; no C coverage claimed')


def main():
    if '--worker' in sys.argv:
        worker()
        return
    BUILD.mkdir(exist_ok=True)
    (BUILD / 'level-header-contract-original.json').unlink(missing_ok=True)
    run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker'],
                cwd=ROOT, check=True, timeout=120, memory_mib=512)


if __name__ == '__main__':
    main()

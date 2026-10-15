"""Focused whole-RAM checks for the 5DC6 entity-pixel preparation leaf."""
import ctypes
import gc
import random
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import capstone
from unicorn import (Uc, UcError, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_WRITE)
from unicorn import x86_const as x
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, sha, write_json
from dat_io_c import MEM, Regs
from unpack import ASSET, unpack, relocated


IMAGE, ORACLE = unpack(ASSET.read_bytes())
ENTRY, RET, END = 0x5DC6, 0x5DF7, 0x5DF8
LOAD = 0x1010
DATA_SEGMENT = (LOAD + 0x09A9) & 0xFFFF
TABLE = 0x547C
MASKS = bytes.fromhex('80 40 20 10 08 04 02 01')
SIZE = 1 << 20
DEFINED_FLAGS = 0x0FD7
COMPARE_FLAGS = DEFINED_FLAGS | 0x0200  # also retain IF across the direct call
CODE = IMAGE[ENTRY:END]
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {i.address: i for i in MD.disasm(CODE, ENTRY)}
BRANCHES = {pc for pc, ins in INS.items() if ins.group(capstone.CS_GRP_JUMP)}
REGS = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'sp', 'cs', 'ds', 'es', 'ss', 'ip')
REG_ID = {
    'ax': x.UC_X86_REG_AX, 'bx': x.UC_X86_REG_BX,
    'cx': x.UC_X86_REG_CX, 'dx': x.UC_X86_REG_DX,
    'si': x.UC_X86_REG_SI, 'di': x.UC_X86_REG_DI,
    'bp': x.UC_X86_REG_BP, 'sp': x.UC_X86_REG_SP,
    'cs': x.UC_X86_REG_CS, 'ds': x.UC_X86_REG_DS,
    'es': x.UC_X86_REG_ES, 'ss': x.UC_X86_REG_SS,
    'ip': x.UC_X86_REG_IP,
}
BRANCH_EDGES = {
    (0x5DD1, 0x5DD5),  # JNS taken: wrapped Y-10h is nonnegative
    (0x5DD1, 0x5DD3),  # JNS not taken: XOR DI,DI clamps the row to zero
}
REPORT = BUILD / 'entity-pixel-differential.json'


class Call(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('data_segment', 'stack_segment', 'stack_offset', 'record_cursor',
                 'saved_value', 'flags')]


class CoreResult(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('value', 'table_cursor', 'column_byte', 'destination_offset',
                 'restored_value', 'stack_offset', 'flags')]


class NativeMismatch(AssertionError):
    """A completed native result differs from completed original execution."""


class OracleFailure(AssertionError):
    """The pinned original did not complete the bounded declared execution."""


def require(condition, message):
    if not condition:
        raise NativeMismatch(message)


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def physical(segment, offset):
    return ((segment << 4) + offset) & 0xFFFFF


def putword(memory, segment, offset, value):
    p = physical(segment, offset)
    memory[p] = value & 255
    memory[(p + 1) & 0xFFFFF] = (value >> 8) & 255


def getword(memory, segment, offset):
    p = physical(segment, offset)
    return memory[p] | (memory[(p + 1) & 0xFFFFF] << 8)


def add_flags(flags, left, right):
    total = left + right
    value = total & 0xFFFF
    status = 0
    if (value & 255).bit_count() % 2 == 0:
        status |= 0x04
    if value == 0:
        status |= 0x40
    if value & 0x8000:
        status |= 0x80
    if total > 0xFFFF:
        status |= 0x01
    if (left ^ right ^ value) & 0x10:
        status |= 0x10
    if (~(left ^ right) & (left ^ value) & 0x8000) != 0:
        status |= 0x800
    return ((flags & ~0x8D5) | status) & 0xFFFF


def cases():
    """Boundary cases target the live table, stack aliases and both JNS exits."""
    specs = []
    for index in range(8):
        specs.append((f'pinned-mask-index-{index}', {
            'x': 0x948 + index, 'y': 0x22 + index,
            'ds': DATA_SEGMENT, 'si': 0x5000, 'table_mode': 'pinned'}))
    specs.extend((
        ('x-column-zero-mask-seven', {'x': 0x0007, 'y': 0x0022}),
        ('custom-live-table-index-5', {
            'x': 0x2D, 'y': 0x22, 'ds': 0x3000, 'si': 0x1000,
            'table_mode': 'custom', 'table_bytes': bytes.fromhex('19 A7 33 5C E2 B6 71 0D')}),
        ('custom-live-table-zero-byte', {
            'x': 0x12, 'y': 0x29, 'ds': 0x3100, 'si': 0x1100,
            'table_mode': 'custom', 'table_bytes': bytes.fromhex('11 22 00 44 55 66 77 88')}),
    ))
    for y in (0x0000, 0x000F, 0x0010, 0x7FFF, 0x8000, 0x800F, 0x8010, 0xFFFF):
        specs.append((f'y-boundary-{y:04x}', {'x': 0x1357, 'y': y}))
    specs.extend((
        ('x-logical-shift-high-bit', {'x': 0xFFFF, 'y': 0x0027}),
        ('row-product-low-word-wrap', {'x': 0xA135, 'y': 0x3456}),
        ('df-clear', {'x': 0x1265, 'y': 0x0023, 'df': False}),
        ('df-set', {'x': 0x1265, 'y': 0x0023, 'df': True}),
        ('record-offset-wrap', {'x': 0xA5D7, 'y': 0x7FFF, 'si': 0xFFFE}),
        ('record-physical-word-wrap', {'x': 0xA5D7, 'y': 0x0031,
                                       'ds': 0xFFFF, 'si': 0x000F}),
        ('stack-sp-zero', {'sp': 0x0000}),
        ('stack-sp-one', {'sp': 0x0001}),
        ('stack-sp-ffff', {'sp': 0xFFFF}),
        ('stack-physical-word-wrap', {'ss': 0xFFFF, 'sp': 0x0011}),
        # PUSH DX overwrites the live X word before the later MOV CX,[SI].
        ('ds-ss-x-alias', {'ds': 0x3000, 'ss': 0x3000, 'si': 0x1000,
                           'sp': 0x1002, 'x': 0x0003, 'y': 0x0040,
                           'dx': 0x1234, 'return_word': 0x0040}),
        # Y is captured by the first MOV before PUSH DX overwrites its word.
        ('ds-ss-y-alias', {'ds': 0x3000, 'ss': 0x3000, 'si': 0x1000,
                           'sp': 0x1004, 'x': 0x031B, 'y': 0x8000,
                           'dx': 0x71A5}),
        # The stack save changes DS:547C before MOV AH,[BX] reads index zero.
        ('ds-ss-table-alias', {'ds': 0x3000, 'ss': 0x3000, 'si': 0x1000,
                               'sp': 0x547E, 'x': 0x0120, 'y': 0x0034,
                               'dx': 0xBBAA}),
        ('near-ret-target', {'return_word': 0xBEEF}),
    ))
    for n in range(6):
        specs.append((f'seeded-coordinate-{n}', {
            'x': (0xA513 + n * 0x211) & 0xFFFF,
            'y': (0x71E7 + n * 0x37D) & 0xFFFF,
            'df': bool(n & 1),
            'ds': 0x3100 + n * 0x101,
            'ss': 0x5200 + n * 0x113,
            'table_mode': 'custom',
            'table_bytes': bytes(((n * 29 + i * 43 + 7) & 255) for i in range(8)),
        }))
    rows = [dict(name=name, seed=i, **updates) for i, (name, updates) in enumerate(specs)]
    if len(rows) != 39:
        raise AssertionError('Entity pixel case count changed')
    return rows


def prepare(case):
    rng = random.Random(0x5DC6 + case['seed'] * 0x9E3779B1)
    memory = bytearray(rng.randbytes(SIZE))
    loaded = relocated(IMAGE, ORACLE['relocations'], LOAD)
    base = LOAD << 4
    memory[base:base + len(loaded)] = loaded
    regs = {name: rng.randrange(65536) for name in REGS}
    regs.update(cs=LOAD, ip=ENTRY,
                ds=case.get('ds', DATA_SEGMENT), ss=case.get('ss', 0x5000),
                es=case.get('es', rng.randrange(65536)),
                si=case.get('si', 0x5000), sp=case.get('sp', 0x8000))
    regs['dx'] = case.get('dx', regs['dx'])
    flags = (rng.randrange(65536) & 0x0FD7) | 2
    flags &= ~0x100  # clear TF so Unicorn executes the declared leaf normally
    if case.get('df', False):
        flags |= 0x400
    else:
        flags &= ~0x400
    if case['seed'] & 1:
        flags |= 0x200
    else:
        flags &= ~0x200
    regs['flags'] = flags

    table_mode = case.get('table_mode', 'pinned')
    table_bytes = case.get('table_bytes', MASKS)
    if table_mode == 'pinned' and regs['ds'] == DATA_SEGMENT:
        actual = bytes(memory[physical(regs['ds'], TABLE) + i] for i in range(8))
        oracle_require(actual == MASKS,
                       case['name'] + ': canonical DS mask table bytes changed')
    else:
        for i, value in enumerate(table_bytes):
            memory[physical(regs['ds'], TABLE + i)] = value

    putword(memory, regs['ds'], regs['si'], case.get('x', 0x1237))
    putword(memory, regs['ds'], (regs['si'] + 2) & 0xFFFF, case.get('y', 0x0027))
    putword(memory, regs['ss'], regs['sp'], case.get('return_word', 0xE300 | case['seed']))
    return memory, regs


def independent(memory, regs, *, core):
    """Direct ordered state model, including the live push-before-X/table reads."""
    output = bytearray(memory)
    y = getword(output, regs['ds'], (regs['si'] + 2) & 0xFFFF)
    row = (y - 0x10) & 0xFFFF
    if row & 0x8000:
        row = 0
    product = (row * 0xD0) & 0xFFFF
    pushed_sp = (regs['sp'] - 2) & 0xFFFF
    putword(output, regs['ss'], pushed_sp, regs['dx'])
    restored = getword(output, regs['ss'], pushed_sp)
    sp = (pushed_sp + 2) & 0xFFFF
    xcoord = getword(output, regs['ds'], regs['si'])
    index = xcoord & 7
    column = xcoord >> 3
    table_cursor = (TABLE + index) & 0xFFFF
    mask = output[physical(regs['ds'], table_cursor)]
    destination = (product + column + 0x4A40) & 0xFFFF
    state = dict(regs)
    state.update(ax=((mask << 8) | (product & 255)),
                 bx=table_cursor, cx=column, dx=restored,
                 di=destination, es=0xA000, sp=sp,
                 flags=add_flags(regs['flags'], index, TABLE), ip=RET)
    edges = {(0x5DD1, 0x5DD3 if ((y - 0x10) & 0xFFFF) & 0x8000 else 0x5DD5)}
    if not core:
        state['ip'] = getword(output, regs['ss'], sp)
        state['sp'] = (sp + 2) & 0xFFFF
    return output, state, edges


def original(case, memory, regs, *, core):
    cpu = Uc(UC_ARCH_X86, UC_MODE_16)
    cpu.mem_map(0, 2 * SIZE)
    cpu.mem_write(0, bytes(memory) * 2)
    for name in REGS:
        cpu.reg_write(REG_ID[name], regs[name])
    cpu.reg_write(x.UC_X86_REG_EFLAGS, regs['flags'])
    code_start = (LOAD << 4) + ENTRY
    oracle_require(bytes(memory[code_start:code_start + len(CODE)]) == CODE,
                   case['name'] + ': executing bytes differ from pinned image')
    sites, edges, failures = set(), set(), []
    previous, done, ret_executed = None, False, False

    def fail(message):
        if not failures:
            failures.append(message)
        cpu.emu_stop()

    def code(uc, pc, _size, _user):
        nonlocal previous, done, ret_executed
        off = uc.reg_read(x.UC_X86_REG_IP) & 0xFFFF
        cs = uc.reg_read(x.UC_X86_REG_CS) & 0xFFFF
        if previous in BRANCHES:
            edges.add((previous, off))
        if previous == RET:
            done = True
            uc.emu_stop()
            return
        if cs != LOAD or off not in INS:
            fail(f'{case["name"]}: original escaped at {cs:04X}:{off:04X}')
            return
        if core and off == RET:
            done = True
            uc.emu_stop()
            return
        if len(sites) >= 100:
            fail(case['name'] + ': original instruction budget exhausted')
            return
        sites.add(off)
        previous = off
        if off == RET:
            ret_executed = True

    def a20_write(uc, _access, address, size, value, _user):
        try:
            for i in range(size):
                raw = address + i
                if raw >= SIZE:
                    uc.mem_write(raw & 0xFFFFF, bytes(((value >> (8 * i)) & 255,)))
        except BaseException as error:
            fail(f'{case["name"]}: A20 write hook failed: {error}')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_WRITE, a20_write)
    try:
        cpu.emu_start((LOAD << 4) + ENTRY, 0, count=100)
    except UcError as error:
        raise OracleFailure(f'{case["name"]}: original Unicorn execution failed: {error}') from error
    oracle_require(not failures, failures[0] if failures else 'original execution failed')
    want_sites = len(INS) - (1 if core else 0)
    oracle_require(done and len(sites) <= want_sites and (core or ret_executed),
                   case['name'] + ': original did not reach declared bounded boundary')
    result = {name: cpu.reg_read(REG_ID[name]) & 0xFFFF for name in REGS}
    result['flags'] = cpu.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
    output = bytes(cpu.mem_read(0, SIZE))
    oracle_require(bytes(output[code_start:code_start + len(CODE)]) == CODE,
                   case['name'] + ': original modified executing code')
    return bytearray(output), result, sites, edges


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-pixel-m{mutation}.dll', mutation, 'entity_pixel')
        self.library = ctypes.CDLL(str(path))
        self.core = self.library.lmn_prepare_entity_pixel_core
        self.core.argtypes = [MEM, ctypes.POINTER(Call)]
        self.core.restype = CoreResult
        self.adapter = self.library.lmn_prepare_entity_pixel_adapter
        self.adapter.argtypes = [MEM, ctypes.POINTER(Regs)]
        self.adapter.restype = None


def buffer(memory):
    return (ctypes.c_uint8 * SIZE).from_buffer(memory)


def native_execute(native, memory, regs, *, core):
    state = dict(regs)
    if core:
        call = Call(state['ds'], state['ss'], state['sp'], state['si'],
                    state['dx'], state['flags'])
        result = native.core(buffer(memory), ctypes.byref(call))
        state.update(ax=result.value, bx=result.table_cursor, cx=result.column_byte,
                     di=result.destination_offset, dx=result.restored_value,
                     es=0xA000, sp=result.stack_offset, flags=result.flags, ip=RET)
    else:
        live = Regs(**{name: state[name] for name in REGS}, flags=state['flags'])
        native.adapter(buffer(memory), ctypes.byref(live))
        state = {name: getattr(live, name) for name in REGS}
        state['flags'] = live.flags
    return memory, state


def compare_state(case, actual, expected, label, error_type=NativeMismatch):
    for name in REGS:
        if actual[name] != expected[name]:
            raise error_type(f'{case["name"]} {label} {name} differs: '
                             f'{actual[name]:04X}/{expected[name]:04X}')
    if ((actual['flags'] ^ expected['flags']) & COMPARE_FLAGS) != 0:
        raise error_type(f'{case["name"]} {label} flags differ: '
                         f'{actual["flags"]:04X}/{expected["flags"]:04X}')


def compare_memory(case, actual, expected, label, error_type=NativeMismatch):
    if actual == expected:
        return
    mismatch = next((p for p, (got, want) in enumerate(zip(actual, expected))
                     if got != want), None)
    raise error_type(f'{case["name"]} {label} RAM differs at {mismatch:05X}: '
                     f'{actual[mismatch]:02X}/{expected[mismatch]:02X}')


def compare_case(native, case):
    union_sites, union_edges = set(), set()
    for core in (True, False):
        initial_memory, initial_regs = prepare(case)
        model_memory, model_regs, model_edges = independent(initial_memory, initial_regs, core=core)
        check_independent_examples(case, initial_memory, initial_regs,
                                   model_memory, model_regs)
        original_memory, original_regs, sites, edges = original(
            case, bytearray(initial_memory), initial_regs, core=core)
        compare_state(case, original_regs, model_regs, 'original/model', OracleFailure)
        compare_memory(case, original_memory, model_memory, 'original/model', OracleFailure)
        oracle_require(edges == model_edges,
                       case['name'] + ': original branch edge differs from independent condition')
        native_memory, native_regs = native_execute(
            native, bytearray(initial_memory), initial_regs, core=core)
        label = 'core' if core else 'adapter'
        compare_state(case, native_regs, original_regs, label)
        compare_memory(case, native_memory, original_memory, label)
        if core:
            oracle_require(original_regs['ip'] == RET and original_regs['sp'] == initial_regs['sp'],
                           case['name'] + ': core did not stop before RET with restored SP')
        else:
            oracle_require(original_regs['sp'] == ((initial_regs['sp'] + 2) & 0xFFFF),
                           case['name'] + ': adapter did not execute actual near RET')
        union_sites.update(sites)
        union_edges.update(edges)
        gc.collect()
    return sorted(union_sites), sorted(union_edges)


def check_independent_examples(case, initial_memory, initial_regs, expected_memory, expected_regs):
    if case['name'].startswith('pinned-mask-index-'):
        index = int(case['name'].rsplit('-', 1)[1])
        oracle_require(expected_regs['bx'] == TABLE + index,
                       case['name'] + ': table cursor does not follow X&7')
        oracle_require(expected_regs['ax'] >> 8 == MASKS[index],
                       case['name'] + ': pinned mask byte differs from live table')
    if case['name'] == 'custom-live-table-index-5':
        oracle_require(expected_regs['ax'] >> 8 == 0xB6,
                       'custom live DS table byte was not selected')


def input_hashes():
    paths = (
        'assets/vgalemmi.exe', 'metadata/symbols.json', 'metadata/hints.json',
        'metadata/regions.json', 'metadata/inputs.json',
        'c/entity_pixel.c', 'c/entity_pixel.h', 'c/lemmings_sym.h', 'c/regs.h',
        'tests/entity_pixel.py', 'tests/dat_io.py', 'tests/dat_io_c.py',
        'docs/entity-pixel.md',
        'tools/cbuild.py', 'tools/difftest.py', 'tools/coverage.py',
        'tools/bounded_process.py', 'tools/unpack.py', 'tools/common.py',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def worker(directory):
    before = input_hashes()
    oracle_require(sha(ASSET.read_bytes()) ==
                   '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d',
                   'Pinned executable identity changed')
    oracle_require(sha(IMAGE) == 'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'Pinned static image identity changed')
    oracle_require(len(CODE) == 50 and len(INS) == 22,
                   'Entity pixel byte/site accounting changed')
    oracle_require(IMAGE[0xEF0C:0xEF14] == MASKS,
                   'Pinned DS:547C bit-mask table identity changed')
    specs = cases()
    baseline = Native(directory)
    coverage, edges, rows = set(), set(), []
    for case in specs:
        sites, case_edges = compare_case(baseline, case)
        coverage.update(sites)
        edges.update(case_edges)
        rows.append(dict(name=case['name'], executed_instruction_addresses=sites,
                         branch_edges=case_edges))
    oracle_require(coverage == set(INS),
                   'Entity pixel original site coverage differs')
    oracle_require(edges == BRANCH_EDGES,
                   f'Entity pixel JNS edges differ: expected {BRANCH_EDGES}, got {edges}')

    mutation_witnesses = (
        (1, 'y-boundary-8000', 'wrapped-row-sign'),
        (2, 'ds-ss-x-alias', 'post-push-live-X'),
        (3, 'custom-live-table-index-5', 'live-DS-mask-table'),
        (4, 'pinned-mask-index-0', 'low-product-AL'),
    )
    by_name = {case['name']: case for case in specs}
    mutations = []
    for mutation, case_name, label in mutation_witnesses:
        variant = Native(directory, mutation)
        try:
            compare_case(variant, by_name[case_name])
        except NativeMismatch as error:
            mutations.append(dict(mutation=mutation, name=label, case=case_name,
                                  mismatch=str(error), completed=True))
        else:
            raise OracleFailure(f'Entity pixel mutant {mutation} survived {case_name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after, 'Entity pixel inputs changed during test run')
    oracle_require(len(rows) == 39 and len(mutations) == 4,
                   'Entity pixel report scope changed')
    write_json(REPORT, dict(image='main', image_sha256=sha(IMAGE),
        case_count=len(rows), auxiliary_core_cases=len(rows), mutation_count=len(mutations),
        mutations=mutations, cases=rows, translated_code_bytes=50,
        native_code_ranges=[[ENTRY, END]], routine_bytes=CODE.hex(),
        executed_instruction_addresses=sorted(coverage), instruction_sites=sorted(coverage),
        instruction_site_count=len(coverage), branch_instruction_addresses=sorted(BRANCHES),
        branch_edges=sorted(edges), domains=[
            'ordinary 1 MiB RAM; intact main image code 5DC6..5DF7; no VGA memory access',
            'live DS record and DS:547C table; all eight pinned mask indexes and custom live bytes',
            'wrapped Y-10h sign clamp, low-word 208-byte row product, logical X/8',
            'DX push/pop ordering before the live DS:SI X read; DS/SS X, Y and table aliases',
            '16-bit record/stack offset wrap and 20-bit physical word wrap',
            'all registers; final ADD flags plus preserved TF-clear, IF and DF state',
            'core stops before RET; adapter executes actual near RET and stops at target'],
        limits=dict(worker_seconds=180, windows_process_mib=384,
                    original_instruction_hook_limit=100, native_callback_budget=0),
        input_hashes=after))
    print(f'PASS entity pixel C: {len(rows)} cases, 50 bytes, 22 sites, '
          f'{len(edges)} JNS edges, {len(mutations)} completed mutants', flush=True)


def main():
    BUILD.mkdir(exist_ok=True)
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if sys.argv[1:]:
        raise SystemExit('Unexpected entity pixel arguments')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-pixel-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=180, memory_mib=384)


if __name__ == '__main__':
    main()

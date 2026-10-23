"""Focused whole-RAM checks for the 283B entity-pattern copy leaf."""
import ctypes
import gc
import random
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import capstone
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import x86_const as x
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, sha, write_json
from dat_io_c import MEM, Regs
from unpack import ASSET, unpack, relocated


IMAGE, ORACLE = unpack(ASSET.read_bytes())
ENTRY, RET, END = 0x283B, 0x287C, 0x287D
LOAD = 0x1010
SIZE = 1 << 20
DEFINED_FLAGS = 0x0FD7
CODE = IMAGE[ENTRY:END]
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
INS = {i.address: i for i in MD.disasm(CODE, ENTRY)}
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
REPORT = BUILD / 'entity-pattern-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-pattern-contract-original.json'


class Call(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('data_segment', 'stack_segment', 'stack_offset', 'record_cursor',
                 'saved_destination', 'saved_value', 'saved_segment', 'flags')]


class CoreResult(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('product', 'map_offset', 'restored_value', 'record_cursor',
                 'restored_destination', 'restored_segment', 'stack_offset', 'flags')]


class NativeMismatch(AssertionError):
    """A completed native result differs from completed original execution."""


class OracleFailure(AssertionError):
    """The pinned original did not complete the declared bounded execution."""


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


def cases():
    """Small boundary set: explicit wrap, DF, stack, RET and overlap contracts."""
    specs = [
        ('geometric-known', {}),
        ('x-underflow', {'x': 0, 'y': 22}),
        ('y-underflow', {'x': 4, 'y': 0}),
        ('xy-underflow', {'x': 0, 'y': 0}),
        ('x-just-under', {'x': 3, 'y': 22}),
        ('y-just-under', {'x': 4, 'y': 21}),
        ('high-coordinate-wrap', {'x': 0xFFFC, 'y': 0xFFF2}),
        # qx=3E9D and qy=0077 give a wrapped final map offset of 000F.
        ('low-word-product-wrap', {'x': 0xFA78, 'y': 0x01F2}),
        ('coordinate-offset-wrap', {'si': 0xFFFE}),
        ('source-offset-wrap', {'si': 0xFFF8}),
        ('physical-source-word-wrap', {'ds': 0xFFFF, 'si': 0xFFF9}),
        ('physical-destination-word-wrap',
         {'x': 0xFA78, 'y': 0x01F2, 'ss': 0xFFFF}),
        ('df-clear', {'df': False}),
        ('df-set', {'df': True}),
        ('df-set-coordinate-wrap', {'df': True, 'x': 0, 'y': 0}),
        ('stack-sp-zero', {'sp': 0}),
        ('stack-sp-one', {'sp': 1}),
        ('stack-sp-ffff', {'sp': 0xFFFF}),
        ('physical-stack-wrap', {'ss': 0xFFFF, 'sp': 1}),
        # DS=SS; the last PUSH SS overwrites the first source word after the
        # coordinates have already been read from SI and SI+2.
        ('ds-ss-last-push-source', {'ds': 0x3000, 'ss': 0x3000,
                                    'si': 0x1000, 'sp': 0x101E}),
        # Coordinates at DS:SI and DS:SI+2 must be captured before stack writes.
        ('coordinates-before-push', {'ds': 0x3000, 'ss': 0x3000,
                                     'si': 0x1000, 'sp': 0x1006}),
        # map=12; source starts at 16 and the pushes expose saved SI as source,
        # while the first output word/byte overwrite saved ES and saved DI.
        ('saved-es-di-si-alias', {'ds': 0x3000, 'ss': 0x3000,
                                  'si': 0, 'sp': 0x18}),
        ('saved-es-alias', {'sp': 0x18}),
        ('saved-di-alias', {'sp': 0x16}),
        ('saved-si-alias', {'sp': 0x14}),
        # The mapped bytes replace the live near-RET word; adapter must return
        # through the new word and stop before its target instruction.
        ('ret-overwrite', {'sp': 0x12}),
        ('ret-overwrite-df', {'sp': 0x12, 'df': True}),
        ('physical-ret-overwrite', {'x': 0xFA78, 'y': 0x01F2,
                                    'ss': 0xFFFF, 'sp': 0x000F}),
        # DS=SS and destination=source+1: MOVSW changes the byte the following
        # MOVSB reads, so a pre-cached memcpy-style copy would differ.
        ('sequential-source-destination-overlap',
         {'ds': 0x3000, 'ss': 0x3000, 'si': 0xFFFB}),
    ]
    for n in range(8):
        specs.append((f'seeded-coordinate-{n}', {
            'x': (0xA513 + n * 0x211) & 0xFFFF,
            'y': (0x71E7 + n * 0x37D) & 0xFFFF,
            'df': bool(n & 1),
            'ds': 0x3100 + n * 0x101,
            'ss': 0x5200 + n * 0x113,
        }))
    rows = [dict(name=name, seed=i, **updates) for i, (name, updates) in enumerate(specs)]
    if len(rows) != 37:
        raise AssertionError('Entity pattern case count changed')
    return rows


def prepare(case):
    rng = random.Random(0x283B + case['seed'] * 0x9E3779B1)
    memory = bytearray(rng.randbytes(SIZE))
    loaded = relocated(IMAGE, ORACLE['relocations'], LOAD)
    base = LOAD << 4
    memory[base:base + len(loaded)] = loaded
    initial = {name: rng.randrange(65536) for name in REGS}
    initial.update(cs=LOAD, ip=ENTRY,
                   ds=case.get('ds', 0x3000), ss=case.get('ss', 0x5000),
                   es=case.get('es', 0x6400), si=case.get('si', 0x1000),
                   sp=case.get('sp', 0x8000))
    flags = rng.randrange(65536) & DEFINED_FLAGS
    flags |= 2
    # TF would raise a debug exception between instructions; the leaf's C
    # domain retains the original quiescent, trap-clear execution seam.
    flags &= ~0x100
    if case.get('df', False):
        flags |= 0x400
    else:
        flags &= ~0x400
    initial['flags'] = flags
    xcoord, ycoord = case.get('x', 4), case.get('y', 22)
    putword(memory, initial['ds'], initial['si'], xcoord)
    putword(memory, initial['ds'], (initial['si'] + 2) & 0xFFFF, ycoord)
    source = (initial['si'] + 0x16) & 0xFFFF
    pattern = bytes((0x41 + ((case['seed'] * 13 + i * 29) & 0x3F)) for i in range(9))
    for i, value in enumerate(pattern):
        memory[physical(initial['ds'], (source + i) & 0xFFFF)] = value
    # A stable, non-code return target. Alias cases intentionally replace it
    # during the original copy and verify actual near-RET behavior.
    putword(memory, initial['ss'], initial['sp'], 0xE300 | (case['seed'] & 0xFF))
    return memory, initial, pattern


def original(case, memory, initial, *, core):
    """Run intact pinned instructions on mirrored canonical 1 MiB ordinary RAM."""
    cpu = Uc(UC_ARCH_X86, UC_MODE_16)
    cpu.mem_map(0, 2 * SIZE)
    cpu.mem_write(0, bytes(memory) * 2)
    for name, value in initial.items():
        reg = x.UC_X86_REG_EFLAGS if name == 'flags' else REG_ID[name]
        cpu.reg_write(reg, value)
    expected_code = CODE
    code_physical = (LOAD << 4) + ENTRY
    oracle_require(bytes(memory[code_physical:code_physical + len(CODE)]) == expected_code,
                   case['name'] + ': executing bytes differ from pinned image')
    code_bytes = {((LOAD << 4) + p + n) & 0xFFFFF: CODE[p - ENTRY + n]
                  for p, ins in INS.items() for n in range(ins.size)}
    sites, failure = set(), []
    ret_executed, done = False, False

    def fail(message):
        if not failure:
            failure.append(message)
        cpu.emu_stop()

    def on_code(uc, address, size, _user):
        nonlocal ret_executed, done
        off, cs = uc.reg_read(x.UC_X86_REG_IP), uc.reg_read(x.UC_X86_REG_CS)
        if ret_executed:
            done = True
            uc.emu_stop()
            return
        if cs != LOAD or off not in INS:
            fail(f'{case["name"]}: original escaped routine at {cs:04X}:{off:04X}')
            return
        if core and off == RET:
            done = True
            uc.emu_stop()
            return
        if len(sites) >= 100:
            fail(case['name'] + ': original instruction budget exhausted')
            return
        sites.add(off)
        if off == RET:
            ret_executed = True

    def on_read(uc, access, address, size, value, _user):
        try:
            for n in range(size):
                p = (address + n) & 0xFFFFF
                uc.mem_write(address + n, bytes((memory[p],)))
        except BaseException as error:
            fail(f'{case["name"]}: RAM read hook failed: {error}')

    def on_write(uc, access, address, size, value, _user):
        try:
            for n in range(size):
                raw = address + n
                p, byte = raw & 0xFFFFF, (value >> (8 * n)) & 255
                if p in code_bytes and byte != code_bytes[p]:
                    oracle_require(False, case['name'] + ': original wrote executing code')
                memory[p] = byte
                uc.mem_write(p, bytes((byte,)))
                uc.mem_write(p + SIZE, bytes((byte,)))
        except BaseException as error:
            fail(f'{case["name"]}: RAM write hook failed: {error}')

    cpu.hook_add(UC_HOOK_CODE, on_code)
    cpu.hook_add(UC_HOOK_MEM_READ, on_read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, on_write)
    cpu.emu_start((LOAD << 4) + ENTRY, 0, count=100)
    oracle_require(not failure, failure[0] if failure else 'original failure')
    oracle_require(done and len(sites) == (36 if core else 37),
                   case['name'] + ': original did not reach declared boundary')
    final = {name: cpu.reg_read(REG_ID[name]) & 0xFFFF for name in REGS}
    final['flags'] = cpu.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
    oracle_require(bytes(memory[code_physical:code_physical + len(CODE)]) == expected_code,
                   case['name'] + ': original changed executing code')
    if core:
        oracle_require(final['ip'] == RET and not ret_executed,
                       case['name'] + ': core did not stop before near RET')
    else:
        oracle_require(ret_executed, case['name'] + ': adapter did not execute near RET')
    return memory, final, sites


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-pattern-m{mutation}.dll', mutation, 'entity_pattern')
        self.library = ctypes.CDLL(str(path))
        self.core = self.library.lmn_copy_entity_pattern_core
        self.core.argtypes = [MEM, ctypes.POINTER(Call)]
        self.core.restype = CoreResult
        self.adapter = self.library.lmn_copy_entity_pattern_adapter
        self.adapter.argtypes = [MEM, ctypes.POINTER(Regs)]
        self.adapter.restype = None


def buffer(memory):
    return (ctypes.c_uint8 * SIZE).from_buffer(memory)


def native_execute(native, memory, initial, *, core):
    state = dict(initial)
    if core:
        call = Call(state['ds'], state['ss'], state['sp'], state['si'],
                    state['di'], state['dx'], state['es'], state['flags'])
        result = native.core(buffer(memory), ctypes.byref(call))
        state.update(ax=result.product, bx=result.map_offset,
                     dx=result.restored_value, si=result.record_cursor,
                     di=result.restored_destination, es=result.restored_segment,
                     sp=result.stack_offset, ip=RET, flags=result.flags)
    else:
        regs = Regs(**{name: state[name] for name in REGS}, flags=state['flags'])
        native.adapter(buffer(memory), ctypes.byref(regs))
        state = {name: getattr(regs, name) for name in REGS}
        state['flags'] = regs.flags
    return memory, state


def compare_state(case, actual, expected, label):
    for name in REGS:
        require(actual[name] == expected[name],
                f'{case["name"]} {label} {name} differs: '
                f'{actual[name]:04X}/{expected[name]:04X}')
    require(((actual['flags'] ^ expected['flags']) & DEFINED_FLAGS) == 0,
            f'{case["name"]} {label} defined flags differ: '
            f'{actual["flags"]:04X}/{expected["flags"]:04X}')


def compare_memory(case, actual, expected, label):
    if actual == expected:
        return
    mismatch = next((p for p, (got, want) in enumerate(zip(actual, expected))
                     if got != want), None)
    if mismatch is not None:
        raise NativeMismatch(
            f'{case["name"]} {label} RAM differs at {mismatch:05X}: '
            f'{actual[mismatch]:02X}/{expected[mismatch]:02X}')


def geometric_check(case, memory, output, pattern):
    if case['name'] != 'geometric-known':
        return
    # x=4, y=22 gives BX=12h; three MOVSW/MOVSB pairs occupy rows
    # 000h, 1A0h and 340h from that map origin.
    expected_offsets = [0x12 + row * 0x1A0 + col
                        for row in range(3) for col in range(3)]
    for i, offset in enumerate(expected_offsets):
        got = output[physical(0x5000, offset)]
        require(got == pattern[i],
                f'geometric-known independent row byte {i} differs: {got:02X}/{pattern[i]:02X}')


def compare_case(native, case):
    union_sites = set()
    for core in (True, False):
        initial_memory, initial, pattern = prepare(case)
        original_memory, expected_state, sites = original(
            case, bytearray(initial_memory), initial, core=core)
        union_sites.update(sites)
        if case['name'] in ('low-word-product-wrap',
                            'physical-destination-word-wrap',
                            'physical-ret-overwrite'):
            oracle_require(expected_state['bx'] == 0x000F,
                           case['name'] + ': independent low-word map offset is not 000F')
        if not core and case['name'] in ('ret-overwrite', 'ret-overwrite-df',
                                         'physical-ret-overwrite'):
            oracle_require(expected_state['ip'] == (pattern[0] | (pattern[1] << 8)),
                           case['name'] + ': actual RET did not use overwritten map word')
        native_memory, actual_state = native_execute(
            native, bytearray(initial_memory), initial, core=core)
        boundary = 'core' if core else 'adapter'
        compare_state(case, actual_state, expected_state, boundary)
        compare_memory(case, native_memory, original_memory, boundary)
        geometric_check(case, original_memory, original_memory, pattern)
        if core:
            require(expected_state['ip'] == RET,
                    case['name'] + ': original core boundary is not before RET')
        else:
            require(expected_state['sp'] == ((initial['sp'] + 2) & 0xFFFF),
                    case['name'] + ': original adapter did not consume live RET word')
        gc.collect()
    return sorted(union_sites)


def input_hashes():
    paths = (
        'assets/vgalemmi.exe', 'metadata/symbols.json',
        'c/entity_pattern.c', 'c/entity_pattern.h', 'c/lemmings_sym.h', 'c/regs.h',
        'tests/entity_pattern.py', 'tests/dat_io_c.py', 'tests/dat_io.py', 'tools/cbuild.py', 'tools/difftest.py', 'tools/coverage.py',
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
    oracle_require(len(CODE) == 66 and len(INS) == 37,
                   'Entity pattern byte/site accounting changed')
    specs = cases()
    coverage, rows = set(), []
    baseline = Native(directory)
    for case in specs:
        sites = compare_case(baseline, case)
        coverage.update(sites)
        rows.append(dict(name=case['name'], executed_instruction_addresses=sites))
    oracle_require(coverage == set(INS), 'Entity pattern original site coverage differs')

    # Preserve a small original-only report as a separate scope. The main
    # differential report below is the native coverage artifact.
    original_before = input_hashes()
    write_json(ORIGINAL_REPORT, dict(image='main', image_sha256=sha(IMAGE),
        case_count=len(rows), auxiliary_core_cases=len(rows),
        translated_code_bytes=0, executed_instruction_addresses=sorted(coverage),
        branch_edges=[], cases=[r['name'] for r in rows], input_hashes=original_before,
        c_coverage_claimed=False))

    mutants = []
    witnesses = (
        (1, 'x-underflow', 'logical-shift'),
        (2, 'geometric-known', 'row-adjust'),
        (3, 'df-set', 'incoming-df'),
        (4, 'ret-overwrite', 'live-ret-prefetch'),
    )
    for mutation, name, label in witnesses:
        variant = Native(directory, mutation)
        case = next(row for row in specs if row['name'] == name)
        try:
            compare_case(variant, case)
        except NativeMismatch as error:
            mutants.append(dict(mutation=mutation, name=label, case=name,
                                mismatch=str(error), completed=True))
        else:
            raise OracleFailure(f'Entity pattern mutant {mutation} survived witness {name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after, 'Entity pattern test inputs changed during run')
    oracle_require(len(rows) == 37 and len(mutants) == 4,
                   'Entity pattern report scope changed')
    write_json(REPORT, dict(image='main', image_sha256=sha(IMAGE),
        case_count=len(rows), auxiliary_core_cases=len(rows),
        mutation_count=len(mutants), mutations=mutants,
        cases=rows, translated_code_bytes=66, native_code_ranges=[[ENTRY, END]],
        executed_instruction_addresses=sorted(coverage), branch_edges=[],
        instruction_sites=37,
        limits=dict(worker_seconds=180, windows_process_mib=384,
                    original_instruction_hook_limit=100),
        input_hashes=after,
        domains=['ordinary 1 MiB RAM; intact main image code 283B..287C',
                 'all general/segment/stack registers; final defined flags 0FD7',
                 'logical coordinate underflow and low-word row multiplication',
                 'DF clear/set with instruction-ordered MOVSW/MOVSB copies',
                 '16-bit offset and 20-bit physical word wrap',
                 'DS/SS overlap; coordinates read before stack writes',
                 'saved ES/DI/SI aliases and live RET overwrite',
                 'core stops before RET; adapter executes RET and stops at its target']))
    print(f'PASS entity pattern C: {len(rows)} cases, 66 bytes, 37 sites, '
          f'{len(mutants)} completed mutants', flush=True)


def main():
    BUILD.mkdir(exist_ok=True)
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if sys.argv[1:]:
        raise SystemExit('Unexpected entity pattern arguments')
    REPORT.unlink(missing_ok=True)
    ORIGINAL_REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-pattern-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=180, memory_mib=384)


if __name__ == '__main__':
    main()

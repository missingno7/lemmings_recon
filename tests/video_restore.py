"""Original-only and native contracts for the two INT10 video restore calls."""
import ast
import ctypes
import gc
import random
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
import capstone
import aligned_masked as fixture
import drawing_caller_oracle as drawing
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, read_json, sha, write_json
from dat_io_c import MEM, Regs
from unpack import ASSET, unpack, relocated

IMAGE, ORACLE = unpack(ASSET.read_bytes())
START, END = 0x0ff8, 0x1007
CODE = bytes.fromhex('a0e11f32e4cd10b405a0e21fcd10c3')
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {i.address: i for i in MD.disasm(CODE, START)}
LOADS = (0x1010, 0x1213, 0x2345)
FIELDS = ('value', 'base_value', 'count', 'argument', 'source_cursor',
          'output_cursor', 'frame_cursor', 'data_segment', 'extra_segment',
          'stack_segment', 'stack_offset', 'flags')
REGS = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'ds', 'es', 'ss', 'sp', 'flags')
FULL, LOGIC = 0xfd7, 0xfc7
REPORT = BUILD / 'video-restore-differential.json'
ORIGINAL_REPORT = BUILD / 'video-restore-contract-original.json'


class NativeMismatch(AssertionError):
    pass


def require(condition, message):
    if not condition:
        raise NativeMismatch(message)


def physical(segment, offset):
    return ((segment << 4) + (offset & 65535)) & 0xfffff


def putword(memory, segment, offset, value):
    p = physical(segment, offset)
    memory[p] = value & 255
    memory[(p + 1) & 0xfffff] = value >> 8


def cases():
    rows = [dict(name=f'mode-page-{n:02x}', seed=n, mode=n, page=(n * 37 + 17) & 255)
            for n in range(256)]
    for kind in ('live-page-same-ds', 'first-writes-return', 'second-writes-return',
                 'mode-ds-a20', 'page-ds-a20', 'ret-a20-word', 'ret-sp-ffff',
                 'ret-sp-zero', 'first-stack-wrap', 'second-register-boundaries',
                 'vga-mode', 'vga-page', 'vga-return', 'overwrite-initial-mode'):
        seed = len(rows)
        rows.append(dict(name=kind, kind=kind, seed=seed, mode=0x83, page=0xfa))
    for load in LOADS:
        for missing in ('no-services', 'missing-mode', 'missing-page'):
            rows.append(dict(name=f'{missing}-{load:04x}', missing=missing,
                             seed=len(rows), mode=0x8d, page=7, load=load))
    for row in rows:
        row.setdefault('load', LOADS[row['seed'] % 3])
    return rows


def prepare(case):
    rng = random.Random(0x0ff8 + case['seed'])
    memory = bytearray(rng.randbytes(1 << 20))
    load = case['load']
    loaded = relocated(IMAGE, ORACLE['relocations'], load)
    memory[load << 4:(load << 4) + len(loaded)] = loaded
    initial = {key: rng.randrange(65536) for key in REGS}
    first = {key: rng.randrange(65536) for key in REGS}
    second = {key: rng.randrange(65536) for key in REGS}
    for index, state in enumerate((initial, first, second)):
        state.update(ds=0x3000 + index * 0x1000, es=0x6100 + index * 0x100,
                     ss=0x7000 + index * 0x100, sp=0x8000 + index * 0x100)
        state['flags'] = 2 | ((case['seed'] * (0x95 + 8 * index) + index * 0x51) & 0xed5)
    kind = case.get('kind')
    if kind == 'live-page-same-ds': first['ds'] = initial['ds']
    if kind == 'first-writes-return': second.update(ss=initial['ss'], sp=initial['sp'])
    if kind == 'mode-ds-a20': initial['ds'] = 0xffff
    if kind == 'page-ds-a20': first['ds'] = 0xffff
    if kind == 'ret-a20-word': second.update(ss=0xffff, sp=0xf)
    if kind == 'ret-sp-ffff': second.update(ss=0x7000, sp=0xffff)
    if kind == 'ret-sp-zero': second.update(ss=0x7000, sp=0)
    if kind == 'first-stack-wrap': first.update(ss=0xffff, sp=0xffff)
    if kind == 'second-register-boundaries':
        second.update(ax=0xffff, bx=0, cx=0xffff, dx=0x8000, si=0xffff,
                      di=0, bp=0x7fff, ds=0xffff, es=0xffff)
    if kind == 'vga-mode': initial['ds'] = 0xa000
    if kind == 'vga-page': first['ds'] = 0xa000
    if kind == 'vga-return': second.update(ss=0xa000, sp=0x1fe2)
    putword(memory, initial['ss'], initial['sp'], (0xee00 + case['seed']) & 65535)
    putword(memory, first['ss'], first['sp'], (0xdd00 + case['seed']) & 65535)
    putword(memory, second['ss'], second['sp'], (0xd000 + case['seed']) & 65535)
    memory[physical(initial['ds'], 0x1fe1)] = case['mode']
    memory[physical(initial['ds'], 0x1fe2)] = case['page'] ^ 0xa5
    memory[physical(first['ds'], 0x1fe2)] = case['page']
    if kind == 'live-page-same-ds':
        memory[physical(initial['ds'], 0x1fe2)] = case['page'] ^ 0xa5
    return memory, initial, first, second


def device(memory, case):
    out = fixture.TraceDevice(bytearray(memory), 0xff800 + case['seed'], read_map=2)
    out.vga.seq[2] = 1
    out.vga.planes[2][0x1fe1] = case['mode']
    out.vga.planes[2][0x1fe2] = case['page']
    if case.get('kind') == 'vga-return':
        out.vga.planes[2][0x1fe2:0x1fe4] = b'\x23\xc1'
    return out


def provider_effect(case, stage, state, memory, initial, first, second):
    kind = case.get('kind')
    changed = []
    def word(segment, offset, value):
        putword(memory, segment, offset, value)
        p = physical(segment, offset)
        changed.extend((p, (p + 1) & 0xfffff))
    if stage == 0 and kind == 'live-page-same-ds':
        p = physical(first['ds'], 0x1fe2)
        memory[p] = case['page']
        changed.append(p)
    if stage == 0 and kind == 'first-writes-return':
        word(second['ss'], second['sp'], 0x55aa)
    if stage == 1 and kind == 'second-writes-return':
        word(second['ss'], second['sp'], 0x55cc)
    if stage == 0 and kind == 'overwrite-initial-mode':
        p = physical(initial['ds'], 0x1fe1)
        memory[p] ^= 255
        changed.append(p)
    return changed


def model(case, memory, initial, first, second, *, core):
    backend = device(memory, case)
    state = dict(initial)
    calls = []
    mask = FULL
    def byte(segment, offset):
        p = physical(segment, offset)
        value = backend.vga.read(backend.memory, p, state['flags'])
        backend.events.add('read', p, value, state['flags'], mask)
        return value
    state['ax'] = byte(state['ds'], 0x1fe1)
    state['flags'] = (state['flags'] & ~0x8c5) | 0x44
    mask = LOGIC
    missing = case.get('missing')
    if missing in ('no-services', 'missing-mode'):
        return backend, state, mask, calls, 0xffd, 1
    calls.append((0, dict(state), dict(first), mask))
    provider_effect(case, 0, state, backend.memory, initial, first, second)
    state = dict(first)
    mask = FULL
    state['ax'] = 0x500 | byte(state['ds'], 0x1fe2)
    if missing == 'missing-page':
        return backend, state, mask, calls, 0x1004, 2
    calls.append((1, dict(state), dict(second), mask))
    provider_effect(case, 1, state, backend.memory, initial, first, second)
    state = dict(second)
    if core:
        return backend, state, mask, calls, 0x1006, 0
    p = physical(state['ss'], state['sp'])
    values = []
    for address in (p, (p + 1) & 0xfffff):
        value = backend.vga.read(backend.memory, address, state['flags'])
        backend.events.add('read', address, value, state['flags'], mask)
        values.append(value)
    state['sp'] = (state['sp'] + 2) & 65535
    return backend, state, mask, calls, values[0] | (values[1] << 8), 0


def original(case, memory, initial, first, second, *, core):
    backend = device(memory, case)
    calls = []
    registers = {key: initial[key] for key in REGS if key != 'flags'}
    registers.update(cs=case['load'], ip=START)
    def interrupt(cpu, number, target):
        if number != 0x10 or len(calls) >= 2:
            raise fixture.VerificationFailure('Unexpected video interrupt')
        stage = len(calls)
        incoming = {key: cpu.reg_read(drawing.oracle.REG[key]) for key in REGS if key != 'flags'}
        incoming['flags'] = cpu.reg_read(drawing.x.UC_X86_REG_EFLAGS) & 65535
        if cpu.reg_read(drawing.oracle.REG['cs']) != case['load']:
            raise fixture.VerificationFailure('BIOS fixture did not return to original CS')
        output = first if stage == 0 else second
        calls.append((stage, incoming, dict(output), LOGIC if stage == 0 else FULL))
        for address in provider_effect(case, stage, incoming, target.memory,
                                       initial, first, second):
            value = bytes((target.memory[address],))
            cpu.mem_write(address, value)
            cpu.mem_write(address + (1 << 20), value)
        for key in REGS:
            reg = drawing.x.UC_X86_REG_EFLAGS if key == 'flags' else drawing.oracle.REG[key]
            cpu.reg_write(reg, output[key])
    missing = case.get('missing')
    stop = (0xffd if missing in ('no-services', 'missing-mode') else
            0x1004 if missing == 'missing-page' else 0x1006 if core else None)
    result = drawing.original(case, backend, registers, initial['flags'],
        instructions=INS, far_calls=set(), interrupt=interrupt, stop_before=stop,
        max_steps=20)
    regs, mask, sites, edges, boundary, *_ = result
    return backend, regs, mask, sites, calls, boundary


def equal_state(actual, expected, mask, fail, label):
    for key in REGS:
        mismatch = ((actual[key] ^ expected[key]) & mask) if key == 'flags' else actual[key] != expected[key]
        if mismatch: fail(label + ' ' + key + ' differs')


def equal_calls(actual, expected, fail, label):
    if len(actual) != len(expected): fail(label + ' provider call count differs')
    for got, want in zip(actual, expected):
        if got[0] != want[0]: fail(label + ' provider order differs')
        equal_state(got[1], want[1], want[3], fail, label + ' provider input')
        equal_state(got[2], want[2], FULL, fail, label + ' provider output')


def equal_device(actual, expected, fail, label):
    actual.check(label)
    expected.check(label)
    if actual.memory != expected.memory: fail(label + ' whole RAM differs')
    if actual.vga.state() != expected.vga.state(): fail(label + ' VGA state differs')
    try:
        fixture.compare_event_traces(actual.events, expected.events, label)
    except fixture.Mismatch as error:
        fail(str(error))


def original_case(case, *, core):
    memory, initial, first, second = prepare(case)
    expected = model(case, memory, initial, first, second, core=core)
    backend, state, mask, calls, target, status = expected
    actual_device, regs, actual_mask, sites, actual_calls, boundary = original(
        case, memory, initial, first, second, core=core)
    def fail(message): raise fixture.VerificationFailure(message)
    equal_state(regs, state, mask, fail, case['name'] + ' model')
    equal_calls(actual_calls, calls, fail, case['name'] + ' model')
    equal_device(actual_device, backend, fail, case['name'] + ' model')
    if (regs['cs'], regs['ip'], actual_mask) != (case['load'], target, mask):
        fail(case['name'] + ' original boundary/mask differs')
    if boundary[0] != ('ready-return' if core or status else 'outer-return'):
        fail(case['name'] + ' original stop kind differs')
    return (memory, initial, first, second, actual_device, regs, mask, sites,
            actual_calls, target, status)


class State(ctypes.Structure):
    _fields_ = [(key, ctypes.c_uint16) for key in FIELDS]


VIDEO = ctypes.CFUNCTYPE(None, ctypes.c_void_p, MEM, ctypes.POINTER(State), ctypes.POINTER(State))


class Services(ctypes.Structure):
    _fields_ = [('context', ctypes.c_void_p), ('set_mode', VIDEO), ('set_active_page', VIDEO)]


class Result(ctypes.Structure):
    _fields_ = [('state', State), ('continuation', ctypes.c_uint16), ('status', ctypes.c_int)]


def state_dict(state):
    return {reg: getattr(state, field) for reg, field in zip(REGS, FIELDS)}


def to_state(registers):
    return State(*(registers[key] for key in REGS))


def native_services(case, backend, initial, first, second):
    calls = []
    def provider(stage):
        @VIDEO
        def invoke(_context, _memory, incoming, outgoing):
            if len(calls) >= 2: fixture.exit_worker(86, 'Video provider trace budget exceeded')
            try:
                entry = state_dict(incoming[0])
                result = first if stage == 0 else second
                calls.append((stage, entry, dict(result), LOGIC if stage == 0 else FULL))
                provider_effect(case, stage, entry, backend.memory, initial, first, second)
                for field, reg in zip(FIELDS, REGS): setattr(outgoing[0], field, result[reg])
            except BaseException as error:
                fixture.exit_worker(87, f'Video provider callback failed: {error}')
        return invoke
    mode, page = provider(0), provider(1)
    missing = case.get('missing')
    service = (None if missing == 'no-services' else Services(None,
        VIDEO() if missing == 'missing-mode' else mode,
        VIDEO() if missing == 'missing-page' else page))
    return service, calls, (mode, page)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'video-restore-m{mutation}.dll', mutation, 'video_restore')
        self.library = ctypes.CDLL(str(path))
        self.core = self.library.lmn_restore_video_mode_page_core
        self.core.argtypes = [MEM, ctypes.POINTER(State), ctypes.POINTER(Services), ctypes.POINTER(fixture.RasterBus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_restore_video_mode_page_adapter
        self.adapter.argtypes = [MEM, ctypes.POINTER(Regs), ctypes.POINTER(Services), ctypes.POINTER(fixture.RasterBus)]
        self.adapter.restype = None


def buffer(memory): return (ctypes.c_uint8 * len(memory)).from_buffer(memory)
def pointer(value): return ctypes.byref(value) if value is not None else None


def compare(native, case):
    observed_sites = set()
    for core in (False, True):
        (memory, initial, first, second, expected, regs, mask, sites,
         expected_calls, target, status) = original_case(case, core=core)
        observed_sites.update(sites)
        for null_bus in (False, True):
            if null_bus and case.get('kind', '').startswith('vga-'): continue
            actual = device(memory, case)
            services, calls, references = native_services(case, actual, initial, first, second)
            bus = None if null_bus else ctypes.byref(actual.bus)
            if core:
                incoming = to_state(initial)
                out = native.core(buffer(actual.memory), ctypes.byref(incoming), pointer(services), bus)
                current = state_dict(out.state)
                require((out.continuation, out.status) == (target, status), case['name'] + ' core boundary differs')
            else:
                current_regs = Regs(**{k: v for k, v in initial.items() if k != 'flags'},
                                    cs=case['load'], ip=START, flags=initial['flags'])
                native.adapter(buffer(actual.memory), ctypes.byref(current_regs), pointer(services), bus)
                current = {key: getattr(current_regs, key) for key in REGS}
                require((current_regs.cs, current_regs.ip) == (case['load'], target),
                        case['name'] + ' adapter ip/cs differs')
            def fail(message): raise NativeMismatch(message)
            equal_state(current, regs, mask, fail, case['name'] + (' core' if core else ' adapter'))
            equal_calls(calls, expected_calls, fail, case['name'])
            if null_bus:
                require(actual.memory == expected.memory, case['name'] + ' null RAM differs')
            else:
                equal_device(actual, expected, fail, case['name'])
    return dict(name=case['name'], missing=case.get('missing'), sites=sorted(observed_sites),
                vga=case.get('kind', '').startswith('vga-'))


def input_hashes(native=False):
    # Progress prose is not consumed by the fixture or its contract.
    paths = {'tests/video_restore.py', 'tools/verify.py', 'tools/bounded_process.py',
             'docs/video-restore.md', 'docs/executable.md',
             'assets/vgalemmi.exe', 'metadata/oracle.json', 'metadata/symbols.json',
             'metadata/hints.json', 'metadata/regions.json', 'metadata/inputs.json',
             'metadata/toolchain-lock.json'}
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / 'src').glob('*.asm'))
    if native:
        paths.update(('c/video_restore.c', 'c/video_restore.h', 'c/regs.h',
                      'c/special_blit.h', 'c/lemmings_sym.h', 'tools/coverage.py', 'tools/difftest.py'))
    pending = [ROOT / p for p in paths if p.endswith('.py')]
    while pending:
        for node in ast.walk(ast.parse(pending.pop().read_text(encoding='utf-8-sig'))):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import) else
                     [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for name in names:
                for directory in ('tests', 'tools'):
                    path = ROOT / directory / (name.split('.')[0] + '.py')
                    key = path.relative_to(ROOT).as_posix()
                    if path.is_file() and key not in paths:
                        paths.add(key)
                        pending.append(path)
    return {p: sha((ROOT / p).read_bytes()) for p in sorted(paths)}


def original_phase():
    before = input_hashes()
    if (sha(IMAGE) != 'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e' or
            sha(ASSET.read_bytes()) != '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d' or
            ORACLE != read_json(ROOT / 'metadata/oracle.json')):
        raise fixture.VerificationFailure('Video contract executable identity differs')
    if IMAGE[START:END] != CODE or len(INS) != 7:
        raise fixture.VerificationFailure('Pinned video helper bytes differ')
    rows, sites = [], set()
    for case in cases():
        phase_sites = {}
        for core in (False, True):
            result = original_case(case, core=core)
            sites.update(result[7])
            phase_sites['core_sites' if core else 'adapter_sites'] = sorted(result[7])
        rows.append(dict(name=case['name'], **phase_sites))
        gc.collect()
    # The core intentionally leaves RET1006 unexecuted; count it from the
    # adapter comparison above, not from this last per-case core observation.
    if sites != set(INS): raise fixture.VerificationFailure('Video site coverage incomplete')
    if input_hashes() != before: raise fixture.VerificationFailure('Video oracle inputs changed')
    write_json(ORIGINAL_REPORT, dict(case_count=len(rows), auxiliary_core_cases=len(rows),
        executed_instruction_addresses=sorted(sites), branch_edges=[], byte_count=15,
        cases=rows, image_sha256=sha(IMAGE), routine_bytes=CODE.hex(),
        c_coverage_claimed=False, input_hashes=before))
    print(f'PASS video restore original: {len(rows)} cases,7 sites; no C coverage')


def worker(directory=None):
    fixture.MAX_BUS_EVENTS = 32
    fixture.MAX_VGA_EVENTS = 32
    drawing.common.MAX_VGA_EVENTS = 32
    before = input_hashes(native=directory is not None)
    original_phase()
    if directory is None: return
    native = Native(directory)
    specs, rows = cases(), []
    for case in specs:
        rows.append(compare(native, case))
        gc.collect()
    mutants = []
    witnesses = {1: specs[0], 2: specs[1],
                 3: next(c for c in specs if c.get('kind') == 'live-page-same-ds'),
                 4: next(c for c in specs if c.get('kind') == 'second-writes-return')}
    for mutation, case in witnesses.items():
        try:
            compare(Native(directory, mutation), case)
        except NativeMismatch as error:
            if mutation == 4: require('adapter ip/cs differs' in str(error), 'Need live RET witness')
            mutants.append(dict(mutation=mutation, case=case['name'], mismatch=str(error), completed=True))
        else:
            raise AssertionError(f'Video mutation{mutation} survived')
        gc.collect()
    if input_hashes(True) != before: raise fixture.VerificationFailure('Video native inputs changed')
    if len(rows) != 279: raise fixture.VerificationFailure('Video case matrix changed')
    write_json(REPORT, dict(image='main', image_sha256=sha(IMAGE), case_count=len(rows),
        auxiliary_core_cases=len(rows), null_bus_adapter_cases=sum(not r['vga'] for r in rows),
        cases=rows, mutation_count=len(mutants), mutations=mutants,
        routine=dict(start=START, end=END, byte_count=15, bytes=CODE.hex()),
        executed_instruction_addresses=sorted({p for row in rows for p in row['sites']}),
        branch_edges=[], translated_code_bytes=15,
        native_code_ranges=[[START, END]], input_hashes=before,
        limits=dict(worker_seconds=120, windows_process_mib=384, windows_tree_mib=640,
                    bus_events=32, provider_calls=2, original_instructions=20),
        domain='Both original INT10 boundaries with explicit returning providers, all general '
               'and DS/ES/SS/SP/flags effects, canonical RAM changes, live field/RET reads; '
               'providers resume in original CS, intact instructions, TFclear/quiescent IRQs.'))
    print(f'PASS video restore C: {len(rows)} cases,7 sites,4 completed mutants')


def main():
    BUILD.mkdir(exist_ok=True)
    if len(sys.argv) == 2 and sys.argv[1] == '--original-worker': worker(); return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker': worker(sys.argv[2]); return
    if sys.argv[1:] == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--original-worker'],
                    cwd=ROOT, timeout=120, memory_mib=384)
        return
    if len(sys.argv) != 1: raise SystemExit('Unexpected video restore arguments')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='video-restore-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=120, memory_mib=384)


if __name__ == '__main__': main()

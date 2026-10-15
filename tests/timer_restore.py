"""Independent model, pinned original execution, and bounded native timer restore."""
import ctypes
import gc
import random
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
import capstone
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INSN, UC_HOOK_INTR)
from unicorn import x86_const as x
import video_restore as common
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, sha, write_json
from dat_io_c import MEM, Regs
from unpack import ASSET, unpack, relocated

IMAGE, ORACLE = unpack(ASSET.read_bytes())
START, END, RET = 0x16a9, 0x16d4, 0x16d3
CODE = bytes.fromhex('1efab036e64332c0e640e64033c0c41ebe1f8ed8891e20008c062200fb1f8b0e9c258b169e25b401cd1ac3')
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
INS = {i.address: i for i in MD.disasm(CODE, START)}
REGS, FIELDS, FULL, LOGIC = common.REGS, common.FIELDS, common.FULL, common.LOGIC
State = common.State
PORT = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint16,
                        ctypes.c_uint8, ctypes.c_uint16)
CLOCK = ctypes.CFUNCTYPE(None, ctypes.c_void_p, MEM,
                         ctypes.POINTER(State), ctypes.POINTER(State))
REPORT = BUILD / 'timer-restore-differential.json'
ORIGINAL_REPORT = BUILD / 'timer-restore-contract-original.json'
SIZE = 1 << 20


class Services(ctypes.Structure):
    _fields_ = [('context', ctypes.c_void_p), ('out_byte', PORT), ('set_clock', CLOCK)]


class Result(ctypes.Structure):
    _fields_ = [('state', State), ('continuation', ctypes.c_uint16), ('status', ctypes.c_int)]


class NativeMismatch(AssertionError):
    pass


def oracle_fail(message): raise common.fixture.VerificationFailure(message)
def native_fail(message): raise NativeMismatch(message)


def cases():
    rows = [dict(name=f'incoming-ah-{n:02x}', seed=n) for n in range(256)]
    kinds = ('push-vector-offset', 'push-vector-segment', 'ivt-save-offset',
             'ivt-save-segment', 'ivt-return-offset', 'push-clock-high', 'push-clock-low',
             'vector-a20', 'push-sp-zero', 'push-sp-one', 'push-a20', 'ret-sp-ffff',
             'ret-a20', 'vector-ivt-overlap', 'bios-stack-zero', 'bios-stack-ffff',
             'bios-stack-a20', 'bios-write-return', 'bios-write-clock',
             'port-write-vector', 'port-write-stack', 'port-write-clock',
             'vga-vector-clock', 'vga-stack', 'vga-return', 'vga-clock-via-ivt')
    for kind in kinds: rows.append(dict(name=kind, kind=kind, seed=len(rows)))
    for load in common.LOADS:
        for missing in ('no-services', 'null-port', 'null-clock'):
            rows.append(dict(name=f'{missing}-{load:04x}', missing=missing,
                             seed=len(rows), load=load))
    for row in rows: row.setdefault('load', common.LOADS[row['seed'] % 3])
    return rows


def prepare(case):
    rng = random.Random(0x16a9 + case['seed'])
    memory = bytearray(rng.randbytes(SIZE))
    loaded = relocated(IMAGE, ORACLE['relocations'], case['load'])
    memory[case['load'] << 4:(case['load'] << 4) + len(loaded)] = loaded
    initial = {k: rng.randrange(65536) for k in REGS}
    output = {k: rng.randrange(65536) for k in REGS}
    initial.update(ax=((case['seed'] & 255) << 8) | rng.randrange(256),
                   ds=0x3000, es=0x6200, ss=0x7000, sp=0x8000,
                   flags=2 | ((case['seed'] * 0x95) & 0xed5))
    output.update(ds=0x5100, es=0x6300, ss=0x7300, sp=0x8200,
                  flags=2 | ((case['seed'] * 0x59 + 0x4d) & 0xed5))
    kind = case.get('kind')
    if kind == 'push-vector-offset': initial.update(ss=initial['ds'], sp=0x1fc0)
    if kind == 'push-vector-segment': initial.update(ss=initial['ds'], sp=0x1fc2)
    if kind in ('ivt-save-offset', 'vga-clock-via-ivt'): initial.update(ss=0, sp=0x22)
    if kind == 'ivt-save-segment': initial.update(ss=0, sp=0x24)
    if kind == 'ivt-return-offset': initial.update(ss=0, sp=0x20)
    if kind == 'push-clock-high': initial.update(ss=initial['ds'], sp=0x259e)
    if kind == 'push-clock-low': initial.update(ss=initial['ds'], sp=0x25a0)
    if kind == 'vector-a20': initial['ds'] = 0xffff
    if kind == 'vector-ivt-overlap': initial['ds'] = 0xfe06
    if kind == 'push-sp-zero': initial['sp'] = 0
    if kind == 'push-sp-one': initial['sp'] = 1
    if kind == 'push-a20': initial.update(ss=0xffff, sp=0x11)
    if kind == 'ret-sp-ffff': initial['sp'] = 0xffff
    if kind == 'ret-a20': initial.update(ss=0xffff, sp=0xf)
    if kind == 'vga-vector-clock': initial['ds'] = 0xa000
    if kind == 'vga-stack': initial['ss'] = 0xa000
    if not case['seed'] & 1 or kind in ('ivt-save-offset', 'ivt-save-segment',
            'ivt-return-offset', 'vga-stack', 'ret-sp-ffff', 'ret-a20', 'push-sp-one'):
        output.update(ss=initial['ss'], sp=initial['sp'])
    if kind == 'bios-stack-zero': output['sp'] = 0
    if kind == 'bios-stack-ffff': output['sp'] = 0xffff
    if kind == 'bios-stack-a20': output.update(ss=0xffff, sp=0xf)
    if kind == 'vga-return': output.update(ss=0xa000, sp=0x1000)
    vector = 0x4100 + case['seed'] * 7
    segment = 0x5100 + case['seed'] * 5
    if case['seed'] == 0: vector, segment = 0, 0xffff
    if case['seed'] == 255: vector, segment = 0xffff, 0
    if kind == 'vga-clock-via-ivt': vector = 0xa000
    for ds in {initial['ds'], vector, segment, 0x4500, 0x3000, 0x5500}:
        common.putword(memory, ds, 0x259c, (0x1234 + case['seed'] * 37) & 65535)
        common.putword(memory, ds, 0x259e, (0xfffe - case['seed'] * 19) & 65535)
    common.putword(memory, initial['ss'], initial['sp'], (0xee00 + case['seed']) & 65535)
    common.putword(memory, output['ss'], output['sp'], (0xe200 + case['seed']) & 65535)
    common.putword(memory, initial['ds'], 0x1fbe, vector)
    common.putword(memory, initial['ds'], 0x1fc0, segment)
    return memory, initial, output


def device(memory, case):
    backend = common.fixture.TraceDevice(bytearray(memory), 0x16a900 + case['seed'], read_map=2)
    backend.vga.seq[2] = 1
    if case.get('kind') == 'vga-vector-clock':
        common.putword(backend.vga.planes[2], 0, 0x1fbe, 0x4455)
        common.putword(backend.vga.planes[2], 0, 0x1fc0, 0x5566)
    common.putword(backend.vga.planes[2], 0, 0x259c, 0x1357)
    common.putword(backend.vga.planes[2], 0, 0x259e, 0x2468)
    if case.get('kind') == 'vga-stack':
        common.putword(backend.vga.planes[2], 0, 0x7ffe, 0x3000)
        common.putword(backend.vga.planes[2], 0, 0x8000, 0xd00d)
    if case.get('kind') == 'vga-return':
        common.putword(backend.vga.planes[2], 0, 0x1000, 0xd55d)
    return backend


def effect(case, phase, memory, initial, output):
    writes, kind = [], case.get('kind')
    if phase == 0 and kind == 'port-write-vector':
        writes = [(initial['ds'], 0x1fbe, 0x5500), (initial['ds'], 0x1fc0, 0x6600)]
    if phase == 2 and kind == 'port-write-stack':
        writes = [(initial['ss'], (initial['sp'] - 2) & 65535, 0x4500)]
    if phase == 2 and kind == 'port-write-clock':
        writes = [(initial['ds'], 0x259c, 0x8000), (initial['ds'], 0x259e, 0xffff)]
    if phase == 3 and kind == 'bios-write-return':
        writes = [(output['ss'], output['sp'], 0x5aa5)]
    if phase == 3 and kind == 'bios-write-clock':
        writes = [(initial['ds'], 0x259c, 0), (initial['ds'], 0x259e, 0x8000)]
    changed = []
    for segment, offset, value in writes:
        common.putword(memory, segment, offset, value)
        p = common.physical(segment, offset)
        changed.extend((p, (p + 1) & 0xfffff))
    return changed


def model(case, memory, initial, output, *, core):
    backend, state, ports, calls = device(memory, case), dict(initial), [], []
    mask = FULL
    def readword(segment, offset):
        values = []
        for p in (common.physical(segment, offset), (common.physical(segment, offset) + 1) & 0xfffff):
            value = backend.vga.read(backend.memory, p, state['flags'])
            backend.events.add('read', p, value, state['flags'], mask)
            values.append(value)
        return values[0] | values[1] << 8
    def writeword(segment, offset, value):
        p = common.physical(segment, offset)
        for address, byte in ((p, value & 255), ((p + 1) & 0xfffff, value >> 8)):
            backend.vga.write(backend.memory, address, byte, state['flags'])
            backend.events.add('write', address, byte, state['flags'], mask)
    def port(number, value):
        stage = len(ports)
        ports.append((number, value, state['flags'], mask))
        backend.events.add('out', number, value, state['flags'], mask)
        effect(case, stage, backend.memory, initial, output)
    state['sp'] = (state['sp'] - 2) & 65535
    writeword(state['ss'], state['sp'], state['ds'])
    state['flags'] &= ~0x200
    state['ax'] = (state['ax'] & 0xff00) | 0x36
    if case.get('missing') in ('no-services', 'null-port'):
        return backend, state, ports, calls, 0x16ad, 1, mask
    port(0x43, 0x36)
    state['ax'] &= 0xff00
    state['flags'] = (state['flags'] & ~0x8c5) | 0x44
    mask = LOGIC
    port(0x40, 0)
    port(0x40, 0)
    state['ax'] = 0
    state['bx'] = readword(state['ds'], 0x1fbe)
    state['es'] = readword(state['ds'], 0x1fc0)
    state['ds'] = 0
    writeword(0, 0x20, state['bx'])
    writeword(0, 0x22, state['es'])
    state['flags'] |= 0x200
    state['ds'] = readword(state['ss'], state['sp'])
    state['sp'] = (state['sp'] + 2) & 65535
    state['cx'] = readword(state['ds'], 0x259c)
    state['dx'] = readword(state['ds'], 0x259e)
    state['ax'] = 0x100
    if case.get('missing') == 'null-clock':
        return backend, state, ports, calls, 0x16d1, 1, mask
    calls.append((0, dict(state), dict(output), LOGIC))
    effect(case, 3, backend.memory, initial, output)
    state, mask = dict(output), FULL
    if core: return backend, state, ports, calls, RET, 0, mask
    target = readword(state['ss'], state['sp'])
    state['sp'] = (state['sp'] + 2) & 65535
    return backend, state, ports, calls, target, 0, mask


def original(case, memory, initial, output, *, core):
    backend, ports, calls, sites = device(memory, case), [], [], set()
    cpu = Uc(UC_ARCH_X86, UC_MODE_16)
    cpu.mem_map(0, SIZE * 2)
    cpu.mem_write(0, bytes(backend.memory) * 2)
    regs = dict(initial, cs=case['load'], ip=START)
    for key, value in regs.items():
        cpu.reg_write(x.UC_X86_REG_EFLAGS if key == 'flags' else common.drawing.oracle.REG[key], value)
    code_bytes = {(case['load'] << 4) + p + n: IMAGE[p + n]
                  for p, ins in INS.items() for n in range(ins.size)}
    if any(backend.memory[p] != v for p, v in code_bytes.items()): oracle_fail('Modified timer code at entry')
    mask, event_flags, previous, done, returned = FULL, initial['flags'], None, False, False
    stop = (0x16ad if case.get('missing') in ('no-services', 'null-port') else
            0x16d1 if case.get('missing') == 'null-clock' else RET if core else None)
    failure = []
    def fail(error):
        if not failure: failure.append(str(error))
        cpu.emu_stop()
    def sync(addresses):
        for p in addresses:
            value = bytes((backend.memory[p],))
            cpu.mem_write(p, value)
            cpu.mem_write(p + SIZE, value)
        if any(backend.memory[p] != v for p, v in code_bytes.items()): oracle_fail('Provider changed timer code')
    def code(uc, _pc, _size, _user):
        nonlocal mask, event_flags, previous, done, returned
        if previous in (0x16af, 0x16b5): mask = LOGIC
        off, cs = uc.reg_read(x.UC_X86_REG_IP), uc.reg_read(x.UC_X86_REG_CS)
        if returned:
            done = True; uc.emu_stop(); return
        if cs != case['load'] or off not in INS: fail(f'Timer original escaped at {cs:04x}:{off:04x}'); return
        if off == stop:
            done = True; uc.emu_stop(); return
        if len(sites) >= 19: fail('Timer original instruction budget'); return
        sites.add(off)
        event_flags, previous = uc.reg_read(x.UC_X86_REG_EFLAGS), off
        if off == RET: returned = True
    def read(uc, _access, address, size, _value, _user):
        try:
            for n in range(size):
                raw, p = address + n, (address + n) & 0xfffff
                value = backend.vga.read(backend.memory, p, event_flags)
                backend.events.add('read', p, value, event_flags, mask)
                uc.mem_write(raw, bytes((value,)))
            backend.check('timer original read')
        except BaseException as error: fail(error)
    def write(uc, _access, address, size, value, _user):
        try:
            for n in range(size):
                p, byte = (address + n) & 0xfffff, (value >> (8 * n)) & 255
                if p in code_bytes and code_bytes[p] != byte: oracle_fail('Timer wrote decoded code')
                backend.vga.write(backend.memory, p, byte, event_flags)
                backend.events.add('write', p, byte, event_flags, mask)
                sync((p,))
            backend.check('timer original write')
        except BaseException as error: fail(error)
    def out(_uc, port, size, value, _user):
        try:
            if size != 1 or len(ports) >= 3: oracle_fail('Unexpected timer port output')
            stage = len(ports)
            ports.append((port, value, event_flags, mask))
            backend.events.add('out', port, value, event_flags, mask)
            sync(effect(case, stage, backend.memory, initial, output))
        except BaseException as error: fail(error)
    def interrupt(uc, number, _user):
        nonlocal mask
        try:
            if number != 0x1a or calls: oracle_fail('Unexpected timer interrupt')
            incoming = {k: uc.reg_read(x.UC_X86_REG_EFLAGS if k == 'flags' else common.drawing.oracle.REG[k]) & 65535 for k in REGS}
            calls.append((0, incoming, dict(output), LOGIC))
            sync(effect(case, 3, backend.memory, initial, output))
            for key in REGS:
                uc.reg_write(x.UC_X86_REG_EFLAGS if key == 'flags' else common.drawing.oracle.REG[key], output[key])
            mask = FULL
        except BaseException as error: fail(error)
    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    cpu.hook_add(UC_HOOK_INSN, out, None, 1, 0, x.UC_X86_INS_OUT)
    cpu.hook_add(UC_HOOK_INTR, interrupt)
    cpu.emu_start((case['load'] << 4) + START, 0, count=24)
    if failure: oracle_fail(f'{case["name"]}: {failure[0]}')
    if not done: oracle_fail('Timer original did not reach declared boundary')
    regs = {k: cpu.reg_read(x.UC_X86_REG_EFLAGS if k == 'flags' else common.drawing.oracle.REG[k]) & 65535 for k in (*REGS, 'cs', 'ip')}
    return backend, regs, ports, calls, mask, sites


def equal_ports(actual, expected, fail, label):
    if len(actual) != len(expected): fail(label + ' port count differs')
    for got, want in zip(actual, expected):
        if got[:2] != want[:2] or (got[2] ^ want[2]) & want[3]: fail(label + ' port value/order/flags differ')


def original_case(case, *, core):
    memory, initial, output = prepare(case)
    expected, state, ports, calls, target, status, mask = model(case, memory, initial, output, core=core)
    backend, regs, observed_ports, observed_calls, actual_mask, sites = original(case, memory, initial, output, core=core)
    common.equal_state(regs, state, mask, oracle_fail, case['name'] + ' model')
    common.equal_device(backend, expected, oracle_fail, case['name'] + ' model')
    common.equal_calls(observed_calls, calls, oracle_fail, case['name'] + ' model')
    equal_ports(observed_ports, ports, oracle_fail, case['name'] + ' model')
    if (regs['cs'], regs['ip'], actual_mask) != (case['load'], target, mask): oracle_fail(case['name'] + ' original boundary/mask differs')
    return memory, initial, output, backend, regs, observed_ports, observed_calls, target, status, mask, sites


def native_services(case, backend, initial, output):
    ports, calls = [], []
    @PORT
    def port(_context, number, value, flags):
        if len(ports) >= 3: common.fixture.exit_worker(86, 'Timer port budget exhausted')
        try:
            stage = len(ports)
            ports.append((number, value, flags, FULL if stage == 0 else LOGIC))
            backend.events.add('out', number, value, flags)
            effect(case, stage, backend.memory, initial, output)
        except BaseException as error: common.fixture.exit_worker(87, f'Timer port callback: {error}')
    @CLOCK
    def clock(_context, _memory, incoming, outgoing):
        if calls: common.fixture.exit_worker(86, 'Timer clock budget exhausted')
        try:
            calls.append((0, common.state_dict(incoming[0]), dict(output), LOGIC))
            effect(case, 3, backend.memory, initial, output)
            for field, key in zip(FIELDS, REGS): setattr(outgoing[0], field, output[key])
        except BaseException as error: common.fixture.exit_worker(87, f'Timer BIOS callback: {error}')
    missing = case.get('missing')
    service = None if missing == 'no-services' else Services(None,
        PORT() if missing == 'null-port' else port, CLOCK() if missing == 'null-clock' else clock)
    return service, ports, calls, (port, clock)


class Native:
    def __init__(self, directory, mutation=0):
        self.library = ctypes.CDLL(str(build(Path(directory) / f'timer-restore-m{mutation}.dll', mutation, 'timer_restore')))
        self.core = self.library.lmn_restore_timer_state_core
        self.core.argtypes = [MEM, ctypes.POINTER(State), ctypes.POINTER(Services), ctypes.POINTER(common.fixture.RasterBus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_restore_timer_state_adapter
        self.adapter.argtypes = [MEM, ctypes.POINTER(Regs), ctypes.POINTER(Services), ctypes.POINTER(common.fixture.RasterBus)]


def compare(native, case):
    observed_sites = set()
    vga = case.get('kind', '').startswith('vga-')
    for core in (False, True):
        memory, initial, output, expected, regs, ports, calls, target, status, mask, sites = original_case(case, core=core)
        observed_sites.update(sites)
        for null in (False, True):
            if null and vga: continue
            backend = device(memory, case)
            service, actual_ports, actual_calls, refs = native_services(case, backend, initial, output)
            bus = None if null else ctypes.byref(backend.bus)
            if core:
                state = common.to_state(initial)
                result = native.core(common.buffer(backend.memory), ctypes.byref(state), common.pointer(service), bus)
                current = common.state_dict(result.state)
                if (result.continuation, result.status) != (target, status): native_fail(case['name'] + ' core boundary differs')
            else:
                current_regs = Regs(**{k: v for k, v in initial.items() if k != 'flags'}, cs=case['load'], ip=START, flags=initial['flags'])
                native.adapter(common.buffer(backend.memory), ctypes.byref(current_regs), common.pointer(service), bus)
                current = {k: getattr(current_regs, k) for k in REGS}
                if (current_regs.cs, current_regs.ip) != (case['load'], target): native_fail(case['name'] + ' adapter ip/cs differs')
            label = case['name'] + (' core' if core else ' adapter')
            common.equal_state(current, regs, mask, native_fail, label)
            common.equal_calls(actual_calls, calls, native_fail, label)
            equal_ports(actual_ports, ports, native_fail, label)
            if null:
                if backend.memory != expected.memory: native_fail(label + ' null RAM differs')
            else: common.equal_device(backend, expected, native_fail, label)
    return dict(name=case['name'], sites=sorted(observed_sites), vga=vga, missing=case.get('missing'))


def input_hashes(native=False):
    paths = set(common.input_hashes(False))
    paths.update(('tests/timer_restore.py', 'docs/timer-restore.md'))
    if native: paths.update(('c/timer_restore.c', 'c/timer_restore.h', 'c/lemmings_sym.h',
                             'c/regs.h', 'c/special_blit.h', 'tools/cbuild.py', 'tools/difftest.py', 'tools/coverage.py'))
    return {p: sha((ROOT / p).read_bytes()) for p in sorted(paths)}


def original_phase():
    before = input_hashes()
    if sha(ASSET.read_bytes()) != '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d': oracle_fail('Pinned EXE changed')
    if sha(IMAGE) != 'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e' or IMAGE[START:END] != CODE: oracle_fail('Timer code identity changed')
    sites, rows = set(), []
    for case in cases():
        for core in (False, True):
            result = original_case(case, core=core)
            sites.update(result[-1])
        rows.append(case['name'])
        gc.collect()
    if len(INS) != 19 or sites != set(INS): oracle_fail('Timer original site coverage differs')
    if before != input_hashes(): oracle_fail('Timer original inputs changed')
    write_json(ORIGINAL_REPORT, dict(image='main', image_sha256=sha(IMAGE), case_count=len(rows),
        auxiliary_core_cases=len(rows), executed_instruction_addresses=sorted(sites), branch_edges=[],
        routine_bytes=CODE.hex(), cases=rows, input_hashes=before, c_coverage_claimed=False))
    print(f'PASS timer restore original: {len(rows)} cases,19 sites;no C coverage', flush=True)


def worker(directory=None):
    common.fixture.MAX_BUS_EVENTS = 64
    common.fixture.MAX_VGA_EVENTS = 64
    before = input_hashes(directory is not None)
    original_phase()
    if directory is None: return
    native, rows, specs = Native(directory), [], cases()
    for case in specs:
        rows.append(compare(native, case)); gc.collect()
    mutants = []
    for mutation, name in ((1, 'incoming-ah-00'), (2, 'ivt-save-offset'),
                            (3, 'ivt-save-segment'), (4, 'bios-stack-a20')):
        variant = Native(directory, mutation)
        case = next(c for c in specs if c['name'] == name)
        try: compare(variant, case)
        except NativeMismatch as error:
            if mutation == 4 and 'adapter ip/cs differs' not in str(error): oracle_fail('Need actual live RET witness')
            mutants.append(dict(mutation=mutation, case=name, mismatch=str(error), completed=True))
        else: oracle_fail(f'Timer mutant {mutation} survived')
        gc.collect()
    if before != input_hashes(True): oracle_fail('Timer native inputs changed')
    if len(rows) != 291: oracle_fail('Timer case matrix changed')
    write_json(REPORT, dict(image='main', image_sha256=sha(IMAGE), case_count=len(rows),
        auxiliary_core_cases=len(rows), null_bus_adapter_cases=sum(not r['vga'] for r in rows),
        mutation_count=len(mutants), mutations=mutants, cases=rows, translated_code_bytes=43,
        native_code_ranges=[[START, END]], routine_bytes=CODE.hex(),
        executed_instruction_addresses=sorted({p for r in rows for p in r['sites']}), branch_edges=[],
        limits=dict(worker_seconds=120, windows_process_mib=384, windows_tree_mib=640,
                    original_instructions=24, bus_events=64, port_calls=3, bios_calls=1), input_hashes=before,
        domain='Intact-code/TFclear/quiescentIRQ PIT/IVT/clock restore; explicit byte-output and returning INT1A providers; '
               'all GPR/DS/ES/SS/SP/definedflags and canonical RAM/VGA effects; live stack/IVT aliases and actualRET.'))
    print(f'PASS timer restore C: {len(rows)} cases,19 sites,4 completed mutants', flush=True)


def main():
    BUILD.mkdir(exist_ok=True)
    if sys.argv[1:] == ['--original-worker']: worker(); return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker': worker(sys.argv[2]); return
    if sys.argv[1:] == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--original-worker'], cwd=ROOT, timeout=120, memory_mib=384)
        return
    if len(sys.argv) != 1: raise SystemExit('Unexpected timer restore arguments')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='timer-restore-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory], cwd=ROOT, timeout=120, memory_mib=384)


if __name__ == '__main__': main()

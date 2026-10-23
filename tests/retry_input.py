"""Frame-free retry input wait: pinned ASM, scalar model and native core."""
import ctypes
import gc
import random
import subprocess
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import x86_const as x
import video_restore as common
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, sha, read_json, write_json
from unpack import ASSET, relocated

IMAGE, ORACLE = common.IMAGE, common.ORACLE
START, POLL, END = 0x4b3b, 0x4b40, 0x4b50
CODE = bytes.fromhex('c606d01f00a11400a9070075088a26d01f22e474f0')
INS = {i.address: i for i in common.MD.disasm(CODE, START)}
EDGES = {(0x4b46, 0x4b48), (0x4b46, END), (0x4b4e, POLL), (0x4b4e, END)}
FULL, LOGIC = common.FULL, common.LOGIC
REPORT = BUILD / 'retry-input-differential.json'
ORIGINAL_REPORT = BUILD / 'retry-input-contract-original.json'
MEM, Regs = common.MEM, common.Regs


class Result(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in ('value', 'flags', 'continuation')]


class Mismatch(AssertionError):
    pass


def fail(message):
    raise common.fixture.VerificationFailure(message)


def mismatch(message):
    raise Mismatch(message)


def cases():
    out = []
    def add(name, **kw):
        out.append(dict(name=name, seed=len(out), **kw))
    for n in range(256):
        add(f'buttons-{n:02x}', buttons=((n ^ 0x55) << 8) | n, scan=0xa5)
    for n in range(1, 256):
        add(f'scan-{n:02x}', buttons=0x8000 | ((n & 31) << 3), scan=n)
    for n in range(256):
        add(f'reset-{n:02x}', clear=True, buttons=0xa501, scan=n)
    for clear in (False, True):
        for kind in ('delayed-buttons', 'delayed-scan', 'word-high-live',
                     'scan-read-changes-buttons', 'reset-provider', 'ds-a20',
                     'ss-alias-buttons', 'ss-alias-scan', 'sp-zero', 'sp-ffff',
                     'vga-mode0', 'vga-mode1'):
            add(f'{int(clear)}-{kind}', clear=clear, kind=kind,
                buttons=0 if kind in ('delayed-buttons', 'delayed-scan',
                                      'scan-read-changes-buttons', 'reset-provider') else 0x1201,
                scan=0, delay=17)
    for row in out:
        row.setdefault('clear', False)
        row.setdefault('load', common.LOADS[row['seed'] % 3])
    return out


def prepare(case):
    rng = random.Random(0x4b3b00 + case['seed'])
    memory = bytearray(rng.randbytes(1 << 20))
    load = case['load']; data = relocated(IMAGE, ORACLE['relocations'], load)
    memory[load << 4:(load << 4) + len(data)] = data
    s = {k: rng.randrange(65536) for k in common.REGS}
    s.update(ds=0x4000, ss=0x7000, sp=0x8000,
             flags=2 | (((case['seed'] * 149) ^ 0xad5) & 0xed5))
    kind = case.get('kind', '')
    if kind == 'ds-a20': s['ds'] = 0xffff
    if kind.startswith('vga-'): s['ds'] = 0xa000
    if kind.startswith('ss-alias-'):
        s.update(ss=s['ds'], sp=0x14 if kind.endswith('buttons') else 0x1fd0)
    if kind.startswith('sp-'): s['sp'] = 0 if kind == 'sp-zero' else 65535
    common.putword(memory, s['ds'], 0x14, case['buttons'])
    memory[common.physical(s['ds'], 0x1fd0)] = case['scan']
    return memory, s


class Backend:
    def __init__(self, memory, case, initial, native=False):
        self.memory = bytearray(memory); self.case = case; self.initial = initial
        self.native = native; self.events = []; self.changed = set()
        self.button_reads = self.scan_reads = 0; self.effect = False
        self.vga = common.fixture.MinimapVga(0x4b3b + case['seed'], 2)
        self.vga.seq[2] = 15; self.vga.gc[0] = self.vga.gc[1] = self.vga.gc[3] = 0
        self.vga.gc[5] = int(case.get('kind') == 'vga-mode1'); self.vga.gc[8] = 255
        for off in (0x14, 0x15, 0x1fd0):
            self.vga.planes[2][off] = memory[common.physical(initial['ds'], off)]

    def add(self, kind, address, value, flags, mask):
        if len(self.events) >= 1024:
            if self.native: common.fixture.exit_worker(86, 'Retry input access budget exhausted')
            fail('Retry input original access budget exhausted')
        self.events.append((kind, address, value, flags, mask))

    def store(self, address, value):
        address &= 0xfffff; self.memory[address] = value; self.changed.add(address)
        if 0xa0000 <= address < 0xb0000:
            for plane in self.vga.planes: plane[address - 0xa0000] = value

    def read(self, address, flags, mask):
        address &= 0xfffff
        value = self.vga.read(self.memory, address, flags)
        self.add('read', address, value, flags, mask)
        p = common.physical(self.initial['ds'], 0x14)
        latch = common.physical(self.initial['ds'], 0x1fd0)
        kind = self.case.get('kind')
        if address == p:
            self.button_reads += 1
            if kind == 'word-high-live' and not self.effect:
                self.store(p + 1, 0xa5); self.effect = True
        if address == latch:
            self.scan_reads += 1
            if kind == 'scan-read-changes-buttons' and self.scan_reads == 1:
                self.store(p, 1)
            if kind in ('delayed-buttons', 'delayed-scan', 'scan-read-changes-buttons', 'reset-provider'):
                delay = 1 if kind == 'scan-read-changes-buttons' else self.case.get('delay', 17)
                if self.scan_reads == delay:
                    self.store(latch if kind == 'delayed-scan' else p, 4 if kind != 'delayed-scan' else 0x80)
                # A second finite event also makes the stale-button mutant terminate.
                if self.scan_reads == delay + 1: self.store(latch, 1)
        return value

    def write(self, address, value, flags, mask):
        address &= 0xfffff
        self.add('write', address, value, flags, mask)
        self.vga.write(self.memory, address, value, flags); self.changed.add(address)
        if self.case.get('kind') == 'reset-provider':
            self.store(common.physical(self.initial['ds'], 0x14), 2)

    def bus(self, empty_read=False, empty_write=False):
        @common.fixture.READ
        def read(_ctx, _memory, address, flags):
            try: return self.read(address, flags, FULL)
            except BaseException as e: common.fixture.exit_worker(87, f'Retry read callback: {e}')
        @common.fixture.WRITE
        def write(_ctx, _memory, address, value, flags):
            try: self.write(address, value, flags, FULL)
            except BaseException as e: common.fixture.exit_worker(87, f'Retry write callback: {e}')
        self.callbacks = (read, write)
        return common.fixture.RasterBus(None, common.fixture.READ() if empty_read else read,
            common.fixture.WRITE() if empty_write else write, common.fixture.OUT())


def logic(flags, value, width):
    f = (4 if (value & 255).bit_count() % 2 == 0 else 0) | (0x40 if value == 0 else 0)
    f |= 0x80 if value & (1 << (width - 1)) else 0
    return (flags & ~0x8d5) | f


def model(case, memory, initial):
    b = Backend(memory, case, initial); s = dict(initial); mask = FULL
    p = common.physical(s['ds'], 0x14); latch = common.physical(s['ds'], 0x1fd0)
    if case['clear']: b.write(latch, 0, s['flags'], mask)
    for _ in range(128):
        low = b.read(p, s['flags'], mask); high = b.read(p + 1, s['flags'], mask)
        s['ax'] = low | (high << 8); pressed = s['ax'] & 7
        s['flags'] = logic(s['flags'], pressed, 16); mask = LOGIC
        if pressed: return b, s
        scan = b.read(latch, s['flags'], mask)
        s['ax'] = (scan << 8) | low; s['flags'] = logic(s['flags'], scan, 8)
        if scan: return b, s
    fail('Scalar retry input fixture did not converge')


def original(case, memory, initial):
    b = Backend(memory, case, initial); u = Uc(UC_ARCH_X86, UC_MODE_16)
    u.mem_map(0, 2 << 20); u.mem_write(0, bytes(memory) * 2)
    start = START if case['clear'] else POLL
    for k, v in dict(initial, cs=case['load'], ip=start).items():
        u.reg_write(x.UC_X86_REG_EFLAGS if k == 'flags' else common.drawing.oracle.REG[k], v)
    code_bytes = {common.physical(case['load'], p + n): IMAGE[p + n]
                  for p, ins in INS.items() for n in range(ins.size)}
    if any(memory[p] != v for p, v in code_bytes.items()): fail('Retry input entered changed code')
    mask = FULL; event_flags = initial['flags']; previous = None
    sites = set(); edges = set(); errors = []; done = False; steps = 0
    def error(e):
        if not errors: errors.append(str(e))
        u.emu_stop()
    def sync(skip=()):
        remaining = set()
        for p in b.changed:
            if p in code_bytes and b.memory[p] != code_bytes[p]: fail('Retry provider changed decoded code')
            if p in skip:
                remaining.add(p); continue
            value = bytes((b.memory[p],)); u.mem_write(p, value); u.mem_write(p + (1 << 20), value)
        b.changed = remaining
    def code(cpu, _p, _size, _ctx):
        nonlocal previous, mask, event_flags, done, steps
        sync()  # Publish provider writes after the preceding instruction consumed its returned bytes.
        off = cpu.reg_read(x.UC_X86_REG_IP)
        if previous in (0x4b43, 0x4b4c): mask = LOGIC
        if previous in (0x4b46, 0x4b4e): edges.add((previous, off))
        if off == END: done = True; cpu.emu_stop(); return
        if cpu.reg_read(x.UC_X86_REG_CS) != case['load'] or off not in INS:
            error('Retry input escaped'); return
        steps += 1
        if steps > 1024: error('Retry instruction budget exhausted'); return
        previous = off; sites.add(off); event_flags = cpu.reg_read(x.UC_X86_REG_EFLAGS)
    def read(cpu, _access, address, size, _value, _ctx):
        try:
            # A provider may update the same canonical byte after returning its
            # old value. Inject that returned value for this instruction and
            # restore canonical memory at the following instruction boundary.
            values = [b.read(address + n, event_flags, mask) for n in range(size)]
            span = {(address + n) & 0xfffff for n in range(size)}
            sync(span)
            for n, value in enumerate(values):
                cpu.mem_write(address + n, bytes((value,)))
                if value != b.memory[(address + n) & 0xfffff]: b.changed.add((address + n) & 0xfffff)
        except BaseException as e: error(e)
    def write(_cpu, _access, address, size, value, _ctx):
        try:
            for n in range(size): b.write(address + n, (value >> (8 * n)) & 255, event_flags, mask)
            sync({(address + n) & 0xfffff for n in range(size)})
        except BaseException as e: error(e)
    u.hook_add(UC_HOOK_CODE, code); u.hook_add(UC_HOOK_MEM_READ, read); u.hook_add(UC_HOOK_MEM_WRITE, write)
    u.emu_start((case['load'] << 4) + start, 0, count=1025)
    if errors or not done: fail(case['name'] + ': ' + (errors[0] if errors else 'Original did not stop'))
    if bytes(u.mem_read(0, 1 << 20)) != b.memory: fail(case['name'] + ': Original RAM mirror differs')
    regs = {k: u.reg_read(x.UC_X86_REG_EFLAGS if k == 'flags' else common.drawing.oracle.REG[k]) & 65535
            for k in (*common.REGS, 'cs', 'ip')}
    return b, regs, sites, edges


def equal(got, expected, error, label, events=True, include=None):
    if got.memory != expected.memory: error(label + ' RAM differs')
    if got.vga.state() != expected.vga.state(): error(label + ' VGA differs')
    if events:
        actual = [e for e in got.events if include is None or e[0] in include]
        wanted = [e for e in expected.events if include is None or e[0] in include]
        if len(actual) != len(wanted): error(label + ' event count differs')
        for a, b in zip(actual, wanted):
            if a[:3] != b[:3] or (a[3] ^ b[3]) & b[4]: error(label + f' phase event differs {a}/{b}')


class Native:
    def __init__(self, directory, mutation=0):
        self.lib = ctypes.CDLL(str(build(Path(directory) / f'retry-input-m{mutation}.dll', mutation, 'retry_input')))
        self.cores = [self.lib.lmn_wait_retry_input_core, self.lib.lmn_clear_and_wait_retry_input_core]
        for core in self.cores:
            core.argtypes = [MEM, ctypes.c_uint16, ctypes.c_uint16, ctypes.POINTER(common.fixture.RasterBus)]
            core.restype = Result
        self.adapter = self.lib.lmn_retry_input_adapter
        self.adapter.argtypes = [MEM, ctypes.POINTER(Regs), ctypes.c_int, ctypes.POINTER(common.fixture.RasterBus)]
        self.adapter.restype = None


def compare(native, case):
    memory, s = prepare(case); expected, scalar = model(case, memory, s)
    b, regs, sites, edges = original(case, memory, s)
    common.equal_state(regs, scalar, LOGIC, fail, case['name'] + ' scalar')
    equal(b, expected, fail, case['name'] + ' scalar')
    if (regs['cs'], regs['ip']) != (case['load'], END): fail('Original wait continuation differs')
    if case.get('kind', '').startswith('vga-'):
        before = Backend(memory, case, s)
        for index in range(4):
            want = before.vga.planes[index][0x1fd0]
            if case['clear']: want = before.vga.latches[index] if case['kind'] == 'vga-mode1' else 0
            if b.vga.planes[index][0x1fd0] != want: fail('Independent VGA reset formula differs')
        if b.vga.latches != [p[0x15] for p in b.vga.planes]: fail('Independent VGA word-read latches differ')
    null_repeat = not case.get('kind')
    if native:
        for core in (False, True):
            for fallback in (('bus', 'null', 'empty', 'read-only', 'write-only') if null_repeat else ('bus',)):
                d = Backend(memory, case, s, native=True)
                bus = d.bus(empty_read=fallback in ('empty', 'write-only'), empty_write=fallback in ('empty', 'read-only'))
                pointer = None if fallback == 'null' else ctypes.byref(bus)
                if core:
                    r = native.cores[int(case['clear'])](common.buffer(d.memory), s['ds'], s['flags'], pointer)
                    got = dict(s, ax=r.value, flags=r.flags, cs=case['load'], ip=r.continuation)
                else:
                    r = Regs(**s, cs=case['load'], ip=START if case['clear'] else POLL)
                    native.adapter(common.buffer(d.memory), ctypes.byref(r), int(case['clear']), pointer)
                    got = {k: getattr(r, k) for k in (*common.REGS, 'cs', 'ip')}
                common.equal_state(got, regs, LOGIC, mismatch, case['name'])
                if (got['cs'], got['ip']) != (case['load'], END): raise Mismatch('Adapter/core continuation differs')
                equal(d, b, mismatch, case['name'], events=fallback not in ('null', 'empty'),
                      include={'read'} if fallback == 'read-only' else {'write'} if fallback == 'write-only' else None)
    return dict(name=case['name'], clear=case['clear'], sites=sorted(sites), edges=sorted(edges),
                null_repeat=null_repeat, events=len(b.events))


def word_matrix(native=None):
    """One reused read-only machine; no instruction histories or per-pair RAM clones."""
    u = Uc(UC_ARCH_X86, UC_MODE_16); u.mem_map(0, 1 << 20)
    load = 0x1010; base = load << 4; ds = 0x4000; p = common.physical(ds, 0x14)
    memory = bytearray(1 << 20); data = relocated(IMAGE, ORACLE['relocations'], load)
    memory[base:base + len(data)] = data; memory[common.physical(ds, 0x1fd0)] = 0x81
    u.mem_write(0, bytes(memory)); buffer = common.buffer(memory)
    for word in range(65536):
        flags = 2 | ((word * 149) & 0xed5); raw = word.to_bytes(2, 'little')
        u.mem_write(p, raw); memory[p:p + 2] = raw
        for reg, value in ((x.UC_X86_REG_CS, load), (x.UC_X86_REG_DS, ds),
                           (x.UC_X86_REG_IP, POLL), (x.UC_X86_REG_AX, 0x5aa5),
                           (x.UC_X86_REG_EFLAGS, flags)):
            u.reg_write(reg, value)
        u.emu_start(base + POLL, base + END, count=12)
        pressed = word & 7; value = word if pressed else (word & 255) | 0x8100
        expected = logic(flags, pressed if pressed else 0x81, 16 if pressed else 8)
        if (u.reg_read(x.UC_X86_REG_IP), u.reg_read(x.UC_X86_REG_AX)) != (END, value): fail('Word matrix original AX/IP differs')
        if (u.reg_read(x.UC_X86_REG_EFLAGS) ^ expected) & LOGIC: fail('Word matrix original flags differ')
        if native:
            r = native.cores[0](buffer, ds, flags, None)
            if (r.value, r.continuation) != (value, END) or (r.flags ^ expected) & LOGIC: raise Mismatch('Word matrix C differs')
    if bytes(u.mem_read(0, 1 << 20)) != memory: fail('Read-only word matrix changed RAM')
    return 65536


def producer_matrix():
    """Original-only 16FE..1759 keyboard producer prefix, before bitmap lookup."""
    u = Uc(UC_ARCH_X86, UC_MODE_16); u.mem_map(0, 1 << 20)
    load = 0x1213; ds = 0x4000; base = load << 4
    u.mem_write(base, relocated(IMAGE, ORACLE['relocations'], load))
    sites = set(); writes = []; instructions = {i.address for i in common.MD.disasm(IMAGE[0x16fe:0x175a], 0x16fe)}
    u.hook_add(UC_HOOK_CODE, lambda cpu, _p, _s, _c: sites.add(cpu.reg_read(x.UC_X86_REG_IP)))
    u.hook_add(UC_HOOK_MEM_WRITE, lambda _u, _a, p, size, v, _c: writes.append((p, size, v)))
    for gate in (0, 255):
        for raw in range(256):
            writes.clear(); buttons = 0xa553; scan = raw & 127
            u.mem_write(common.physical(ds, 0x14), buttons.to_bytes(2, 'little'))
            u.mem_write(common.physical(ds, 0x1fd0), b'\xe7'); u.mem_write(common.physical(ds, 0x200b), bytes((gate,)))
            for reg, value in ((x.UC_X86_REG_CS, load), (x.UC_X86_REG_DS, ds),
                               (x.UC_X86_REG_IP, 0x16fe), (x.UC_X86_REG_AX, 0xa500 | raw),
                               (x.UC_X86_REG_EFLAGS, 2)):
                u.reg_write(reg, value)
            u.emu_start(base + 0x16fe, base + 0x175a, count=40)
            latch = 0 if raw & 128 else scan
            expected_ax = (scan << 8) | raw
            if gate == 255 and scan in (0x7d, 0x7e):
                bit = 2 if scan == 0x7d else 1
                buttons = buttons & ~bit if raw & 128 else buttons | bit
                latch = 0; expected_ax = 0
            if u.reg_read(x.UC_X86_REG_IP) != 0x175a or u.reg_read(x.UC_X86_REG_AX) != expected_ax: fail('Keyboard prefix AX/control differs')
            actual = int.from_bytes(u.mem_read(common.physical(ds, 0x14), 2), 'little')
            if actual != buttons or u.mem_read(common.physical(ds, 0x1fd0), 1)[0] != latch: fail('Keyboard producer memory differs')
            if any(p not in (common.physical(ds, 0x14), common.physical(ds, 0x1fd0)) or size not in (1, 2) for p, size, _v in writes): fail('Keyboard producer escaped write domain')
    if sites - instructions: fail('Keyboard producer escaped instruction domain')
    return dict(case_count=512, executed_instruction_addresses=sorted(sites), c_coverage_claimed=False,
                domain='16FE..1759 scan-code/button prefix only, no IRQ entry/IRET, port services, bitmap lookup or scheduler')


def input_hashes(native=False):
    paths = set(common.input_hashes(False)) | {'tests/retry_input.py', 'tools/bounded_process.py', 'src/game_code_late.asm', 'src/entry_services.asm', 'src/image_tail.asm', 'metadata/symbols.json'}
    if native: paths |= {'c/retry_input.c', 'c/retry_input.h', 'c/special_blit.h', 'c/regs.h',
        'c/lemmings_sym.h', 'tools/cbuild.py', 'tools/difftest.py', 'tools/coverage.py'}
    return {p: sha((ROOT / p).read_bytes()) for p in sorted(paths)}


def worker(directory=None):
    before = input_hashes(directory is not None)
    if IMAGE[START:END] != CODE or len(INS) != 7: fail('Retry input bytes/boundaries changed')
    if sha(ASSET.read_bytes()) != '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d': fail('Pinned EXE changed')
    native = Native(directory) if directory else None
    matrix = word_matrix(native); producers = producer_matrix(); rows = []
    for case in cases(): rows.append(compare(native, case)); gc.collect()
    sites = {p for r in rows for p in r['sites']}; edges = {tuple(e) for r in rows for e in r['edges']}
    if sites != set(INS) or edges != EDGES: fail('Retry input coverage incomplete')
    mutants = []
    if native:
        for mutation, name in ((1, 'buttons-04'), (2, 'scan-01'), (3, 'buttons-01'),
                               (4, '0-delayed-buttons'), (5, 'scan-80'), (6, 'reset-01'), (7, 'buttons-01')):
            try: compare(Native(directory, mutation), next(c for c in cases() if c['name'] == name))
            except Mismatch as e: mutants.append(dict(mutation=mutation, case=name, reason=str(e), completed=True))
            else: fail(f'Retry input mutant{mutation} survived')
    if before != input_hashes(directory is not None): fail('Retry input sources changed during verification')
    write_json(Path(directory) / 'result.json' if native else ORIGINAL_REPORT, dict(image='main', image_sha256=sha(IMAGE),
        case_count=len(rows), boundary_fixtures=len(rows), native_boundaries_each_fixture=2 if native else 0,
        null_bus_cases_each_boundary=sum(r['null_repeat'] for r in rows),
        ram_fallback_variants=['null','empty','read-only','write-only'],
        exhaustive_word_cases=matrix, producer_contracts=producers, cases=rows,
        executed_instruction_addresses=sorted(sites), branch_edges=sorted(edges),
        native_code_ranges=[[START, END]] if native else [], translated_code_bytes=21 if native else 0,
        mutation_count=len(mutants), mutations_detected=mutants, input_hashes=before,
        c_coverage_claimed=bool(native), limits=dict(worker_seconds=120, process_mib=384, tree_mib=640,
            instructions_per_fixture=1024, events_per_fixture=1024),
        domain='Frame-free reset/wait before4B50, full AX/defined flags/registers/RAM/phase bus/VGA; finite canonical-memory updates; intact wait code/sameCS/TFclear/quiescentIRQ. Producer prefix evidence is original-only and adds no C coverage.'))
    print(f'PASS retry input {"C" if native else "original"}: {matrix} words,{len(rows)} fixtures,7 sites/4 edges,{len(mutants)} mutants;512 original-only producer cases', flush=True)


def probe(directory, null=False):
    case = dict(name='no-event-guard', seed=0, load=0x1010, buttons=0, scan=0, clear=False)
    memory, initial = prepare(case); b = Backend(memory, case, initial, native=True)
    native = Native(directory); bus = b.bus()
    if null: (Path(directory) / 'entered-native').touch()
    native.cores[0](common.buffer(b.memory), initial['ds'], initial['flags'], None if null else ctypes.byref(bus))
    fail('No-event wait unexpectedly returned')


def run(original=False):
    report = ORIGINAL_REPORT if original else REPORT; report.unlink(missing_ok=True)
    try:
        with temporary_build_directory(prefix='retry-input-', parent=BUILD) as directory:
            run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', '-' if original else directory],
                        cwd=ROOT, timeout=120, memory_mib=384)
            if not original: accepted = read_json(Path(directory) / 'result.json')
        if not original:
            with temporary_build_directory(prefix='retry-input-budget-', parent=BUILD) as directory:
                r = run_bounded([sys.executable, str(Path(__file__).resolve()), '--probe', directory],
                    cwd=ROOT, timeout=15, memory_mib=384, check=False, stderr=subprocess.PIPE, text=True)
                if r.returncode != 86 or 'Retry input access budget exhausted' not in r.stderr: fail('Retry access guard did not fail as expected')
            with temporary_build_directory(prefix='retry-input-timeout-', parent=BUILD) as directory:
                try:
                    run_bounded([sys.executable, str(Path(__file__).resolve()), '--null-probe', directory],
                                cwd=ROOT, timeout=5, memory_mib=384)
                except subprocess.TimeoutExpired:
                    if not (Path(directory) / 'entered-native').exists(): fail('Timeout occurred before entering no-event wait')
                else: fail('Expected no-event native deadline did not fire')
            if accepted['input_hashes'] != input_hashes(True): fail('Retry input sources changed before acceptance')
            accepted.update(access_guard_exit=86, null_bus_deadline_verified=True); write_json(report, accepted)
    except BaseException:
        report.unlink(missing_ok=True); raise


if __name__ == '__main__':
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == '--worker': worker(None if args[1] == '-' else args[1])
    elif len(args) == 2 and args[0] in ('--probe', '--null-probe'): probe(args[1], args[0] == '--null-probe')
    elif args == ['--original-only']: run(True)
    elif not args: run()
    else: raise SystemExit('Unexpected retry input arguments')

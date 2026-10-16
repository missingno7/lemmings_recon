"""Bounded original/native checks for CopyResourcePlanesToVga (57D1)."""
from __future__ import annotations

import copy
import ctypes as ct
import gc
import json
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]

import capstone
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
from resources import decode_section, section_spans
import entity_interactions as oracle
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import relocated

IMAGE, ORACLE = oracle.IMAGE, oracle.ORACLE
SIZE, MASK, FLAGS = oracle.SIZE, oracle.MASK, oracle.FLAGS
ENTRY, RET, END = 0x57D1, 0x5826, 0x5827
LOAD = 0x1010
MAX_STEPS, MAX_EVENTS = 1_000_000, 180_000
WORKER_SECONDS, MEMORY_MIB = 420, 384
REPORT = BUILD / 'vga-plane-copy-differential.json'
ORIGINAL_REPORT = BUILD / 'vga-plane-copy-original-differential.json'
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
OWN_SITES = set(OWN_INS)
REGS = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'sp',
        'cs', 'ds', 'es', 'ss', 'ip', 'flags')
CALL_REGS = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es',
             'ss', 'sp', 'flags')
CALL_FIELDS = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'code_segment',
               'data_segment', 'extra_segment', 'stack_segment', 'stack_offset',
               'flags')
RESULT_FIELDS = CALL_FIELDS + ('continuation', 'status')
MEM = ct.POINTER(ct.c_uint8)


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in CALL_FIELDS]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in RESULT_FIELDS]


READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8,
                     ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class Bus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class OracleFailure(AssertionError):
    pass


class Mismatch(AssertionError):
    pass


def check(condition, message):
    if not condition:
        raise OracleFailure(message)


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def physical(segment, offset):
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK


def put8(memory, segment, offset, value):
    memory[physical(segment, offset)] = value & 0xFF


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def section_image(index):
    packed = (ROOT / 'assets' / 'main.dat').read_bytes()
    spans = section_spans(packed)
    check(len(spans) == 7, 'MAIN.DAT section count changed')
    start, end = spans[index]
    image, metadata = decode_section(packed[start:end])
    return image, metadata


SECTION2, SECTION2_META = section_image(2)
SECTION6, SECTION6_META = section_image(6)
check(len(SECTION2) == 0x20C0, 'MAIN.DAT section 2 extent changed')
check(len(SECTION6) == 0x2020, 'MAIN.DAT section 6 extent changed')


def cases():
    specs = [
        dict(name='normal-caller-main-section-2', source='section2', si=0,
             independent=True),
        dict(name='normal-caller-main-section-6', source='section6', si=0,
             independent=True),
        dict(name='small-constructed-copy', bx=0x0203, cx=2, ax=7,
             independent=True),
        dict(name='df-backward-rep-copy', bx=0x0203, cx=2, ax=7,
             flags=0x0ED7, independent=True),
        dict(name='zero-row-width-bl', bx=0x0200, cx=1),
        dict(name='zero-plane-count-bh-wraps-256', bx=0x0001, cx=1,
             independent=True),
        dict(name='zero-cx-live-pop-provider', bx=0x0402, cx=0,
             provider='zero-cx'),
        dict(name='live-row-bx-pop', bx=0x0102, cx=2, ss=0xA000,
             sp=0x9000, di=0x8FF6, provider='row-bx'),
        dict(name='live-row-di-pop', bx=0x0102, cx=2, ss=0xA000,
             sp=0x9000, di=0x8FF8, provider='row-di'),
        dict(name='live-row-cx-pop', bx=0x0102, cx=2, ss=0xA000,
             sp=0x9000, di=0x8FFA, provider='row-cx'),
        dict(name='live-row-cx-pop-vga-stack', bx=0x0102, cx=2,
             ss=0xA000, sp=0x9000, provider='row-cx'),
        dict(name='stack-mirror-overwrites-saved-ax', bx=0x0102, cx=2,
             ss=0x5000, sp=0x000E, ax=0x002C),
        dict(name='source-ea-wrap-ffff', bx=0x0104, cx=1, si=0xFFFE,
             independent=True),
        dict(name='source-physical-fffff-wrap', bx=0x0104, cx=1,
             ds=0xFFFF, si=0x000E, independent=True),
        dict(name='stack-offset-wrap-one', bx=0x0102, cx=1,
             ss=0x1000, sp=0x0001),
        dict(name='stack-offset-ffff-word-high', bx=0x0102, cx=1,
             ss=0x1000, sp=0xFFFF),
        dict(name='stack-word-crosses-physical-fffff', bx=0x0102, cx=1,
             ss=0xFFFF, sp=0x000F),
        dict(name='outer-ret-overwritten-by-vga-copy', bx=0x0102, cx=1,
             ss=0xA000, sp=0x9000, di=0x9000, source='ret-alias'),
        dict(name='vga-source-ds', bx=0x0103, cx=2, ds=0xA000,
             si=0x0100, independent=True),
        dict(name='vga-stack-ss', bx=0x0102, cx=2, ss=0xA000, sp=0x4000),
        dict(name='vga-destination-plane-projection', bx=0x0103, cx=2,
             independent=True),
    ]
    base = dict(ax=0x002C, bx=0x0428, cx=0x0028, dx=0xD39B,
                si=0x1900, di=0xF91F, bp=0x79A3, cs=LOAD,
                ds=0x3000, es=0x6000, ss=0x5000, sp=0x9000,
                flags=0x0AD7, provider=None, source='constructed',
                seed=0x57D100)
    rows = []
    for index, spec in enumerate(specs):
        row = dict(base)
        row['seed'] += index * 0x101
        row.update(spec)
        rows.append(row)
    return rows


def sync_seed(memory, device, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    if device is not None and VGA_BASE <= address < VGA_END:
        device.planes[0][address - VGA_BASE] = value & 0xFF


def setup(case):
    rng = random.Random(case['seed'])
    memory = bytearray(rng.randbytes(SIZE))
    loaded = relocated(IMAGE, ORACLE['relocations'], LOAD)
    code_start = LOAD << 4
    memory[code_start:code_start + len(loaded)] = loaded

    device = MinimapVga(case['seed'] ^ 0x57D1, read_map=0)
    device.seq[2] = 0x0F
    for index in (0, 1, 3, 4, 5):
        device.gc[index] = 0
    device.gc[6] = 5
    device.gc[8] = 0xFF
    memory[VGA_BASE:VGA_END] = device.planes[0]

    regs = dict(ax=case['ax'], bx=case['bx'], cx=case['cx'], dx=case['dx'],
                si=case['si'], di=case['di'], bp=case['bp'], cs=case['cs'],
                ds=case['ds'], es=case['es'], ss=case['ss'], sp=case['sp'],
                ip=ENTRY, flags=case['flags'])
    if case['source'] in ('section2', 'section6'):
        source = SECTION2 if case['source'] == 'section2' else SECTION6
        for offset, value in enumerate(source):
            sync_seed(memory, device, regs['ds'], offset, value)
    elif case['source'] == 'ret-alias':
        sync_seed(memory, device, regs['ds'], regs['si'], 0x34)
        sync_seed(memory, device, regs['ds'], regs['si'] + 1, 0x12)
    else:
        length = max(0x100, (regs['bx'] & 0xFF) * max(1, regs['cx']) *
                     max(1, (regs['bx'] >> 8) & 0xFF))
        for index in range(length):
            value = (0x35 + 73 * index + 19 * (index >> 2) + case['seed']) & 0xFF
            offset = (regs['si'] + index) & 0xFFFF
            sync_seed(memory, device, regs['ds'], offset, value)

    # Decoys make both 16-bit EA wrap and the physical top wrap observable.
    if case['name'] == 'source-ea-wrap-ffff':
        decoy = (physical(regs['ds'], 0xFFFF) + 1) & MASK
        memory[decoy] ^= 0xA7
    if case['name'] == 'source-physical-fffff-wrap':
        memory[0] ^= 0x5B

    put16(memory, regs['ss'], regs['sp'], 0xD00D)
    if regs['ss'] == 0xA000:
        address = physical(regs['ss'], regs['sp'])
        device.planes[0][address - VGA_BASE] = memory[address]
        device.planes[0][((address + 1) & MASK) - VGA_BASE] = memory[(address + 1) & MASK]
    return memory, regs, device


class Access(oracle.Access):
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device, *, native=False):
        super().__init__(case, memory, regs, device)
        self.native = native
        self.pending = []
        self.low_bytes = {}
        self.skipped_pushes = set()
        self.armed = False

    def queue(self, offset, value, label):
        self.pending.append((self.regs['ss'], offset & 0xFFFF, value, label))

    def instruction_complete(self):
        pending, self.pending = self.pending, []
        for segment, offset, value, label in pending:
            self.modify_word(segment, offset, value)
            address = physical(segment, offset)
            if self.device is not None:
                for delta, byte in enumerate((value & 0xFF, value >> 8)):
                    at = (address + delta) & MASK
                    if VGA_BASE <= at < VGA_END:
                        for plane in self.device.planes:
                            plane[at - VGA_BASE] = byte
            self.used.add(label)

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        result = super().access(kind, address, flags, mask, value)
        case = self.case
        label = case.get('provider')
        if kind == 'write' and self.armed and label and label not in self.used:
            depths = {'row-bx': (10, 0x0103), 'row-di': (8, 0x0340),
                      'row-cx': (6, 0x0001)}
            if label == 'zero-cx':
                targets = ((4, 0x0001, 'outer'), (6, 0x0001, 'row'))
            else:
                depth, replacement = depths[label]
                targets = ((depth, replacement, label),)
            for depth, replacement, tag in targets:
                offset = (case['sp'] - depth) & 0xFFFF
                start = physical(case['ss'], offset)
                high = (start + 1) & MASK
                if address == start:
                    self.low_bytes[tag] = result
                elif address == high and tag in self.low_bytes:
                    low = self.low_bytes.pop(tag)
                    saved_register = {'row-bx': case['bx'],
                                      'row-di': case['di'],
                                      'row-cx': case['cx']}.get(label)
                    if (label != 'zero-cx' and tag not in self.skipped_pushes and
                            (low | (result << 8)) == saved_register):
                        self.skipped_pushes.add(tag)
                    elif tag == 'outer':
                        self.queue(offset, replacement, 'zero-cx-outer')
                    else:
                        self.queue(offset, replacement, label)
                    if self.native:
                        self.instruction_complete()
        return result

    def out_word(self, port, value, flags, mask=FLAGS):
        if len(self.events) >= self.event_limit:
            raise OracleFailure('VGA plane-copy bus callback budget exhausted')
        self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        if port == 0x3C4 and not self.armed:
            self.armed = True
            if self.case.get('provider') == 'zero-cx':
                self.queue((self.case['sp'] - 4) & 0xFFFF, 1, 'zero-cx-outer')
                if self.native:
                    self.instruction_complete()


def original(case, memory, regs, device, *, core):
    observers = []
    result = oracle.original(
        case, bytearray(memory), dict(regs), copy.deepcopy(device), core,
        entry_flag_mask=FLAGS, main_instructions=OWN_INS,
        access_factory=lambda c, m, r, d: observers.append(
            Access(c, m, r, d)) or observers[-1],
        instruction_limit=MAX_STEPS)
    result['providers'] = set(observers[0].used)
    return result


def expected_edges():
    edges = set()
    for address, ins in OWN_INS.items():
        if ins.group(capstone.CS_GRP_JUMP) or ins.mnemonic.lower().startswith('loop'):
            target = ins.operands[0].imm & 0xFFFF
            edges.add((address, target))
            if ins.mnemonic.lower() != 'jmp':
                edges.add((address, (address + ins.size) & 0xFFFF))
    return edges


def independent_planes(case, initial, initial_device, expected):
    if not case.get('independent'):
        return 0
    planes = [bytearray(plane) for plane in initial_device.planes]
    source_segment, source_offset = case['ds'], case['si']
    destination = case['di']
    direction = -1 if case['flags'] & 0x0400 else 1
    rows, width = case['cx'], case['bx'] & 0xFF
    remaining_planes = (case['bx'] >> 8) & 0xFF
    plane_count = remaining_planes or 256
    written = 0
    map_mask = 1
    for _plane_index in range(plane_count):
        source = source_offset
        row_start = destination
        for _row in range(rows):
            target = row_start
            for _column in range(width):
                source_address = physical(source_segment, source)
                value = initial[source_address]
                target_offset = target & 0xFFFF
                for plane_index in range(4):
                    if map_mask & (1 << plane_index):
                        planes[plane_index][target_offset] = value
                        written += 1
                source = (source + direction) & 0xFFFF
                target = (target + direction) & 0xFFFF
            row_start = (row_start + case['ax']) & 0xFFFF
        source_offset = source
        map_mask = (map_mask << 1) & 0xFF
    for index, plane in enumerate(planes):
        check(bytes(plane) == bytes(expected['device'].planes[index]),
              f"{case['name']}: independent VGA plane {index} differs")
    return written


def validate(case, initial, initial_device, regs, expected, *, core):
    check(expected['status'] == 0, case['name'] + ': original did not reach READY')
    providers = ({case['provider']} if case.get('provider') else set())
    if case.get('provider') == 'zero-cx':
        providers.add('zero-cx-outer')
    check(expected['providers'] == providers,
          case['name'] + ': provider transition differs')
    check(expected['regs']['es'] == 0xA000,
          case['name'] + ': VGA aperture segment differs')
    if core:
        check(expected['regs']['ip'] == RET,
              case['name'] + ': core did not stop before RET')
        check(expected['regs']['sp'] == regs['sp'],
              case['name'] + ': core did not restore entry SP')
    else:
        check(expected['regs']['ip'] == get16(expected['memory'],
              expected['regs']['ss'], regs['sp']),
              case['name'] + ': adapter did not consume the actual live RET')
        check(expected['regs']['sp'] == ((regs['sp'] + 2) & 0xFFFF),
              case['name'] + ': actual RET did not advance SP')
        if case['name'] == 'outer-ret-overwritten-by-vga-copy':
            check(expected['regs']['ip'] == 0x1234,
                  case['name'] + ': VGA source did not replace the outer RET word')
    check((expected['regs']['flags'] & 0x0400) == (regs['flags'] & 0x0400),
          case['name'] + ': DF changed')
    return independent_planes(case, initial, initial_device, expected)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'vga-plane-copy-m{mutation}.dll',
                     mutation, 'vga_plane_copy')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_copy_resource_planes_vga_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(Bus)]
        self.core.restype = Result
        self.adapter = self.lib.lmn_copy_resource_planes_vga_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(oracle.Regs), ct.POINTER(Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, memory, regs, device, *, core):
        access = Access(case, memory, regs, device, native=True)

        def die(error):
            code = 86 if 'budget' in str(error).lower() else 87
            try:
                os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
            finally:
                os._exit(code)

        def read(_context, _memory, address, flags):
            try:
                if len(access.events) >= MAX_EVENTS:
                    raise OracleFailure('VGA plane-copy callback budget exhausted')
                return access.access('read', address, flags)
            except BaseException as error:
                die(error)

        def write(_context, _memory, address, value, flags):
            try:
                if len(access.events) >= MAX_EVENTS:
                    raise OracleFailure('VGA plane-copy callback budget exhausted')
                access.access('write', address, flags, value=value)
            except BaseException as error:
                die(error)

        def out(_context, port, value, flags):
            try:
                access.out_word(port, value, flags)
            except BaseException as error:
                die(error)

        callbacks = (READ(read), WRITE(write), OUT(out))
        bus = Bus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = oracle.Regs(**regs)
        if core:
            call_values = [regs[name] for name in CALL_REGS]
            call = Call(*call_values)
            result = self.core(ram, ct.byref(call), ct.byref(bus))
            for role, name in zip(CALL_FIELDS, CALL_REGS):
                target = {'code_segment': 'cs', 'data_segment': 'ds',
                          'extra_segment': 'es', 'stack_segment': 'ss',
                          'stack_offset': 'sp'}.get(role, role)
                setattr(state, target, getattr(result, role))
            state.ip = result.continuation
            status = result.status
        else:
            status = self.adapter(ram, ct.byref(state), ct.byref(bus))
        return dict(memory=bytes(memory),
                    regs={name: getattr(state, name) for name in oracle.REG_NAMES},
                    status=status, events=access.events, providers=set(access.used),
                    device=device)


def compare(native, case, *, core):
    memory, regs, device = setup(case)
    expected = original(case, memory, regs, device, core=core)
    independent_bytes = validate(case, memory, device, regs, expected, core=core)
    actual = native.run(case, bytearray(memory), dict(regs),
                        copy.deepcopy(device), core=core)
    compare_result(actual, expected, case['name'] + (' core' if core else ' adapter'))
    return expected, independent_bytes


def compare_result(actual, expected, label):
    require(actual['status'] == expected['status'], label + ': status differs')
    require(actual['memory'] == expected['memory'], label + ': RAM differs')
    for name in oracle.REG_NAMES:
        mask = expected['flag_mask'] if name == 'flags' else 0xFFFF
        require(((actual['regs'][name] ^ expected['regs'][name]) & mask) == 0,
                f"{label}: {name} {actual['regs'][name]:04X}/"
                f"{expected['regs'][name]:04X} mask={mask:04X}")
    require(actual['providers'] == expected['providers'], label + ': providers differ')
    require(len(actual['events']) == len(expected['events']), label + ': event count differs')
    for index, (got, want) in enumerate(zip(actual['events'], expected['events'])):
        require(got[:3] == want[:3], f'{label}: event {index} differs: {got!r}/{want!r}')
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f'{label}: event {index} FLAGS differ {got[3]:04X}/{want[3]:04X}')
    require(actual['device'].state() == expected['device'].state(),
            label + ': VGA state differs')
    require([event[:3] for event in actual['device'].trace] ==
            [event[:3] for event in expected['device'].trace],
            label + ': VGA trace differs')


def edges_for(rows):
    return {tuple(edge) for row in rows for edge in row['edges']}


def collect(expected, case, core, independent_bytes):
    return dict(case=case['name'], boundary='core' if core else 'adapter',
                sites=sorted(address for scope, address in expected['sites']
                             if scope == 'main'),
                edges=sorted([source, target] for scope, source, target in expected['edges']
                             if scope == 'main'),
                events=len(expected['events']), steps=expected['steps'],
                independent_plane_bytes=independent_bytes)


def hash_inputs():
    # Pin this suite's causal closure explicitly; docs and the generated raw
    # symbol ledger are outside its behavioral evidence scope.
    paths = {
        'AGENTS.md', 'assets/vgalemmi.exe', 'assets/main.dat',
        'assets/adlib.dat', 'assets/tandysnd.dat',
        'metadata/inputs.json', 'metadata/oracle.json',
        'metadata/toolchain-lock.json',
        'src/game_code_late_after_palette.asm',
        'c/vga_plane_copy.c', 'c/vga_plane_copy.h', 'c/lemmings_sym.h',
        'c/regs.h', 'c/special_blit.h',
        'tests/vga_plane_copy.py', 'tests/entity_interactions.py',
        'tests/minimap_vga.py', 'tests/sound_latches.py',
        'tests/pcspeaker_dispatch.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/difftest.py', 'tools/resources.py', 'tools/unpack.py',
    }
    return {path: sha((ROOT / path).read_bytes()) for path in sorted(paths)}


def rows_original():
    before = hash_inputs()
    rows = []
    for case in cases():
        print(f"CHECKED original {case['name']}", flush=True)
        memory, regs, device = setup(case)
        for core in (True, False):
            expected = original(case, memory, regs, device, core=core)
            count = validate(case, memory, device, regs, expected, core=core)
            rows.append(collect(expected, case, core, count))
        gc.collect()
    check({address for row in rows for address in row['sites']} == OWN_SITES,
          'original campaign did not cover all 45 sites')
    check(edges_for(rows) == expected_edges(),
          'original campaign did not cover every branch edge')
    check(before == hash_inputs(), 'inputs changed during original campaign')
    return before, rows


def publish(path, before, rows, mutants=None):
    sites = {address for row in rows for address in row['sites']}
    branches = edges_for(rows)
    check(sites == OWN_SITES, f'missing instruction sites: {OWN_SITES - sites}')
    check(branches == expected_edges(),
          f'missing branch outcomes: {expected_edges() - branches}')
    report = dict(image='main', image_sha256=sha(IMAGE), entry=ENTRY, ret=RET,
        end=END, case_count=len(cases()), comparison_count=len(rows),
        translated_code_bytes=END - ENTRY, instruction_sites=len(OWN_SITES),
        executed_instruction_addresses=sorted(sites),
        branch_edges=sorted([source, target] for source, target in branches),
        branch_edge_count=len(branches),
        ordered_events=sum(row['events'] for row in rows),
        instruction_steps=sum(row['steps'] for row in rows),
        independent_plane_bytes=sum(row['independent_plane_bytes'] for row in rows),
        original_only=mutants is None, mutation_count=len(mutants or []),
        mutations=mutants or [], rows=rows, input_hashes=before,
        section2_sha256=SECTION2_META['image_sha256'],
        section6_sha256=SECTION6_META['image_sha256'],
        limits=dict(timeout_seconds=WORKER_SECONDS, process_commit_mib=MEMORY_MIB,
                    original_instruction_limit=MAX_STEPS, bus_event_limit=MAX_EVENTS))
    write_json(path, report)
    print(f'PASS VGA plane copy: {len(cases())} fixtures/{len(rows)} boundaries, '
          f'{len(sites)} sites/{len(branches)} edges, {report["ordered_events"]} events, '
          f'{len(mutants or [])} mutants', flush=True)


def original_worker():
    before, rows = rows_original()
    publish(ORIGINAL_REPORT, before, rows)


def worker(directory, snapshot):
    before = json.loads(Path(snapshot).read_text())
    check(before == hash_inputs(), 'input hash snapshot differs')
    native = Native(directory)
    rows = []
    for case in cases():
        for core in (True, False):
            expected, independent_bytes = compare(native, case, core=core)
            rows.append(collect(expected, case, core, independent_bytes))
        gc.collect()
    witnesses = (
        (1, 'zero-plane-count-bh-wraps-256', True),
        (2, 'zero-cx-live-pop-provider', True),
        (3, 'df-backward-rep-copy', True),
        (4, 'stack-mirror-overwrites-saved-ax', True),
        (5, 'normal-caller-main-section-2', True),
        (6, 'live-row-bx-pop', True),
        (7, 'live-row-di-pop', True),
        (8, 'small-constructed-copy', True),
        (9, 'outer-ret-overwritten-by-vga-copy', False),
        (10, 'normal-caller-main-section-2', False),
    )
    by_name = {case['name']: case for case in cases()}
    mutants = []
    for number, name, core in witnesses:
        try:
            compare(Native(directory, number), by_name[name], core=core)
        except Mismatch as error:
            mutants.append(dict(mutation=number, case=name, core=core,
                                completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f'mutation {number} survived')
        gc.collect()
    check(before == hash_inputs(), 'inputs changed during native campaign')
    publish(REPORT, before, rows, mutants)


def main():
    BUILD.mkdir(exist_ok=True)
    if sys.argv[1:] == ['--original-worker']:
        original_worker()
        return
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        worker(sys.argv[2], sys.argv[3])
        return
    if sys.argv[1:] == ['--original-only']:
        run_bounded([sys.executable, __file__, '--original-worker'], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=MEMORY_MIB, check=True)
        return
    if sys.argv[1:]:
        raise SystemExit('usage: vga_plane_copy.py [--original-only]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='vga-plane-copy-', parent=BUILD) as directory:
        snapshot = Path(directory) / 'input-hashes.json'
        snapshot.write_text(json.dumps(hash_inputs(), sort_keys=True))
        run_bounded([sys.executable, __file__, '--worker', directory, str(snapshot)],
                    cwd=ROOT, timeout=WORKER_SECONDS, memory_mib=MEMORY_MIB,
                    check=True)


if __name__ == '__main__':
    main()

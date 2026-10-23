"""Bounded original/native checks for 5CC1..5D17 fixed word banks."""
from __future__ import annotations

from array import array
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
import entity_interactions as oracle
import sprite_bank as shared
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated


IMAGE, META = unpack(ASSET.read_bytes())
SIZE, MASK, FLAGS = oracle.SIZE, oracle.MASK, oracle.FLAGS
ENTRY, CHILD, RET, END = 0x5CC1, 0x5CDD, 0x5D17, 0x5D18
SELECTOR, SOURCE_A, SOURCE_B = 0x1FEA, 0x52BC, 0x531C
LOAD, STATIC_DS = 0x1010, 0x19B9
MAX_STEPS, MAX_EVENTS = 250_000, 150_000
WORKER_SECONDS, MEMORY_MIB = 420, 384
REPORT = BUILD / 'fixed-word-banks-differential.json'
ORIGINAL_REPORT = BUILD / 'fixed-word-banks-original-differential.json'
CALL_RETURNS = {0x5CCF: ({RET}, 101)}
REGS = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es', 'ss', 'sp', 'flags')
ROLE_NAMES = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'code_segment',
              'data_segment', 'extra_segment', 'stack_segment', 'stack_offset', 'flags')
MEM = ct.POINTER(ct.c_uint8)
READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
PARENT_INS = {i.address: i for i in MD.disasm(IMAGE[ENTRY:CHILD], ENTRY)}
CHILD_INS = {i.address: i for i in MD.disasm(IMAGE[CHILD:END], CHILD)}
MAIN_INS = PARENT_INS | CHILD_INS


class CompactEvents:
    """Packed, bounded event storage used by both original and native runs."""
    def __init__(self):
        self.data = array('I')

    def __len__(self):
        return len(self.data) // 5

    def append(self, event):
        kind, address, value, flags, mask = event
        self.data.extend((int(kind == 'write'), address, value, flags, mask))

    def __iter__(self):
        for n in range(0, len(self.data), 5):
            yield ('write' if self.data[n] else 'read', *self.data[n + 1:n + 5])


class StopSecondReturn:
    """Let the real first CALL return, then stop before the shared final RET."""
    def __init__(self):
        self.visits = 0

    def __contains__(self, address):
        if address != RET:
            return False
        self.visits += 1
        return self.visits == 2

    def __getitem__(self, address):
        if address != RET:
            raise KeyError(address)
        return 0


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in ROLE_NAMES]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ROLE_NAMES + ('continuation', 'status', 'child_entry')]


class Bus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]


class OracleFailure(AssertionError):
    pass


Mismatch = shared.Mismatch


def check(value, message):
    if not value:
        raise OracleFailure(message)


def require(value, message):
    if not value:
        raise Mismatch(message)


def physical(segment, offset):
    return ((segment << 4) + (offset & 0xFFFF)) & MASK


def put8(memory, segment, offset, value):
    memory[physical(segment, offset)] = value & 0xFF


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def cases():
    base = dict(ds=0x2000, es=0x6000, ss=0x8000, sp=0x9000,
                flags=0x0AD7, source='constructed', provider=None,
                seed=0x5CC100, independent=False)
    specs = [
        dict(name='static-executable-source', ds=STATIC_DS, es=0x6000,
             source='static', independent=True),
        dict(name='constructed-source', independent=True),
        dict(name='df-backward-source', flags=0x0ED7, independent=True),
        dict(name='selector-provider', provider='selector', provider_value=0x6400,
             selector=0x6000, independent=True),
        dict(name='changed-first-child-return', provider='child-ret'),
        dict(name='provider-saved-bx-vga-stack', provider='saved-bx',
             ss=0xA000, vga=True),
        dict(name='provider-saved-dx-shortens-first-bank', provider='saved-dx'),
        dict(name='provider-finite-cursor-and-counts', provider='finite-controls'),
        dict(name='output-replaces-outer-ret', es=0x4000, ss=0x4000,
             sp=0x0000),
        dict(name='source-output-overlap', ds=0x3000, es=0x352B,
             source='constructed'),
        dict(name='source-stack-alias', ds=0x2000, ss=0x2000, sp=0x52C0,
             source='constructed'),
        dict(name='output-segment-wrap', es=0xFFF0, independent=True),
        dict(name='stack-offset-one', sp=1),
        dict(name='stack-offset-ffff', sp=0xFFFF, ss=0xFFFF),
        dict(name='physical-stack-wrap', sp=0x000F, ss=0xFFFF),
    ]
    return [dict(base, seed=base['seed'] + n, **spec) for n, spec in enumerate(specs)]


def setup(case):
    memory = bytearray(random.Random(case['seed']).randbytes(SIZE))
    code = relocated(IMAGE, META['relocations'], LOAD)
    memory[LOAD << 4:(LOAD << 4) + len(code)] = code
    data_segment = case['ds']
    if case['source'] == 'static':
        static_source = bytes(memory[(physical(data_segment, SOURCE_A) + n) & MASK]
                              for n in range(0xC0))
        check(static_source == IMAGE[0xED4C:0xEE0C],
              'static executable source does not map to image ED4C..EE0B')
    else:
        rng = random.Random(case['seed'] ^ 0x5D17A9)
        for start in (SOURCE_A, SOURCE_B):
            # Eight banks each consume 48 words in source order.
            direction = -1 if case['flags'] & 0x0400 else 1
            for n in range(384):
                offset = (start + direction * 2 * n) & 0xFFFF
                put16(memory, data_segment, offset, rng.randrange(0x10000))

    es = case.get('selector', case['es'])
    regs = dict(cs=LOAD, ip=ENTRY, ax=0xBEEF, bx=0xC17D, cx=0x4A93,
                dx=0xB271, si=0x1234, di=0xABCD, bp=0x79A3,
                ds=data_segment, es=0x3510, ss=case['ss'], sp=case['sp'],
                flags=case['flags'])
    put16(memory, regs['ds'], SELECTOR, es)
    device = None
    if case.get('vga'):
        device = MinimapVga(case['seed'], read_map=0)
        device.seq[2] = 0x0F
        for n in (0, 1, 3, 4, 5):
            device.gc[n] = 0
        device.gc[6] = 5
        device.gc[8] = 0xFF
        memory[VGA_BASE:VGA_END] = device.planes[0]
    put16(memory, regs['ss'], regs['sp'], 0xD00D)
    if device is not None:
        stack_address = physical(regs['ss'], regs['sp'])
        for n, byte in enumerate((0x0D, 0xD0)):
            at = (stack_address + n) & MASK
            if VGA_BASE <= at < VGA_END:
                for plane in device.planes:
                    plane[at - VGA_BASE] = byte
    return memory, regs, device


class Access(oracle.Access):
    event_limit = MAX_EVENTS

    def __init__(self, case, memory, regs, device, *, native=False):
        super().__init__(case, memory, regs, device)
        self.events = CompactEvents()
        self.native = native
        self.pending = []

    def modify_word(self, segment, offset, value):
        super().modify_word(segment, offset, value)
        address = physical(segment, offset)
        for n, byte in enumerate((value & 0xFF, (value >> 8) & 0xFF)):
            at = (address + n) & MASK
            if self.device is not None and VGA_BASE <= at < VGA_END:
                for plane in self.device.planes:
                    plane[at - VGA_BASE] = byte

    def queue(self, segment, offset, value, label):
        self.pending.append((segment, offset & 0xFFFF, value & 0xFFFF, label))

    def instruction_complete(self):
        pending, self.pending = self.pending, []
        for segment, offset, value, label in pending:
            self.modify_word(segment, offset, value)
            self.used.add(label)

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        case = self.case
        address &= MASK
        # Editing the selector on its low-byte read changes the high byte
        # before the guest's second byte operand is fetched.
        if (kind == 'read' and case['provider'] == 'selector' and
                'selector' not in self.used and
                address == physical(self.regs['ds'], SELECTOR)):
            self.modify_word(self.regs['ds'], SELECTOR, case['provider_value'])
            self.used.add('selector')

        result = super().access(kind, address, flags, mask, value)
        if kind == 'write' and case['provider']:
            ss, sp = self.regs['ss'], self.regs['sp']
            targets = []
            if case['provider'] == 'child-ret':
                targets = [(sp - 2, 'child-ret')]
            elif case['provider'] == 'saved-bx':
                targets = [(sp - 6, 'saved-bx')]
            elif case['provider'] == 'saved-dx':
                targets = [(sp - 4, 'saved-dx')]
            elif case['provider'] == 'finite-controls':
                targets = [(sp - 8, 'finite-si'), (sp - 10, 'finite-bx'),
                           (sp - 14, 'finite-cx')]
            for offset, label in targets:
                start = physical(ss, offset)
                if address != ((start + 1) & MASK):
                    continue
                if label == 'child-ret' and label not in self.used:
                    self.queue(ss, offset, 0x1234, label)
                elif label == 'saved-bx':
                    low = self.memory[start]
                    self.queue(ss, offset, (0x5A << 8) | low, label)
                elif label == 'saved-dx' and label not in self.used:
                    low = self.memory[start]
                    self.queue(ss, offset, 0x0700 | low, label)
                elif label == 'finite-si' and label not in self.used:
                    self.queue(ss, offset, 0x5400, label)
                elif label == 'finite-bx':
                    low = self.memory[start]
                    self.queue(ss, offset, (self.memory[(start + 1) & MASK] << 8) | 1,
                               label)
                elif label == 'finite-cx':
                    self.queue(ss, offset, 1, label)
        if self.native:
            self.instruction_complete()
        return result


def original(case, memory, regs, device, *, core):
    accessors = []
    stops = StopSecondReturn() if core else {}
    ref = oracle.original(
        case, bytearray(memory), dict(regs), copy.deepcopy(device), False,
        entry_flag_mask=FLAGS, main_instructions=MAIN_INS,
        main_call_returns=CALL_RETURNS, stop_offsets=stops,
        instruction_limit=MAX_STEPS,
        access_factory=lambda c, m, r, d: accessors.append(Access(c, m, r, d)) or accessors[-1])
    raw_status = ref['status']
    ref['raw_status'] = raw_status
    changed = raw_status >= 101
    ref.update(status=1 if changed else raw_status,
               child_entry=CHILD if changed else 0,
               provider_events=accessors[0].used)
    return ref


def expected_bytes(memory, case):
    direction = -1 if case['flags'] & 0x0400 else 1
    output = bytearray()
    for start in (SOURCE_A, SOURCE_B):
        for shift in range(8):
            # SI is saved around each DH bank, so every shift rereads the
            # same 48 source words unless the live saved SI slot is edited.
            cursor = start
            for _ in range(48):
                lo = memory[physical(case['ds'], cursor)]
                hi = memory[(physical(case['ds'], cursor) + 1) & MASK]
                value = (((lo << 16) | (hi << 8)) >> shift) & 0xFFFFFF
                output.extend(value.to_bytes(3, 'big'))
                cursor = (cursor + direction * 2) & 0xFFFF
    return bytes(output)


def validate(case, initial, regs, ref, *, core):
    stopped = case['provider'] == 'child-ret'
    check(ref['status'] == (1 if stopped else 0), case['name'] + ': original status')
    expected_used = set()
    if case['provider'] == 'selector':
        expected_used.add('selector')
    elif case['provider'] == 'child-ret':
        expected_used.add('child-ret')
    elif case['provider'] == 'saved-bx':
        expected_used.add('saved-bx')
    elif case['provider'] == 'saved-dx':
        expected_used.add('saved-dx')
    elif case['provider'] == 'finite-controls':
        expected_used = {'finite-si', 'finite-bx', 'finite-cx'}
    check(ref['provider_events'] == expected_used,
          case['name'] + ': provider transitions ' + repr(ref['provider_events']))
    if stopped:
        check(ref['regs']['ip'] == 0x1234, case['name'] + ': changed child target')
        check(ref['regs']['sp'] == regs['sp'],
              case['name'] + ': changed child frame')
        return 0
    check(ref['regs']['sp'] == ((regs['sp'] + (0 if core else 2)) & 0xFFFF),
          case['name'] + ': stack boundary')
    check(ref['regs']['ip'] == (RET if core else get16(ref['memory'], regs['ss'], regs['sp'])),
          case['name'] + ': actual RET target')
    if case['provider'] == 'selector':
        check(ref['regs']['es'] == case['provider_value'], case['name'] + ': live ES selector')
    if case['provider'] == 'saved-bx':
        check(ref['regs']['bx'] >> 8 == 0x5A, case['name'] + ': live POP BX')
    if case['provider'] in ('saved-dx', 'finite-controls'):
        first = physical(ref['regs']['es'], 0)
        second = physical(ref['regs']['es'], 0x480)
        writes = [event[1] for event in ref['events'] if event[0] == 'write']
        first_count = sum(first <= address < first + 0x480 for address in writes)
        second_count = sum(second <= address < second + 0x480 for address in writes)
        if case['provider'] == 'saved-dx':
            check(first_count == 0x90, case['name'] + ': DH save did not end after one shift')
        else:
            check(first_count == 8 * 3 and second_count == 117,
                  case['name'] + ': live CX/BX/SI edits changed the expected finite banks')
    if not case['independent']:
        return 0
    output = expected_bytes(initial, case)
    actual = bytes(ref['memory'][(physical(ref['regs']['es'], n)) & MASK]
                   for n in range(len(output)))
    check(actual == output, case['name'] + ': independent 2304-byte bank equation')
    check(len(output) == 0x900, case['name'] + ': output size')
    return len(output)


class Native:
    def __init__(self, directory, mutation=0):
        library = build(Path(directory) / f'fixed-word-banks-m{mutation}.dll',
                        mutation, 'fixed_word_banks')
        self.lib = ct.CDLL(str(library))
        self.core = self.lib.lmn_generate_fixed_word_mask_banks_core
        self.core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(Bus)]
        self.core.restype = Result
        self.adapter = self.lib.lmn_generate_fixed_word_mask_banks_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(oracle.Regs), ct.POINTER(Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, memory, regs, device, *, core):
        access = Access(case, memory, regs, device, native=True)

        def read(_context, _memory, address, flags):
            try:
                return access.access('read', address, flags)
            except BaseException as error:
                shared.die(error)

        def write(_context, _memory, address, value, flags):
            try:
                access.access('write', address, flags, value=value)
            except BaseException as error:
                shared.die(error)

        def out(*_args):
            shared.die('unexpected OUT in fixed word banks')

        callbacks = READ(read), WRITE(write), OUT(out)
        bus = Bus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = oracle.Regs(**regs)
        child_entry = 0
        if core:
            result = self.core(ram, ct.byref(Call(*(regs[n] for n in REGS))), ct.byref(bus))
            for role, reg in zip(ROLE_NAMES, REGS):
                setattr(state, reg, getattr(result, role))
            state.ip = result.continuation
            status, child_entry = result.status, result.child_entry
        else:
            status = self.adapter(ram, ct.byref(state), ct.byref(bus))
        return dict(memory=bytes(memory), regs={n: getattr(state, n) for n in oracle.REG_NAMES},
                    status=status, events=access.events, used=access.used,
                    device=device, child_entry=child_entry)


def compare(native, case, *, core):
    memory, regs, device = setup(case)
    ref = original(case, memory, regs, device, core=core)
    checks = validate(case, memory, regs, ref, core=core)
    got = native.run(case, bytearray(memory), dict(regs), copy.deepcopy(device), core=core)
    shared.equal(got, ref, case['name'] + (' core' if core else ' adapter'))
    if core:
        require(got['child_entry'] == ref['child_entry'],
                case['name'] + ': child entry provenance')
    return ref, checks


def branch_edges(instructions):
    return {(pc, target) for pc, ins in instructions.items()
            if ins.group(capstone.CS_GRP_JUMP) or ins.mnemonic == 'loop'
            for target in ((ins.operands[0].imm & 0xFFFF), (pc + ins.size) & 0xFFFF)
            if ins.mnemonic != 'jmp' or target == (ins.operands[0].imm & 0xFFFF)}


def hashes():
    # Hash only this campaign's maintained sources and helper closure. Other
    # new suites can be authored concurrently without invalidating its snapshot.
    paths = {
        'assets/vgalemmi.exe', 'src/game_code_after_sprite_banks.asm',
        'assets/main.dat', 'assets/adlib.dat', 'assets/tandysnd.dat',
        'metadata/inputs.json', 'metadata/oracle.json', 'metadata/toolchain-lock.json',
        'c/fixed_word_banks.c', 'c/fixed_word_banks.h', 'c/mask_generators.c',
        'c/mask_generators.h', 'c/lemmings_sym.h', 'c/regs.h', 'c/special_blit.h',
        'tests/fixed_word_banks.py', 'tests/entity_interactions.py',
        'tests/sprite_bank.py', 'tests/minimap_vga.py', 'tests/entity_sprite_layout.py',
        'tests/entity_sprite_planes.py',
        'tests/pcspeaker_dispatch.py', 'tests/sound_latches.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/difftest.py', 'tools/resources.py', 'tools/unpack.py',
    }
    return {p: sha((ROOT / p).read_bytes()) for p in sorted(paths)}


def collect(ref, case, core, checks):
    return dict(case=case['name'], boundary='core' if core else 'adapter',
                status=ref['status'], sites=sorted(pc for scope, pc in ref['sites']
                                                   if scope == 'main'),
                edges=sorted([a, b] for scope, a, b in ref['edges'] if scope == 'main'),
                ordered_events=len(ref['events']), original_steps=ref['steps'],
                trace_storage_bytes=len(ref['events'].data) * ref['events'].data.itemsize,
                independent_bytes=checks, output_segment=ref['regs']['es'],
                output_offset=ref['regs']['di'])


def publish(path, before, rows, mutants=None):
    sites = {pc for row in rows for pc in row['sites']}
    edges = {tuple(edge) for row in rows for edge in row['edges']}
    check(sites == set(MAIN_INS), 'missing translated instruction sites')
    check(edges <= branch_edges(MAIN_INS), 'unexpected integrated branch outcome')
    check(edges & branch_edges(MAIN_INS) == branch_edges(MAIN_INS),
          'missing fixed word branch outcome')
    report = dict(image='main', image_sha256=sha(IMAGE), case_count=len(cases()),
                  comparison_count=len(rows), translated_code_bytes=28,
                  instruction_sites=10, integrated_code_bytes=len(IMAGE[ENTRY:END]),
                  integrated_instruction_sites=len(MAIN_INS),
                  child_translated_code_bytes=len(IMAGE[CHILD:END]),
                  child_instruction_sites=len(CHILD_INS),
                  executed_instruction_addresses=sorted(sites),
                  parent_executed_instruction_addresses=sorted(sites & set(PARENT_INS)),
                  child_executed_instruction_addresses=sorted(sites & set(CHILD_INS)),
                  branch_edges=sorted([a, b] for a, b in edges),
                  branch_edge_count=len(edges),
                  ordered_events=sum(row['ordered_events'] for row in rows),
                  original_instruction_steps=sum(row['original_steps'] for row in rows),
                  independent_output_bytes=sum(row['independent_bytes'] for row in rows),
                  original_only=mutants is None, mutation_count=len(mutants or []),
                  mutations=mutants or [], rows=rows, input_hashes=before,
                  source_a=SOURCE_A, source_b=SOURCE_B,
                  limits=dict(timeout_seconds=WORKER_SECONDS, process_commit_mib=MEMORY_MIB,
                              original_instruction_limit=MAX_STEPS, bus_event_limit=MAX_EVENTS,
                              trace_bytes_per_event=20))
    write_json(path, report)
    print(f'PASS fixed word banks: {len(cases())} fixtures/{len(rows)} boundaries, '
          f'{len(sites)} sites/{len(edges)} edges, {report["ordered_events"]} events, '
          f'{len(mutants or [])} mutants', flush=True)


def worker(directory, snapshot):
    before = json.loads(Path(snapshot).read_text())
    check(before == hashes(), 'input snapshot differs')
    native = Native(directory)
    rows = []
    for case in cases():
        for core in (True, False):
            ref, checks = compare(native, case, core=core)
            rows.append(collect(ref, case, core, checks))
            del ref
            gc.collect()
        print('CHECKED native ' + case['name'], flush=True)
    by_name = {case['name']: case for case in cases()}
    witnesses = [
        (1, 'selector-provider', True),
        (2, 'constructed-source', True),
        (3, 'provider-saved-bx-vga-stack', True),
        (4, 'constructed-source', True),
        (5, 'changed-first-child-return', True),
        (6, 'df-backward-source', True),
        (7, 'constructed-source', True),
        (8, 'stack-offset-one', True),
        (9, 'output-replaces-outer-ret', False),
        (10, 'constructed-source', False),
    ]
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
    check(before == hashes(), 'inputs changed during native campaign')
    publish(REPORT, before, rows, mutants)


def original_campaign():
    before, rows = hashes(), []
    for case in cases():
        memory, regs, device = setup(case)
        for core in (True, False):
            ref = original(case, memory, regs, device, core=core)
            rows.append(collect(ref, case, core, validate(case, memory, regs, ref, core=core)))
            del ref
            gc.collect()
        print('CHECKED original ' + case['name'], flush=True)
    check(before == hashes(), 'inputs changed during original campaign')
    publish(ORIGINAL_REPORT, before, rows)


def main():
    args = sys.argv[1:]
    if len(args) == 3 and args[0] == '--worker':
        worker(args[1], args[2])
        return
    if args == ['--original-worker']:
        original_campaign()
        return
    if args not in ([], ['--original-only']):
        raise SystemExit('usage: fixed_word_banks.py [--original-only]')
    BUILD.mkdir(exist_ok=True)
    if args:
        run_bounded([sys.executable, __file__, '--original-worker'], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=MEMORY_MIB, check=True)
        return
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='fixed-word-banks-', parent=BUILD) as directory:
        snapshot = Path(directory) / 'inputs.json'
        snapshot.write_text(json.dumps(hashes()))
        run_bounded([sys.executable, __file__, '--worker', str(directory), str(snapshot)],
                    cwd=ROOT, timeout=WORKER_SECONDS, memory_mib=MEMORY_MIB, check=True)


if __name__ == '__main__':
    main()

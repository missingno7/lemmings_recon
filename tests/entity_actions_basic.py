"""Bounded original-versus-C checks for selector 2/3/4 action bodies."""
import copy
import ctypes as ct
import gc
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]
import capstone
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
import entity_interactions as interactions
import entity_action_sound as feedback
import sound_latches as sound
from minimap_vga import VGA_BASE

SIZE, MASK, FLAGS = interactions.SIZE, interactions.MASK, interactions.FLAGS
EVENT_LIMIT, INSTRUCTION_LIMIT = 2048, 1024
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 180, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-actions-basic-differential.json'
IMAGE = interactions.IMAGE

ENTRIES = {2: 0x329B, 3: 0x3557, 4: 0x31C4}
RANGES = ((0x329B, 0x32BD), (0x3557, 0x357E), (0x31C4, 0x31E5),
          (0x320C, 0x320D))
MAIN_INS = dict(feedback.OWN_INS)
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
for start, end in RANGES:
    for ins in MD.disasm(IMAGE[start:end], start):
        if ins.address in MAIN_INS:
            raise AssertionError(f'overlapping action instruction {ins.address:04X}')
        MAIN_INS[ins.address] = ins
OWN_INS = {address: ins for address, ins in MAIN_INS.items()
           if any(start <= address < end for start, end in RANGES)}
OWN_BYTES = sum(end - start for start, end in RANGES)
OWN_EDGES = set()
for address, ins in OWN_INS.items():
    if ins.group(capstone.CS_GRP_JUMP):
        target = ins.operands[0].imm & 0xFFFF
        OWN_EDGES.add((address, target))
        if ins.mnemonic.lower() != 'jmp':
            OWN_EDGES.add((address, (address + ins.size) & 0xFFFF))
assert OWN_BYTES == 107 and len(OWN_INS) == 31 and len(OWN_EDGES) == 22


class BasicCall(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('entry', 'value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y',
                 'code_segment', 'data_segment', 'extra_segment',
                 'stack_segment', 'stack_offset', 'flags')]


class BasicResult(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y',
                 'code_segment', 'data_segment', 'extra_segment',
                 'stack_segment', 'stack_offset', 'flags', 'continuation',
                 'status')]


class BasicAccess(interactions.Access):
    event_limit = EVENT_LIMIT

    def __init__(self, case, memory, regs, device, *, defer_providers=False):
        super().__init__(case, memory, regs, device)
        self.defer_providers = defer_providers
        self.pending = []

    def instruction_complete(self):
        pending, self.pending = self.pending, []
        for address, value in pending:
            self.store(address, value)

    def _apply_or_defer(self, address, value):
        if self.defer_providers:
            self.pending.append((address & MASK, value & 0xFF))
        else:
            self.store(address, value)

    def _provider_word(self, segment, offset, value):
        address = interactions.physical(segment, offset)
        self._apply_or_defer(address, value & 0xFF)
        self._apply_or_defer(address + 1, value >> 8)

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        address &= MASK
        # This provider changes the live count byte after its CMP read. The
        # next selector-3 marker read aliases the same byte, then the later DEC
        # must read the value written by MOV [SI+25],FF.
        count_alias = (self.case.get('provider') == 'live-count-alias' and
                       kind == 'read' and 'live-count' not in self.used and
                       address == interactions.physical(self.regs['ds'], 0x006D))
        saved_ds_alias = (self.case.get('provider') == 'sound-saved-ds' and
                          kind == 'write' and 'sound-ds' not in self.used and
                          address == interactions.physical(self.regs['ss'],
                              (self.regs['sp'] - 7) & 0xFFFF))
        result = super().access(kind, address, flags, mask, value)
        if count_alias:
            self.used.add('live-count')
            self._apply_or_defer(address, 0)
        if saved_ds_alias:
            segment = self.regs['ss']
            offset = (self.regs['sp'] - 8) & 0xFFFF
            self._provider_word(segment, offset, self.case['provider_ds'])
            self.used.add('sound-ds')
        return result

    def out_word(self, port, value, flags, mask):
        if len(self.events) >= self.event_limit:
            raise interactions.OracleFailure(
                'entity-actions-basic callback event budget exhausted')
        if self.device is None or port not in (0x3C4, 0x3CE):
            raise interactions.OracleFailure(
                f'entity-actions-basic unexpected OUT {port:04X}')
        self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))


def make_case(name, selector, **kwargs):
    return dict(name=name, selector=selector, **kwargs)


def cases():
    rows = [
        make_case('s2-success-replaces-whole-latch', 2, count=1,
                  flag24=2, state=0),
        make_case('s2-count-wrap', 2, count=0xFF, flag24=0, state=0),
        make_case('s2-counter-overflow-80', 2, count=0x80, flag24=0, state=0),
        make_case('s2-count-zero-reject', 2, count=0, flag24=0, state=0),
        make_case('s2-bit-zero-latch-reject', 2, count=1, flag24=1, state=0),
        make_case('s2-mask-high-0100-reject', 2, count=1, flag24=0,
                  state=0x0100),
        make_case('s2-mask-bit-zero-reject', 2, count=1, flag24=0, state=1),
        make_case('s2-mask-bit-one-reject', 2, count=1, flag24=0, state=2),
        make_case('s2-df-set', 2, count=1, flag24=0, state=0, flags=0x04D7),
        make_case('s2-stack-word-wrap', 2, count=1, flag24=0, state=0,
                  ss=0xFFFF, sp=0x000F, outer_return=0xABCD),
        make_case('s2-vga-live-ret-stack', 2, count=1, flag24=0, state=0,
                  ss=0xA000, sp=0x0800, vga=True, outer_return=0xBEEF),
        make_case('s2-pc-feedback', 2, count=1, flag24=0, state=0,
                  enabled=0, options=1),
        make_case('s2-pc-unbound-vector', 2, count=1, flag24=0, state=0,
                  enabled=0, options=1, pc_vector=(0x0182, 0x6200)),
        make_case('s3-success', 3, count=1, marker25=0, state=0),
        make_case('s3-count-wrap', 3, count=0xFF, marker25=0, state=0),
        make_case('s3-counter-overflow-80', 3, count=0x80, marker25=0, state=0),
        make_case('s3-count-zero-reject', 3, count=0, marker25=0, state=0),
        make_case('s3-marker-reject', 3, count=1, marker25=1, state=0),
        make_case('s3-mask-high-0100-reject', 3, count=1, marker25=0,
                  state=0x0100),
        make_case('s3-mask-bit-zero-reject', 3, count=1, marker25=0, state=1),
        make_case('s3-mask-bit-one-reject', 3, count=1, marker25=0, state=2),
        make_case('s3-live-count-marker-alias', 3, count=1, marker25=1,
                  state=0, si=0x0048, provider='live-count-alias'),
        make_case('s3-adlib-feedback', 3, count=1, marker25=0, state=0,
                  enabled=0xFF, options=3, driver='adlib'),
        make_case('s3-tandy-feedback', 3, count=1, marker25=0, state=0,
                  enabled=0xFF, options=3, driver='tandysnd'),
        make_case('s3-unbound-sound-vector', 3, count=1, marker25=0,
                  state=0, enabled=0xFF, options=3,
                  sound_vector=(0, 0x6200)),
        make_case('s3-changed-sound-iret', 3, count=1, marker25=0,
                  state=0, enabled=0xFF, options=3,
                  provider='sound-interrupt-return', provider_return=0x31F8),
        make_case('s3-sound-returned-ds', 3, count=1, marker25=0,
                  state=0, enabled=0xFF, options=3,
                  provider='sound-saved-ds', provider_ds=0x6200),
        make_case('s4-success', 4, count=1, flag20=0, state=0),
        make_case('s4-count-wrap', 4, count=0xFF, flag20=0, state=0),
        make_case('s4-counter-overflow-80', 4, count=0x80, flag20=0, state=0),
        make_case('s4-count-zero-reject', 4, count=0, flag20=0, state=0),
        make_case('s4-marker-reject', 4, count=1, flag20=1, state=0),
        make_case('s4-mask-bit-zero-reject', 4, count=1, flag20=0, state=1),
        make_case('s4-mask-bit-one-reject', 4, count=1, flag20=0, state=2),
        make_case('s4-mask-4000-reject', 4, count=1, flag20=0,
                  state=0x4000),
        make_case('s4-mask-8000-reject', 4, count=1, flag20=0,
                  state=0x8000),
        make_case('s4-refresh-marker-alias', 4, count=1, flag20=0,
                  state=0, si=0x0052),
        make_case('s4-count-state-alias', 4, count=4, flag20=0,
                  state=4, si=0x0068),
        make_case('s4-sound-feedback', 4, count=1, flag20=0, state=0,
                  enabled=0xFF, options=3),
    ]
    return rows


def put8(memory, segment, offset, value):
    memory[interactions.physical(segment, offset)] = value & 0xFF


def put16(memory, segment, offset, value):
    address = interactions.physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def get8(memory, segment, offset):
    return memory[interactions.physical(segment, offset)]


def get16(memory, segment, offset):
    address = interactions.physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def setup(case):
    memory, regs, device, pc_binding, sound_binding, _ = interactions.setup(case)
    selector = case['selector']
    regs['ip'] = ENTRIES[selector]
    ds, si = regs['ds'], regs['si']
    # Distinct neighboring globals make unintended selector writes visible.
    for offset, value in ((0x6A, 0x31), (0x6D, 0x42), (0x70, 0x53),
                          (0x6B, 0x19), (0x6C, 0x29), (0x6E, 0x39),
                          (0x6F, 0x49), (0x71, 0x59), (0x72, 0x69)):
        put8(memory, ds, offset, value)
    count_offset = {2: 0x6A, 3: 0x6D, 4: 0x70}[selector]
    put8(memory, ds, count_offset, case.get('count', 1))
    put16(memory, ds, si + 8, case.get('state', 0))
    put8(memory, ds, si + 0x20, case.get('flag20', 0))
    put8(memory, ds, si + 0x24, case.get('flag24', 0))
    put8(memory, ds, si + 0x25, case.get('marker25', 0))

    if case.get('vga'):
        if device is None or regs['ss'] != 0xA000:
            raise AssertionError(case['name'] + ': invalid VGA RET-stack fixture')
        device.seq[2] = 0x0F
        device.gc[0] = device.gc[1] = device.gc[3] = device.gc[5] = 0
        device.gc[8] = 0xFF
        address = interactions.physical(regs['ss'], regs['sp'])
        offset = (address - VGA_BASE) & 0xFFFF
        ret = case.get('outer_return', interactions.OUTER_RETURN)
        device.planes[0][offset] = ret & 0xFF
        device.planes[0][(offset + 1) & 0xFFFF] = ret >> 8
    return memory, regs, device, pc_binding, sound_binding


def original(case, memory, regs, device, *, core):
    regs['ip'] = ENTRIES[case['selector']]
    factory = lambda c, m, r, d: BasicAccess(
        c, m, r, d, defer_providers=True)
    core_stops = ({0x320B: 0, 0x320C: 0, 0x329A: 0}
                  if core else None)
    return interactions.original(
        case, memory, regs, device, core, entry_flag_mask=FLAGS,
        main_instructions=MAIN_INS, access_factory=factory,
        stop_offsets=core_stops,
        instruction_limit=INSTRUCTION_LIMIT)


def independent_action(case, initial_memory, initial_regs):
    """Project the selector-owned memory effects independently of the CPU run."""
    memory = bytearray(initial_memory)
    selector = case['selector']
    ds, si = initial_regs['ds'], initial_regs['si']
    count_offset = {2: 0x6A, 3: 0x6D, 4: 0x70}[selector]
    provider_count = case.get('provider') == 'live-count-alias'
    count_before = get8(memory, ds, count_offset)
    if provider_count:
        interactions.oracle_require(selector == 3 and count_before != 0,
            case['name'] + ': invalid live-count provider witness')
        put8(memory, ds, count_offset, 0)

    if selector == 2:
        eligible = (count_before != 0 and
                    (get8(memory, ds, si + 0x24) & 1) == 0 and
                    (get16(memory, ds, si + 8) & 0x0103) == 0)
    elif selector == 3:
        marker = get8(memory, ds, si + 0x25)
        eligible = (count_before != 0 and marker == 0 and
                    (get16(memory, ds, si + 8) & 0x0103) == 0)
    else:
        eligible = (count_before != 0 and get8(memory, ds, si + 0x20) == 0 and
                    (get16(memory, ds, si + 8) & 0xC003) == 0)

    writes = []
    if eligible:
        if selector == 2:
            value = (get8(memory, ds, count_offset) - 1) & 0xFF
            put8(memory, ds, count_offset, value)
            writes.append((interactions.physical(ds, count_offset), value))
            put8(memory, ds, si + 0x24, 1)
            writes.append((interactions.physical(ds, si + 0x24), 1))
        elif selector == 3:
            put8(memory, ds, si + 0x25, 0xFF)
            writes.append((interactions.physical(ds, si + 0x25), 0xFF))
            value = (get8(memory, ds, count_offset) - 1) & 0xFF
            put8(memory, ds, count_offset, value)
            writes.append((interactions.physical(ds, count_offset), value))
            put8(memory, ds, 0x6F, 0)
            writes.append((interactions.physical(ds, 0x6F), 0))
        else:
            value = (get8(memory, ds, count_offset) - 1) & 0xFF
            put8(memory, ds, count_offset, value)
            writes.append((interactions.physical(ds, count_offset), value))
            put8(memory, ds, 0x72, 0)
            writes.append((interactions.physical(ds, 0x72), 0))
            put8(memory, ds, si + 0x20, 0x4F)
            writes.append((interactions.physical(ds, si + 0x20), 0x4F))
    return eligible, memory, writes


def assert_independent_action(case, initial_memory, initial_regs, observed, *, core):
    eligible, projected, expected_writes = independent_action(
        case, initial_memory, initial_regs)
    interactions.oracle_require(observed['status'] in (0, 1, 2, 3, 4, 5, 6),
                                case['name'] + ': unexpected action status')
    if eligible:
        interactions.oracle_require(observed['continuation'] != 0x320C,
            case['name'] + ': eligible selector took shared failure RET')
    elif core:
        interactions.oracle_require(observed['continuation'] == 0x320C,
            case['name'] + ': rejected selector missed shared failure RET')
    else:
        outer = case.get('outer_return', interactions.OUTER_RETURN)
        interactions.oracle_require(observed['continuation'] == outer,
            case['name'] + ': failure RET did not consume the live outer word')
    ds, si = initial_regs['ds'], initial_regs['si']
    offsets = {0x6A, 0x6B, 0x6C, 0x6D, 0x6E, 0x6F,
               0x70, 0x71, 0x72, si + 8, si + 0x20,
               si + 0x24, si + 0x25}
    for offset in offsets:
        address = interactions.physical(ds, offset)
        interactions.oracle_require(observed['memory'][address] == projected[address],
            f"{case['name']}: independent action byte DS:{offset & 0xFFFF:04X} "
            f"{observed['memory'][address]:02X}/{projected[address]:02X}; "
            f"status={observed['status']} continuation="
            f"{observed['continuation']:04X} writes=" + repr([
                (f'{event[1]:05X}', f'{event[2]:02X}')
                for event in observed['events'] if event[0] == 'write'][:12]))
    if expected_writes:
        writes = [(event[1], event[2]) for event in observed['events']
                  if event[0] == 'write']
        at = 0
        for expected in expected_writes:
            try:
                at = writes.index(expected, at) + 1
            except ValueError as error:
                raise interactions.OracleFailure(
                    f"{case['name']}: missing ordered selector write {expected}") from error
    if case.get('provider') == 'live-count-alias':
        interactions.oracle_require('live-count' in observed['used'],
                                    case['name'] + ': count provider did not fire')
    if case.get('provider') == 'sound-saved-ds':
        interactions.oracle_require('sound-ds' in observed['used'] and
                                    observed['regs']['ds'] == case['provider_ds'],
            case['name'] + ': sound saved-DS provider did not reach returned DS')


def own_row(case, expected, core):
    sites = {address for source, address in expected['sites']
             if source == 'main' and address in OWN_INS}
    edges = {(source_ip, target)
             for source, source_ip, target in expected['edges']
             if source == 'main' and source_ip in OWN_INS}
    return dict(name=case['name'], selector=case['selector'], core=core,
                status=expected['status'], continuation=expected['continuation'],
                sites=sorted(sites), edges=[list(edge) for edge in sorted(edges)],
                steps=expected['steps'], event_count=len(expected['events']),
                providers=sorted(expected['used']))


def original_only():
    before = input_hashes()
    all_sites, all_edges = set(), set()
    rows = []
    for case in cases():
        memory, regs, device, _, _ = setup(case)
        for core in (True, False):
            expected = original(case, bytearray(memory), dict(regs),
                                copy.deepcopy(device), core=core)
            assert_independent_action(case, memory, regs, expected, core=core)
            row = own_row(case, expected, core)
            rows.append(row)
            all_sites.update(row['sites'])
            all_edges.update(tuple(edge) for edge in row['edges'])
            if case.get('provider') == 'live-count-alias':
                interactions.oracle_require('live-count' in expected['used'],
                    case['name'] + ': live provider absent in preflight')
    interactions.oracle_require(all_sites == set(OWN_INS),
        f'original action site coverage {len(all_sites)}/{len(OWN_INS)}')
    interactions.oracle_require(all_edges == OWN_EDGES,
        f'original action branch coverage {len(all_edges)}/{len(OWN_EDGES)}')
    interactions.oracle_require(before == input_hashes(),
                                'action inputs changed during original preflight')
    print(f'PASS original entity actions basic: {len(cases())} fixtures x core/adapter, '
          f'{len(all_sites)} sites/{len(all_edges)} edges', flush=True)


def worker_fail(code, error):
    try:
        os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


class Native:
    # Identical live-role APIs reuse this bounded callback/adapter transport.
    cluster = 'entity_actions_basic'
    core_name = 'lmn_entity_actions_basic_core'
    adapter_name = 'lmn_entity_actions_basic_adapter'
    access_type = BasicAccess

    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'{self.cluster}-m{mutation}.dll',
                     mutation, self.cluster)
        self.lib = ct.CDLL(str(path))
        self.core = getattr(self.lib, self.core_name)
        self.core.argtypes = [interactions.MEM, ct.POINTER(BasicCall),
                              ct.POINTER(interactions.PcBinding),
                              ct.POINTER(interactions.SoundBinding),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = BasicResult
        self.adapter = getattr(self.lib, self.adapter_name)
        self.adapter.argtypes = [interactions.MEM,
                                 ct.POINTER(interactions.Regs), ct.c_uint16,
                                 ct.POINTER(interactions.PcBinding),
                                 ct.POINTER(interactions.SoundBinding),
                                 ct.POINTER(interactions.Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial, initial_regs, initial_device,
            pc_binding, sound_binding, *, core):
        memory = bytearray(initial)
        device = copy.deepcopy(initial_device)
        access = self.access_type(case, memory, dict(initial_regs), device)

        def read(_context, _memory, address, flags):
            try:
                return access.access('read', address, flags, FLAGS)
            except BaseException as error:
                worker_fail(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            error)

        def write(_context, _memory, address, value, flags):
            try:
                access.access('write', address, flags, FLAGS, value)
            except BaseException as error:
                worker_fail(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            error)

        def out(_context, port, value, flags):
            try:
                access.out_word(port, value, flags, FLAGS)
            except BaseException as error:
                worker_fail(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            error)

        callbacks = (interactions.READ(read), interactions.WRITE(write),
                     interactions.OUT(out))
        bus = interactions.Bus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = interactions.Regs(**initial_regs)
        pc = ct.byref(pc_binding) if pc_binding is not None else None
        sb = ct.byref(sound_binding) if sound_binding is not None else None
        if core:
            call = BasicCall(
                case['selector'], initial_regs['ax'], initial_regs['bx'],
                initial_regs['cx'], initial_regs['dx'], initial_regs['si'],
                initial_regs['di'], initial_regs['bp'], initial_regs['cs'],
                initial_regs['ds'], initial_regs['es'], initial_regs['ss'],
                initial_regs['sp'], initial_regs['flags'])
            result = self.core(ram, ct.byref(call), pc, sb, ct.byref(bus))
            state.ax, state.bx, state.cx, state.dx = (
                result.value, result.map_cursor, result.count,
                result.auxiliary_value)
            state.si, state.di, state.bp = (result.record_cursor,
                                            result.object_cursor,
                                            result.candidate_y)
            state.cs, state.ds, state.es = (result.code_segment,
                                            result.data_segment,
                                            result.extra_segment)
            state.ss, state.sp, state.flags, state.ip = (
                result.stack_segment, result.stack_offset, result.flags,
                result.continuation)
            status = result.status
        else:
            status = self.adapter(ram, ct.byref(state), case['selector'], pc,
                                  sb, ct.byref(bus))
        return dict(memory=bytes(memory),
                    regs={name: getattr(state, name)
                          for name in interactions.REG_NAMES},
                    device=device, events=access.events,
                    providers=set(access.used), status=status,
                    continuation=state.ip)


def compare_events(label, actual, expected):
    interactions.require(len(actual) == len(expected),
        f'{label}: ordered bus events {len(actual)}/{len(expected)}')
    for index, (got, ref) in enumerate(zip(actual, expected)):
        interactions.require(got[:3] == ref[:3],
            f'{label}: event {index} {got[:3]!r}/{ref[:3]!r}')
        interactions.require(((got[3] ^ ref[3]) & ref[4]) == 0,
            f'{label}: event {index} FLAGS {got[3]:04X}/{ref[3]:04X} '
            f'under {ref[4]:04X}')


def compare_case(native, case, *, core):
    memory, regs, device, pc_binding, sound_binding = setup(case)
    label = case['name'] + (' core' if core else ' adapter')
    expected = original(case, bytearray(memory), dict(regs),
                        copy.deepcopy(device), core=core)
    assert_independent_action(case, memory, regs, expected, core=core)
    actual = native.run(case, bytearray(memory), dict(regs),
                        copy.deepcopy(device), pc_binding, sound_binding,
                        core=core)
    interactions.require(actual['status'] == expected['status'],
        f'{label}: status {actual["status"]}/{expected["status"]}')
    interactions.require(actual['continuation'] == expected['continuation'],
        f'{label}: continuation {actual["continuation"]:04X}/'
        f'{expected["continuation"]:04X}')
    for name in interactions.REG_NAMES:
        if name == 'flags':
            continue
        interactions.require(actual['regs'][name] == expected['regs'][name],
            f'{label}: {name} {actual["regs"][name]:04X}/'
            f'{expected["regs"][name]:04X}')
    flag_mask = expected['flag_mask']
    interactions.require(((actual['regs']['flags'] ^ expected['regs']['flags']) &
                          flag_mask) == 0,
        f'{label}: FLAGS {actual["regs"]["flags"]:04X}/'
        f'{expected["regs"]["flags"]:04X} under {flag_mask:04X}')
    interactions.require(actual['memory'] == expected['memory'],
                         label + ': full 1 MiB RAM differs')
    compare_events(label, actual['events'], expected['events'])
    interactions.require(actual['providers'] == expected['used'],
        f'{label}: provider effects {actual["providers"]}/{expected["used"]}')
    if expected['device'] is not None:
        interactions.require(actual['device'].state() == expected['device'].state(),
                              label + ': VGA registers/planes/latches differ')
        got_trace = [(a, b, c) for a, b, c, _ in actual['device'].trace]
        ref_trace = [(a, b, c) for a, b, c, _ in expected['device'].trace]
        interactions.require(got_trace == ref_trace, label + ': VGA trace differs')
    return own_row(case, expected, core)


MUTATION_WITNESSES = {
    1: ('s2-success-replaces-whole-latch', True),
    2: ('s2-mask-high-0100-reject', True),
    3: ('s2-success-replaces-whole-latch', True),
    4: ('s3-live-count-marker-alias', True),
    5: ('s3-live-count-marker-alias', True),
    6: ('s4-refresh-marker-alias', True),
    7: ('s4-success', True),
}


def input_hashes():
    paths = [
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md',
        'docs/bottom-up.md', 'docs/entity-actions.md',
        'src/game_code.asm', 'src/entity_actions.asm', 'src/game_code_late.asm',
        'src/game_code_late_after_palette.asm',
        'src/game_code_late_after_entities.asm', 'src/game_code_late_tail.asm',
        'src/image_tail.asm', 'src/program.asm',
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat',
        'assets/tandysnd.dat', 'metadata/oracle.json', 'metadata/symbols.json',
        'metadata/inputs.json', 'metadata/regions.json', 'metadata/hints.json',
        'metadata/toolchain-lock.json', 'metadata/sound-oracle.json',
        'metadata/pcspeaker-encodings.json', 'metadata/pcspeaker-producers.json',
        'metadata/pcspeaker-regions.json', 'metadata/pcspeaker-symbols.json',
        'metadata/adlib-symbols.json', 'metadata/tandysnd-symbols.json',
        'requirements.txt', 'c/entity_actions_basic.c', 'c/entity_actions_basic.h',
        'c/entity_action_sound.c', 'c/entity_action_sound.h',
        'c/pcspeaker_interrupt.c', 'c/pcspeaker_interrupt.h',
        'c/pcspeaker_dispatch.c', 'c/pcspeaker_dispatch.h', 'c/pcspeaker.c',
        'c/pcspeaker.h', 'c/sound_interrupt.c', 'c/sound_interrupt.h',
        'c/sound_latches.c', 'c/sound_latches.h', 'c/regs.h',
        'c/special_blit.h', 'c/lemmings_sym.h', 'c/pcspeaker_sym.h',
        'c/sound_latches_sym.h', 'tests/entity_actions_basic.py',
        'tests/entity_action_sound.py', 'tests/entity_interactions.py',
        'tests/pcspeaker_dispatch.py', 'tests/sound_latches.py',
        'tests/minimap_vga.py', 'tests/pcspeaker_interrupt.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/coverage.py', 'tools/resources.py', 'tools/unpack.py',
        'tools/difftest.py',
    ]
    return {name: sha((ROOT / name).read_bytes()) for name in sorted(set(paths))}


def worker(directory):
    before = input_hashes()
    specs = cases()
    by_name = {case['name']: case for case in specs}
    baseline = Native(directory, 0)
    rows, all_sites, all_edges = [], set(), set()
    total_events = total_steps = 0
    for case in specs:
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            rows.append(row)
            all_sites.update(row['sites'])
            all_edges.update(tuple(edge) for edge in row['edges'])
            total_events += row['event_count']
            total_steps += row['steps']
    interactions.oracle_require(all_sites == set(OWN_INS),
        f'native action site coverage {len(all_sites)}/{len(OWN_INS)}')
    interactions.oracle_require(all_edges == OWN_EDGES,
        f'native action edge coverage {len(all_edges)}/{len(OWN_EDGES)}')
    del baseline
    gc.collect()

    mutations = []
    for mutation, (name, core) in MUTATION_WITNESSES.items():
        mutant = Native(directory, mutation)
        try:
            compare_case(mutant, by_name[name], core=core)
        except interactions.Mismatch as error:
            mutations.append(dict(id=mutation, witness=name, core=core,
                                  mismatch=str(error), completed=True))
        else:
            raise AssertionError(f'entity-actions-basic mutant {mutation} survived')
        del mutant
        gc.collect()
    interactions.oracle_require(before == input_hashes(),
        'entity-actions-basic inputs changed during bounded native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE), code_ranges=[list(r) for r in RANGES],
        translated_code_bytes=OWN_BYTES, instruction_sites=len(OWN_INS),
        own_static_branch_edges=len(OWN_EDGES),
        conditional_branch_outcomes=sum(2 for address, ins in OWN_INS.items()
            if ins.group(capstone.CS_GRP_JUMP) and ins.mnemonic.lower() != 'jmp'),
        unconditional_jump_edges=sum(1 for address, ins in OWN_INS.items()
            if ins.mnemonic.lower() == 'jmp'),
        parent_feasible_branch_edges=len(all_edges), case_count=len(specs),
        core_adapter_comparisons=len(rows), mutation_count=len(mutations),
        mutations=mutations, executed_instruction_addresses=sorted(all_sites),
        static_instruction_addresses=sorted(OWN_INS),
        branch_edges=[list(edge) for edge in sorted(all_edges)],
        static_branch_edges=[list(edge) for edge in sorted(OWN_EDGES)],
        total_bus_events=total_events, original_instruction_hook_steps=total_steps,
        cases=rows, input_hashes=before,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=TREE_MIB,
                    original_instruction_limit=INSTRUCTION_LIMIT,
                    ordered_bus_event_limit=EVENT_LIMIT,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        domain='Selector entries 329B (2), 3557 (3), and 31C4 (4), plus the '
               'shared failure RET at 320C. The harness compares the whole 1 MiB '
               'RAM image, logical registers, defined FLAGS, ordered RAM/VGA bus '
               'events, live outer RET behavior, and VGA device state when SS uses '
               'the A000 aperture. The independent projection checks each action '
               'eligibility predicate and ordered record/global writes. Fixtures '
               'cover count wrap/zero, each action mask, record/global aliases, a '
               'live count reread provider, PC and AdLib/Tandy feedback, unbound and '
               'changed sound returns, sound-returned DS, DF, stack physical wrap, '
               'and a VGA-backed outer RET. The selector-2 path deliberately leaves '
               'global refresh byte 6C untouched.'))
    print(f'PASS entity actions basic: {len(specs)} fixtures x core/adapter, '
          f'{len(all_sites)} sites/{len(all_edges)} edges, {total_events} events, '
          f'{len(mutations)} completed mutants', flush=True)


def main():
    if sys.argv[1:] == ['--original-only']:
        result = run_bounded([sys.executable, str(Path(__file__).resolve()),
                              '--original-worker'], cwd=ROOT,
                             timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB,
                             check=True)
        if result.stdout:
            sys.stdout.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
        return
    if sys.argv[1:] == ['--original-worker']:
        original_only()
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if sys.argv[1:]:
        raise SystemExit('usage: entity_actions_basic.py [--original-only | --worker DLL_DIRECTORY]')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-actions-basic-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     str(directory)], cwd=ROOT, timeout=WORKER_SECONDS,
                    memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()

"""Bounded original-versus-native checks for the 3150 entity-action prefix."""
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
import sound_latches as sound
from minimap_vga import VGA_BASE, VGA_END
from unpack import ASSET, unpack

SIZE, MASK, FLAGS = interactions.SIZE, interactions.MASK, interactions.FLAGS
ENTRY, END = 0x3150, 0x31C4
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 240, 384, 640
INSTRUCTION_LIMIT, EVENT_LIMIT = 512, 4096
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-action-dispatch-differential.json'

IMAGE = interactions.IMAGE
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True

# UNKNOWN bytes at 3160, 3199 and 31BC are intentionally left out of the
# disassembly. Selector children 2/3/4 and their shared feedback tail are
# included only so the original oracle can follow those real direct JMPs.
OWN_RANGES = ((0x3150, 0x3160), (0x3161, 0x3199),
              (0x319A, 0x31BC), (0x31BD, 0x31C4))
OWN_INS = {}
for start, end in OWN_RANGES:
    OWN_INS.update({ins.address: ins for ins in MD.disasm(IMAGE[start:end], start)})
COMPOSED_INS = dict(OWN_INS)
for start, end in ((0x31C4, 0x320D), (0x329B, 0x32BD), (0x3557, 0x357E)):
    COMPOSED_INS.update({ins.address: ins for ins in MD.disasm(IMAGE[start:end], start)})

CONDITIONALS = {
    address for address, ins in OWN_INS.items()
    if ins.group(capstone.CS_GRP_JUMP) and ins.mnemonic.lower() != 'jmp'
}
OWN_EDGES = set()
for address in CONDITIONALS:
    ins = OWN_INS[address]
    OWN_EDGES.add((address, ins.operands[0].imm & 0xFFFF))
    OWN_EDGES.add((address, (address + ins.size) & 0xFFFF))
UNTRANSLATED = {5: 0x3336, 6: 0x32BD, 7: 0x34CE,
                8: 0x3598, 9: 0x320D}
STOP_OFFSETS = {address: 1 for address in UNTRANSLATED.values()}
NAMES = interactions.REG_NAMES
REG_IDS = interactions.REG_IDS
MEM = interactions.MEM

assert sum(end - start for start, end in OWN_RANGES) == 113
assert len(OWN_INS) == 43
assert len(OWN_EDGES) == 28


class DispatchCall(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y',
                 'code_segment', 'data_segment', 'extra_segment',
                 'stack_segment', 'stack_offset', 'flags')]


class DispatchResult(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y',
                 'code_segment', 'data_segment', 'extra_segment',
                 'stack_segment', 'stack_offset', 'flags', 'continuation',
                 'status', 'child_entry', 'child_status')]


class DispatchAccess(interactions.Access):
    event_limit = EVENT_LIMIT

    def _provider(self, kind, address):
        super()._provider(kind, address)
        if (self.case.get('provider') == 'latch-selector' and kind == 'write' and
                address == interactions.physical(self.regs['ds'], 0x61) and
                'dispatch' not in self.used):
            self.modify_word(self.regs['ds'], 0x58,
                             self.case.get('provider_record', 0x4100))
            self.store(interactions.physical(self.regs['ds'], 0x82),
                       self.case.get('provider_selector', 5))
            self.used.add('dispatch')


def setup(case):
    memory, regs, device, pc_binding, sound_binding, _ = interactions.setup(case)
    regs['ip'] = ENTRY
    ds = regs['ds']
    interactions.put8(memory, ds, 0x2B, case.get('update_gate', 0))
    interactions.put8(memory, ds, 0x50, case.get('work_guard', 0))
    interactions.put8(memory, ds, 0x63, case.get('candidate_count', 1))
    interactions.put16(memory, ds, 0x14, case.get('input_word', 0xA501))
    interactions.put8(memory, ds, 0x61, case.get('latch', 0))
    interactions.put16(memory, ds, 0x58,
                       case.get('selected_record', regs['si']))
    interactions.put8(memory, ds, 0x82, case.get('selector', 2))

    # Access to a VGA-aperture stack word is device-backed by the shared oracle.
    # Mirror the constructed RET in the selected read plane as well as RAM.
    if device is not None:
        address = interactions.physical(regs['ss'], regs['sp'])
        if VGA_BASE <= address < VGA_END:
            offset = (address - VGA_BASE) & 0xFFFF
            ret = case.get('outer_return', interactions.OUTER_RETURN)
            device.planes[device.gc[4] & 3][offset] = ret & 0xFF
            device.planes[device.gc[4] & 3][(offset + 1) & 0xFFFF] = ret >> 8
    return memory, regs, device, pc_binding, sound_binding


def get8(memory, segment, offset):
    return memory[interactions.physical(segment, offset)]


def original(case, memory, regs, device, *, core):
    regs['ip'] = ENTRY
    return interactions.original(
        case, memory, regs, device, core,
        entry_flag_mask=FLAGS,
        main_instructions=COMPOSED_INS,
        stop_offsets=STOP_OFFSETS if core else STOP_OFFSETS,
        access_factory=DispatchAccess,
        instruction_limit=INSTRUCTION_LIMIT)


def expected_child(case, observed):
    if (case.get('update_gate', 0) == 0xFF or
            case.get('work_guard', 0) == 0xFF or
            case.get('candidate_count', 1) == 0 or
            (case.get('input_word', 0xA501) & 1) == 0 or
            case.get('latch', 0) == 0xFF):
        return 0, 0xFFFF
    selector = case.get('provider_selector', 5) if case.get('provider') == 'latch-selector' else case.get('selector', 2)
    if observed['continuation'] in UNTRANSLATED.values() and observed['status'] == 1:
        return observed['continuation'], 0xFFFF
    for value in (2, 3, 4):
        entry = selector_entry(value)
        if ('main', entry) in observed['sites']:
            return entry, 0 if observed['status'] == 0 else observed['status']
    return 0, 0xFFFF


def selector_entry(selector):
    return {2: 0x329B, 3: 0x3557, 4: 0x31C4}[selector]


def parent_status(case, observed):
    child_entry, _ = expected_child(case, observed)
    if child_entry in UNTRANSLATED.values():
        return 1
    if child_entry in (0x329B, 0x3557, 0x31C4) and observed['status'] != 0:
        return 2
    return observed['status']


def case_record(case, expected, core):
    sites = {address for source, address in expected['sites']
             if source == 'main' and address in OWN_INS}
    edges = {(source_ip, target)
             for source, source_ip, target in expected['edges']
             if source == 'main' and source_ip in CONDITIONALS}
    return dict(name=case['name'], selector=case.get('selector'), core=core,
                status=parent_status(case, expected),
                continuation=expected['continuation'], sites=sorted(sites),
                edges=[list(edge) for edge in sorted(edges)],
                event_count=len(expected['events']), steps=expected['steps'],
                providers=sorted(expected['used']))


def cases():
    rows = [dict(name=f'raw-selector-{value:02x}', selector=value)
            for value in range(256)]
    rows.extend([
        dict(name='gate-update-ff-latch-77', selector=2,
             update_gate=0xFF, latch=0x77),
        dict(name='gate-work-guard-ff', selector=2, work_guard=0xFF),
        dict(name='gate-no-candidates', selector=2, candidate_count=0),
        dict(name='input-clear', selector=2, input_word=0xA500),
        dict(name='input-clear-clears-latched', selector=2,
             input_word=0xFFFE, latch=0xFF),
        dict(name='latch-already-set', selector=2, latch=0xFF),
        dict(name='input-high-word', selector=0x0A, input_word=0xA501),
        dict(name='provider-latch-reread-selector', selector=2,
             provider='latch-selector', provider_record=0x4100,
             provider_selector=5),
        dict(name='physical-stack-word-wrap', selector=0x0A,
             ss=0xFFFF, sp=0x000F),
        dict(name='vga-stack-return', selector=0x0A,
             ss=0xA000, sp=0x0400, vga=True),
        dict(name='ds-segment-wrap', selector=0x0A, ds=0xFFFF),
        dict(name='df-set-selector', selector=0x0A, flags=0x04D7),
        dict(name='ds-ss-selected-pointer-alias', selector=0x0A,
             ds=0x5000, ss=0x5000, sp=0x0058, si=0x4000,
             selected_record=0x4000, outer_return=0x4000),
        dict(name='selector2-basic-failure', selector=2),
        dict(name='selector2-feedback-pc-returned-ds', selector=2,
             action_count0=1, record_bits=0, entity_flags=0,
             enabled=0, options=1, provider='pc-registers',
             provider_ds=0x6200, provider_si=0x7070, provider_cx=0x3131,
             provider_enabled=0xFF, provider_options=3),
        dict(name='selector2-feedback-pc-changed-return', selector=2,
             action_count0=1, record_bits=0, entity_flags=0,
             enabled=0, options=1, provider='pc-interrupt-return',
             provider_return=0x3456),
        dict(name='selector2-feedback-pc-unbound', selector=2,
             action_count0=1, record_bits=0, entity_flags=0,
             enabled=0, options=1, pc_vector=(0x0182, 0x6200)),
        dict(name='selector2-feedback-pc-changed-child', selector=2,
             action_count0=1, record_bits=0, entity_flags=0,
             enabled=0, options=1, provider='pc-child-return',
             provider_return=0x3456),
        dict(name='selector3-feedback-external', selector=3,
             action_count1=1, record_bits=0, marker3=0,
             enabled=0xFF, options=3),
        dict(name='selector3-feedback-sound-changed-return', selector=3,
             action_count1=1, record_bits=0, marker3=0,
             enabled=0xFF, options=3, provider='sound-interrupt-return',
             provider_return=0x3456),
        dict(name='selector3-feedback-sound-unbound', selector=3,
             action_count1=1, record_bits=0, marker3=0,
             enabled=0xFF, options=3, sound_vector=(0, 0x6200)),
        dict(name='selector3-feedback-tandy', selector=3, driver='tandysnd',
             action_count1=1, record_bits=0, marker3=0,
             enabled=0xFF, options=3),
        dict(name='selector4-feedback-df', selector=4,
             action_count2=1, record_bits=0, action4_flag=0,
             enabled=0xFF, options=0, flags=0x04D7),
    ])
    for row in rows:
        row.setdefault('action_count0', 0)
        row.setdefault('action_count1', 0)
        row.setdefault('action_count2', 0)
    return rows


def set_action_fields(memory, regs, case):
    ds, si = regs['ds'], regs['si']
    for selector, key, offset in ((2, 'action_count0', 0x6A),
                                  (3, 'action_count1', 0x6D),
                                  (4, 'action_count2', 0x70)):
        interactions.put8(memory, ds, offset, case.get(key, 0))
    interactions.put8(memory, ds, si + 0x24,
                       case.get('entity_flags', 0xA5))
    interactions.put8(memory, ds, si + 0x25, case.get('marker3', 0xFF))
    interactions.put8(memory, ds, si + 0x20,
                       case.get('action4_flag', 0x4F))
    if 'record_bits' in case:
        interactions.put16(memory, ds, si + 8, case['record_bits'])


def setup_case(case):
    memory, regs, device, pc_binding, sound_binding = setup(case)
    set_action_fields(memory, regs, case)
    # Make a provider-selected record readable and semantically inactive.
    if case.get('provider') == 'latch-selector':
        interactions.put16(memory, regs['ds'], case.get('provider_record', 0x4100) + 8, 0)
        interactions.put8(memory, regs['ds'], case.get('provider_record', 0x4100) + 0x24, 0)
    return memory, regs, device, pc_binding, sound_binding


def assert_original_path(case, expected, *, core):
    selector = case.get('provider_selector', 5) if case.get('provider') == 'latch-selector' else case.get('selector', 2)
    initial_latch = case.get('latch', 0)
    gate_return = None
    if case.get('update_gate', 0) == 0xFF:
        gate_return = 0x31BD
    elif case.get('work_guard', 0) == 0xFF:
        gate_return = 0x31BD
    elif case.get('candidate_count', 1) == 0:
        gate_return = 0x31BD
    elif (case.get('input_word', 0xA501) & 1) == 0:
        gate_return = 0x31C3
    elif initial_latch == 0xFF:
        gate_return = 0x31BD
    if gate_return is not None:
        want_ip = gate_return if core else case.get('outer_return', interactions.OUTER_RETURN)
        interactions.oracle_require(expected['status'] == 0 and
                                    expected['continuation'] == want_ip,
            f"{case['name']}: gate return expected {want_ip:04X}, got "
            f"{expected['continuation']:04X}/{expected['status']}")
        return
    if expected['continuation'] in UNTRANSLATED.values() and expected['status'] == 1:
        target = expected['continuation']
        interactions.oracle_require(target == UNTRANSLATED[selector],
            f"{case['name']}: unsupported selector target {target:04X} mismatches")
        return
    if selector in (2, 3, 4) and ('main', selector_entry(selector)) in expected['sites']:
        interactions.oracle_require(expected['status'] == 0 or
                                    case.get('provider') in
                                    ('pc-interrupt-return', 'pc-child-return',
                                     'sound-interrupt-return') or
                                    case.get('pc_vector') is not None or
                                    case.get('sound_vector') is not None or
                                    case.get('pc_binding') is False,
            f"{case['name']}: basic action stopped unexpectedly with status "
            f"{expected['status']}")
        interactions.oracle_require(expected['status'] != 0 or core or
                                    expected['continuation'] == case.get(
                                        'outer_return', interactions.OUTER_RETURN),
            f"{case['name']}: adapter did not consume live outer RET")
        return
    if selector in UNTRANSLATED:
        interactions.oracle_require(expected['status'] == 1 and
                                    expected['continuation'] == UNTRANSLATED[selector],
            f"{case['name']}: unsupported selector did not stop at "
            f"{UNTRANSLATED[selector]:04X}")
        return
    want_ip = 0x31BD if core else case.get('outer_return', interactions.OUTER_RETURN)
    interactions.oracle_require(expected['status'] == 0 and
                                expected['continuation'] == want_ip,
        f"{case['name']}: ordinary selector expected {want_ip:04X}, got "
        f"{expected['continuation']:04X}/{expected['status']}")


def assert_prefix_effects(case, regs, expected):
    ds = regs['ds']
    initial_latch = case.get('latch', 0)
    gated = (case.get('update_gate', 0) == 0xFF or
             case.get('work_guard', 0) == 0xFF or
             case.get('candidate_count', 1) == 0)
    input_word = case.get('input_word', 0xA501)
    if gated:
        interactions.oracle_require(
            get8(expected['memory'], ds, 0x61) == initial_latch,
            case['name'] + ': early gate changed the press latch')
        interactions.oracle_require(expected['regs']['ax'] == regs['ax'] and
                                    expected['regs']['si'] == regs['si'],
            case['name'] + ': early gate changed AX/SI before input/pointer loads')
        return
    if (input_word & 1) == 0:
        interactions.oracle_require(expected['regs']['ax'] == 0 and
            get8(expected['memory'], ds, 0x61) == 0,
            case['name'] + ': released-input path did not clear latch / AX')
        return
    if initial_latch == 0xFF:
        interactions.oracle_require(expected['regs']['ax'] == 1 and
            get8(expected['memory'], ds, 0x61) == 0xFF and
            expected['regs']['si'] == regs['si'],
            case['name'] + ': held-latch path loaded selector/pointer or changed latch')
        return

    interactions.oracle_require(
        get8(expected['memory'], ds, 0x61) == 0xFF,
        case['name'] + ': armed action did not set press latch')
    latch_address = interactions.physical(ds, 0x61)
    pointer_address = interactions.physical(ds, 0x58)
    selector_address = interactions.physical(ds, 0x82)
    latch_write = next((i for i, event in enumerate(expected['events'])
                        if event[0] == 'write' and event[1] == latch_address and
                        event[2] == 0xFF), None)
    pointer_read = next((i for i, event in enumerate(expected['events'])
                         if event[0] == 'read' and event[1] == pointer_address), None)
    selector_read = next((i for i, event in enumerate(expected['events'])
                          if event[0] == 'read' and event[1] == selector_address), None)
    interactions.oracle_require(latch_write is not None and pointer_read is not None and
                                selector_read is not None and
                                latch_write < pointer_read < selector_read,
        case['name'] + ': latch write did not precede the live pointer/selector reads')
    if case.get('provider') == 'latch-selector':
        interactions.oracle_require('dispatch' in expected['used'] and
            expected['regs']['si'] == case['provider_record'] and
            (expected['regs']['ax'] & 0xFF) == case['provider_selector'],
            case['name'] + ': latch provider did not change later SI/selector reads')
    elif expected_child(case, expected)[0] == 0:
        selected = case.get('selected_record', regs['si'])
        selector = case.get('selector', 2)
        interactions.oracle_require(expected['regs']['si'] == selected and
            expected['regs']['ax'] == selector,
            case['name'] + ': armed prefix did not retain selected pointer/raw selector')


def original_only():
    before = input_hashes()
    all_sites, all_edges = set(), set()
    seen = 0
    for case in cases():
        memory, regs, device, _pc, _sound = setup_case(case)
        modes = (True,) if case['name'].startswith('raw-selector-') else (True, False)
        for core in modes:
            expected = original(case, bytearray(memory), dict(regs),
                                copy.deepcopy(device), core=core)
            assert_original_path(case, expected, core=core)
            assert_prefix_effects(case, regs, expected)
            assert_special_original(case, expected)
            row = case_record(case, expected, core)
            all_sites.update(row['sites'])
            all_edges.update(tuple(edge) for edge in row['edges'])
            seen += 1
    interactions.oracle_require(all_sites == set(OWN_INS),
        f'original action-dispatch prefix site coverage {len(all_sites)}/{len(OWN_INS)}')
    interactions.oracle_require(all_edges == OWN_EDGES,
        f'original action-dispatch prefix edge coverage {len(all_edges)}/{len(OWN_EDGES)}')
    interactions.oracle_require(before == input_hashes(),
                                'action-dispatch inputs changed during original preflight')
    print(f'PASS original entity action dispatch: {seen} executions, '
          f'{len(all_sites)} prefix sites/{len(all_edges)} branch outcomes', flush=True)


def assert_special_original(case, expected):
    provider = case.get('provider')
    if provider == 'pc-interrupt-return':
        interactions.oracle_require(expected['status'] == 4 and 'pc' in expected['used'],
            case['name'] + ': expected changed INT60 IRET status 4')
    elif provider == 'pc-child-return':
        interactions.oracle_require(expected['status'] == 3 and 'pc' in expected['used'],
            case['name'] + ': expected changed PC child RET status 3')
    elif provider == 'sound-interrupt-return':
        interactions.oracle_require(expected['status'] == 4 and
                                    'sound' in expected['used'],
            case['name'] + ': expected changed INT61 IRET status 4')
    elif provider == 'pc-registers':
        interactions.oracle_require(expected['status'] == 0 and
            'pc' in expected['used'] and expected['regs']['ds'] == case['provider_ds'] and
            expected['regs']['si'] == case['provider_si'] and
            expected['regs']['cx'] == case['provider_cx'],
            case['name'] + ': returned PC register/DS state was not observed')
    elif case.get('pc_vector') is not None:
        interactions.oracle_require(expected['status'] == 1,
            case['name'] + ': expected unbound PC vector status 1')
    elif case.get('sound_vector') is not None:
        interactions.oracle_require(expected['status'] == 1,
            case['name'] + ': expected unbound INT61 vector status 1')


def worker_fail(code, error):
    try:
        os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-action-dispatch-m{mutation}.dll',
                     mutation, 'entity_action_dispatch')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_entity_action_dispatch_core
        self.core.argtypes = [MEM, ct.POINTER(DispatchCall),
                              ct.POINTER(interactions.PcBinding),
                              ct.POINTER(interactions.SoundBinding),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = DispatchResult
        self.adapter = self.lib.lmn_entity_action_dispatch_adapter
        self.adapter.argtypes = [MEM, ct.POINTER(interactions.Regs),
                                 ct.POINTER(interactions.PcBinding),
                                 ct.POINTER(interactions.SoundBinding),
                                 ct.POINTER(interactions.Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial, initial_regs, initial_device,
            pc_binding, sound_binding, *, core):
        memory = bytearray(initial)
        device = copy.deepcopy(initial_device)
        access = DispatchAccess(case, memory, dict(initial_regs), device)

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
            worker_fail(CALLBACK_EXIT,
                        f'unexpected action-dispatch OUT {port:04X}={value:04X}')

        callbacks = (interactions.READ(read), interactions.WRITE(write),
                     interactions.OUT(out))
        bus = interactions.Bus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        regs = interactions.Regs(**initial_regs)
        pb = ct.byref(pc_binding) if pc_binding is not None else None
        sb = ct.byref(sound_binding) if sound_binding is not None else None
        if core:
            call = DispatchCall(*(initial_regs[name] for name in
                ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'cs', 'ds', 'es',
                 'ss', 'sp', 'flags')))
            result = self.core(ram, ct.byref(call), pb, sb, ct.byref(bus))
            regs.ax, regs.bx, regs.cx, regs.dx = (
                result.value, result.map_cursor, result.count,
                result.auxiliary_value)
            regs.si, regs.di, regs.bp = (result.record_cursor,
                                         result.object_cursor,
                                         result.candidate_y)
            regs.cs, regs.ds, regs.es = (result.code_segment,
                                         result.data_segment,
                                         result.extra_segment)
            regs.ss, regs.sp, regs.flags, regs.ip = (
                result.stack_segment, result.stack_offset, result.flags,
                result.continuation)
            status, child_entry, child_status = (
                result.status, result.child_entry, result.child_status)
        else:
            status = self.adapter(ram, ct.byref(regs), pb, sb, ct.byref(bus))
            child_entry, child_status = None, None
        return dict(memory=bytes(memory),
                    regs={name: getattr(regs, name) for name in NAMES},
                    device=device, events=access.events, providers=set(access.used),
                    status=status, continuation=regs.ip,
                    child_entry=child_entry, child_status=child_status)


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
    memory, regs, device, pc_binding, sound_binding = setup_case(case)
    label = case['name'] + (' core' if core else ' adapter')
    expected = original(case, bytearray(memory), dict(regs),
                        copy.deepcopy(device), core=core)
    assert_original_path(case, expected, core=core)
    assert_prefix_effects(case, regs, expected)
    assert_special_original(case, expected)
    actual = native.run(case, bytearray(memory), dict(regs),
                        copy.deepcopy(device), pc_binding, sound_binding,
                        core=core)
    want_status = parent_status(case, expected)
    interactions.require(actual['status'] == want_status,
        f'{label}: status {actual["status"]}/{want_status}')
    interactions.require(actual['continuation'] == expected['continuation'],
        f'{label}: continuation {actual["continuation"]:04X}/'
        f'{expected["continuation"]:04X}')
    for name in NAMES:
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
    child_entry, child_status = expected_child(case, expected)
    if core:
        interactions.require(actual['child_entry'] == child_entry,
            f'{label}: child entry {actual["child_entry"]:04X}/{child_entry:04X}')
        interactions.require(actual['child_status'] == child_status,
            f'{label}: child status {actual["child_status"]:04X}/{child_status:04X}')
    if expected['device'] is not None:
        interactions.require(actual['device'].state() == expected['device'].state(),
                              label + ': VGA registers/planes/latches differ')
        got_trace = [(a, b, c) for a, b, c, _ in actual['device'].trace]
        ref_trace = [(a, b, c) for a, b, c, _ in expected['device'].trace]
        interactions.require(got_trace == ref_trace, label + ': VGA trace differs')
    return case_record(case, expected, core)


MUTATION_WITNESSES = {
    1: ('gate-update-ff-latch-77', True),
    2: ('provider-latch-reread-selector', True),
    3: ('raw-selector-ff', True),
    4: ('provider-latch-reread-selector', True),
    5: ('input-high-word', True),
    6: ('selector2-basic-failure', True),
}


def input_hashes():
    paths = [
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md',
        'docs/bottom-up.md', 'docs/entity-actions.md', 'src/game_code.asm',
        'src/program.asm', 'src/sound/pcspeaker.asm', 'src/sound/adlib.asm',
        'src/sound/tandysnd.asm', 'assets/vgalemmi.exe', 'assets/main.dat',
        'assets/adlib.dat', 'assets/tandysnd.dat', 'metadata/oracle.json',
        'metadata/symbols.json', 'metadata/inputs.json', 'metadata/regions.json',
        'metadata/hints.json', 'metadata/toolchain-lock.json',
        'metadata/sound-oracle.json', 'metadata/pcspeaker-encodings.json',
        'metadata/pcspeaker-producers.json', 'metadata/pcspeaker-regions.json',
        'metadata/pcspeaker-symbols.json', 'metadata/adlib-symbols.json',
        'metadata/tandysnd-symbols.json', 'requirements.txt',
        'c/entity_action_dispatch.c', 'c/entity_action_dispatch.h',
        'c/entity_actions_basic.c', 'c/entity_actions_basic.h',
        'c/entity_action_sound.c', 'c/entity_action_sound.h',
        'c/pcspeaker_interrupt.c', 'c/pcspeaker_interrupt.h',
        'c/pcspeaker_dispatch.c', 'c/pcspeaker_dispatch.h',
        'c/pcspeaker.c', 'c/pcspeaker.h', 'c/sound_interrupt.c',
        'c/sound_interrupt.h', 'c/sound_latches.c', 'c/sound_latches.h',
        'c/regs.h', 'c/special_blit.h', 'c/lemmings_sym.h',
        'c/pcspeaker_sym.h', 'c/sound_latches_sym.h',
        'tests/entity_action_dispatch.py', 'tests/entity_action_sound.py',
        'tests/entity_interactions.py', 'tests/pcspeaker_dispatch.py',
        'tests/sound_latches.py', 'tests/minimap_vga.py',
        'tests/pcspeaker_interrupt.py', 'tools/bounded_process.py',
        'tools/cbuild.py', 'tools/common.py', 'tools/coverage.py',
        'tools/resources.py', 'tools/unpack.py', 'tools/difftest.py',
    ]
    return {name: sha((ROOT / name).read_bytes()) for name in sorted(set(paths))}


def worker(directory):
    before = input_hashes()
    specs = cases()
    by_name = {case['name']: case for case in specs}
    selected = specs
    baseline = Native(directory, 0)
    rows, all_sites, all_edges = [], set(), set()
    total_events = total_steps = 0
    for case in selected:
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            rows.append(row)
            all_sites.update(row['sites'])
            all_edges.update(tuple(edge) for edge in row['edges'])
            total_events += row['event_count']
            total_steps += row['steps']
    interactions.oracle_require(all_sites == set(OWN_INS),
        f'native action-dispatch prefix site coverage {len(all_sites)}/{len(OWN_INS)}')
    interactions.oracle_require(all_edges == OWN_EDGES,
        f'native action-dispatch prefix edge coverage {len(all_edges)}/{len(OWN_EDGES)}')
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
            raise AssertionError(f'entity-action-dispatch mutant {mutation} survived')
        del mutant
        gc.collect()
    interactions.oracle_require(len(mutations) == len(MUTATION_WITNESSES),
                                'entity-action-dispatch mutant witness count changed')
    interactions.oracle_require(before == input_hashes(),
        'action-dispatch inputs changed during bounded native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE),
        code_ranges=[list(pair) for pair in OWN_RANGES],
        translated_code_bytes=113, instruction_sites=len(OWN_INS),
        own_static_branch_edges=len(OWN_EDGES),
        parent_feasible_branch_edges=len(all_edges), case_count=len(selected),
        original_prefix_selector_cases=256,
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
                    callback_budget_exit=GUARD_EXIT,
                    callback_error_exit=CALLBACK_EXIT),
        domain=('The known 3150..31C4 DispatchEntityAction prefix (113 known bytes; '
                'UNKNOWN bytes at 3160, 3199 and 31BC remain excluded). Original-only '
                'fixtures exercise all 256 raw selector bytes. Native fixtures compare '
                'the complete 1 MiB RAM, all registers, instruction-defined FLAGS, '
                'ordered memory callbacks, provider transitions and VGA state where '
                'the live outer stack word occupies the VGA aperture. Selectors 2/3/4 '
                'compose their actual basic-action and shared feedback instructions; '
                'selectors 5..9 stop at their exact untranslated handler entries.')))
    print(f'PASS entity action dispatch: {len(selected)} fixtures x core/adapter, '
          f'{len(all_sites)} sites/{len(all_edges)} branch outcomes, '
          f'{total_events} events, {len(mutations)} completed mutants', flush=True)


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
        raise SystemExit('usage: entity_action_dispatch.py [--original-only | --worker DLL_DIRECTORY]')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-action-dispatch-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     str(directory)], cwd=ROOT, timeout=WORKER_SECONDS,
                    memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()

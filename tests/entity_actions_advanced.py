"""Bounded original-versus-C checks for action selectors 6/7/8/9."""
import copy
import gc
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]
import capstone
from bounded_process import run_bounded, temporary_build_directory
from common import BUILD, sha, write_json
import entity_actions_basic as basic
import entity_interactions as interactions
import entity_action_sound as feedback

SIZE, MASK, FLAGS = interactions.SIZE, interactions.MASK, interactions.FLAGS
EVENT_LIMIT, INSTRUCTION_LIMIT = 4096, 2048
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 240, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-actions-advanced-differential.json'
IMAGE = interactions.IMAGE

ENTRIES = {6: 0x32BD, 7: 0x34CE, 8: 0x3598, 9: 0x320D}
# UNKNOWN 35A1 and 35AB are deliberately excluded from decoding and ownership.
RANGES = ((0x32BD, 0x3336), (0x34CE, 0x3557), (0x320D, 0x3287),
          (0x3598, 0x35A1), (0x35A2, 0x35AB), (0x35AC, 0x3634))
MAIN_INS = dict(basic.MAIN_INS)
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
for start, end in RANGES:
    for ins in MD.disasm(IMAGE[start:end], start):
        if ins.address in MAIN_INS:
            raise AssertionError(f'overlapping advanced action instruction {ins.address:04X}')
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
assert OWN_BYTES == 534 and len(OWN_INS) == 150

MASKS = {6: 0xF5EF, 7: 0xF76F, 8: 0xFD6F, 9: 0xF57F}
COUNT_OFFSETS = {6: 0x76, 7: 0x79, 8: 0x7C, 9: 0x7F}
REFRESH_OFFSETS = {6: 0x78, 7: 0x7B, 8: 0x7E, 9: 0x81}


class AdvancedAccess(basic.BasicAccess):
    event_limit = EVENT_LIMIT

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        address &= MASK
        live_alt = (self.case.get('provider') == 'live-alt-pointer' and
                    kind == 'read' and 'alt-pointer' not in self.used and
                    address == interactions.physical(self.regs['ds'], 0x005F))
        inject_bit = (self.case.get('provider') == 'inject-transition-bit9' and
                      kind == 'read' and 'transition-bit' not in self.used and
                      address == interactions.physical(self.regs['ds'],
                                                       self.regs['si'] + 0x27))
        result = super().access(kind, address, flags, mask, value)
        if live_alt:
            self._apply_or_defer(
                interactions.physical(self.regs['ds'], 0x005A),
                self.case['provider_alt'] & 0xFF)
            self._apply_or_defer(
                interactions.physical(self.regs['ds'], 0x005B),
                self.case['provider_alt'] >> 8)
            self.used.add('alt-pointer')
        if inject_bit:
            self._apply_or_defer(
                interactions.physical(self.regs['ds'], self.regs['si'] + 9), 2)
            self.used.add('transition-bit')
        return result


class Native(basic.Native):
    cluster = 'entity_actions_advanced'
    core_name = 'lmn_entity_actions_advanced_core'
    adapter_name = 'lmn_entity_actions_advanced_adapter'
    access_type = AdvancedAccess


def make_case(name, selector, **kwargs):
    return dict(name=name, selector=selector, **kwargs)


def cases():
    rows = []
    # Single-bit probes exhaust each 16-bit eligibility mask. They exercise
    # both admitted and rejected bits without narrowing the selector's domain.
    for selector in (6, 7, 8, 9):
        for bit in range(16):
            rows.append(make_case(
                f's{selector}-mask-bit-{bit:02d}', selector,
                state=1 << bit, x=6, y=5))

    # DEC flags at 80 and FF are produced before later actions/tails overwrite
    # them; these keep the signed overflow and wrap inputs observable.
    for selector in (6, 7, 8, 9):
        for count in (0x80, 0xFF):
            rows.append(make_case(f's{selector}-count-{count:02x}', selector,
                                  count=count, state=0, x=6, y=5))

    # Both selector-7/8 direction comparisons use only the low nibble, while
    # the exact byte value 01 selects AH=7 and every other value selects AH=8.
    for selector in (7, 8):
        for direction_state in (1, 0xFE):
            for nibble in range(16):
                rows.append(make_case(
                    f's{selector}-direction-{direction_state:02x}-{nibble:x}',
                    selector, count=1, direction=0xA0 | nibble,
                    direction_state=direction_state, state=0))

    rows += [
        make_case('s6-count-zero', 6, count=0, x=6, y=5),
        make_case('s6-sum-equal-ten-reject', 6, count=1, x=4, y=6),
        make_case('s6-sum-high-bit-unsigned-pass', 6, count=1,
                  x=0x8000, y=0),
        make_case('s6-sum-wrap-above-ten', 6, count=1, x=0xFFF8, y=0x20),
        make_case('s6-sum-wrap-nine-reject', 6, count=1, x=0xFFFF, y=0x000A),
        make_case('s6-mask-reject-sentinel', 6, count=1, state=1, x=6, y=5),
        make_case('s6-mask-alternate-success', 6, count=1, state=1,
                  x=6, y=5, alternate=True, alt_state=0),
        make_case('s6-alternate-mask-reject', 6, count=1, state=1,
                  x=6, y=5, alternate=True, alt_state=1),
        make_case('s6-fallback-does-not-repeat-sum', 6, count=1, state=1,
                  x=6, y=5, alternate=True, alt_state=0, alt_x=4, alt_y=6),
        make_case('s6-live-alternate-pointer', 6, count=1, state=1,
                  x=6, y=5, alternate=True, alt_state=0, alt_x=4, alt_y=6,
                  alt_pointer=0x6100, wrong_alt_state=1,
                  provider='live-alt-pointer', provider_alt=0x6000),
        make_case('s6-live-pointer-alternate-record', 6, count=1, state=1,
                  x=6, y=5, alternate=True, alt_state=0, alt_x=4, alt_y=6,
                  alt_pointer=0x6100, wrong_alt_state=1),

        make_case('s7-count-zero', 7, count=0),
        make_case('s7-mask-reject-sentinel', 7, count=1, state=1),
        make_case('s7-mask-alternate-success', 7, count=1, state=1,
                  alternate=True, alt_state=0),
        make_case('s7-alternate-mask-reject', 7, count=1, state=1,
                  alternate=True, alt_state=1),
        make_case('s7-direction-seven-rejected', 7, count=1,
                  direction=7, direction_state=1),
        make_case('s7-direction-eight-rejected', 7, count=1,
                  direction=8, direction_state=0),
        make_case('s7-direction-seven-accepted', 7, count=1,
                  direction=7, direction_state=0),
        make_case('s7-direction-eight-accepted', 7, count=1,
                  direction=8, direction_state=1),
        make_case('s7-service-nibble-nine-no-int', 7, count=1,
                  direction=9, enabled=0xFF, options=0),
        make_case('s7-callback-marker-alias', 7, count=1, si=0x000A,
                  state=0, direction=0x12, direction_state=0,
                  slot34=0x1234),
        make_case('s7-transition-mask-reread-bit9', 7, count=1, state=0,
                  direction=0, direction_state=0,
                  provider='inject-transition-bit9'),

        make_case('s8-count-zero', 8, count=0),
        make_case('s8-mask-reject-sentinel', 8, count=1, state=1),
        make_case('s8-mask-alternate-success', 8, count=1, state=1,
                  alternate=True, alt_state=0),
        make_case('s8-alternate-mask-reject', 8, count=1, state=1,
                  alternate=True, alt_state=1),
        make_case('s8-alternate-nibble-gate-rechecked', 8, count=1,
                  state=1, alternate=True, alt_state=0, alt_nibble2c=9),
        make_case('s8-selected-nibble-nine-rejected', 8, count=1,
                  state=0, nibble2c=9),
        make_case('s8-direction-seven-rejected', 8, count=1,
                  direction=7, direction_state=1),
        make_case('s8-direction-eight-rejected', 8, count=1,
                  direction=8, direction_state=0),
        make_case('s8-direction-nine-service', 8, count=1, direction=9,
                  enabled=0xFF, options=0),
        make_case('s8-callback-late-state-alias', 8, count=1, si=0x002E,
                  state=0, nibble2c=0),
        make_case('s8-word-increment-low-wrap', 8, count=1, x=0x12FF,
                  state=0, direction=0, direction_state=0),
        make_case('s8-y-ffff-wrap0', 8, count=1, x=0xFFFF, y=0xFFFF,
                  state=0, direction=0, direction_state=0),

        make_case('s9-count-zero', 9, count=0, nibble2c=1),
        make_case('s9-selected-nibble-nine-rejected', 9, count=1,
                  nibble2c=9),
        make_case('s9-mask-reject-sentinel', 9, count=1, state=1,
                  nibble2c=1),
        make_case('s9-mask-alternate-bypasses-selected-nibble', 9, count=1,
                  state=1, nibble2c=1, alternate=True, alt_state=0,
                  alt_nibble2c=9),
        make_case('s9-alternate-mask-reject', 9, count=1, state=1,
                  nibble2c=1, alternate=True, alt_state=1),

        make_case('s6-dual-pc-feedback', 6, count=1, state=0, x=6, y=5,
                  enabled=0, options=1),
        make_case('s6-pc-returned-ds-live-gate', 6, count=1, state=0,
                  x=6, y=5, enabled=0, options=1,
                  provider='pc-registers', provider_ds=0x6200,
                  provider_si=0x5300, provider_cx=0xF00D),
        make_case('s6-pc-unbound-vector', 6, count=1, state=0, x=6, y=5,
                  enabled=0, options=1, pc_vector=(0x0182, 0x6200)),
        make_case('s7-adlib-service-0412', 7, count=1, direction=9,
                  enabled=0xFF, options=1, driver='adlib'),
        make_case('s8-tandy-service-0412', 8, count=1, direction=9,
                  enabled=0xFF, options=1, driver='tandysnd'),
        make_case('s8-service-unbound-vector', 8, count=1, direction=9,
                  enabled=0xFF, options=1, sound_vector=(0, 0x6200)),
        make_case('s8-service-changed-iret', 8, count=1, direction=9,
                  enabled=0xFF, options=1,
                  provider='sound-interrupt-return', provider_return=0x329A),
        make_case('s8-service-returned-ds', 8, count=1, direction=9,
                  enabled=0xFF, options=1, provider='sound-saved-ds',
                  provider_ds=0x6200, provider_enabled=0xFF,
                  provider_options=3),
        make_case('s9-tandy-feedback', 9, count=1, nibble2c=0,
                  enabled=0xFF, options=3, driver='tandysnd'),
        make_case('s9-df-and-physical-stack-wrap', 9, count=1, nibble2c=0,
                  flags=0x0ED7, ss=0xFFFF, sp=0x000F,
                  outer_return=0xA55A),
        make_case('s6-vga-backed-outer-ret', 6, count=1, state=0,
                  x=6, y=5, vga=True, ss=0xA000, sp=0x0800,
                  outer_return=0xBEEF),
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


def seed_record(memory, ds, pointer, case, prefix=''):
    get = lambda name, default: case.get(prefix + name, default)
    put16(memory, ds, pointer + 0x02, get('x', 6))
    put16(memory, ds, pointer + 0x06, get('y', 5))
    put16(memory, ds, pointer + 0x08, get('state', 0))
    put8(memory, ds, pointer + 0x27, get('direction_state', 0))
    put8(memory, ds, pointer + 0x2B, get('direction', 0))
    put8(memory, ds, pointer + 0x2C, get('nibble2c', 0))
    put8(memory, ds, pointer + 0x24, get('flag24', 0xA5))


def setup(case):
    memory, regs, device, pc_binding, sound_binding, _ = interactions.setup(case)
    selector = case['selector']
    regs['ip'] = ENTRIES[selector]
    ds, si = regs['ds'], regs['si']

    # Seed distinct globals so a wrong selector count/refresh offset is visible.
    for offset in range(0x76, 0x83):
        put8(memory, ds, offset, (0x31 + offset) & 0xFF)
    put8(memory, ds, COUNT_OFFSETS[selector], case.get('count', 1))
    put8(memory, ds, REFRESH_OFFSETS[selector], case.get('refresh', 0x5A))
    put8(memory, ds, 0x5F, 0 if case.get('alternate') else 0xFF)
    alternate_pointer = case.get('alt_pointer', 0x6000)
    put16(memory, ds, 0x5A, alternate_pointer)

    # Callback words are seeded first so record aliases can overwrite them.
    put16(memory, ds, 0x34, case.get('slot34', 0x6134))
    put16(memory, ds, 0x36, case.get('slot36', 0x6136))
    put16(memory, ds, 0x38, case.get('slot38', 0x6138))
    seed_record(memory, ds, si, case)
    if case.get('alternate'):
        seed_record(memory, ds, case.get('alt_seed_pointer', 0x6000), case, 'alt_')
        if case.get('alt_pointer') is not None and case['alt_pointer'] != 0x6000:
            seed_record(memory, ds, case['alt_pointer'], case, 'wrong_alt_')

    if case.get('vga'):
        if device is None or regs['ss'] != 0xA000:
            raise AssertionError(case['name'] + ': invalid VGA outer-RET fixture')
        device.seq[2] = 0x0F
        device.gc[0] = device.gc[1] = device.gc[3] = device.gc[5] = 0
        device.gc[8] = 0xFF
        address = interactions.physical(regs['ss'], regs['sp'])
        offset = (address - interactions.VGA_BASE) & 0xFFFF
        ret = case.get('outer_return', interactions.OUTER_RETURN)
        device.planes[0][offset] = ret & 0xFF
        device.planes[0][(offset + 1) & 0xFFFF] = ret >> 8
    return memory, regs, device, pc_binding, sound_binding


def original(case, memory, regs, device, *, core):
    regs['ip'] = ENTRIES[case['selector']]
    factory = lambda c, m, r, d: AdvancedAccess(
        c, m, r, d, defer_providers=True)
    stops = ({0x320B: 0, 0x320C: 0, 0x329A: 0} if core else None)
    return interactions.original(
        case, memory, regs, device, core, entry_flag_mask=FLAGS,
        main_instructions=MAIN_INS, access_factory=factory,
        stop_offsets=stops, instruction_limit=INSTRUCTION_LIMIT)


def select_path(case, memory, regs):
    """Independent eligibility model; returns fail/service/transition and SI."""
    selector, ds, si = case['selector'], regs['ds'], regs['si']
    count = get8(memory, ds, COUNT_OFFSETS[selector])
    def alternate_pointer():
        if case.get('provider') == 'live-alt-pointer':
            return case['provider_alt']
        return get16(memory, ds, 0x5A)

    if count == 0:
        return 'fail', si
    state = get16(memory, ds, si + 8)
    if selector == 6:
        if ((get16(memory, ds, si + 2) + get16(memory, ds, si + 6)) & 0xFFFF) <= 10:
            return 'fail', si
        if (state & MASKS[6]) == 0:
            return 'transition', si
        if get8(memory, ds, 0x5F) == 0xFF:
            return 'fail', si
        alt = alternate_pointer()
        return ('transition' if (get16(memory, ds, alt + 8) & MASKS[6]) == 0
                else 'fail'), alt
    if selector == 7:
        if state & MASKS[7]:
            if get8(memory, ds, 0x5F) == 0xFF:
                return 'fail', si
            si = alternate_pointer()
            if get16(memory, ds, si + 8) & MASKS[7]:
                return 'fail', si
        direction = get8(memory, ds, si + 0x2B) & 0x0F
        comparison = 7 if get8(memory, ds, si + 0x27) == 1 else 8
        if direction == comparison:
            return 'fail', si
        return ('service' if direction == 9 else 'transition'), si
    if selector == 8:
        if state & MASKS[8]:
            if get8(memory, ds, 0x5F) == 0xFF:
                return 'fail', si
            si = alternate_pointer()
            if get16(memory, ds, si + 8) & MASKS[8]:
                return 'fail', si
        if (get8(memory, ds, si + 0x2C) & 0x0F) == 9:
            return 'fail', si
        direction = get8(memory, ds, si + 0x2B) & 0x0F
        comparison = 7 if get8(memory, ds, si + 0x27) == 1 else 8
        if direction == comparison:
            return 'fail', si
        return ('service' if direction == 9 else 'transition'), si
    if (get8(memory, ds, si + 0x2C) & 0x0F) == 9:
        return 'fail', si
    if (state & MASKS[9]) == 0:
        return 'transition', si
    if get8(memory, ds, 0x5F) == 0xFF:
        return 'fail', si
    alt = alternate_pointer()
    return ('transition' if (get16(memory, ds, alt + 8) & MASKS[9]) == 0
            else 'fail'), alt


def assert_independent(case, initial_memory, initial_regs, observed, *, core):
    path, active = select_path(case, initial_memory, initial_regs)
    selector, ds = case['selector'], initial_regs['ds']
    if path == 'fail':
        expected = 0x320C if core else case.get('outer_return', interactions.OUTER_RETURN)
        interactions.oracle_require(observed['continuation'] == expected,
            f"{case['name']}: independent rejection continuation "
            f"{observed['continuation']:04X}/{expected:04X}")
        return path
    if path == 'service':
        interactions.oracle_require(
            observed['continuation'] not in (0x320C, 0x320B),
            case['name'] + ': direction-9 service fell into failure/feedback')
        interactions.oracle_require(
            observed['memory'][interactions.physical(ds, COUNT_OFFSETS[selector])] ==
            get8(initial_memory, ds, COUNT_OFFSETS[selector]),
            case['name'] + ': service path consumed the action count')
        interactions.oracle_require(
            observed['memory'][interactions.physical(ds, REFRESH_OFFSETS[selector])] ==
            get8(initial_memory, ds, REFRESH_OFFSETS[selector]),
            case['name'] + ': service path cleared the refresh counter')
        if observed['status'] == 0:
            expected_service_return = (0x329A if core else
                case.get('outer_return', interactions.OUTER_RETURN))
            interactions.oracle_require(observed['continuation'] == expected_service_return,
                f'{case["name"]}: service return '
                f'{observed["continuation"]:04X}/{expected_service_return:04X}')
        for offset in range(0x30):
            before = initial_memory[interactions.physical(ds, active + offset)]
            after = observed['memory'][interactions.physical(ds, active + offset)]
            interactions.oracle_require(after == before,
                f'{case["name"]}: service path changed record byte +{offset:02X}')
        return path

    record = active
    count_addr = interactions.physical(ds, COUNT_OFFSETS[selector])
    if selector == 6:
        interactions.oracle_require(observed['memory'][count_addr] ==
            ((get8(initial_memory, ds, COUNT_OFFSETS[6]) - 1) & 0xFF),
            case['name'] + ': selector-6 count was not consumed')
        interactions.oracle_require(get16(observed['memory'], ds, record + 8) == 0x0080,
                                    case['name'] + ': selector-6 state transition')
        interactions.oracle_require(get16(observed['memory'], ds, record + 4) == 0xFFF8 and
                                    get16(observed['memory'], ds, record + 6) == 0xFFF3,
                                    case['name'] + ': selector-6 coordinates')
    elif selector == 7:
        interactions.oracle_require(observed['memory'][count_addr] ==
            ((get8(initial_memory, ds, COUNT_OFFSETS[7]) - 1) & 0xFF),
            case['name'] + ': selector-7 count was not consumed')
        interactions.oracle_require(get16(observed['memory'], ds, record + 8) & 0x0200,
                                    case['name'] + ': selector-7 active state bit')
        interactions.oracle_require(get16(observed['memory'], ds, record + 4) == 0xFFF8 and
                                    get16(observed['memory'], ds, record + 6) == 0xFFF6,
                                    case['name'] + ': selector-7 coordinates')
    elif selector == 8:
        interactions.oracle_require(observed['memory'][count_addr] ==
            ((get8(initial_memory, ds, COUNT_OFFSETS[8]) - 1) & 0xFF),
            case['name'] + ': selector-8 count was not consumed')
        interactions.oracle_require(get16(observed['memory'], ds, record + 8) & 0x0800,
                                    case['name'] + ': selector-8 active state bit')
        x = get16(initial_memory, ds, record + 2)
        # The action increments the live word after all callback/state writes.
        interactions.oracle_require(get16(observed['memory'], ds, record + 2) ==
                                    ((x + 1) & 0xFFFF),
                                    case['name'] + ': selector-8 word increment')
    else:
        interactions.oracle_require(observed['memory'][count_addr] ==
            ((get8(initial_memory, ds, COUNT_OFFSETS[9]) - 1) & 0xFF),
            case['name'] + ': selector-9 count was not consumed')
        interactions.oracle_require(get16(observed['memory'], ds, record + 8) & 0x0010,
                                    case['name'] + ': selector-9 active state bit')
        interactions.oracle_require(get16(observed['memory'], ds, record + 4) == 0xFFF8 and
                                    get16(observed['memory'], ds, record + 6) == 0xFFF4,
                                    case['name'] + ': selector-9 coordinates')
    refresh = interactions.physical(ds, REFRESH_OFFSETS[selector])
    interactions.oracle_require(observed['memory'][refresh] == 0,
                                case['name'] + ': refresh counter was not cleared')

    if case['name'] == 's7-callback-marker-alias':
        interactions.oracle_require(get16(observed['memory'], ds, 0x1E) == 0x12FF,
            'selector-7 callback must read DS:34 after the aliased +2A marker write')
    if case['name'] == 's7-transition-mask-reread-bit9':
        address = interactions.physical(ds, initial_regs['si'] + 8)
        writes = [(event[1], event[2]) for event in observed['events']
                  if event[0] == 'write']
        expected_mask_write = [(address, 0), (address + 1, 0)]
        interactions.oracle_require(any(writes[i:i + 2] == expected_mask_write
                                         for i in range(max(0, len(writes) - 1))),
            'selector-7 transition must clear bit 9 in the F56F AND before OR 0200')
    if case['name'] == 's8-callback-late-state-alias':
        interactions.oracle_require(get16(observed['memory'], ds, record + 0x14) == 0x0800,
            'selector-8 callback should read the state word after its ordered update')
    if case['name'] == 's8-word-increment-low-wrap':
        interactions.oracle_require(get16(observed['memory'], ds, record + 2) == 0x1300,
            'selector-8 increments the full coordinate word across the low-byte wrap')
    if case.get('provider') == 'live-alt-pointer':
        interactions.oracle_require('alt-pointer' in observed['used'] and
                                    observed['regs']['si'] == case['provider_alt'],
            case['name'] + ': alternate pointer provider did not affect live SI')
    if case.get('provider') == 'inject-transition-bit9':
        interactions.oracle_require('transition-bit' in observed['used'],
            case['name'] + ': transition-bit provider did not fire')
    return path


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
    all_sites, all_edges, rows = set(), set(), []
    for case in cases():
        memory, regs, device, _, _ = setup(case)
        for core in (True, False):
            expected = original(case, bytearray(memory), dict(regs),
                                copy.deepcopy(device), core=core)
            assert_independent(case, memory, regs, expected, core=core)
            row = own_row(case, expected, core)
            rows.append(row)
            all_sites.update(row['sites'])
            all_edges.update(tuple(edge) for edge in row['edges'])
    interactions.oracle_require(all_sites == set(OWN_INS),
        f'advanced action original sites {len(all_sites)}/{len(OWN_INS)}')
    interactions.oracle_require(all_edges == OWN_EDGES,
        f'advanced action original edges {len(all_edges)}/{len(OWN_EDGES)}; '
        f'missing={sorted(OWN_EDGES-all_edges)}')
    interactions.oracle_require(before == input_hashes(),
                                'advanced action inputs changed during preflight')
    print(f'PASS original entity advanced actions: {len(cases())} fixtures x core/adapter, '
          f'{len(all_sites)} sites/{len(all_edges)} edges', flush=True)


def compare_case(native, case, *, core):
    memory, regs, device, pc_binding, sound_binding = setup(case)
    label = case['name'] + (' core' if core else ' adapter')
    expected = original(case, bytearray(memory), dict(regs),
                        copy.deepcopy(device), core=core)
    assert_independent(case, memory, regs, expected, core=core)
    actual = native.run(case, bytearray(memory), dict(regs),
                        copy.deepcopy(device), pc_binding, sound_binding,
                        core=core)
    interactions.require(actual['status'] == expected['status'],
        f'{label}: status {actual["status"]}/{expected["status"]}')
    interactions.require(actual['continuation'] == expected['continuation'],
        f'{label}: continuation {actual["continuation"]:04X}/'
        f'{expected["continuation"]:04X}')
    for name in interactions.REG_NAMES:
        if name != 'flags':
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
    basic.compare_events(label, actual['events'], expected['events'])
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
    1: ('s6-sum-equal-ten-reject', True),
    2: ('s6-mask-bit-07', True),
    3: ('s6-fallback-does-not-repeat-sum', True),
    4: ('s7-mask-bit-09', True),
    5: ('s7-transition-mask-reread-bit9', True),
    6: ('s7-callback-marker-alias', True),
    7: ('s7-service-nibble-nine-no-int', True),
    8: ('s9-mask-alternate-bypasses-selected-nibble', True),
    9: ('s8-alternate-nibble-gate-rechecked', True),
    10: ('s8-word-increment-low-wrap', True),
}


def input_hashes():
    paths = [
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md',
        'docs/bottom-up.md', 'docs/entity-actions.md',
        'src/game_code.asm', 'src/entity_actions.asm', 'src/game_code_late.asm',
        'src/game_code_late_after_palette.asm',
        'src/game_code_late_after_entities.asm', 'src/game_code_late_tail.asm',
        'src/image_tail.asm', 'src/program.asm', 'src/sound/pcspeaker.asm',
        'src/sound/adlib.asm', 'src/sound/tandysnd.asm',
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat',
        'assets/tandysnd.dat', 'metadata/oracle.json', 'metadata/symbols.json',
        'metadata/inputs.json', 'metadata/regions.json', 'metadata/hints.json',
        'metadata/toolchain-lock.json', 'metadata/sound-oracle.json',
        'metadata/pcspeaker-encodings.json', 'metadata/pcspeaker-producers.json',
        'metadata/pcspeaker-regions.json', 'metadata/pcspeaker-symbols.json',
        'metadata/adlib-symbols.json', 'metadata/tandysnd-symbols.json',
        'requirements.txt', 'c/entity_actions_advanced.c',
        'c/entity_actions_advanced.h', 'c/entity_actions_basic.c',
        'c/entity_actions_basic.h', 'c/entity_action_sound.c',
        'c/entity_action_sound.h', 'c/pcspeaker_interrupt.c',
        'c/pcspeaker_interrupt.h', 'c/pcspeaker_dispatch.c',
        'c/pcspeaker_dispatch.h', 'c/pcspeaker.c', 'c/pcspeaker.h',
        'c/sound_interrupt.c', 'c/sound_interrupt.h', 'c/sound_latches.c',
        'c/sound_latches.h', 'c/regs.h', 'c/special_blit.h',
        'c/lemmings_sym.h', 'c/pcspeaker_sym.h', 'c/sound_latches_sym.h',
        'tests/entity_actions_advanced.py', 'tests/entity_actions_basic.py',
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
        f'advanced native sites {len(all_sites)}/{len(OWN_INS)}')
    interactions.oracle_require(all_edges == OWN_EDGES,
        f'advanced native edges {len(all_edges)}/{len(OWN_EDGES)}')
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
            raise AssertionError(f'entity-actions-advanced mutant {mutation} survived')
        del mutant
        gc.collect()
    interactions.oracle_require(before == input_hashes(),
        'advanced action inputs changed during bounded native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE), code_ranges=[list(r) for r in RANGES],
        translated_code_bytes=OWN_BYTES, instruction_sites=len(OWN_INS),
        own_static_branch_edges=len(OWN_EDGES),
        conditional_branch_outcomes=sum(2 for ins in OWN_INS.values()
            if ins.group(capstone.CS_GRP_JUMP) and ins.mnemonic.lower() != 'jmp'),
        unconditional_jump_edges=sum(1 for ins in OWN_INS.values()
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
        domain='Selectors 6/7/8/9 at 32BD,34CE,3598,320D. The 534 known bytes '
               'exclude the two UNKNOWN selector-8 bytes 35A1 and 35AB. The '
               'comparison covers core and actual outer-RET adapter boundaries, '
               'full RAM/register/defined-FLAGS state, ordered RAM/VGA events, and '
               'VGA state. Fixtures include all single-bit eligibility probes, '
               'alternate-record rechecks and bypasses, signed direction gates, '
               'callback aliases, selector-8 word increment wrap, PC/external '
               'feedback, driver/vector/IRET seams, DF, physical stack wrap, and '
               'a VGA-backed outer return.'))
    print(f'PASS entity actions advanced: {len(specs)} fixtures x core/adapter, '
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
        raise SystemExit('usage: entity_actions_advanced.py [--original-only | --worker DLL_DIRECTORY]')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-actions-advanced-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     str(directory)], cwd=ROOT, timeout=WORKER_SECONDS,
                    memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()

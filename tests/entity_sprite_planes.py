"""Bounded differential checks for five three/four-plane sprite callbacks.

The five identified ranges are independently callable: 66D7..6816 (3x10),
6817..6956 (3x13), 6957..6A96 (3x14), 6A97..6BDA (3x16), and 6CFC..6E82
(4x14). Each core stops before its own near RET; each adapter consumes the
actual live SS:SP word. The 6BDB..6CFB wide-sprite gap is not part of this suite.
"""
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
import entity_interactions as interactions
import entity_sprite_layout as sprite_layout
import entity_sprite_shifted as shifted
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, unpack, relocated

IMAGE, ORACLE = unpack(ASSET.read_bytes())
SIZE, MASK = interactions.SIZE, interactions.MASK
FLAGS = interactions.FLAGS
DF, IF = 0x0400, 0x0200
LOAD = 0x1010
MAX_INSTRUCTIONS, MAX_EVENTS = 100_000, 20_000
WORKER_SECONDS, PROCESS_MIB = 360, 384
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-sprite-planes-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-sprite-planes-original-differential.json'

PROFILES = {
    '3plane10': dict(entry=0x66D7, ret=0x6816, rows=10, planes=3,
                     counter_ax=False, prefix=0x6736, symbol='3plane_10',
                     producer_shift=0),
    '3plane13': dict(entry=0x6817, ret=0x6956, rows=13, planes=3,
                     counter_ax=False, prefix=0x6876, symbol='3plane_13',
                     producer_shift=1),
    '3plane14': dict(entry=0x6957, ret=0x6A96, rows=14, planes=3,
                     counter_ax=False, prefix=0x69B6, symbol='3plane_14',
                     producer_shift=7),
    '3plane16': dict(entry=0x6A97, ret=0x6BDA, rows=16, planes=3,
                     counter_ax=True, prefix=0x6AF6, symbol='3plane_16',
                     producer_shift=3),
    '4plane14': dict(entry=0x6CFC, ret=0x6E82, rows=14, planes=4,
                     counter_ax=True, prefix=0x6D5B, symbol='4plane_14',
                     producer_shift=5),
}
for key, profile in PROFILES.items():
    profile['end'] = profile['ret'] + 1
    profile['source_dx'] = ((profile['planes'] << 8) | profile['rows'])
    profile['name'] = key

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {}
for profile in PROFILES.values():
    code = IMAGE[profile['entry']:profile['end']]
    decoded = {ins.address: ins for ins in MD.disasm(code, profile['entry'])}
    if sum(ins.size for ins in decoded.values()) != len(code):
        raise RuntimeError(f"incomplete static decode for {profile['name']}")
    OWN_INS.update(decoded)
OWN_SITES = set(OWN_INS)
CODE_BYTES = sum(ins.size for ins in OWN_INS.values())
CORE_NAMES, REG_FIELDS = shifted.CORE_NAMES, shifted.REG_FIELDS
Call, Result, RasterBus = shifted.Call, shifted.Result, shifted.RasterBus
Mismatch = shifted.Mismatch
PRODUCER_WITNESSES = None


def oracle_require(condition, message):
    if not condition:
        raise interactions.OracleFailure(message)


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def worker_exit(code, message):
    try:
        os.write(2, (str(message) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


def physical(segment, offset):
    return ((((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK)


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def seed_physical(memory, device, address, value):
    address &= MASK
    value &= 0xFF
    memory[address] = value
    if device is not None and VGA_BASE <= address < VGA_END:
        device.planes[device.gc[4] & 3][address - VGA_BASE] = value


def seed_word(memory, device, segment, offset, value):
    address = physical(segment, offset)
    seed_physical(memory, device, address, value)
    seed_physical(memory, device, address + 1, value >> 8)


def source_pattern(words, seed):
    return [((0x8193 + index * 0x2D71 + seed * 0x0103) ^
             (0xA55A >> (index & 7))) & 0xFFFF
            for index in range(words)]


def mask_pattern(rows, seed):
    return [((0xF03D ^ (index * 0x197B) ^ (seed * 0x0311)) & 0xFFFF)
            for index in range(rows)]


def make_cases():
    """Small cases target all five siblings and each new live-stack mutation."""
    specs = []
    seed = 1
    for name, profile in PROFILES.items():
        for shift in (0, 8, 17, 255):
            specs.append(dict(name=f'{name}-shift-{shift:03d}', profile=name,
                              seed=seed, shift=shift, plane_check=True))
            seed += 1
        specs.append(dict(name=f'{name}-df-reverse-shift17', profile=name,
                          seed=seed, shift=17, df=True, si=0x1200, di=0x3400,
                          plane_check=True))
        seed += 1
        specs.append(dict(name=f'{name}-producer-5bb0', profile=name,
                          seed=seed, shift=profile['producer_shift'],
                          producer_dx=profile['source_dx'], plane_check=True))
        seed += 1

    specs.extend((
        dict(name='incoming-cx-source-not-entry-ds', profile='3plane10', seed=41,
             shift=8, ds=0x3500, source_segment=0x6100, plane_check=True),
        dict(name='entry-if-set-before-first-cli', profile='3plane10', seed=42,
             shift=17, iflag=True, plane_check=True),
        dict(name='provider-rereads-second-mask-word', profile='3plane10', seed=43,
             shift=1, providers=[dict(trigger=8, segment=0x6100, offset=0x2202,
                                      before=mask_pattern(10, 43)[1],
                                      after=mask_pattern(10, 43)[1] ^ 0xA55A,
                                      tag='second-mask')]),
        dict(name='provider-live-popped-row-count', profile='3plane16', seed=44,
             shift=8, providers=[dict(trigger=8, segment=0x5000, offset=0x8FFA,
                                      before=16, after=2, tag='row-count')]),
        dict(name='provider-live-plane-boundary-di', profile='4plane14', seed=45,
             shift=8, providers=[dict(trigger=47, segment=0x5000, offset=0x8FFC,
                                      before=0x3000, after=0x4567, tag='saved-di')]),
        dict(name='provider-live-final-saved-ds', profile='3plane13', seed=46,
             shift=8, providers=[dict(trigger=49, segment=0x5000, offset=0x8FFE,
                                      before=0x3500, after=0x7000, tag='saved-ds')]),
        dict(name='source-word-physical-wrap', profile='3plane10', seed=47,
             shift=17, source_segment=0xFFFF, si=0x000F),
        dict(name='source-word-offset-wrap', profile='3plane13', seed=48,
             shift=8, si=0xFFFF),
        dict(name='mask-word-physical-wrap', profile='3plane14', seed=49,
             shift=17, source_segment=0xFFFF, bx=0x000F),
        dict(name='destination-offset-wrap', profile='3plane16', seed=50,
             shift=8, di=0xFFF0),
        dict(name='caller-return-word-physical-wrap', profile='4plane14', seed=51,
             shift=8, ss=0xFFFF, sp=0x000F, return_word=0x4321),
        dict(name='source-from-vga-read-map-one', profile='3plane13', seed=52,
             shift=17, source_segment=0xA000, si=0x2400, read_map=1),
        dict(name='vga-stack-safe-fixed-source', profile='3plane13', seed=53,
             shift=8, ss=0xA000, sp=0x3010, di=0x5000,
             source_words=[0xFFFF] * 39, mask_words=[0xFFFF] * 13),
        dict(name='ss-mirrors-overwrite-live-saved-ds', profile='3plane10', seed=54,
             shift=8, sp=0x0010, plane_check=False),
    ))

    cases = []
    for spec in specs:
        row = dict(profile='3plane10', seed=0, shift=0, ds=0x3500,
                   source_segment=0x6100, ss=0x5000, sp=0x9000,
                   si=0x1200, bx=0x2200, di=0x3000, ax=0xB45A,
                   dx=0xC400, bp=0x51A3, es=0x4123,
                   flags=FLAGS & ~DF, df=False, iflag=False,
                   return_word=0xE000, read_map=0, source_words=None,
                   mask_words=None, providers=[], plane_check=False,
                   producer_dx=None)
        row.update(spec)
        profile = PROFILES[row['profile']]
        if row.get('producer_dx') is not None:
            oracle_require(row['producer_dx'] == profile['source_dx'],
                           row['name'] + ': producer dimension differs from leaf shape')
        cases.append(row)
    oracle_require(35 <= len(cases) <= 45,
                   f'entity sprite plane fixture count outside scope: {len(cases)}')
    return cases


def configure_vga(seed, read_map):
    device = MinimapVga(0x66D7 ^ seed, read_map=read_map)
    device.seq[2] = 0x0F
    device.gc[0] = 0
    device.gc[1] = 0x0E
    device.gc[3] = 0
    device.gc[5] = 0
    device.gc[6] = 0x05
    device.gc[8] = 0xFF
    return device


def prepare_producer_handoffs():
    """Run each 5BB0 shape once; keep its producer evidence separate."""
    global PRODUCER_WITNESSES
    if PRODUCER_WITNESSES is not None:
        return PRODUCER_WITNESSES
    witnesses = {}
    for name, profile in PROFILES.items():
        dx = profile['source_dx']
        witness = sprite_layout.produce_5bb0(dx, 0x5B0000 | dx)
        bank = witness.banks[0]
        expected_plane = 2 * profile['planes'] * profile['rows']
        expected_mask = 2 * profile['rows']
        oracle_require(witness.dx == dx and bank.plane_length == expected_plane and
                       bank.mask_length == expected_mask and
                       bank.output_length == expected_plane + expected_mask,
                       f'{name}: producer bank does not match consumer source geometry')
        actual = bytes(witness.memory[
            sprite_layout.physical(witness.destination_segment,
                                   witness.destination_offset):
            sprite_layout.physical(witness.destination_segment,
                                   witness.destination_offset) + bank.output_length])
        oracle_require(actual == witness.output_bytes == witness.bank(),
                       f'{name}: producer post-run RAM differs from bank descriptor')
        witnesses[dx] = witness
    PRODUCER_WITNESSES = witnesses
    return witnesses


def producer_handoff_report():
    result = []
    for dx, witness in sorted(prepare_producer_handoffs().items()):
        bank = witness.banks[0]
        result.append(dict(entry=witness.entry, dx=dx,
                           destination_segment=witness.destination_segment,
                           destination_offset=witness.destination_offset,
                           bank_bytes=bank.output_length,
                           plane_bytes=bank.plane_length,
                           plane_stride=bank.plane_stride,
                           mask_bytes=bank.mask_length,
                           producer_steps=witness.steps,
                           producer_memory_transactions=witness.event_count,
                           bank_sha256=sha(witness.output_bytes),
                           producer_instruction_addresses=sorted(witness.sites),
                           producer_branch_edges=[list(edge)
                                                  for edge in sorted(witness.edges)],
                           evidence='one bounded original producer execution; excluded from leaf sites/events'))
    return result


def _source_and_mask(case, profile):
    rows, planes = profile['rows'], profile['planes']
    if case['producer_dx'] is not None:
        producer = prepare_producer_handoffs()[case['producer_dx']]
        bank = producer.banks[0]
        data = producer.bank()
        copied = data[bank.plane_offset:bank.plane_offset + bank.plane_length]
        mask_bytes = data[bank.mask_offset:bank.mask_offset + bank.mask_length]
        sources = [int.from_bytes(copied[i:i + 2], 'little')
                   for i in range(0, len(copied), 2)]
        masks = [int.from_bytes(mask_bytes[i:i + 2], 'little')
                 for i in range(0, len(mask_bytes), 2)]
    else:
        sources = list(case['source_words'] or source_pattern(rows * planes, case['seed']))
        masks = list(case['mask_words'] or mask_pattern(rows, case['seed']))
    oracle_require(len(sources) == rows * planes and len(masks) == rows,
                   case['name'] + ': source/mask count differs from declared profile')
    return sources, masks


def producer_bank_digest(case, memory, error_type):
    """Prove the real 5BB0 output bank remains intact across this consumer."""
    if case['producer_dx'] is None:
        return None
    witness = prepare_producer_handoffs()[case['producer_dx']]
    address = physical(witness.destination_segment, witness.destination_offset)
    actual = bytes(memory[address:address + len(witness.output_bytes)])
    if actual != witness.output_bytes:
        raise error_type(case['name'] + ': actual producer bank changed during consumer')
    return sha(actual)


def setup(case):
    profile = PROFILES[case['profile']]
    rows = profile['rows']
    rng = random.Random(0x66D7 + case['seed'] * 0x9E3779B1 + profile['entry'])
    producer = (prepare_producer_handoffs()[case['producer_dx']]
                if case['producer_dx'] is not None else None)
    memory = bytearray(producer.memory if producer is not None else rng.randbytes(SIZE))
    loaded = relocated(IMAGE, ORACLE['relocations'], LOAD)
    base = physical(LOAD, 0)
    first = min(len(loaded), SIZE - base)
    memory[base:base + first] = loaded[:first]
    if first < len(loaded):
        memory[:len(loaded) - first] = loaded[first:]

    device = configure_vga(case['seed'], case['read_map'])
    regs = {name: rng.randrange(0x10000) for name in interactions.REG_NAMES}
    flags = ((case['flags'] | 2) & FLAGS) & ~0x0100
    if case['df']:
        flags |= DF
    if case['iflag']:
        flags |= IF
    regs.update(cs=LOAD, ip=profile['entry'], ax=case['ax'],
                cx=(sprite_layout.DESTINATION_SEGMENT if producer is not None
                    else case['source_segment']),
                dx=(case['dx'] & 0xFF00) | (case['shift'] & 0xFF),
                si=(sprite_layout.DESTINATION_OFFSET if producer is not None
                    else case['si']),
                bx=(sprite_layout.DESTINATION_OFFSET + producer.banks[0].plane_length
                    if producer is not None else case['bx']),
                di=case['di'], bp=case['bp'], ds=case['ds'], es=case['es'],
                ss=case['ss'], sp=case['sp'], flags=flags)

    sources, masks = _source_and_mask(case, profile)
    direction = -1 if flags & DF else 1
    if producer is None:
        for index, value in enumerate(sources):
            offset = (regs['si'] + index * direction * 2) & 0xFFFF
            seed_word(memory, device, regs['cx'], offset, value)
            if regs['ds'] != regs['cx']:
                seed_word(memory, device, regs['ds'], offset,
                          value ^ (0x5D3A + index * 0x0101))
        for index, value in enumerate(masks):
            seed_word(memory, device, regs['cx'], regs['bx'] + index * 2, value)
    else:
        bank = producer.banks[0]
        start = physical(producer.destination_segment, producer.destination_offset)
        oracle_require(bytes(memory[start:start + bank.output_length]) == producer.bank(),
                       case['name'] + ': setup modified actual producer bytes')

    # Give each plane distinct initial contents so masked writes and every OR
    # pass are visible independently. Provider/alias fixtures skip projection,
    # but retain the same finite seeded aperture.
    if case['plane_check']:
        for row in range(rows):
            row_start = (regs['di'] + row * (0x29 + 3 * direction)) & 0xFFFF
            for column in range(3):
                offset = (row_start + column * direction) & 0xFFFF
                address = physical(0xA000, offset)
                if VGA_BASE <= address < VGA_END:
                    vga_offset = address - VGA_BASE
                    for plane_no, plane in enumerate(device.planes):
                        plane[vga_offset] = (0x31 + row * 19 + column * 7 +
                                             plane_no * 53 + case['seed']) & 0xFF
                    memory[address] = device.planes[device.gc[4] & 3][vga_offset]

    put16(memory, regs['ss'], regs['sp'], case['return_word'])
    # Mutation providers target the exact live saves created by each leaf.
    case['_sources'], case['_masks'] = sources, masks
    return memory, regs, device


class PlanesAccess(shifted.ShiftedAccess):
    event_limit = MAX_EVENTS


def shift_word(value, count):
    return shifted.shift_word(value, count)


def independent_plane_projection(case, initial_memory, initial_device):
    """Independent 16-bit-to-24-bit shift and planar write-mode projection."""
    profile = PROFILES[case['profile']]
    rows, planes = profile['rows'], profile['planes']
    oracle_require(case['plane_check'] and not case['providers'] and
                   case['source_segment'] != 0xA000 and case['ss'] != 0xA000,
                   case['name'] + ': plane projection domain must be disjoint')
    device = copy.deepcopy(initial_device)
    memory = bytearray(initial_memory)
    shift = case['shift'] & 0xFF
    direction = -1 if case['df'] else 1
    dest0 = case['di'] & 0xFFFF
    sources, masks = case['_sources'], case['_masks']
    flags = ((case['flags'] | 2) & FLAGS) & ~0x0100
    if case['df']:
        flags |= DF
    if case['iflag']:
        flags |= IF

    for port, word in ((0x3C4, 0x0F02), (0x3CE, 0x0000),
                       (0x3CE, 0x0E01), (0x3CE, 0x0005),
                       (0x3CE, 0x0003)):
        device.out(port, word, flags)

    checks = 0
    def pixels(offset, value):
        nonlocal checks
        address = physical(0xA000, offset)
        device.read(memory, address, flags & ~IF)
        device.write(memory, address, value, flags & ~IF)
        checks += 4

    # The masked first pass writes shifted data through three shifted mask
    # bytes. Every STOSB is preceded by the original VGA latch read.
    for row in range(rows):
        src, src_spill = shift_word(sources[row], shift)
        mask, mask_spill = shift_word(masks[row], shift)
        data_bytes = (src >> 8, src & 0xFF, src_spill)
        mask_bytes = (mask >> 8, mask & 0xFF, mask_spill)
        row_start = (dest0 + row * (0x29 + 3 * direction)) & 0xFFFF
        for col, (value, mask_byte) in enumerate(zip(data_bytes, mask_bytes)):
            device.out(0x3CE, (mask_byte << 8) | 8, flags)
            pixels((row_start + col * direction) & 0xFFFF, value)

    for port, word in ((0x3CE, 0x0001), (0x3CE, 0x1003),
                       (0x3CE, 0xFF08), (0x3C4, 0x0202)):
        device.out(port, word, flags)

    # The remaining source rows are separate source planes. The literal map
    # masks are 02, 04 for three-plane entries, and 02, 04, 08 for four-plane.
    for plane_index in range(1, planes):
        if plane_index > 1:
            device.out(0x3C4, ((1 << plane_index) << 8) | 0x02, flags)
        first_source = plane_index * rows
        for row in range(rows):
            src, spill = shift_word(sources[first_source + row], shift)
            data_bytes = (src >> 8, src & 0xFF, spill)
            row_start = (dest0 + row * (0x29 + 3 * direction)) & 0xFFFF
            for col, value in enumerate(data_bytes):
                pixels((row_start + col * direction) & 0xFFFF, value)
    return device, checks


def run_original(case, memory, regs, device, *, core, stop_offsets=None):
    profile = PROFILES[case['profile']]
    stops = ({profile['ret']: 0} if core else None) if stop_offsets is None else stop_offsets
    return interactions.original(
        case, memory, regs, device, core, entry_flag_mask=FLAGS,
        main_instructions=OWN_INS, stop_offsets=stops,
        access_factory=PlanesAccess, instruction_limit=MAX_INSTRUCTIONS)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-sprite-planes-m{mutation}.dll',
                     mutation, 'entity_sprite_planes')
        self.library = ct.CDLL(str(path))
        self.cores, self.adapters = {}, {}
        for profile in PROFILES.values():
            name = profile['symbol']
            core = getattr(self.library, f'lmn_draw_entity_sprite_{name}_core')
            core.argtypes = [shifted.MEM, ct.POINTER(Call), ct.POINTER(RasterBus)]
            core.restype = Result
            adapter = getattr(self.library,
                              f'lmn_draw_entity_sprite_{name}_adapter')
            adapter.argtypes = [shifted.MEM, ct.POINTER(interactions.Regs),
                                ct.POINTER(RasterBus)]
            adapter.restype = ct.c_uint16
            self.cores[profile['name']], self.adapters[profile['name']] = core, adapter

    def run(self, case, memory, regs, device, *, core):
        profile = PROFILES[case['profile']]
        access = PlanesAccess(case, memory, regs, device)

        def read(_ctx, _memory, address, flags):
            try:
                return access.access('read', address, flags, FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT, error)

        def write(_ctx, _memory, address, value, flags):
            try:
                access.access('write', address, flags, FLAGS, value)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT, error)

        def out(_ctx, port, value, flags):
            try:
                access.out_word(port, value, flags, FLAGS)
            except BaseException as error:
                worker_exit(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT, error)

        callbacks = (shifted.READ(read), shifted.WRITE(write), shifted.OUT(out))
        bus = RasterBus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = interactions.Regs(**regs)
        name = profile['name']
        if core:
            call = Call(*(regs[REG_FIELDS[field]] for field in CORE_NAMES))
            result = self.cores[name](ram, ct.byref(call), ct.byref(bus))
            for field in CORE_NAMES:
                setattr(state, REG_FIELDS[field], getattr(result, field))
            state.ip = result.continuation
            status, continuation = result.status, result.continuation
        else:
            status = self.adapters[name](ram, ct.byref(state), ct.byref(bus))
            continuation = state.ip
        return dict(memory=bytes(memory),
                    regs={field: getattr(state, field) for field in interactions.REG_NAMES},
                    device=device, events=access.events, used=access.used,
                    status=status, continuation=continuation)


def static_edges():
    edges = set()
    for address, ins in OWN_INS.items():
        if ins.group(capstone.CS_GRP_JUMP):
            if ins.mnemonic.lower() not in ('jmp', 'ljmp'):
                edges.add((address, (address + ins.size) & 0xFFFF))
            if ins.operands and ins.operands[-1].type == capstone.x86.X86_OP_IMM:
                edges.add((address, ins.operands[-1].imm & 0xFFFF))
    return edges


def compare_case(native, case, *, core):
    initial_memory, initial_regs, initial_device = setup(case)
    label = f'{case["name"]} {"core" if core else "adapter"}'
    expected = run_original(case, bytearray(initial_memory), dict(initial_regs),
                            copy.deepcopy(initial_device), core=core)
    oracle_require(expected['status'] == 0,
                   label + f': original stopped with status {expected["status"]}')
    oracle_require(expected['steps'] <= MAX_INSTRUCTIONS and
                   len(expected['events']) <= MAX_EVENTS,
                   label + ': original exceeded a declared finite bound')
    producer_digest = producer_bank_digest(case, expected['memory'],
                                           interactions.OracleFailure)
    oracle_require(expected['used'] == {provider['tag']
                   for provider in case['providers']},
                   label + ': original did not use every declared provider')

    checks = 0
    if case['plane_check']:
        projected, checks = independent_plane_projection(
            case, initial_memory, initial_device)
        oracle_require([bytes(p) for p in expected['device'].planes] ==
                       [bytes(p) for p in projected.planes],
                       label + ': independent shifted-plane projection differs')

    actual = native.run(case, bytearray(initial_memory), dict(initial_regs),
                        copy.deepcopy(initial_device), core=core)
    require(actual['status'] == 0, label + f': native status {actual["status"]}')
    require(actual['continuation'] == expected['continuation'],
            label + f': continuation {actual["continuation"]:04X}/'
            f'{expected["continuation"]:04X}')
    shifted.compare_regs(label, actual['regs'], expected['regs'],
                         expected['flag_mask'], Mismatch)
    shifted.compare_memory(label, actual['memory'], expected['memory'], Mismatch)
    actual_producer_digest = producer_bank_digest(case, actual['memory'], Mismatch)
    require(actual_producer_digest == producer_digest,
            label + ': producer bank digest differs after native consumer')
    shifted.compare_events(label, actual['events'], expected['events'], Mismatch)
    shifted.compare_devices(label, actual['device'], expected['device'], Mismatch)
    require(actual['used'] == expected['used'],
            label + f': provider effects {actual["used"]!r}/{expected["used"]!r}')
    if core:
        profile = PROFILES[case['profile']]
        oracle_require(expected['regs']['ip'] == profile['ret'] and
                       expected['regs']['sp'] == initial_regs['sp'],
                       label + ': core crossed its pre-RET boundary')
    else:
        oracle_require(expected['regs']['sp'] == ((initial_regs['sp'] + 2) & 0xFFFF),
                       label + ': adapter failed to consume the actual RET')
    if case['name'] == 'provider-live-final-saved-ds':
        oracle_require(expected['regs']['ds'] == 0x7000,
                       label + ': final POP DS ignored the provider-updated save')
    if case['name'] == 'provider-live-popped-row-count':
        oracle_require(expected['regs']['ax'] == 0,
                       label + ': altered live row count did not terminate at two rows')
    return dict(name=case['name'], profile=case['profile'],
                boundary='core' if core else 'adapter',
                sites=sorted(off for scope, off in expected['sites'] if scope == 'main'),
                edges=sorted([src, dst] for scope, src, dst in expected['edges']
                             if scope == 'main'),
                events=len(expected['events']), steps=expected['steps'],
                independent_plane_byte_checks=checks,
                producer_bank_sha256=producer_digest,
                providers=sorted(expected['used']))


def input_hashes():
    paths = (
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md', 'docs/bottom-up.md',
        'docs/entity-sprites.md', 'docs/entity-vga.md', 'docs/minimap-vga.md',
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat', 'assets/tandysnd.dat',
        'metadata/oracle.json', 'metadata/inputs.json', 'metadata/symbols.json',
        'metadata/regions.json', 'metadata/hints.json', 'metadata/sound-oracle.json',
        'metadata/pcspeaker-encodings.json', 'metadata/pcspeaker-producers.json',
        'metadata/pcspeaker-regions.json', 'metadata/pcspeaker-symbols.json',
        'metadata/adlib-symbols.json', 'metadata/tandysnd-symbols.json',
        'metadata/toolchain-lock.json', 'src/program.asm', 'src/game_code.asm',
        'src/entity_sprite_planes.asm', 'src/entity_sprite_wide.asm',
        'src/entity_sprite_four_planes.asm', 'src/image_tail.asm',
        'src/game_code_late_after_palette.asm', 'src/entry_services.asm',
        'src/sound/pcspeaker.asm', 'src/sound/adlib.asm', 'src/sound/tandysnd.asm',
        'c/entity_sprite_shifted.c', 'c/entity_sprite_shifted.h', 'c/regs.h',
        'c/special_blit.h', 'c/lemmings_sym.h', 'tests/entity_sprite_planes.py',
        'tests/entity_sprite_shifted.py', 'tests/entity_sprite_layout.py',
        'tests/sound_latches.py', 'tests/pcspeaker_dispatch.py',
        'tests/entity_strip.py',
        'tests/entity_interactions.py', 'tests/minimap_vga.py', 'tools/resources.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/unpack.py', 'tools/difftest.py', 'tools/coverage.py', 'requirements.txt',
    )
    missing = [path for path in paths if not (ROOT / path).is_file()]
    oracle_require(not missing, 'missing entity-sprite-planes hash inputs: ' + ', '.join(missing))
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def original_prefix_sweep():
    """Check every unchecked CL through each sibling's first SHR/RCR loop."""
    rows, sites = [], set()
    total_steps = total_events = 0
    for name, profile in PROFILES.items():
        template = next(case for case in make_cases()
                        if case['profile'] == name and case['shift'] == 0 and
                        case['plane_check'])
        for shift in range(256):
            case = copy.deepcopy(template)
            case['name'] = f'prefix-{name}-{shift:03d}'
            case['shift'] = shift
            memory, regs, device = setup(case)
            expected = run_original(case, bytearray(memory), dict(regs),
                                    copy.deepcopy(device), core=False,
                                    stop_offsets={profile['prefix']: 2})
            oracle_require(expected['status'] == 2 and
                           expected['regs']['ip'] == profile['prefix'],
                           case['name'] + ': missed the declared post-shift boundary')
            source, source_spill = shift_word(case['_sources'][0], shift)
            mask, mask_spill = shift_word(case['_masks'][0], shift)
            result = expected['regs']
            direction = -1 if regs['flags'] & DF else 1
            checks = {'si': source, 'bp': mask,
                      'ax': ((mask_spill << 8) | source_spill),
                      'cx': shift & 0xFF,
                      'bx': (regs['bx'] + 2) & 0xFFFF,
                      'dx': 0x03CE, 'es': 0xA000,
                      'sp': (regs['sp'] - 8) & 0xFFFF}
            for field, value in checks.items():
                oracle_require(result[field] == value,
                               f'{case["name"]}: {field} {result[field]:04X}/{value:04X}')
            carry_out = (((shifted.swap_word(case['_masks'][0]) << 8) >> (shift - 1)) & 1
                         if shift else 0)
            expected_flags = (regs['flags'] & ~shifted.ARITH) | 0x0044 | carry_out
            oracle_require(((result['flags'] ^ expected_flags) &
                            expected['flag_mask']) == 0,
                           f'{case["name"]}: FLAGS {result["flags"]:04X}/'
                           f'{expected_flags:04X} under {expected["flag_mask"]:04X}')
            saved_si = (regs['si'] + direction * 2) & 0xFFFF
            actual_saved_si = shifted.get16(expected['memory'], regs['ss'], result['sp'])
            oracle_require(actual_saved_si == saved_si,
                           f'{case["name"]}: live saved SI {actual_saved_si:04X}/'
                           f'{saved_si:04X}')
            own_sites = {off for scope, off in expected['sites'] if scope == 'main'}
            sites.update(own_sites)
            total_steps += expected['steps']
            total_events += len(expected['events'])
            rows.append(dict(profile=name, shift=shift, steps=expected['steps'],
                             events=len(expected['events']), sites=sorted(own_sites),
                             saved_si=actual_saved_si, flags=result['flags'],
                             defined_flag_mask=expected['flag_mask']))
            if shift % 32 == 31:
                gc.collect()
    return rows, sites, total_steps, total_events


def original_campaign(cases, before):
    oracle_require(before == input_hashes(), 'inputs changed before original preflight')
    producers = producer_handoff_report()
    rows, sites, edges = [], set(), set()
    for case in cases:
        for core in (True, False):
            memory, regs, device = setup(case)
            try:
                expected = run_original(case, bytearray(memory), dict(regs),
                                        copy.deepcopy(device), core=core)
            except interactions.OracleFailure as error:
                boundary = 'core' if core else 'adapter'
                raise interactions.OracleFailure(
                    f'{case["name"]} {boundary}: original oracle failed: {error}') from error
            oracle_require(expected['status'] == 0,
                           case['name'] + ': original did not complete at its seam')
            producer_digest = producer_bank_digest(case, expected['memory'],
                                                   interactions.OracleFailure)
            oracle_require(expected['used'] == {p['tag'] for p in case['providers']},
                           case['name'] + ': provider phase did not fire')
            checks = 0
            if case['plane_check']:
                projected, checks = independent_plane_projection(case, memory, device)
                oracle_require([bytes(p) for p in expected['device'].planes] ==
                               [bytes(p) for p in projected.planes],
                               case['name'] + ': independent plane replay differs')
            profile = PROFILES[case['profile']]
            if core:
                oracle_require(expected['regs']['ip'] == profile['ret'] and
                               expected['regs']['sp'] == regs['sp'],
                               case['name'] + ': core boundary/SP differs')
            else:
                oracle_require(expected['regs']['sp'] == ((regs['sp'] + 2) & 0xFFFF),
                               case['name'] + ': adapter did not execute actual RET')
            if case['name'] == 'provider-live-final-saved-ds':
                oracle_require(expected['regs']['ds'] == 0x7000,
                               'saved-DS provider did not reach final POP DS')
            own_sites = {off for scope, off in expected['sites'] if scope == 'main'}
            own_edges = {(src, dst) for scope, src, dst in expected['edges']
                         if scope == 'main'}
            rows.append(dict(name=case['name'], profile=case['profile'],
                             boundary='core' if core else 'adapter',
                             sites=sorted(own_sites),
                             edges=[list(edge) for edge in sorted(own_edges)],
                             events=len(expected['events']), steps=expected['steps'],
                             independent_plane_byte_checks=checks,
                             producer_bank_sha256=producer_digest,
                             providers=sorted(expected['used'])))
            sites.update(own_sites)
            edges.update(own_edges)
            gc.collect()
    oracle_require(sites == OWN_SITES,
        f'original site union differs: missing={sorted(OWN_SITES-sites)} '
        f'extra={sorted(sites-OWN_SITES)}')
    oracle_require(edges == static_edges(),
        f'original branch union differs: missing={sorted(static_edges()-edges)} '
        f'extra={sorted(edges-static_edges())}')
    oracle_require(before == input_hashes(), 'inputs changed during original cases')
    sweep, sweep_sites, sweep_steps, sweep_events = original_prefix_sweep()
    oracle_require(before == input_hashes(), 'inputs changed during original prefix sweep')
    return rows, sites, edges, sweep, sweep_sites, sweep_steps, sweep_events, producers


def worker(directory, hash_path):
    before = json.loads(Path(hash_path).read_text(encoding='utf-8'))
    oracle_require(before == input_hashes(), 'inputs changed before native campaign')
    oracle_require(CODE_BYTES == 1675 and len(OWN_SITES) == 838,
                   f'static inventory differs: {CODE_BYTES} bytes/{len(OWN_SITES)} sites')
    oracle_require(sha(IMAGE) == 'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'pinned executable image identity changed')
    cases = make_cases()
    producers = producer_handoff_report()
    baseline = Native(directory)
    rows, sites, edges = [], set(), set()
    total_events = total_steps = plane_checks = 0
    for case in cases:
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            rows.append(row)
            sites.update(row['sites'])
            edges.update(tuple(edge) for edge in row['edges'])
            total_events += row['events']
            total_steps += row['steps']
            plane_checks += row['independent_plane_byte_checks']
        gc.collect()
    oracle_require(sites == OWN_SITES,
        f'native site union differs: missing={sorted(OWN_SITES-sites)} '
        f'extra={sorted(sites-OWN_SITES)}')
    oracle_require(edges == static_edges(),
        f'native edge union differs: missing={sorted(static_edges()-edges)} '
        f'extra={sorted(edges-static_edges())}')

    by_name = {case['name']: case for case in cases}
    witnesses = {
        1: '3plane10-df-reverse-shift17',
        2: '3plane10-df-reverse-shift17',
        3: 'incoming-cx-source-not-entry-ds',
        4: '3plane10-shift-255',
        5: 'provider-rereads-second-mask-word',
        6: 'provider-live-popped-row-count',
        7: 'provider-live-plane-boundary-di',
        8: '4plane14-shift-017',
        9: 'entry-if-set-before-first-cli',
        10: 'provider-live-final-saved-ds',
    }
    mutations = []
    for mutation, name in witnesses.items():
        variant = Native(directory, mutation)
        case = by_name[name]
        try:
            compare_case(variant, case, core=True)
        except Mismatch as error:
            mutations.append(dict(mutation=mutation, name=name,
                                  profile=case['profile'], completed=True,
                                  mismatch=str(error)))
        else:
            raise interactions.OracleFailure(
                f'entity sprite plane mutation {mutation} survived {name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after, 'input hashes changed during native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE),
        code_ranges=[[p['entry'], p['end']] for p in PROFILES.values()],
        translated_code_bytes=CODE_BYTES,
        instruction_sites=len(OWN_SITES),
        static_instruction_addresses=sorted(OWN_SITES),
        branch_edge_count=len(static_edges()),
        static_branch_edges=[list(edge) for edge in sorted(static_edges())],
        case_count=len(cases), core_adapter_comparisons=len(rows),
        mutation_count=len(mutations), mutations=mutations,
        executed_instruction_addresses=sorted(sites),
        branch_edges=[list(edge) for edge in sorted(edges)], cases=rows,
        total_bus_events=total_events, original_instruction_steps=total_steps,
        independent_plane_byte_checks=plane_checks, input_hashes=after,
        producer_handoffs=producers,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    native_bus_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        domain=('Three-plane 10/13/14/16-row and four-plane 14-row sprite leaves. '
                'Each core stops after its live POP DS and before its own RET; adapters '
                'read the live SS:SP target. Comparisons cover every RAM byte, all 13 '
                'register roles plus IP, defined FLAGS, ordered RAM/VGA/OUT events, and '
                'complete VGA planes/latches/registers. Independent replay models each '
                '24-bit source/mask shift, per-byte map mask, and OR plane. The suite '
                'includes unchecked shift counts, DF-sensitive LODSW/STOSB, live row/DI/DS '
                'stack slots, physical word wrap, VGA source/stack aliases, and five actual '
                '5BB0 producer-bank handoffs. The 6BDB..6CFB wide-sprite range is excluded.')))
    print(f'PASS entity sprite planes: {len(cases)} fixtures x core/adapter, '
          f'{len(sites)} sites/{len(edges)} edges, {total_events} events, '
          f'{plane_checks} plane-byte checks, {len(mutations)} completed mutants',
          flush=True)


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:]
    if args == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='entity-sprite-planes-original-', parent=BUILD) as directory:
            hashes = Path(directory) / 'input-hashes.json'
            write_json(hashes, input_hashes())
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hashes)], cwd=ROOT,
                        timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    if len(args) == 2 and args[0] == '--original-worker':
        before = json.loads(Path(args[1]).read_text(encoding='utf-8'))
        (rows, sites, edges, sweep, sweep_sites, sweep_steps, sweep_events,
         producers) = original_campaign(make_cases(), before)
        write_json(ORIGINAL_REPORT, dict(
            image='main', image_sha256=sha(IMAGE),
            code_ranges=[[p['entry'], p['end']] for p in PROFILES.values()],
            translated_code_bytes=CODE_BYTES, instruction_sites=len(OWN_SITES),
            static_instruction_addresses=sorted(OWN_SITES),
            branch_edge_count=len(static_edges()),
            executed_instruction_addresses=sorted(sites),
            branch_edges=[list(edge) for edge in sorted(edges)],
            case_count=len(make_cases()), core_adapter_comparisons=len(rows),
            cases=rows, original_prefix_probe_count=len(sweep),
            prefix_probe_values_per_entry=256,
            prefix_probe_instruction_addresses=sorted(sweep_sites),
            prefix_probe_steps=sweep_steps, prefix_probe_events=sweep_events,
            prefix_probes=sweep, producer_handoffs=producers,
            input_hashes=before,
            limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                        original_instruction_limit=MAX_INSTRUCTIONS,
                        oracle_bus_event_limit=MAX_EVENTS),
            domain='Original-only preflight; no native evidence.'))
        print(f'PASS original entity sprite planes: {len(rows)} boundary fixtures, '
              f'{len(sites)} sites/{len(edges)} edges; {len(sweep)} prefix probes',
              flush=True)
        return
    if len(args) == 3 and args[0] == '--native-worker':
        worker(args[1], args[2])
        return
    if args:
        raise SystemExit('usage: entity_sprite_planes.py [--original-only | --native-worker DIR HASHES]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-sprite-planes-native-', parent=BUILD) as directory:
        hashes = Path(directory) / 'input-hashes.json'
        write_json(hashes, input_hashes())
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--native-worker', str(directory), str(hashes)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()

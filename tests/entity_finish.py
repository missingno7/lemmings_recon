"""Bounded original-versus-C checks for the 1FE8/20D6/20E2/2148 JMP tails."""
import copy
import ctypes as ct
import gc
import json
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
from unpack import ASSET
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_16
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE

SIZE, MASK, FLAGS = interactions.SIZE, interactions.MASK, interactions.FLAGS
ENTRY_POINTS = {
    'interaction-call-1fe8': (0, 0x1FE8),
    'store-height-20d6': (1, 0x20D6),
    'mark-inactive-20e2': (2, 0x20E2),
    'resolve-height-2148': (3, 0x2148),
}
ENTRY_IDS = {address: entry for entry, address in ENTRY_POINTS.values()}
RANGES = ((0x1FE8, 0x1FEB), (0x20D6, 0x20E9), (0x2148, 0x2169))
MAX_PREFIX_INSTRUCTIONS, MAX_TOTAL_EVENTS = 64, 1024
WORKER_SECONDS, PROCESS_MIB = 180, 384
CALLBACK_BUDGET_EXIT, CALLBACK_ERROR_EXIT = 86, 87
CHILD_ENTRY, FINISH_CONTINUATION = 0x2EC0, 0x1FEB
IMAGE, ORACLE = interactions.IMAGE, interactions.ORACLE
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
FINISH_INS = {
    ins.address: ins
    for start, end in RANGES
    for ins in MD.disasm(IMAGE[start:end], start)
}
STATIC_SITES = set(FINISH_INS)
STATIC_EDGES = set()
for _address, _ins in FINISH_INS.items():
    if not _ins.group(capstone.CS_GRP_JUMP):
        continue
    if _ins.mnemonic.lower() not in ('jmp', 'ljmp'):
        STATIC_EDGES.add((_address, (_address + _ins.size) & 0xFFFF))
    if _ins.operands and _ins.operands[-1].type == capstone.x86.X86_OP_IMM:
        STATIC_EDGES.add((_address, _ins.operands[-1].imm & 0xFFFF))
REPORT = BUILD / 'entity-finish-differential.json'


class OracleFailure(AssertionError):
    """The original escaped an identified entry/provider seam or a hard bound."""


class Mismatch(AssertionError):
    """Only a completed original/native comparison counts as mutant evidence."""


class FinishAccess(interactions.Access):
    """A bounded provider that changes the live height word between reads."""

    def __init__(self, case, memory, regs, device, *, native=False):
        super().__init__(case, memory, regs, device)
        self.native = native

    def change_height_word(self):
        if self.case.get('provider') != 'height-reread' or 'height' in self.used:
            return
        address = interactions.physical(self.regs['ds'], self.regs['si'] + 6)
        value = self.case['provider_height_delta'] & 0xFFFF
        self.store(address, value & 0xFF)
        self.store(address + 1, value >> 8)
        self.used.add('height')

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        result = super().access(kind, address, flags, mask, value)
        # For native bytewise reads, mutate only after the first word's high
        # byte has been returned, so that word remains internally consistent.
        trigger = interactions.physical(self.regs['ds'], self.regs['si'] + 7)
        if (self.native and kind == 'read' and (address & MASK) == trigger and
                self.case.get('provider') == 'height-reread'):
            self.change_height_word()
        return result


def oracle_require(condition, message):
    if not condition:
        raise OracleFailure(message)


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def signed16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def read16(memory, segment, offset):
    address = interactions.physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def write16(memory, segment, offset, value):
    address = interactions.physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


class FinishCall(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('entry', 'value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y', 'code_segment',
                 'data_segment', 'extra_segment', 'stack_segment', 'stack_offset',
                 'flags')]


class FinishResult(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value', 'record_cursor',
                 'object_cursor', 'candidate_y', 'code_segment', 'data_segment',
                 'extra_segment', 'stack_segment', 'stack_offset', 'flags',
                 'continuation', 'status')]


MEM = interactions.MEM
Regs = interactions.Regs
PcBinding = interactions.PcBinding
SoundBinding = interactions.SoundBinding
Bus = interactions.Bus


def setup(case):
    # Every tail is reached after the parent PUSH ES at 1F3B. The continuation
    # at 1FEB will eventually consume this word, but this harness stops there.
    setup_case = dict(case)
    setup_case.setdefault('sp', 0xDFFE)
    memory, regs, device, pc_binding, sound_binding, _ = interactions.setup(setup_case)
    entry, address = ENTRY_POINTS[case['entry']]
    regs['ip'] = address
    regs['bp'] = case.get('candidate_y', case.get('bp', 0x20))
    if 'height_delta' in case:
        write16(memory, regs['ds'], regs['si'] + 6, case['height_delta'])
    # A valid parent entry has a live saved-ES word at SS:SP.
    write16(memory, regs['ss'], regs['sp'], regs['es'])
    raw = regs['flags']
    admissible = ((raw & 0x7FD5) | 2) & ~0x0100
    oracle_require(raw == admissible,
                   case['name'] + ': entry FLAGS are outside the declared IRET domain')
    return memory, regs, device, pc_binding, sound_binding, entry


def prefix_original(case, memory, regs, device):
    """Execute only the four maintained entry spans, stopping at 1FEB or CALL 2EC0."""
    cpu = Uc(UC_ARCH_X86, UC_MODE_16)
    cpu.mem_map(0, SIZE * 2)
    cpu.mem_write(0, bytes(memory))
    cpu.mem_write(SIZE, bytes(memory))
    for name, value in regs.items():
        cpu.reg_write(interactions.REG_IDS[name], value)

    access = FinishAccess(case, memory, regs, device)

    def mirror(address, value):
        address &= MASK
        cpu.mem_write(address, bytes((value & 0xFF,)))
        cpu.mem_write(address + SIZE, bytes((value & 0xFF,)))

    access.mirror = mirror
    current_flags, current_mask = regs['flags'], FLAGS
    previous = None
    steps, stopped, failure, boundary = 0, False, None, None
    sites, edges = set(), set()

    def stop(reason):
        nonlocal stopped, boundary
        stopped, boundary = True, reason
        cpu.emu_stop()

    def fail(message):
        nonlocal failure
        failure = message
        cpu.emu_stop()

    def code(u, _address, _size, _):
        nonlocal previous, current_flags, current_mask, steps
        steps += 1
        if steps > MAX_PREFIX_INSTRUCTIONS:
            fail('original finish-prefix instruction budget exhausted')
            return
        cs = u.reg_read(interactions.REG_IDS['cs']) & 0xFFFF
        off = u.reg_read(interactions.REG_IDS['ip']) & 0xFFFF
        previous_instruction = previous
        if previous_instruction is not None:
            prev_off, prev_ins = previous_instruction
            if prev_ins.group(capstone.CS_GRP_JUMP):
                edges.add((prev_off, off))
            current_mask = interactions.flags_after(prev_ins, current_mask)
            previous = None
            if prev_off == 0x214B:
                access.change_height_word()
        current_flags = u.reg_read(interactions.REG_IDS['flags']) & 0xFFFF
        if cs == regs['cs'] and off == FINISH_CONTINUATION:
            stop('finish-continuation')
            return
        if (cs == regs['cs'] and off == CHILD_ENTRY and
                previous_instruction is not None):
            prev_off, prev_ins = previous_instruction
            if prev_ins.mnemonic.lower() == 'call':
                stop('interaction-call')
                return
        if cs != regs['cs'] or off not in FINISH_INS:
            fail(f'original finish escaped owned entry spans at {cs:04x}:{off:04x}')
            return
        ins = FINISH_INS[off]
        load, loaded = interactions.code_for_case(case)
        expected = loaded[off:off + ins.size]
        actual = bytes(u.mem_read(interactions.physical(cs, off), ins.size))
        if actual != expected:
            fail(f'original finish code changed at {cs:04x}:{off:04x}: '
                 f'{actual.hex()}/{expected.hex()}')
            return
        previous = (off, ins)
        sites.add(off)

    def on_read(u, _kind, address, size, _value, _):
        for delta in range(size):
            access.access('read', address + delta, current_flags, current_mask)

    def on_write(u, _kind, address, size, value, _):
        for delta in range(size):
            access.access('write', address + delta, current_flags, current_mask,
                          (value >> (delta * 8)) & 0xFF)

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, on_read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, on_write)
    try:
        cpu.emu_start(interactions.physical(regs['cs'], regs['ip']), 0,
                      count=MAX_PREFIX_INSTRUCTIONS)
    except UcError as error:
        raise OracleFailure(case['name'] + ': bounded original prefix failed') from error
    oracle_require(stopped and failure is None,
                   case['name'] + ': ' + (failure or 'prefix missed its declared seam'))
    state = {name: cpu.reg_read(interactions.REG_IDS[name]) & 0xFFFF
             for name in interactions.REG_NAMES}
    oracle_require(bytes(cpu.mem_read(0, SIZE)) == bytes(memory),
                   case['name'] + ': prefix RAM mirror diverged')
    if boundary == 'interaction-call':
        oracle_require(state['ip'] == CHILD_ENTRY and
                       state['sp'] == ((regs['sp'] - 2) & 0xFFFF) and
                       read16(memory, state['ss'], state['sp']) == FINISH_CONTINUATION,
                       case['name'] + ': original CALL did not push live 1FEB')
    return dict(memory=bytes(memory), regs=state, device=device,
                events=access.events, used=access.used, boundary=boundary,
                sites=sites, edges=edges, steps=steps, flag_mask=current_mask)


def original(case, core=False):
    memory, regs, device, _pc, _sound, _entry = setup(case)
    prefix = prefix_original(case, bytearray(memory), dict(regs), copy.deepcopy(device))
    events = list(prefix['events'])
    used = set(prefix['used'])
    sites = set(prefix['sites'])
    edges = set(prefix['edges'])
    child_sites, child_edges, child_calls, child_steps = set(), set(), set(), 0

    if prefix['boundary'] == 'interaction-call':
        # Consume the real child CALL/RET with its own audited original oracle.
        child_case = dict(case)
        child = interactions.original(child_case, bytearray(prefix['memory']),
                                      dict(prefix['regs']), copy.deepcopy(prefix['device']),
                                      core=False, entry_flag_mask=prefix['flag_mask'])
        events.extend(child['events'])
        used.update(child['used'])
        child_sites.update(off for scope, off in child['sites'] if scope == 'main')
        child_edges.update((src, dst) for scope, src, dst in child['edges'] if scope == 'main')
        child_calls.update(child['call_targets'])
        child_steps = child['steps']
        out_memory, out_regs, out_device = child['memory'], child['regs'], child['device']
        child_status = child['status']
        if child_status == 0 and (out_regs['cs'] != regs['cs'] or
                                  out_regs['ip'] != FINISH_CONTINUATION):
            status = 5  # The actual near RET did not consume the live 1FEB word.
        else:
            status = child_status
        flag_mask = child['flag_mask']
    else:
        out_memory, out_regs, out_device = (prefix['memory'], prefix['regs'],
                                            prefix['device'])
        status, flag_mask = 0, prefix['flag_mask']

    oracle_require(len(events) <= MAX_TOTAL_EVENTS,
                   case['name'] + ': combined original event budget exhausted')

    result = dict(memory=out_memory, regs=out_regs, device=out_device,
                  events=events, used=used, status=status,
                  continuation=out_regs['ip'], sites=sites, edges=edges,
                  child_sites=child_sites, child_edges=child_edges,
                  child_calls=child_calls, steps=prefix['steps'] + child_steps,
                  flag_mask=flag_mask, boundary=prefix['boundary'])
    check_independent(case, result, regs, memory)
    return result


def check_independent(case, result, entry_regs, entry_memory):
    label = case['name']
    regs = result['regs']
    ds, si = entry_regs['ds'], entry_regs['si']
    if case['entry'] == 'store-height-20d6':
        y = case.get('candidate_y', case.get('bp', 0x20)) & 0xFFFF
        oracle_require(read16(result['memory'], ds, si + 2) == y,
                       label + ': 20D6 did not store its candidate height')
        mark = signed16(y) >= 0x00B4
        if mark:
            oracle_require(result['status'] == 0 and
                           result['continuation'] == 0x1FEB,
                           label + ': independent signed 20D6 mark edge disagrees')
        else:
            oracle_require(result['boundary'] == 'interaction-call',
                           label + ': independent signed 20D6 CALL edge disagrees')
    elif case['entry'] == 'mark-inactive-20e2':
        mark_address = interactions.physical(ds, si + 0x26)
        oracle_require(result['status'] == 0 and result['continuation'] == 0x1FEB and
                       result['memory'][mark_address] == 0xFF and
                       result['memory'][(mark_address + 1) & MASK] ==
                       entry_memory[(mark_address + 1) & MASK] and
                       result['boundary'] == 'finish-continuation',
                       label + ': standalone mark-only path did not stop at 1FEB')
    elif case['entry'] == 'resolve-height-2148':
        initial_y = case.get('candidate_y', case.get('bp', 0x20)) & 0xFFFF
        delta = case.get('height_delta', 0) & 0xFFFF
        summed = (initial_y + delta) & 0xFFFF
        adjust = signed16(summed) <= 10
        oracle_require((0x2156 in result['sites']) == adjust,
                       label + ': independent signed 2148 branch disagrees')
        if adjust:
            second_delta = case.get('provider_height_delta', delta) & 0xFFFF
            expected_y = (9 - second_delta) & 0xFFFF
            oracle_require(read16(result['memory'], ds, si + 2) == expected_y and
                           result['memory'][interactions.physical(ds, si + 0x27)] ==
                           ((-(case.get('record_delta', 0) & 0xFF)) & 0xFF) and
                           (read16(result['memory'], ds, si + 8) & 8) == 0,
                           label + ': independent 2148 signed-step writes disagree')
    if case.get('expect_status') is not None:
        oracle_require(result['status'] == case['expect_status'],
                       f'{label}: original status {result["status"]}, expected '
                       f'{case["expect_status"]}')


def cases():
    rows = [
        dict(name='direct-interaction-call', entry='interaction-call-1fe8',
             sample=0, record_bits=0xFFFF),
        dict(name='height-b3-signed-low', entry='store-height-20d6',
             candidate_y=0x00B3, sample=0, record_bits=0xFFFF),
        dict(name='height-b4-signed-mark', entry='store-height-20d6',
             candidate_y=0x00B4, sample=0, record_bits=0xFFFF),
        dict(name='height-negative-signed-low', entry='store-height-20d6',
             candidate_y=0xFFFF, sample=0, record_bits=0xFFFF),
        dict(name='height-negative-highbit', entry='store-height-20d6',
             candidate_y=0x8000, sample=0, record_bits=0xFFFF),
        dict(name='height-positive-high', entry='store-height-20d6',
             candidate_y=0x7FFF, sample=0, record_bits=0xFFFF),
        dict(name='direct-mark-only', entry='mark-inactive-20e2',
             candidate_y=0x1234, sample=0, record_bits=0xFFFF),
        dict(name='direct-mark-offset-wrap-and-flags', entry='mark-inactive-20e2',
             candidate_y=0xABCD, ds=0x5000, si=0xFFF0, flags=0x0A47,
             sample=0, record_bits=0xFFFF),
        dict(name='height-write-saved-es-alias', entry='store-height-20d6',
             candidate_y=0x00B4, ds=0x5000, ss=0x5000, si=0xDFFC,
             sample=0, record_bits=0xFFFF),
        dict(name='step-sum-ten-adjust', entry='resolve-height-2148',
             candidate_y=4, height_delta=6, record_delta=1, record_bits=0xFFFF,
             sample=0),
        dict(name='step-sum-eleven-interact', entry='resolve-height-2148',
             candidate_y=4, height_delta=7, sample=0, record_bits=0xFFFF),
        dict(name='step-negative-signed-adjust', entry='resolve-height-2148',
             candidate_y=0, height_delta=0xFFFF, record_delta=0x80,
             sample=0, record_bits=0xFFFF),
        dict(name='step-add-wrap-adjust', entry='resolve-height-2148',
             candidate_y=0xFFFF, height_delta=1, record_delta=0x01,
             sample=0, record_bits=0xFFFF),
        dict(name='step-rmw-entry-flags', entry='resolve-height-2148',
             candidate_y=3, height_delta=4, record_delta=1,
             record_bits=0xFFFF, sample=0, flags=0x0E47),
        dict(name='step-live-height-reread', entry='resolve-height-2148',
             candidate_y=4, height_delta=6, provider='height-reread',
             provider_height_delta=1, record_delta=1,
             record_bits=0xFFFF, sample=0),
        dict(name='call-return-word-overwritten', entry='interaction-call-1fe8',
             sample=0, second_sample=0, record_bits=0xFFFF,
             ds=0x5000, ss=0x5000, si=0xDFD1),
        dict(name='child-unbound-pc-vector', entry='interaction-call-1fe8',
             sample=1, record_bits=0, enabled=0, options=1,
             pc_vector=(0x0182, 0x6200), expect_status=1),
        dict(name='child-unbound-sound-vector', entry='interaction-call-1fe8',
             sample=5, record_bits=0, enabled=0xFF, options=3,
             sound_vector=(0, 0x6200), expect_status=1),
        dict(name='child-vga-map-and-stack-alias', entry='interaction-call-1fe8',
             sample=1, record_bits=0, enabled=0, options=1,
             vga=True, ss=0x9FFF, expect_status=0),
        dict(name='child-untranslated-pc-target', entry='interaction-call-1fe8',
             sample=1, record_bits=0, enabled=0, options=1,
             pc_table_target=0x01B3, expect_status=2),
        dict(name='child-changed-pc-child-return', entry='interaction-call-1fe8',
             sample=1, record_bits=0, enabled=0, options=1,
             provider='pc-child-return', expect_status=3),
        dict(name='child-changed-pc-iret', entry='interaction-call-1fe8',
             sample=1, record_bits=0, enabled=0, options=1,
             provider='pc-interrupt-return', expect_status=4),
    ]
    # Height-tail edges that select both paths through the shared interaction CALL.
    rows.extend([
        dict(name='height-entry-bypass-at-10', entry='resolve-height-2148',
             candidate_y=0, height_delta=10, sample=0, record_bits=0xFFFF),
        dict(name='height-entry-bypass-above-10', entry='resolve-height-2148',
             candidate_y=0, height_delta=11, sample=0, record_bits=0xFFFF),
    ])
    return rows


def input_hashes():
    paths = [
        'assets/vgalemmi.exe', 'assets/main.dat', 'assets/adlib.dat',
        'assets/tandysnd.dat',
        'c/entity_finish.c', 'c/entity_finish.h',
        'c/entity_interactions.c', 'c/entity_interactions.h',
        'c/pcspeaker_interrupt.c', 'c/pcspeaker_interrupt.h',
        'c/pcspeaker_dispatch.c', 'c/pcspeaker_dispatch.h',
        'c/pcspeaker.c', 'c/pcspeaker.h', 'c/pcspeaker_sym.h',
        'c/sound_interrupt.c', 'c/sound_interrupt.h',
        'c/sound_latches.c', 'c/sound_latches.h', 'c/sound_latches_sym.h',
        'c/regs.h', 'c/special_blit.h', 'c/lemmings_sym.h',
        'metadata/oracle.json', 'metadata/symbols.json',
        'metadata/sound-oracle.json', 'metadata/pcspeaker-encodings.json',
        'metadata/pcspeaker-producers.json', 'metadata/pcspeaker-regions.json',
        'metadata/pcspeaker-symbols.json', 'metadata/adlib-symbols.json',
        'metadata/tandysnd-symbols.json', 'metadata/toolchain-lock.json',
        'src/game_code.asm', 'src/sound/pcspeaker.asm',
        'src/sound/adlib.asm', 'src/sound/tandysnd.asm',
        'tests/entity_finish.py', 'tests/entity_interactions.py',
        'tests/pcspeaker_dispatch.py', 'tests/sound_latches.py',
        'tests/minimap_vga.py', 'tools/bounded_process.py', 'tools/cbuild.py',
        'tools/common.py', 'tools/resources.py', 'tools/unpack.py',
        'tools/difftest.py',
    ]
    return {name: sha((ROOT / name).read_bytes()) for name in paths}


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-finish-{mutation}.dll',
                     mutation, 'entity_finish')
        self.lib = ct.CDLL(str(path))
        self.lib.lmn_entity_finish_core.argtypes = [
            MEM, ct.POINTER(FinishCall), ct.POINTER(PcBinding),
            ct.POINTER(SoundBinding), ct.POINTER(Bus)]
        self.lib.lmn_entity_finish_core.restype = FinishResult
        self.lib.lmn_entity_finish_adapter.argtypes = [
            MEM, ct.POINTER(Regs), ct.c_uint16, ct.POINTER(PcBinding),
            ct.POINTER(SoundBinding), ct.POINTER(Bus)]
        self.lib.lmn_entity_finish_adapter.restype = ct.c_uint16

    def run(self, case, memory, regs, device, pc_binding, sound_binding,
            entry, core):
        # Interaction callbacks are based on the child-entry SP after the real
        # 1FE8 CALL. Provider writes therefore target the live child save frame.
        access_regs = dict(regs)
        access_regs['sp'] = (regs['sp'] - 2) & 0xFFFF
        access = FinishAccess(case, memory, access_regs, device, native=True)

        def read(_context, _memory, address, flags):
            try:
                return access.access('read', address, flags, FLAGS)
            except BaseException as error:
                interactions.worker_fail(CALLBACK_BUDGET_EXIT if 'budget' in str(error)
                                         else CALLBACK_ERROR_EXIT, error)

        def write(_context, _memory, address, value, flags):
            try:
                access.access('write', address, flags, FLAGS, value)
            except BaseException as error:
                interactions.worker_fail(CALLBACK_BUDGET_EXIT if 'budget' in str(error)
                                         else CALLBACK_ERROR_EXIT, error)

        def out(_context, port, value, flags):
            interactions.worker_fail(CALLBACK_ERROR_EXIT,
                f'unexpected entity-finish port {port:04x}={value:04x}')

        callbacks = (interactions.READ(read), interactions.WRITE(write),
                     interactions.OUT(out))
        bus = Bus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = Regs(**regs)
        pc = ct.byref(pc_binding) if pc_binding is not None else None
        sb = ct.byref(sound_binding) if sound_binding is not None else None
        if core:
            call = FinishCall(entry, regs['ax'], regs['bx'], regs['cx'], regs['dx'],
                              regs['si'], regs['di'], regs['bp'], regs['cs'],
                              regs['ds'], regs['es'], regs['ss'], regs['sp'],
                              regs['flags'])
            result = self.lib.lmn_entity_finish_core(
                ram, ct.byref(call), pc, sb, ct.byref(bus))
            state.ax, state.bx, state.cx = result.value, result.map_cursor, result.count
            state.dx, state.si, state.di = result.auxiliary_value, result.record_cursor, result.object_cursor
            state.bp, state.cs = result.candidate_y, result.code_segment
            state.ds, state.es = result.data_segment, result.extra_segment
            state.ss, state.sp = result.stack_segment, result.stack_offset
            state.flags, state.ip = result.flags, result.continuation
            status = result.status
        else:
            status = self.lib.lmn_entity_finish_adapter(
                ram, ct.byref(state), entry, pc, sb, ct.byref(bus))
        return dict(memory=bytes(memory),
                    regs={name: getattr(state, name) for name in interactions.REG_NAMES},
                    device=device, events=access.events, used=access.used,
                    status=status, continuation=state.ip)


def compare(native, case, core):
    memory, regs, device, pc_binding, sound_binding, entry = setup(case)
    expected = original(case, core=False)
    actual = native.run(case, bytearray(memory), dict(regs), copy.deepcopy(device),
                        pc_binding, sound_binding, entry, core)
    label = case['name'] + (' core' if core else ' adapter')
    require(actual['status'] == expected['status'],
            f'{label}: status {actual["status"]}/{expected["status"]}')
    require(actual['memory'] == expected['memory'], label + ': RAM differs')
    for name in interactions.REG_NAMES:
        mask = expected['flag_mask'] if name == 'flags' else 0xFFFF
        require(((actual['regs'][name] ^ expected['regs'][name]) & mask) == 0,
                f'{label}: {name} {actual["regs"][name]:04x}/'
                f'{expected["regs"][name]:04x} under {mask:04x}')
    require(len(actual['events']) == len(expected['events']),
            f'{label}: bus event count {len(actual["events"])}/'
            f'{len(expected["events"])}')
    for index, (got, ref) in enumerate(zip(actual['events'], expected['events'])):
        require(got[:3] == ref[:3],
                f'{label}: event {index} {got[:3]!r}/{ref[:3]!r}')
        require(((got[3] ^ ref[3]) & ref[4]) == 0,
                f'{label}: event {index} FLAGS {got[3]:04x}/{ref[3]:04x} '
                f'under {ref[4]:04x}')
    require(actual['used'] == expected['used'],
            f'{label}: provider effects {actual["used"]}/{expected["used"]}')
    if expected['device'] is not None:
        require(actual['device'].state() == expected['device'].state(),
                label + ': VGA state differs')
        got_trace = [(a, b, c) for a, b, c, _ in actual['device'].trace]
        ref_trace = [(a, b, c) for a, b, c, _ in expected['device'].trace]
        require(got_trace == ref_trace, label + ': VGA traces differ')
    if case['entry'] == 'resolve-height-2148' and case.get('height_delta') is not None:
        summed = (case.get('candidate_y', 0x20) + case['height_delta']) & 0xFFFF
        if signed16(summed) <= 10:
            addr = interactions.physical(regs['ds'], regs['si'] + 0x27)
            writes = [e for e in expected['events'] if e[0] == 'write' and e[1] == addr]
            oracle_require(bool(writes), label + ': NEG write missing from oracle trace')
    return expected


def worker(directory):
    before = input_hashes()
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'static main image identity changed')
    oracle_require(len(STATIC_SITES) == 18,
                   f'finish entry instruction inventory changed: {len(STATIC_SITES)}')
    baseline = Native(directory)
    fixture_rows = cases()
    sites, edges, child_sites, child_edges, child_calls = set(), set(), set(), set(), set()
    event_count = instruction_count = 0
    rows = []
    for case in fixture_rows:
        boundary_results = []
        for core in (True, False):
            expected = compare(baseline, case, core)
            boundary_results.append(expected)
            sites.update(expected['sites'])
            edges.update(expected['edges'])
            child_sites.update(expected['child_sites'])
            child_edges.update(expected['child_edges'])
            child_calls.update(expected['child_calls'])
            event_count += len(expected['events'])
            instruction_count += expected['steps']
        rows.append(dict(name=case['name'], entry=case['entry'],
                         entry_offset=ENTRY_POINTS[case['entry']][1],
                         statuses=[r['status'] for r in boundary_results],
                         continuations=[r['continuation'] for r in boundary_results],
                         candidate_y=case.get('candidate_y', case.get('bp', 0x20)),
                         height_delta=case.get('height_delta'),
                         expected_status=case.get('expect_status')))
        gc.collect()

    oracle_require(sites == STATIC_SITES,
                   f'finish entry site union differs: {sites ^ STATIC_SITES}')
    oracle_require(edges == STATIC_EDGES,
                   f'finish entry edge union differs: '
                   f'missing={STATIC_EDGES - edges}, extra={edges - STATIC_EDGES}')
    for number, name in (
        (1, 'call-return-word-overwritten'),
        (2, 'direct-interaction-call'),
        (3, 'height-negative-signed-low'),
        (4, 'step-negative-signed-adjust'),
        (5, 'step-rmw-entry-flags'),
        (6, 'call-return-word-overwritten'),
    ):
        mutant = Native(directory, number)
        witness = next(row for row in fixture_rows if row['name'] == name)
        try:
            compare(mutant, witness, core=False)
        except Mismatch as error:
            rows.append(dict(mutation=number, case=name, completed=True,
                             mismatch=str(error)))
        else:
            raise OracleFailure(f'entity-finish mutation {number} survived')
        gc.collect()

    oracle_require(before == input_hashes(),
                   'inputs changed during bounded entity-finish campaign')
    write_json(REPORT, dict(image='main', image_sha256=sha(IMAGE),
        code_ranges=[list(bounds) for bounds in RANGES],
        translated_code_bytes=sum(end - start for start, end in RANGES),
        case_count=len(fixture_rows), comparisons=len(fixture_rows) * 2,
        cases=rows, executed_instruction_addresses=sorted(sites),
        static_instruction_addresses=sorted(STATIC_SITES),
        branch_edges=sorted(edges), static_branch_edges=sorted(STATIC_EDGES),
        integrated_interaction_instruction_addresses=sorted(child_sites),
        integrated_interaction_branch_edges=sorted(child_edges),
        dynamic_interaction_call_targets=sorted(child_calls),
        total_bus_events=event_count, original_instructions_executed=instruction_count,
        mutation_count=6,
        mutations=[r for r in rows if 'mutation' in r],
        input_hashes=before,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=PROCESS_MIB + 256,
                    original_prefix_instruction_limit=MAX_PREFIX_INSTRUCTIONS,
                    interaction_child_instruction_limit=interactions.MAX_INSTRUCTIONS,
                    native_callback_event_limit=MAX_TOTAL_EVENTS,
                    callback_budget_exit=CALLBACK_BUDGET_EXIT,
                    callback_error_exit=CALLBACK_ERROR_EXIT),
        domain='Original 1FE8,20D6,20E2,2148 shared JMP entries through 1FEB or '
               'declared interaction-child status seams. Includes original CALL push, '
               'actual interaction RET word, signed height/step comparisons, mark-only '
               'continuation, live stack/record aliases and composed INT60/INT61 child '
               'statuses. Incoming parent JMP sites and execution after 1FEB remain outside scope.'))
    print(f'PASS entity finish: {len(fixture_rows)} fixtures at core+adapter; '
          f'{len(STATIC_SITES)} entry sites/{len(edges)} edges; '
          f'{len(child_sites)} interaction sites/{len(child_calls)} child targets; '
          f'{event_count} bus events; 6 completed mutants', flush=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if sys.argv[1:]:
        raise SystemExit('Unexpected entity-finish arguments')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-finish-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB)


if __name__ == '__main__':
    main()

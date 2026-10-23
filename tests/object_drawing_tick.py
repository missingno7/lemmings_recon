"""Bounded differential coverage for the 7BB8 object-drawing caller."""
from __future__ import annotations

import ctypes
import copy
import gc
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]

import capstone
import terrain_drawing as drawing
import object_drawing_cases as fixtures
import drawing_caller_oracle as original_caller
import object_animation as animation_suite
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
from dat_io import REG_NAMES
from dat_io_c import MEM, Regs
from unpack import ASSET, unpack, relocated


IMAGE, META = unpack(ASSET.read_bytes())
SIZE = 1 << 20
MASK = SIZE - 1
ENTRY, END, OUTER_RET = 0x7BB8, 0x7C0A, 0x7C09
BITMAP_ENTRY, BITMAP_FAR_RETURN = 0x8822, 0x9966
BITMAP_CALL, BITMAP_CALL_RETURN = 0x7BF9, 0x7BFE
MISSING_PROVIDER_RETURN = 0x969C
READY, MISSING_PROVIDER, CHANGED_CHILD_NEAR, CHILD_BOUNDARY, CHANGED_FAR_RETURN = range(5)
MAX_ORIGINAL_INSTRUCTIONS = 3_000_000
MAX_BUS_EVENTS = 2_000_000
MAX_VGA_EVENTS = 1_200_000
WORKER_SECONDS, PROCESS_MIB = 360, 512
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'object-drawing-tick-differential.json'
DEFINED_FLAGS = 0x0FD7

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
LOCAL = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
CHILD = {pc: ins for pc, ins in drawing.INS.items()
         if BITMAP_ENTRY <= pc < 0x9A90}
INS = LOCAL | CHILD
LOCAL_BRANCHES = {pc for pc, ins in LOCAL.items()
                  if ins.group(capstone.CS_GRP_JUMP) or ins.mnemonic.startswith('loop')}
LOCAL_EDGES = {
    (pc, ins.operands[0].imm & 0xFFFF)
    for pc, ins in LOCAL.items() if pc in LOCAL_BRANCHES
}
LOCAL_EDGES |= {
    (pc, (pc + ins.size) & 0xFFFF)
    for pc, ins in LOCAL.items()
    if pc in LOCAL_BRANCHES and ins.mnemonic != 'jmp'
}
drawing.common.MAX_BUS_EVENTS = MAX_BUS_EVENTS
drawing.common.MAX_VGA_EVENTS = MAX_VGA_EVENTS


class Call(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in (
        'value', 'map_cursor', 'count', 'auxiliary_value', 'record_cursor',
        'object_cursor', 'candidate_y', 'code_segment', 'data_segment',
        'extra_segment', 'stack_segment', 'stack_offset', 'flags',
        'game_data_segment')]


class Result(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in (
        'value', 'map_cursor', 'count', 'auxiliary_value', 'record_cursor',
        'object_cursor', 'candidate_y', 'code_segment', 'data_segment',
        'extra_segment', 'stack_segment', 'stack_offset', 'flags',
        'game_data_segment', 'continuation', 'status')]


def _read8(memory, segment, offset):
    return memory[((segment << 4) + (offset & 0xFFFF)) & MASK]


def _read16(memory, segment, offset):
    address = ((segment << 4) + (offset & 0xFFFF)) & MASK
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def _put16(memory, segment, offset, value):
    address = ((segment << 4) + (offset & 0xFFFF)) & MASK
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def _row(index, *, x=0x20, y=0x10, draw_flags=1, width=16, height=1,
         source=None, mask=None):
    if source is None:
        source = 0x1000 + index * 0x0100
    if mask is None:
        mask = 0x7000 + index * 0x0100
    return (index, x & 0xFFFF, y & 0xFFFF, draw_flags & 0xFFFF,
            width & 0xFF, height & 0xFF, source & 0xFFFF, mask & 0xFFFF)


def _case(name, objects=(), **kwargs):
    return dict(name=name, seed=kwargs.pop('_seed', 0), real=False,
                objects=tuple(objects), independent=kwargs.pop('independent', True),
                **kwargs)


def cases():
    out = []

    def add(name, objects=(), **kwargs):
        out.append(_case(name, objects, _seed=len(out), **kwargs))

    add('all-inactive')
    for index in range(32):
        add(f'single-active-slot-{index:02d}',
            (_row(index, x=0x20 + (index % 4) * 8,
                  y=8 + (index % 4) * 2, width=16, height=1),),
            df=bool(index & 1), if_flag=bool(index & 2))
    all_rows = tuple(_row(i, x=0x20 + (i % 8) * 8,
                          y=8 + (i % 4) * 2, width=8, height=1)
                     for i in range(32))
    add('all-32-active-forward', all_rows)
    add('all-32-active-backward-if', all_rows, df=True, if_flag=True)

    add('scroll-positive-origin', (_row(4, x=0x30, y=0x10),), scroll=0x08)
    add('scroll-negative-subtraction-wrap', (_row(4, x=0x10, y=0x10),), scroll=0x20)
    add('scroll-origin-ffff-wrap', (_row(4, x=1, y=0x10),), scroll=0xFFF0)
    add('incoming-ds-distinct-from-game-data', (_row(5, x=0x30),),
        data_segment=0x6000, scroll=0x10)
    add('definition-bit-zero-is-cleared', (_row(6, draw_flags=1),))
    add('definition-bit-zero-was-already-clear', (_row(6, draw_flags=0),))
    add('df-if-with-live-render-child', (_row(7, x=0x28, width=24, height=2),),
        df=True, if_flag=True)
    add('physical-stack-word-wrap', (_row(8, width=8),), ss=0xFFFF, sp=0x0011)
    add('resource-segment-read-from-live-ds', (_row(9, source=0x1800, mask=0x7200),),
        graphics_segment=0x5100)
    add('ds-equals-ss-normal-frame',
        (_row(11, x=0x20, y=0x10, width=16, height=1),),
        same_segments=True, independent=False)
    # The original 397D caller's proven dirty-read seam is reproduced with the
    # same child inputs; the 7BB8 wrapper owns a different CALL frame.
    add('changed-child-near-read-mask-alias',
        (_row(12, x=0x10, y=0, draw_flags=0x000F, width=8, height=8),),
        scroll=0x10, sp=0x480A, dirty=0xFF, dirty_base=0x47FD,
        expected_status=CHANGED_CHILD_NEAR, independent=False)
    add('missing-read-mask-provider-seam',
        (_row(13, x=0x20, y=4, draw_flags=0x4003, width=24, height=3),),
        provider='missing-in', expected_status=MISSING_PROVIDER, independent=False)
    # At the first child VGA OUT, the bounded provider edits the real saved
    # stack words.  These are distinct witnesses for live DS, CX, and FAR RET.
    add('provider-live-child-ds',
        (_row(14, x=0x20, y=0x10, width=16, height=1),),
        ss=0x6000, sp=0x8000, provider='saved-ds-provider',
        provider_delta=-12, provider_value=0x7000,
        provider_alt_segment=0x7000, independent=False)
    add('provider-live-saved-cx',
        (_row(15, x=0x20, y=0x10, width=16, height=1),),
        ss=0x6000, sp=0x8000, provider='saved-cx-provider',
        provider_words=((-2, 2), (-4, fixtures.field('LevelObjectDefinitions') + 8),
                        (-6, fixtures.field('LevelObjectGraphicsRecords') + 28)),
        independent=False)
    add('provider-changed-child-far-return',
        (_row(16, x=0x20, y=0x10, width=16, height=1),),
        ss=0x6000, sp=0x8000, provider='far-ip-provider',
        provider_delta=-10, provider_value=0x4567,
        expected_status=CHANGED_FAR_RETURN, independent=False)
    return out


def prepare(case):
    memory, regs, flags, game_data_segment = fixtures.prepare(case)
    original_ds = regs['ds']
    if 'data_segment' in case:
        target = case['data_segment']
        source_at = original_ds << 4
        target_at = target << 4
        memory[target_at:target_at + 0x10000] = memory[source_at:source_at + 0x10000]
        regs['ds'] = target

    regs['ip'] = ENTRY
    regs['es'] = (regs['ds'] if case.get('output_segment') == 'data'
                  else case.get('output_segment', 0xA000))
    regs['ss'] = regs['ds'] if case.get('same_segments') else case.get('ss', regs['ss'])
    regs['sp'] = case.get('sp', regs['sp'])
    if case.get('df'):
        flags |= 0x0400
    else:
        flags &= ~0x0400
    if case.get('if_flag'):
        flags |= 0x0200
    else:
        flags &= ~0x0200

    source_segment = case.get('graphics_segment', 0x5000)
    _put16(memory, regs['ds'], fixtures.field('GraphicsResourceSegment'), source_segment)
    _put16(memory, game_data_segment, fixtures.field('GraphicsResourceSegment'), source_segment)
    _put16(memory, regs['ds'], 0, case.get('scroll', 0))
    _put16(memory, game_data_segment, 0, case.get('scroll', 0))
    if 'dirty' in case:
        for segment in {regs['ds'], game_data_segment}:
            memory[((segment << 4) + fixtures.field('DrawingDirtyCellsEnabledByte')) & MASK] = case['dirty']
            _put16(memory, segment, fixtures.field('DrawingDirtyCellMapOffset'),
                   case['dirty_base'])

    if case.get('provider_alt_segment') is not None:
        source_at = (regs['ds'] << 4) & MASK
        target_at = (case['provider_alt_segment'] << 4) & MASK
        memory[target_at:target_at + 0x10000] = memory[source_at:source_at + 0x10000]
        for offset in range(32 * 8):
            memory[((target_at + fixtures.field('LevelObjectDefinitions') + offset)
                    & MASK)] = 0

    _put16(memory, regs['ss'], regs['sp'], case.get('outer_ip', 0xEED1))
    image = relocated(IMAGE, META['relocations'], regs['cs'])
    code_at = ((regs['cs'] << 4) + ENTRY) & MASK
    if bytes(memory[code_at:code_at + END - ENTRY]) != image[ENTRY:END]:
        raise drawing.common.VerificationFailure('tick fixture modified 7BB8..7C09 code')
    return memory, regs, flags, game_data_segment


def _apply_stack_provider(device, case, regs, uc=None):
    provider = case.get('provider')
    if provider not in ('saved-ds-provider', 'saved-cx-provider', 'far-ip-provider'):
        return
    fired = device._tick_provider_fired
    if provider in fired:
        return
    words = case['provider_words'] if 'provider_words' in case else (
        (case['provider_delta'], case['provider_value']),)
    for delta, value in words:
        offset = (regs['sp'] + delta) & 0xFFFF
        address = ((regs['ss'] << 4) + offset) & MASK
        for index, byte in enumerate((value & 0xFF, (value >> 8) & 0xFF)):
            p = (address + index) & MASK
            device.memory[p] = byte
            if uc is not None:
                uc.mem_write(p, bytes((byte,)))
    fired.add(provider)


def _new_device(memory, case, regs):
    device = drawing.common.TraceDevice(bytearray(memory), case['seed'] + ENTRY)
    provider = case.get('provider')
    device._tick_provider_fired = set()
    if provider in ('saved-ds-provider', 'saved-cx-provider', 'far-ip-provider'):
        original_out = device.vga.out

        def out(port, value, flags):
            original_out(port, value, flags)
            _apply_stack_provider(device, case, regs)

        device.vga.out = out
    return device


def _original_run(case, memory, regs, flags, game_data_segment, *, core):
    device = _new_device(memory, case, regs)
    device.vga.trace = original_caller.DeviceTrace()
    expected_active = [row for row in case.get('objects', ()) if row[1] != 0]
    observed = dict(child_calls=0, independent_plane_checks=0, pending_planes=None)

    def observe(off, cpu, _device):
        if (case.get('provider') in ('saved-ds-provider', 'saved-cx-provider',
                                     'far-ip-provider') and
                INS[off].mnemonic.startswith('out')):
            _apply_stack_provider(device, case, regs, cpu)
        if off == BITMAP_ENTRY:
            if observed['child_calls'] < len(expected_active) and case.get('independent'):
                index, x_pos, y_pos, draw_flags, width, height, source, mask = \
                    expected_active[observed['child_calls']]
                ds = cpu.reg_read(original_caller.oracle.REG['ds'])
                scroll = _read16(device.memory, ds, 0)
                expected = dict(ax=(x_pos - scroll + 0x10) & 0xFFFF,
                    bx=y_pos, bp=draw_flags & 0xFFFE, dx=width,
                    cx=0x0400 | height, si=source, di=(source + mask) & 0xFFFF)
                for name, value in expected.items():
                    drawing.common.require(
                        cpu.reg_read(original_caller.oracle.REG[name]) == value,
                        f'{case["name"]}: independent child input {name} '
                        f'for slot {index}')
            observed['child_calls'] += 1
        if off in drawing.FAMILIES and case.get('independent'):
            family = drawing.FAMILIES[off]
            entry = {name: cpu.reg_read(reg)
                     for name, reg in original_caller.oracle.REG.items()}
            entry['flags'] = cpu.reg_read(drawing.x.UC_X86_REG_EFLAGS)
            drawing.bitmap.configure(family)
            observed['pending_planes'] = drawing.render._independent_planes(
                device.vga.planes, device.memory, entry, game_data_segment)
        elif INS[off].mnemonic == 'retf' and observed['pending_planes'] is not None:
            drawing.common.require(observed['pending_planes'] == device.vga.planes,
                f'{case["name"]}: independent renderer plane footprint')
            observed['pending_planes'] = None
            observed['independent_plane_checks'] += 1

    continuation = {OUTER_RET} if core else set()
    if case.get('provider') in ('missing-in', 'missing-out'):
        continuation.add(MISSING_PROVIDER_RETURN)
    result = original_caller.original(case, device, regs, flags,
        instructions=INS, far_calls={BITMAP_CALL}, continuations=continuation,
        observe=observe, max_steps=MAX_ORIGINAL_INSTRUCTIONS)
    (state, flag_mask, sites, edges, boundary, child_entry, body) = result
    expected_status = _status_from_boundary(boundary)
    if 'expected_status' in case:
        drawing.common.require(expected_status == case['expected_status'],
            f'{case["name"]}: original did not reach expected status '
            f'{case["expected_status"]}; got {boundary!r}')
    if core and expected_status == READY:
        drawing.common.require(state['ip'] == OUTER_RET,
            f'{case["name"]}: core did not stop before the actual outer RET')
    if not core and expected_status == READY:
        drawing.common.require(boundary[0] == 'outer-return',
            f'{case["name"]}: adapter oracle did not execute the live outer RET')
    if case.get('provider') in ('saved-ds-provider', 'saved-cx-provider',
                                'far-ip-provider'):
        drawing.common.require(case['provider'] in device._tick_provider_fired,
            f'{case["name"]}: stack provider did not fire')
    if case.get('provider') == 'saved-ds-provider':
        drawing.common.require(state['ds'] == case['provider_value'],
            f'{case["name"]}: original did not restore provider-updated DS')
    if case.get('provider') == 'saved-cx-provider':
        expected_si = (fixtures.field('LevelObjectGraphicsRecords') + 3 * 28) & 0xFFFF
        expected_di = (fixtures.field('LevelObjectDefinitions') + 3 * 8) & 0xFFFF
        drawing.common.require(state['cx'] == 0 and state['si'] == expected_si and
                               state['di'] == expected_di,
            f'{case["name"]}: original did not use live saved SI/DI/CX words')
    if case.get('provider') == 'far-ip-provider':
        drawing.common.require(boundary[0] == 'changed-child-far' and
                                boundary[1] == regs['cs'] and boundary[2] == 0x4567,
            f'{case["name"]}: original did not stop at the changed live FAR RET')
    drawing.common.require(observed['pending_planes'] is None,
        f'{case["name"]}: renderer did not reach a far return')
    return dict(memory=device.memory, regs=state, flags_mask=flag_mask,
        device=device, status=expected_status, boundary=boundary,
        child_calls=observed['child_calls'],
        independent_plane_checks=observed['independent_plane_checks'],
        provider_fired=sorted(device._tick_provider_fired),
        sites=sites, edges=edges)


def original_only_case(case, *, core):
    memory, regs, flags, game_data_segment = prepare(case)
    return _original_run(case, memory, regs, flags, game_data_segment, core=core)


def original_only():
    before = input_hashes()
    all_sites, all_edges = set(), set()
    specs = cases()
    for index, case in enumerate(specs):
        for core in (True, False):
            result = original_only_case(case, core=core)
            all_sites.update(result['sites'] & set(LOCAL))
            all_edges.update(edge for edge in result['edges'] if edge[0] in LOCAL)
        if index % 8 == 0:
            print(f'ORIGINAL {index + 1}/{len(specs)} {case["name"]}', flush=True)
            gc.collect()
    drawing.common.require(all_sites == set(LOCAL),
        f'original caller sites {len(all_sites)}/{len(LOCAL)}; '
        f'missing={sorted(set(LOCAL) - all_sites)}')
    drawing.common.require(all_edges == LOCAL_EDGES,
        f'original caller edges {len(all_edges)}/{len(LOCAL_EDGES)}; '
        f'missing={sorted(LOCAL_EDGES - all_edges)}')
    drawing.common.require(before == input_hashes(),
        'object-drawing tick inputs changed during original-only preflight')
    print(f'PASS original object-drawing tick: {len(specs)} fixtures x core/adapter, '
          f'{len(all_sites)} caller sites/{len(all_edges)} edges', flush=True)


def animation_handoff(directory, tick_lib):
    anim_case = next(case for case in animation_suite.cases()
                     if case['name'] == 'one-shot-equal-limit')
    memory, regs, device = animation_suite.setup(anim_case)
    game_data_segment = regs['ds']
    regs['es'] = 0xA000
    fixtures._put_renderer_layout(memory, game_data_segment, source_segment=0x5000)
    _put16(memory, game_data_segment, fixtures.field('GraphicsResourceSegment'), 0x5000)
    fixtures._put_source_pixels(memory, 0x5000)
    definitions = fixtures.field('LevelObjectDefinitions')
    graphics = fixtures.field('LevelObjectGraphicsRecords')
    fixtures._write_be16(memory, game_data_segment, definitions, 0x0020)
    fixtures._write_be16(memory, game_data_segment, definitions + 2, 0x0010)
    fixtures._write_be16(memory, game_data_segment, definitions + 6, 0x0001)
    memory[((game_data_segment << 4) + graphics + 4) & MASK] = 16
    memory[((game_data_segment << 4) + graphics + 5) & MASK] = 2
    _put16(memory, game_data_segment, graphics + 8, 0x7000)

    initial_hashes = input_hashes()
    original_state = animation_suite.run_original(
        anim_case, bytearray(memory), dict(regs), copy.deepcopy(device), core=False)
    native_animation = animation_suite.Native(directory, mutation=0)
    native_state = native_animation.run(
        anim_case, memory, regs, device, core=False)
    animation_suite.verify_case_contract(anim_case, original_state, core=False)
    animation_suite.verify_independent_projection(anim_case, memory, original_state)
    drawing.common.require(native_state['memory'] == original_state['memory'],
        'native animation handoff: producer full RAM differs from original')
    for name in animation_suite.REG_NAMES:
        if name == 'flags':
            mask = original_state['flags_mask']
            drawing.common.require(
                not ((native_state['regs'][name] ^ original_state['regs'][name]) & mask),
                'native animation handoff: producer defined FLAGS differ')
        else:
            drawing.common.require(native_state['regs'][name] == original_state['regs'][name],
                f'native animation handoff: producer {name} differs')
    animation_suite.compare_events('native animation handoff',
        native_state['events'], original_state['events'])
    drawing.common.require(native_state['status'] == original_state['status'] and
                           native_state['continuation'] == original_state['continuation'],
        'native animation handoff: producer status/continuation differs')
    drawing.common.require(animation_suite.get16(native_state['memory'], game_data_segment,
        graphics + 0x17) == 0x0100,
        'native animation handoff: expected producer frame offset was not stored')

    handoff_row = _row(0, x=0x20, y=0x10, draw_flags=1,
                       width=16, height=2, source=0x0100, mask=0x7000)
    tick_case = _case('native-animation-to-drawing-handoff', (handoff_row,),
                      _seed=0xA61, independent=True)
    tick_memory = bytearray(native_state['memory'])
    tick_regs = dict(native_state['regs'])
    tick_regs['ip'] = ENTRY
    _put16(tick_memory, tick_regs['ss'], tick_regs['sp'], 0xEED1)
    prepared = dict(memory=tick_memory, regs=tick_regs,
                    game_data_segment=game_data_segment)
    row = compare(tick_lib, tick_case, core=False, prepared=prepared)
    row['producer'] = 'object_animation:one-shot-equal-limit/native-adapter'
    row['producer_status'] = native_state['status']
    row['producer_return'] = native_state['continuation']
    drawing.common.require(input_hashes() == initial_hashes,
        'native animation-to-drawing handoff inputs changed')
    del native_animation
    gc.collect()
    return row


def library(directory, mutation=0):
    path = Path(directory) / f'object-drawing-tick-{mutation}.dll'
    build(path, mutation, 'object_drawing_tick')
    lib = ctypes.CDLL(str(path))
    lib.lmn_draw_level_object_graphics_core.argtypes = [
        MEM, ctypes.POINTER(Call), ctypes.POINTER(drawing.common.RasterBus),
        ctypes.POINTER(drawing.Ports)]
    lib.lmn_draw_level_object_graphics_core.restype = Result
    lib.lmn_draw_level_object_graphics_adapter.argtypes = [
        MEM, ctypes.POINTER(Regs), ctypes.c_uint16,
        ctypes.POINTER(drawing.common.RasterBus), ctypes.POINTER(drawing.Ports)]
    lib.lmn_draw_level_object_graphics_adapter.restype = ctypes.c_uint16
    return lib


def _core_call(regs, flags, game_data_segment):
    return Call(regs['ax'], regs['bx'], regs['cx'], regs['dx'], regs['si'],
                regs['di'], regs['bp'], regs['cs'], regs['ds'], regs['es'],
                regs['ss'], regs['sp'], flags, game_data_segment)


def _result_regs(result):
    return dict(ax=result.value, bx=result.map_cursor, cx=result.count,
        dx=result.auxiliary_value, si=result.record_cursor, di=result.object_cursor,
        bp=result.candidate_y, cs=result.code_segment, ds=result.data_segment,
        es=result.extra_segment, ss=result.stack_segment, sp=result.stack_offset,
        ip=result.continuation, flags=result.flags)


def _ports_for(case, device):
    ports = drawing.byte_ports(device)
    if case.get('provider') == 'missing-in':
        return drawing.Ports(None, ports.out_byte, drawing.IN_BYTE())
    if case.get('provider') == 'missing-out':
        return drawing.Ports(None, drawing.OUT_BYTE(), ports.in_byte)
    return ports


def _status_from_boundary(boundary):
    kind = boundary[0]
    if kind in ('continuation', 'ready-return'):
        target = boundary[-1]
        if target == OUTER_RET:
            return READY
        if target == 0x969C:
            return MISSING_PROVIDER
        return CHILD_BOUNDARY
    if kind == 'changed-child-near':
        return CHANGED_CHILD_NEAR
    if kind == 'changed-child-far':
        return CHANGED_FAR_RETURN
    if kind == 'outer-return':
        return READY
    raise drawing.common.VerificationFailure(f'unclassified tick boundary {boundary!r}')


def compare(lib, case, *, core=False, prepared=None):
    if prepared is None:
        memory, regs, flags, game_data_segment = prepare(case)
    else:
        memory = bytearray(prepared['memory'])
        regs = dict(prepared['regs'])
        flags = regs.pop('flags', prepared.get('flags', 0x0002))
        game_data_segment = prepared['game_data_segment']
    c_device = _new_device(memory, case, regs)
    o_device = _new_device(memory, case, regs)
    c_device.vga.trace = original_caller.DeviceTrace()
    o_device.vga.trace = original_caller.DeviceTrace()
    ports = _ports_for(case, c_device)
    ports_pointer = None if case.get('provider') == 'no-ports' else ctypes.byref(ports)
    bus_pointer = None if case.get('null_bus') else ctypes.byref(c_device.bus)
    state = Regs(**regs, flags=flags)
    started = time.monotonic()

    if core:
        call = _core_call(regs, flags, game_data_segment)
        result = lib.lmn_draw_level_object_graphics_core(
            (ctypes.c_uint8 * SIZE).from_buffer(c_device.memory), ctypes.byref(call),
            bus_pointer, ports_pointer)
        state = Regs(**_result_regs(result))
        c_status = result.status
    else:
        c_status = lib.lmn_draw_level_object_graphics_adapter(
            (ctypes.c_uint8 * SIZE).from_buffer(c_device.memory), ctypes.byref(state),
            game_data_segment, bus_pointer, ports_pointer)

    child_index = 0
    pending_planes = None
    independent_count = 0
    expected_active = [row for row in case.get('objects', ()) if row[1] != 0]

    def observe(off, cpu, device):
        nonlocal child_index, pending_planes, independent_count
        if (case.get('provider') in ('saved-ds-provider', 'saved-cx-provider',
                                     'far-ip-provider') and
                INS[off].mnemonic.startswith('out')):
            _apply_stack_provider(device, case, regs, cpu)
        if off == BITMAP_ENTRY:
            if child_index < len(expected_active) and case.get('independent'):
                index, x, y, draw_flags, width, height, source, mask = expected_active[child_index]
                ds = cpu.reg_read(original_caller.oracle.REG['ds'])
                scroll = _read16(device.memory, ds, 0)
                expected = dict(ax=(x - scroll + 0x10) & 0xFFFF,
                    bx=y, bp=draw_flags & 0xFFFE, dx=width,
                    cx=0x0400 | height, si=source, di=(source + mask) & 0xFFFF)
                for name, value in expected.items():
                    drawing.common.require(
                        cpu.reg_read(original_caller.oracle.REG[name]) == value,
                        f'{case["name"]}: independent child input {name} for slot {index}')
            child_index += 1
        if off in drawing.FAMILIES and case.get('independent'):
            family = drawing.FAMILIES[off]
            entry = {name: cpu.reg_read(reg)
                     for name, reg in original_caller.oracle.REG.items()}
            entry['flags'] = cpu.reg_read(drawing.x.UC_X86_REG_EFLAGS)
            drawing.bitmap.configure(family)
            pending_planes = drawing.render._independent_planes(
                device.vga.planes, device.memory, entry, game_data_segment)
        elif INS[off].mnemonic == 'retf' and pending_planes is not None:
            drawing.common.require(pending_planes == device.vga.planes,
                f'{case["name"]}: independent renderer plane footprint')
            pending_planes = None
            independent_count += 1

    continuation = set()
    if core:
        continuation.add(OUTER_RET)
    if case.get('provider') in ('missing-in', 'missing-out'):
        continuation.add(MISSING_PROVIDER_RETURN)
    original_state, flag_mask, sites, edges, boundary, child_entry, body = \
        original_caller.original(case, o_device, regs, flags,
            instructions=INS, far_calls={BITMAP_CALL}, continuations=continuation,
            observe=observe, max_steps=MAX_ORIGINAL_INSTRUCTIONS)

    for name in REG_NAMES:
        drawing.common.require(getattr(state, name) == original_state[name],
            f'{case["name"]}: {name} C={getattr(state,name):04X}/'
            f'ASM={original_state[name]:04X}; boundary={boundary}')
    drawing.common.require(not ((state.flags ^ original_state['flags']) & flag_mask),
        f'{case["name"]}: defined FLAGS differ at {boundary}')
    drawing.common.require(c_device.memory == o_device.memory,
        f'{case["name"]}: whole RAM differs')
    drawing.common.compare_event_traces(c_device.events, o_device.events, case['name'])
    drawing.common.require(c_device.vga.state() == o_device.vga.state(),
        f'{case["name"]}: VGA state differs')
    drawing.common.require(c_device.vga.trace.signature() == o_device.vga.trace.signature(),
        f'{case["name"]}: VGA event order differs')
    if case.get('provider') in ('saved-ds-provider', 'saved-cx-provider',
                                'far-ip-provider'):
        drawing.common.require(case['provider'] in c_device._tick_provider_fired and
                               case['provider'] in o_device._tick_provider_fired,
            f'{case["name"]}: saved-stack provider did not fire in both runs')
    if case.get('provider') == 'saved-ds-provider':
        drawing.common.require(original_state['ds'] == case['provider_value'],
            f'{case["name"]}: original did not restore provider-updated DS')
    if case.get('provider') == 'saved-cx-provider':
        expected_si = (fixtures.field('LevelObjectGraphicsRecords') + 3 * 28) & 0xFFFF
        expected_di = (fixtures.field('LevelObjectDefinitions') + 3 * 8) & 0xFFFF
        drawing.common.require(original_state['cx'] == 0 and
                               original_state['si'] == expected_si and
                               original_state['di'] == expected_di,
            f'{case["name"]}: provider-updated CX/SI/DI were not consumed live')
    if case.get('provider') == 'far-ip-provider':
        drawing.common.require(boundary[0] == 'changed-child-far' and
                               boundary[1] == regs['cs'] and boundary[2] == 0x4567,
            f'{case["name"]}: original did not stop at the changed live FAR RET')

    expected_status = _status_from_boundary(boundary)
    if 'expected_status' in case:
        drawing.common.require(expected_status == case['expected_status'],
            f'{case["name"]}: fixture did not reach requested status {case["expected_status"]}; '
            f'got {boundary}')
    if core:
        drawing.common.require(c_status == expected_status,
            f'{case["name"]}: core status {c_status} != expected {expected_status}')
        drawing.common.require(result.game_data_segment == game_data_segment,
            f'{case["name"]}: game-data segment changed')
    else:
        drawing.common.require(c_status == expected_status,
            f'{case["name"]}: adapter status {c_status} != expected {expected_status}')
    if expected_status == READY:
        expected_ip = OUTER_RET if core else original_state['ip']
        drawing.common.require(state.ip == expected_ip,
            f'{case["name"]}: wrong ready continuation {state.ip:04X}')

    return dict(name=case['name'], core=core, boundary=boundary,
        child_calls=child_index, independent_plane_checks=independent_count,
        bus_events=c_device.events.count,
        executed_instruction_addresses=sorted(sites),
        branch_edges=sorted(edge for edge in edges if edge[0] in LOCAL),
        integrated_branch_edges=sorted(edges),
        providers=sorted(c_device._tick_provider_fired),
        seconds=round(time.monotonic() - started, 3))


def input_hashes():
    c_sources = ('object_drawing_tick', 'object_drawing', 'drawing_render', 'drawing_plan',
        'drawing_inputs', 'drawing_clip', 'drawing_dirty', 'drawing_dispatch', 'drawing_source',
        'aligned_opaque', 'aligned_masked', 'aligned_mask_effects', 'aligned_protected',
        'aligned_read_mask', 'shifted_mask_effects', 'shifted_opaque', 'shifted_masked',
        'shifted_protected', 'shifted_read_mask')
    paths = {f'c/{name}{ext}' for name in c_sources for ext in ('.c', '.h')}
    paths |= {'src/object_graphics_tick.asm',
        'src/program.asm', 'c/regs.h', 'c/lemmings_sym.h', 'c/special_blit.h',
        'c/object_animation.c', 'c/object_animation.h',
        'metadata/symbols.json', 'metadata/inputs.json', 'metadata/oracle.json',
        'metadata/toolchain-lock.json', 'assets/vgalemmi.exe', 'tools/cbuild.py',
        'tools/difftest.py', 'tools/bounded_process.py', 'tools/coverage.py',
        'tools/unpack.py', 'tools/common.py', 'tests/object_drawing_tick.py',
        'tests/object_drawing.py', 'tests/object_drawing_cases.py',
        'tests/drawing_caller_oracle.py', 'tests/terrain_drawing.py',
        'tests/drawing_render.py', 'tests/drawing_bitmap.py', 'tests/drawing_plan.py',
        'tests/drawing_inputs.py', 'tests/aligned_masked.py', 'tests/aligned_opaque.py',
        'tests/aligned_read_mask.py', 'tests/aligned_protected.py',
        'tests/aligned_mask_effects.py', 'tests/shifted_mask_effects.py',
        'tests/shifted_opaque.py', 'tests/shifted_masked.py',
        'tests/shifted_protected.py', 'tests/minimap_vga.py', 'tests/special_blit.py',
        'tests/dat_io.py', 'tests/dat_io_c.py', 'tests/object_animation.py'}
    paths |= set(animation_suite.input_hashes())
    return {path: sha((ROOT / path).read_bytes()) for path in sorted(paths)}


def worker(directory, selection=()):
    start_hashes = input_hashes()
    baseline = cases()
    if selection:
        baseline = [case for case in baseline if case['name'] in selection]
        if len(baseline) != len(selection):
            raise RuntimeError('Unknown selected object-drawing tick case')
    lib = library(directory)
    results = []
    sites, edges, integrated_sites = set(), set(), set()
    for index, case in enumerate(baseline):
        row = compare(lib, case, core=True)
        results.append(row)
        sites.update(row['executed_instruction_addresses'])
        edges.update(map(tuple, row['branch_edges']))
        integrated_sites.update(row['executed_instruction_addresses'])
        if index in (0, 2, 9, 35, len(baseline) - 1) and not case.get('provider'):
            adapter_row = compare(lib, case, core=False)
            adapter_row['name'] += '-adapter'
            results.append(adapter_row)
            sites.update(adapter_row['executed_instruction_addresses'])
            edges.update(map(tuple, adapter_row['branch_edges']))
            integrated_sites.update(adapter_row['executed_instruction_addresses'])
        print(f'PASS {row["name"]}: {row["child_calls"]} child calls, '
              f'{row["bus_events"]} events, {row["seconds"]}s', flush=True)
        gc.collect()
    if selection:
        return
    handoff_row = animation_handoff(directory, lib)
    results.append(handoff_row)
    sites.update(handoff_row['executed_instruction_addresses'])
    edges.update(map(tuple, handoff_row['branch_edges']))
    integrated_sites.update(handoff_row['executed_instruction_addresses'])
    drawing.common.require(set(LOCAL) <= sites,
        f'missing caller instruction sites {sorted(set(LOCAL) - sites)}')
    drawing.common.require(LOCAL_EDGES <= edges,
        f'missing caller branch outcomes {sorted(LOCAL_EDGES - edges)}')
    mutations = []
    by_name = {case['name']: case for case in baseline}
    for mutation, witness in ((1, 'scroll-positive-origin'),
                              (2, 'definition-bit-zero-is-cleared'),
                              (3, 'provider-live-child-ds'),
                              (4, 'provider-live-saved-cx'),
                              (5, 'provider-changed-child-far-return'),
                              (6, 'missing-read-mask-provider-seam')):
        try:
            compare(library(directory, mutation), by_name[witness], core=True)
        except drawing.common.Mismatch as error:
            mutations.append(dict(mutation=mutation, case=witness,
                                  reason=str(error), completed=True))
        else:
            raise drawing.common.VerificationFailure(
                f'object-drawing-tick mutation {mutation} survived')
        gc.collect()
    if input_hashes() != start_hashes:
        raise drawing.common.VerificationFailure('object-drawing tick inputs changed during run')
    write_json(REPORT, dict(image='main', image_sha256=sha(IMAGE),
        code_ranges=[[ENTRY, END]], translated_code_bytes=END - ENTRY,
        caller_instruction_addresses=sorted(LOCAL),
        static_instruction_addresses=sorted(LOCAL),
        static_branch_edges=sorted(LOCAL_EDGES), caller_branch_edge_count=len(LOCAL_EDGES),
        case_count=len(baseline) + 1, comparison_count=len(results), cases=results,
        mutation_count=len(mutations), mutations_detected=mutations,
        executed_instruction_addresses=sorted(sites), integrated_instruction_addresses=sorted(integrated_sites),
        branch_edges=sorted(edges), input_hashes=start_hashes,
        limits=dict(worker_timeout_seconds=WORKER_SECONDS,
            windows_process_commit_mib=PROCESS_MIB, windows_tree_commit_mib=768,
            bus_events=MAX_BUS_EVENTS,
            vga_events=MAX_VGA_EVENTS, original_instructions=MAX_ORIGINAL_INSTRUCTIONS),
        domain='7BB8..7C09 DrawLevelObjectGraphics caller composed with typed native 8822 core; '
            'all 32 record positions, active/inactive LOOP paths, live DS scroll and resource '
            'segment, caller save/child far-return/provider seams, DF/IF, full RAM/registers/'
            'defined FLAGS/ordered bus/VGA, independent child inputs and planar output. '
            'The 8822 body is already translated and is not counted as new caller bytes.'))
    print(f'PASS object drawing tick: {len(baseline) + 1} cases, {len(LOCAL)} caller sites, '
          f'{len(edges)} caller edges, {len(mutations)} completed mutants', flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['--original-only']:
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--original-worker'], cwd=ROOT, timeout=WORKER_SECONDS,
                    memory_mib=PROCESS_MIB, check=True)
    elif sys.argv[1:] == ['--original-worker']:
        original_only()
    if len(sys.argv) >= 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2], sys.argv[3:])
    elif len(sys.argv) == 1 or sys.argv[1] == '--selected':
        BUILD.mkdir(exist_ok=True)
        if len(sys.argv) == 1:
            REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='object-drawing-tick-', parent=BUILD) as directory:
            run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                         directory, *sys.argv[2:]], cwd=ROOT, timeout=WORKER_SECONDS,
                        memory_mib=PROCESS_MIB, check=True)
    elif sys.argv[1:] not in (['--original-only'], ['--original-worker']):
        raise SystemExit('usage: object_drawing_tick.py [--selected CASE ... | --worker DLL_DIRECTORY]')

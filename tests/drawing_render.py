"""Connected original 8822 entry and aligned opaque VGA renderer at 983B."""
import ctypes
import random
import os
import gc
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import capstone
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INSN,
                     UC_HOOK_INTR)
from unicorn import x86_const as x

from common import ROOT, BUILD, read_json, write_json, sha
from cbuild import build
from bounded_process import run_bounded, temporary_build_directory
from dat_io_c import Regs, MEM
from minimap_vga import MinimapVga, fixture_vectors
from special_blit import Bus, READ, WRITE, OUT
from unpack import ASSET, unpack, relocated
import dat_io as oracle
import drawing_plan as plan

LIBRARY_DIRECTORY = BUILD
NATIVE_EVENT_LIMIT = 1000000
BYTE_PORT_FIXTURE = None


IMAGE, ORACLE = unpack(ASSET.read_bytes())
SYMS = {s['symbol_name']: s for s in read_json(ROOT / 'metadata/symbols.json')}
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
START = plan.START
PROLOGUE = plan.PROLOGUE
PREP_INS = plan.INS
PREP_BRANCHES = plan.BRANCHES
PREP_EDGES = plan.EDGES
PREP_EXITS = set(plan.EXITS) - {0x983b}
BODY_START = 0x983b
BODY_RETF = 0x9966
BODY_SPANS = ((0x983b, 0x98f4), (0x98f5, 0x9932), (0x9933, 0x9967))
BODY_INS = {}
for span_start, span_end in BODY_SPANS:
    BODY_INS.update({i.address: i for i in MD.disasm(
        IMAGE[span_start:span_end], span_start)})
BODY_BRANCHES = {pc for pc, ins in BODY_INS.items()
                 if ins.group(capstone.CS_GRP_JUMP) or ins.mnemonic.startswith('loop')}
BODY_EDGES = {(pc, ins.operands[0].imm & 0xffff)
              for pc, ins in BODY_INS.items() if pc in BODY_BRANCHES}
BODY_EDGES |= {(pc, pc + ins.size) for pc, ins in BODY_INS.items()
               if pc in BODY_BRANCHES and ins.mnemonic != 'jmp'}
INS = dict(PREP_INS)
INS.update(BODY_INS)
BRANCHES = PREP_BRANCHES | BODY_BRANCHES
LOGICAL = {'and', 'or', 'xor', 'test', 'shr', 'shl'}
ARITH = {'add', 'sub', 'cmp', 'neg', 'inc', 'dec', 'mul'}
FLAG_MASK = 0xfc7  # Defined arithmetic flags, IF and DF; AF may be undefined.
FULL_ARITH_MASK = 0xfd7
VGA_BASE = 0xa0000


def field(name):
    return SYMS[name]['address']


def cases():
    """Reuse the 744 preparation/boundary cases and add complete body classes."""
    out = []
    for original in plan.cases():
        case = original.copy()
        if case['name'] == 'stack-ffff':
            continue
        if _body_case(case) and _unbounded_body_case(case):
            continue
        out.append(case)
    for plane_limit in (0, 1, 2, 3, 4, 5, 0xff):
        for width_index, width in enumerate((8, 16, 24)):
            for df in (0, 1):
                residue = (plane_limit + width_index) & 1
                left = 17 if residue else 16
                control = 0 if left & 7 else 1
                if (plane_limit + width_index + df) & 1:
                    control |= 0x80
                rows = 1 + ((plane_limit + width_index + df) % 3)
                out.append(dict(
                    name=f'planes-{plane_limit:02x}-width-{width}-df-{df}-rev-{int(bool(control & 0x80))}',
                    seed=len(out), control=control, left=left, top=1,
                    width=width, height=(plane_limit << 8) | rows,
                    dirty=0, df=df, independent=True))
    # Cover the original right-edge shrink loop, leaving one drawable byte.
    out.append(dict(name='aligned-opaque-right-edge-clipped-row',
        seed=len(out), control=4, left=1652, top=1, width=24,
        height=0x0101, dirty=0, df=0, independent=True))
    # CL=0 makes the original LOOP execute 65,536 copies. Keep CH nonzero.
    out.append(dict(name='aligned-opaque-zero-byte-count-loop-65536',
        seed=len(out), control=0, left=16, top=1, width=0,
        height=0x0101, dirty=0, df=0, independent=True))
    # DS:6702 aliases the saved BP word at SS:6702 before POP BP at 983A.
    out.append(dict(name='aligned-opaque-live-ds-ss-saved-bp-alias',
        seed=len(out), same_segments=True, sp=0x6704, control=0x80,
        left=16, top=2, width=16, height=0x0202, dirty=0,
        df=1))
    return out


def _body_case(case):
    if case.get('return_ip') not in (None, BODY_START):
        return False
    control = case.get('post_control', case.get('control', 0))
    left = case.get('left', 16)
    return not (control & 2) and not ((control & 1) and (left & 7))


def _unbounded_body_case(case):
    """Keep inherited edge cases with huge byte loops outside this connection."""
    width = case.get('width', 24)
    left = case.get('left', 16)
    control = case.get('control', 0)
    if control & 4 and 0 <= left < 1664 and left + width > 1664:
        width = 1664 - left
    byte_count = (width >> 3) & 0xff
    height = case.get('height', 0x4508)
    row_count = height & 0xff
    rows = row_count if row_count else 256
    plane_limit = (height >> 8) & 0xff
    passes = plane_limit if 1 <= plane_limit <= 4 else 4
    if byte_count == 0:
        return case['name'] != 'aligned-opaque-zero-byte-count-loop-65536'
    return byte_count * rows * passes > 4096


def prepare(case):
    memory, regs, flags = plan.prepare(case)
    game_ds = (regs['cs'] + 0x09a9) & 0xffff
    oracle.put16(memory, regs['ds'], field('DrawingPitchBytes'), 208)
    oracle.put16(memory, regs['ds'], field('DrawingOrigin'), 0x1000)
    oracle.put16(memory, regs['ds'], field('DrawingPageByteOffset'), 0x0200)
    resource_segment = 0x5000
    oracle.put16(memory, regs['ds'], field('GraphicsResourceSegment'), resource_segment)
    if case.get('df'):
        flags |= 0x0400
    else:
        flags &= ~0x0400
    return memory, regs, flags, game_ds


def library(mutation=0):
    lib = ctypes.CDLL(str(build(LIBRARY_DIRECTORY / f'drawing-render-connection-m{mutation}.dll',
                                mutation, 'drawing_render')))
    lib.lmn_draw_prepared_aligned_opaque_adapter.argtypes = [
        MEM, ctypes.POINTER(Regs), ctypes.c_uint16, ctypes.POINTER(Bus)]
    lib.lmn_draw_prepared_aligned_opaque_adapter.restype = None
    return lib


def _put_regs(u, regs, flags):
    for name, reg in oracle.REG.items():
        u.reg_write(reg, regs[name])
    u.reg_write(x.UC_X86_REG_EFLAGS, flags)


def _get_regs(u):
    return {name: u.reg_read(reg) for name, reg in oracle.REG.items()}


def _event_equal(left, right, mask):
    return left[:3] == right[:3] and ((left[3] ^ right[3]) & mask) == 0


def _vga_trace_equal(left, right):
    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        if a[:3] != b[:3] or ((a[3] ^ b[3]) & FLAG_MASK):
            return False
    return True


def _defined_mask(mnemonic, prior):
    if mnemonic in LOGICAL:
        return FLAG_MASK
    if mnemonic == 'mul':
        return 0xf03
    if mnemonic in ARITH:
        return FULL_ARITH_MASK
    return prior


def _independent_planes(initial_planes, source_memory, body_entry,
                        data_segment):
    """Model the four VGA plane footprints from the documented body contract."""
    expected = [bytearray(plane) for plane in initial_planes]
    source_segment = oracle.get16(source_memory, data_segment,
                                  field('GraphicsResourceSegment'))
    extent = oracle.get16(source_memory, data_segment,
                          field('DrawingSourcePlaneExtent'))
    source_row = oracle.get16(source_memory, data_segment,
                              field('DrawingSourceRowAdvance'))
    destination_row = oracle.get16(source_memory, data_segment,
                                   field('DrawingActiveDestinationRowAdvance'))
    plane_limit = (body_entry['dx'] >> 8) & 0xff
    passes = plane_limit if 1 <= plane_limit <= 4 else 4
    initial_source = body_entry['si']
    initial_destination = body_entry['di']
    count = body_entry['cx'] & 0xff
    row_count = (body_entry['cx'] >> 8) & 0xff
    rows = row_count if row_count else 256
    step = -1 if body_entry['flags'] & 0x0400 else 1
    byte_count = count if count else 65536
    for pass_index in range(passes):
        source = (initial_source + pass_index * extent) & 0xffff
        destination = initial_destination
        for _ in range(rows):
            for _ in range(byte_count):
                physical = (((source_segment << 4) + source) & 0xfffff)
                value = source_memory[physical]
                offset = destination & 0xffff
                if pass_index == 0:
                    expected[0][offset] = value
                    expected[1][offset] = 0
                    expected[2][offset] = 0
                    expected[3][offset] = 0
                else:
                    expected[pass_index][offset] = value
                source = (source + step) & 0xffff
                destination = (destination + step) & 0xffff
            source = (source + source_row) & 0xffff
            destination = (destination + destination_row) & 0xffff
    return expected


def _wrap_hooks(u):
    def read_wrap(uc, access, address, size, value, _):
        for i in range(size):
            p = address + i
            if p >= 1 << 20:
                uc.mem_write(p, bytes(uc.mem_read(p & 0xfffff, 1)))

    def write_wrap(uc, access, address, size, value, _):
        for i in range(size):
            p = address + i
            if p >= 1 << 20:
                uc.mem_write(p & 0xfffff, bytes(((value >> (8 * i)) & 0xff,)))

    return (u.hook_add(UC_HOOK_MEM_READ, read_wrap),
            u.hook_add(UC_HOOK_MEM_WRITE, write_wrap))


def compare(lib, case):
    memory, regs, flags, game_ds = prepare(case)
    u = Uc(UC_ARCH_X86, UC_MODE_16)
    u.mem_map(0, 2 << 20)
    u.mem_write(0, bytes(memory) * 2)
    _put_regs(u, regs, flags)
    prologue = set()
    at_span = False

    def prologue_code(uc, pc, size, _):
        nonlocal at_span
        off = pc - (regs['cs'] << 4)
        if off == START:
            at_span = True
            uc.emu_stop()
            return
        if off not in PROLOGUE:
            raise RuntimeError(f'{case["name"]}: original 8822 prologue escaped at {off:04x}')
        prologue.add(off)

    prologue_hook = u.hook_add(UC_HOOK_CODE, prologue_code)
    wrap_read_hook, wrap_write_hook = _wrap_hooks(u)
    u.emu_start((regs['cs'] << 4) + 0x8822, 0, count=20)
    if not at_span or prologue != set(PROLOGUE):
        raise RuntimeError(f'{case["name"]}: original prologue did not reach 882D')
    u.hook_del(prologue_hook)

    span_regs = _get_regs(u)
    span_flags = u.reg_read(x.UC_X86_REG_EFLAGS)
    u_memory = bytearray(u.mem_read(0, 1 << 20))
    c_memory = bytearray(u_memory)
    c_regs = Regs(**span_regs, flags=span_flags)
    c_events = []
    u_events = []
    u_event_masks = []
    c_vga = MinimapVga(case['seed'] + 0x983b)
    u_vga = MinimapVga(case['seed'] + 0x983b)
    initial_planes = [bytearray(p) for p in c_vga.planes]

    @READ
    def c_read(ctx, mem, p, event_flags):
        if len(c_events) >= NATIVE_EVENT_LIMIT:
            os.write(2, b'drawing_render: native access budget exceeded\n')
            os._exit(86)
        try:
            value = c_vga.read(c_memory, p & 0xfffff, event_flags)
        except Exception as error:
            os.write(2, (f'drawing_render: native read fixture failed: {error}\n').encode())
            os._exit(87)
        c_events.append(('read', p & 0xfffff, value, event_flags))
        return value

    @WRITE
    def c_write(ctx, mem, p, value, event_flags):
        if len(c_events) >= NATIVE_EVENT_LIMIT:
            os.write(2, b'drawing_render: native access budget exceeded\n')
            os._exit(86)
        try:
            c_vga.write(c_memory, p & 0xfffff, value, event_flags)
        except Exception as error:
            os.write(2, (f'drawing_render: native write fixture failed: {error}\n').encode())
            os._exit(87)
        c_events.append(('write', p & 0xfffff, value, event_flags))

    @OUT
    def c_output(ctx, port, value, event_flags):
        try:
            c_vga.out(port, value, event_flags)
        except Exception as error:
            os.write(2, (f'drawing_render: native port fixture failed: {error}\n').encode())
            os._exit(87)

    bus = Bus(None, c_read, c_write, c_output)
    bus.verification = dict(memory=c_memory, vga=c_vga, events=c_events, case=case,
                            span_registers=span_regs)
    lib.lmn_draw_prepared_aligned_opaque_adapter(
        (ctypes.c_uint8 * (1 << 20)).from_buffer(c_memory),
        ctypes.byref(c_regs), game_ds, ctypes.byref(bus))

    last_op = None
    flag_mask = FLAG_MASK
    instruction_flags = span_flags
    seen = set()
    edges = set()
    previous = None
    previous_op = None
    boundary = None
    body_entry = None
    body_memory = None
    steps = 0
    retf_flags = None

    def code(uc, pc, size, _):
        nonlocal last_op, flag_mask, instruction_flags, previous
        nonlocal previous_op, boundary, body_entry, body_memory, steps, retf_flags
        if last_op is not None:
            flag_mask = _defined_mask(last_op, flag_mask)
        off = (pc - (regs['cs'] << 4)) & 0xffff
        if previous in BRANCHES:
            edges.add((previous, off))
        if off in PREP_EXITS:
            boundary = ('continuation', off)
            uc.emu_stop()
            return
        if off == BODY_START and body_entry is None:
            body_entry = _get_regs(uc)
            body_entry['flags'] = uc.reg_read(x.UC_X86_REG_EFLAGS)
            body_memory = bytes(u_memory)
        if off == BODY_RETF:
            seen.add(off)
            previous = off
            last_op = 'retf'
            retf_flags = uc.reg_read(x.UC_X86_REG_EFLAGS)
            boundary = ('body-retf', off)
            uc.emu_stop()
            return
        if off not in INS:
            if previous_op in ('ret', 'retf'):
                boundary = ('changed-child-return', off)
                uc.emu_stop()
                return
            raise RuntimeError(f'{case["name"]}: original drawing flow reached unresolved {off:04x}')
        if uc.reg_read(oracle.REG['cs']) != regs['cs']:
            raise RuntimeError(f'{case["name"]}: original drawing flow changed CS before its boundary')
        steps += 1
        if steps > 900000:
            raise RuntimeError(f'{case["name"]}: original drawing instruction budget exceeded')
        seen.add(off)
        previous = off
        instruction_flags = uc.reg_read(x.UC_X86_REG_EFLAGS)
        last_op = INS[off].mnemonic
        previous_op = last_op

    hook = u.hook_add(UC_HOOK_CODE, code)

    def u_read(uc, access, address, size, value, _):
        for i in range(size):
            p = (address + i) & 0xfffff
            byte = u_vga.read(u_memory, p, instruction_flags)
            u_events.append(('read', p, byte, instruction_flags))
            u_event_masks.append(flag_mask)
            if address + i >= 1 << 20 or VGA_BASE <= p < VGA_BASE + 0x10000:
                uc.mem_write(address + i, bytes((byte,)))

    def u_write(uc, access, address, size, value, _):
        for i in range(size):
            p = (address + i) & 0xfffff
            byte = (value >> (8 * i)) & 0xff
            u_vga.write(u_memory, p, byte, instruction_flags)
            u_events.append(('write', p, byte, instruction_flags))
            u_event_masks.append(flag_mask)
            if address + i >= 1 << 20:
                uc.mem_write(p, bytes((byte,)))

    def u_output(uc, port, size, value, _):
        if size == 1 and BYTE_PORT_FIXTURE is not None:
            BYTE_PORT_FIXTURE.out_byte(u_vga, port, value, instruction_flags)
            u_events.append(('outb', port, value, instruction_flags))
            u_event_masks.append(flag_mask)
        elif size == 2:
            u_vga.out(port, value, uc.reg_read(x.UC_X86_REG_EFLAGS))
        else:
            raise RuntimeError(f'{case["name"]}: non-word VGA output')

    def u_input(uc, port, size, _):
        if size != 1 or BYTE_PORT_FIXTURE is None:
            raise RuntimeError(f'{case["name"]}: unsupported port input')
        value = BYTE_PORT_FIXTURE.in_byte(u_vga, port, instruction_flags, case)
        u_events.append(('inb', port, value, instruction_flags))
        u_event_masks.append(flag_mask)
        return value

    def intr(uc, num, _):
        raise RuntimeError(f'{case["name"]}: unexpected INT{num:02x}')

    read_hook = u.hook_add(UC_HOOK_MEM_READ, u_read)
    u.hook_add(UC_HOOK_MEM_WRITE, u_write)
    u.hook_add(UC_HOOK_INSN, u_output, None, 1, 0, x.UC_X86_INS_OUT)
    u.hook_add(UC_HOOK_INSN, u_input, None, 1, 0, x.UC_X86_INS_IN)
    u.hook_add(UC_HOOK_INTR, intr)
    u.emu_start((regs['cs'] << 4) + START, 0, count=900000)
    if boundary is None:
        live = _get_regs(u)
        raise RuntimeError(f'{case["name"]}: no bounded renderer exit after {steps} sites at '
            f'{live["cs"]:04x}:{live["ip"]:04x}, previous={previous!r}')

    if boundary[0] == 'body-retf':
        # The pinned Unicorn RETF/read-hook artifact is handled exactly as in
        # level_drawing.py: record the real stack bytes, remove only the read
        # hook, and execute the original RETF opcode once without patching it.
        ss = u.reg_read(oracle.REG['ss'])
        sp = u.reg_read(oracle.REG['sp'])
        for delta in range(4):
            address = (ss << 4) + ((sp + delta) & 0xffff)
            p = address & 0xfffff
            byte = u_vga.read(u_memory, p, retf_flags)
            u_events.append(('read', p, byte, retf_flags))
            u_event_masks.append(flag_mask)
            u.mem_write(address, bytes((byte,)))
        u.hook_del(hook)
        u.hook_del(read_hook)
        u.hook_del(wrap_read_hook)
        u.hook_del(wrap_write_hook)
        u.ctl_remove_cache(0, 2 << 20)
        u.emu_start((regs['cs'] << 4) + BODY_RETF, 0, count=1)
        boundary = ('body-returned', BODY_RETF)
    elif boundary[0] == 'continuation' or boundary[0] == 'changed-child-return':
        pass

    u_regs = _get_regs(u)
    u_flags = u.reg_read(x.UC_X86_REG_EFLAGS)
    if boundary[0] == 'body-returned' and (u_regs['ip'] != oracle.get16(u_memory, regs['ss'], regs['sp']) or u_regs['cs'] != oracle.get16(u_memory, regs['ss'], (regs['sp'] + 2) & 0xffff)):
        raise AssertionError(f'{case["name"]}: original far return did not consume the live frame: '
            f'actual={u_regs["cs"]:04x}:{u_regs["ip"]:04x} sp={u_regs["sp"]:04x}, '
            f'frame={oracle.get16(u_memory, regs["ss"], regs["sp"]):04x}:'
            f'{oracle.get16(u_memory, regs["ss"], (regs["sp"] + 2) & 0xffff):04x}')

    for name in oracle.REG_NAMES:
        if getattr(c_regs, name) != u_regs[name]:
            raise AssertionError(f'{case["name"]}: {name} C={getattr(c_regs, name):04x}/ASM={u_regs[name]:04x}; boundary={boundary}')
    if (c_regs.flags ^ u_flags) & flag_mask:
        raise AssertionError(f'{case["name"]}: defined flags differ C={c_regs.flags:04x}/ASM={u_flags:04x}, mask={flag_mask:04x}')

    actual = bytes(u.mem_read(0, 1 << 20))
    if actual != c_memory:
        p = next(i for i, (a, b) in enumerate(zip(actual, c_memory)) if a != b)
        raise AssertionError(f'{case["name"]}: whole RAM differs at {p:05x}')
    if len(c_events) != len(u_events):
        raise AssertionError(f'{case["name"]}: ordered byte event count differs {len(c_events)}/{len(u_events)}')
    for index, (a, b) in enumerate(zip(c_events, u_events)):
        if not _event_equal(a, b, u_event_masks[index]):
            raise AssertionError(f'{case["name"]}: ordered byte event {index} differs {a}/{b}')
    if c_vga.state() != u_vga.state():
        raise AssertionError(f'{case["name"]}: VGA planes/latches/registers differ')
    if not _vga_trace_equal(c_vga.trace, u_vga.trace):
        raise AssertionError(f'{case["name"]}: ordered VGA/port trace differs')

    if body_entry is not None and (case.get('independent') or case['name'].startswith('matrix-')):
        expected = _independent_planes(initial_planes, body_memory, body_entry,
                                        game_ds)
        if expected != u_vga.planes:
            plane = next(i for i in range(4) if expected[i] != u_vga.planes[i])
            offset = next(i for i, (a, b) in enumerate(zip(expected[plane], u_vga.planes[plane])) if a != b)
            raise AssertionError(f'{case["name"]}: independent whole-plane footprint differs at plane {plane}, byte {offset:04x}')

    if body_entry is None and boundary[0] == 'body-returned':
        raise AssertionError(f'{case["name"]}: far return without entering 983B')
    intact_image = relocated(IMAGE, ORACLE['relocations'], regs['cs'])
    for start, end in ((0x8822, 0x88aa), (0x88ac, 0x890e),
                       (0x9140, 0x916b), (0x939e, 0x9810),
                       (0x9810, 0x9967), (0x9967, 0x9a8f)):
        p = (regs['cs'] << 4) + start
        if actual[p:p + end - start] != intact_image[start:end]:
            raise AssertionError(f'{case["name"]}: executing drawing bytes changed at {start:04x}')
    return seen, edges, prologue, boundary, body_entry is not None


def retf_hook_observation():
    """Reuse the isolated, original-opcode RETF/read-hook observation."""
    from level_drawing import retf_hook_observation as observe
    return observe()


def main():
    report = BUILD / 'drawing-render-differential.json'
    report.unlink(missing_ok=True)
    fixture_vectors()
    hook_observation = retf_hook_observation()
    baseline = cases()
    lib = library()
    seen, edges, prologue = set(), set(), set()
    boundaries = {}
    body_cases = 0
    for case in baseline:
        case_seen, case_edges, case_prologue, boundary, ran_body = compare(lib, case)
        seen |= case_seen
        edges |= case_edges
        prologue |= case_prologue
        boundaries[boundary[0]] = boundaries.get(boundary[0], 0) + 1
        body_cases += int(ran_body)
        gc.collect()

    expected_sites = set(PREP_INS) | set(BODY_INS)
    expected_edges = (PREP_EDGES - {(0x88a6, 0x88ab)}) | BODY_EDGES
    if seen != expected_sites:
        raise AssertionError(f'Missing integrated instruction sites {expected_sites-seen}/{seen-expected_sites}')
    if edges != expected_edges:
        raise AssertionError(f'Missing integrated branch edges {expected_edges-edges}/{edges-expected_edges}')
    if prologue != set(PROLOGUE):
        raise AssertionError('Original-only 8822 prologue site coverage differs')

    mutations = []
    mutant_cases = (
        (1, 'planes-01-width-16-df-1-rev-1'),
        (2, 'planes-04-width-24-df-1-rev-1'),
        (3, 'planes-01-width-16-df-0-rev-0'),
    )
    by_name = {case['name']: case for case in baseline}
    for mutation, name in mutant_cases:
        try:
            compare(library(mutation), by_name[name])
        except AssertionError:
            mutations.append(dict(mutation=mutation, case=name))
        else:
            raise AssertionError(f'Drawing-render mutation {mutation} survived')

    paths = tuple('c/' + name for name in (
        'drawing_render.c', 'drawing_render.h', 'aligned_opaque.c',
        'aligned_opaque.h', 'aligned_masked.c', 'aligned_masked.h',
        'aligned_protected.c', 'aligned_protected.h',
        'aligned_mask_effects.c', 'aligned_mask_effects.h',
        'aligned_read_mask.c', 'aligned_read_mask.h',
        'drawing_plan.c', 'drawing_plan.h',
        'drawing_inputs.c', 'drawing_inputs.h', 'drawing_clip.c',
        'drawing_clip.h', 'drawing_dirty.c', 'drawing_dirty.h',
        'drawing_dispatch.c', 'drawing_dispatch.h', 'drawing_source.c',
        'drawing_source.h', 'special_blit.h', 'regs.h', 'lemmings_sym.h'))
    paths += ('tests/drawing_render.py', 'tests/drawing_plan.py',
        'tests/drawing_inputs.py', 'tests/special_blit.py',
        'tests/minimap_vga.py', 'tests/level_drawing.py',
        'tests/dat_io.py', 'tests/dat_io_c.py', 'tools/cbuild.py',
        'tools/difftest.py', 'tools/coverage.py', 'tools/unpack.py',
        'metadata/symbols.json', 'tools/bounded_process.py')
    write_json(report, dict(image='main', image_sha256=sha(IMAGE),
        case_count=len(baseline), body_case_count=body_cases,
        mutation_count=3, cases=baseline, mutations_detected=mutations,
        executed_instruction_addresses=sorted(seen),
        preparation_instruction_addresses=sorted(PREP_INS),
        body_instruction_addresses=sorted(BODY_INS),
        branch_edges=sorted(edges),
        original_only_prologue_sites=sorted(prologue),
        boundary_counts=boundaries, translated_code_bytes=0,
        excluded_normal_entry_edge=[0x88a6, 0x88ab],
        retf_hook_observation=hook_observation,
        input_hashes={path: sha((ROOT / path).read_bytes()) for path in paths},
        device_contract='Seeded unchained A0000 planar VGA fixture; mode-0 reads/writes, latches and ordered word ports',
        domain='Original 8822 entry and three-save frame; connected 882D preparation; execute only the aligned opaque 983B body through 9966 and consume its live far frame. Other body entries, 88AB, and changed child returns are stop boundaries. Compare canonical RAM, all registers, defined flags, ordered byte events, VGA planes/latches/registers/ports, intact code and independent whole-plane footprints. Quiescent IRQ; bounded nonzero row count except controlled CL=0/LOOP 65536 case.'))
    print(f'PASS drawing render: {len(baseline)} cases, {body_cases} aligned opaque body cases, '
          f'{len(seen)} integrated sites, {len(edges)} branch edges; '
          f'3 compiled mutations detected; {len(prologue)} prologue sites excluded from C coverage')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--bounded-worker':
        LIBRARY_DIRECTORY = Path(sys.argv[2])
        main()
    elif len(sys.argv) == 1:
        (BUILD / 'drawing-render-differential.json').unlink(missing_ok=True)
        with temporary_build_directory(prefix='drawing-render-', parent=BUILD) as directory:
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--bounded-worker', directory], cwd=ROOT, timeout=180)
    else:
        raise SystemExit('Unexpected drawing_render arguments')

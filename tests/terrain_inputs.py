"""Original7C67 terrain-record caller prefix versus its native C core."""
import ctypes
import os
from pathlib import Path
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import capstone
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE
from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import x86_const as x

from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, read_json, write_json, sha
from dat_io_c import Regs, MEM
from special_blit import READ, WRITE, OUT, Bus
from unpack import ASSET, unpack, relocated
import dat_io as oracle


IMAGE, ORACLE = unpack(ASSET.read_bytes())
SYMS = {row['symbol_name']: row for row in read_json(ROOT / 'metadata/symbols.json')}


def field(name):
    return SYMS[name]['address']


START = field('DrawPackedTerrainPiece')
PREFIX_END = 0x7CB5  # Stop before the five-byte far CALL to8822.
CHILD_RETURN = field('TerrainPieceAfterBitmap')
OWN_RETURN = field('TerrainPieceReturn')
GROUND = field('GroundTerrainRecordWidthByte')
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {ins.address: ins for ins in MD.disasm(IMAGE[START:PREFIX_END], START)}
BRANCHES = {pc for pc, ins in INS.items()
            if ins.group(capstone.CS_GRP_JUMP) or ins.mnemonic.startswith('loop')}
EDGES = {(pc, ins.operands[0].imm & 0xffff)
         for pc, ins in INS.items() if pc in BRANCHES}
EDGES |= {(pc, pc + ins.size) for pc, ins in INS.items()
          if pc in BRANCHES and ins.mnemonic != 'jmp'}

MEMORY_SIZE = 1 << 20
MEMORY_MASK = MEMORY_SIZE - 1
MEMORY_TEMPLATE = bytes((address * 37 + (address >> 8) * 13 + 0x5a) & 0xff
                        for address in range(MEMORY_SIZE))
FLAG_MASK = 0xFC7  # Compare all defined exit flags; AF is undefined after XOR.
NATIVE_EVENT_LIMIT = 64
NATIVE_ACCESS_EXIT = 86
NATIVE_CALLBACK_EXIT = 87


class TerrainCall(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in (
        'data_segment', 'game_data_segment', 'stack_segment', 'stack_offset',
        'code_segment', 'packed_horizontal', 'packed_vertical', 'source_cursor',
        'output_segment', 'flags')]


class PlanarBitmapCall(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in (
        'data_segment', 'game_data_segment', 'stack_segment', 'stack_offset',
        'left', 'top', 'packed_height', 'width', 'source_cursor',
        'destination_cursor', 'control', 'output_segment', 'flags')]


def physical(segment, offset):
    return (((segment << 4) + offset) & MEMORY_MASK)


def put_byte(memory, segment, offset, value):
    memory[physical(segment, offset)] = value & 0xff


def put_word(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xff
    memory[(address + 1) & MEMORY_MASK] = (value >> 8) & 0xff


def get_word(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MEMORY_MASK] << 8)


def fixture_records(memory, segment, special_selector=None):
    """Seed64 eight-byte records, preserving distinct opaque +6/+7 bytes."""
    for selector in range(64):
        offset = (GROUND + selector * 8) & 0xffff
        put_byte(memory, segment, offset, (selector * 13 + 3) & 0xff)
        put_byte(memory, segment, offset + 1, (selector * 7 + 1) & 0xff)
        put_word(memory, segment, offset + 2, (0x1234 + selector * 37) & 0xffff)
        put_word(memory, segment, offset + 4, (0xabcd ^ (selector * 91)) & 0xffff)
        put_byte(memory, segment, offset + 6, (0x80 + selector) & 0xff)
        put_byte(memory, segment, offset + 7, (0x40 ^ selector) & 0xff)
    if special_selector is not None:
        # The selector mutant reads record127. Give that adjacent memory a
        # deliberate width/height/source/mask signature distinct from record63.
        offset = (GROUND + special_selector * 8) & 0xffff
        put_byte(memory, segment, offset, 0xe7)
        put_byte(memory, segment, offset + 1, 0x5d)
        put_word(memory, segment, offset + 2, 0x9137)
        put_word(memory, segment, offset + 4, 0x62ac)


def cases():
    out = []
    horizontals = (0x0000, 0x2000, 0x4000, 0x6000,
                   0x8000, 0xffff, 0x1fff, 0x7fff)
    # Every six-bit record selector is tested with BX bit6 both clear and set.
    # The flags value rotates through0..7 over the selector matrix.
    for selector in range(64):
        for bit6 in (0, 0x40):
            seed = len(out)
            flags = (selector + int(bool(bit6))) & 7
            out.append(dict(name=f'selector-{selector:02x}-bit6-{int(bool(bit6))}-flags-{flags}',
                seed=seed, horizontal=horizontals[(selector + flags + bool(bit6)) % len(horizontals)],
                vertical=selector | bit6, flags=flags, adapter=(seed % 32 == 0)))

    # The complete ten-by-seven boundary matrix: signed-Y transitions,
    # packed control bits, and horizontal truncation/carry boundaries.
    explicit_verticals = (0x0000, 0x007f, 0x0080, 0x3fff, 0x4000,
                          0x7fff, 0x8000, 0xff7f, 0xff80, 0xffff)
    explicit_horizontals = (0x0007, 0x1fff, 0x2000, 0x4000,
                            0x6000, 0x8000, 0xffff)
    for vertical in explicit_verticals:
        for horizontal in explicit_horizontals:
            seed = len(out)
            out.append(dict(name=f'packed-{vertical:04x}-{horizontal:04x}', seed=seed,
                horizontal=horizontal, vertical=vertical,
                flags=(seed & 7) | (0x200 if seed & 1 else 0) |
                      (0x400 if seed & 2 else 0),
                adapter=horizontal in (0x2000, 0x8000)))

    # Exercise each initial arithmetic-flag pattern through each control/carry
    # path, independent of the all-selector index matrix above.
    control_horizontals = (0x0000, 0x2000, 0x4000,
                           0x6000, 0x8000, 0xe000)
    for initial_flags in range(8):
        for horizontal in control_horizontals:
            seed = len(out)
            out.append(dict(name=f'flags-{initial_flags}-horizontal-{horizontal:04x}',
                seed=seed, horizontal=horizontal, vertical=0x2140 | initial_flags,
                flags=initial_flags, adapter=horizontal in (0x2000, 0x8000)))

    # Initial SP wrap, physical 20-bit wrap, independently relocated images,
    # and DS reads from a wrapped physical record frame.
    for ss, sp in ((0x7000, 0x0000), (0x7000, 0x0001), (0xffff, 0x0011),
                   (0xffff, 0x0001), (0xfff0, 0x0021)):
        seed = len(out)
        out.append(dict(name=f'stack-wrap-{ss:04x}-{sp:04x}', seed=seed,
            horizontal=0x8000 if seed & 1 else 0x2000,
            vertical=(0x8000 | seed), flags=0x200 | (0x400 if seed & 1 else 0),
            ss=ss, sp=sp, adapter=True))
    for segment in (0xffff, 0xfff0, 0x2345):
        seed = len(out)
        out.append(dict(name=f'data-segment-{segment:04x}', seed=seed,
            horizontal=0x6000, vertical=0x8040 | seed,
            flags=0x400 | (seed & 7), ds=segment, adapter=True))

    # DS:record aliases all three live PUSH saves. The loads see the just-saved
    # coordinates and SI, while POP AX/BX still consume those live words.
    for selector in (0, 5, 63):
        seed = len(out)
        record = (GROUND + selector * 8) & 0xffff
        out.append(dict(name=f'record-live-stack-alias-{selector:02x}', seed=seed,
            horizontal=(0x2000 + selector) & 0xffff, vertical=selector,
            flags=0x400 | (seed & 7), alias_record=True,
            ds_mode='game', ss_mode='ds', sp=(record + 6) & 0xffff,
            adapter=True))

    # Independent AX and flags low-bit combinations catch accidental use of
    # incoming CX/DX/DI/BP or an incoming CF in the RCL path.
    for horizontal in range(8):
        seed = len(out)
        out.append(dict(name=f'ax-small-{horizontal}-flags-{horizontal}', seed=seed,
            horizontal=horizontal, vertical=0x4080 | seed,
            flags=horizontal, adapter=(horizontal == 0)))
    return out


def prepare(case):
    seed = case['seed']
    load = (0x1010, 0x1213, 0x2345)[seed % 3]
    game_ds = (load + 0x09a9) & 0xffff
    data_segment = case.get('ds', game_ds)
    if case.get('ds_mode') == 'game':
        data_segment = game_ds
    stack_segment = case.get('ss', 0x7000)
    if case.get('ss_mode') == 'ds':
        stack_segment = data_segment
    stack_offset = case.get('sp', 0x8000)

    # A deterministic full 20-bit RAM pattern preserves visible aliases while
    # avoiding fixture state outside the declared executable/data frame.
    memory = bytearray(MEMORY_TEMPLATE)
    relocated_image = relocated(IMAGE, ORACLE['relocations'], load)
    memory[load << 4:(load << 4) + len(relocated_image)] = relocated_image
    fixture_records(memory, data_segment, 127)

    regs = {name: 0 for name in oracle.REG_NAMES}
    regs.update(cs=load, ip=START, ds=data_segment, es=0x6500,
        ss=stack_segment, sp=stack_offset, ax=case['horizontal'],
        bx=case['vertical'], cx=0xa55a, dx=0x6b7c, si=0x2468,
        di=0xdead, bp=0xbeef)
    flags = 2 | (case.get('flags', 0) & 0x0ad5)
    caller_return = 0x6abc
    put_word(memory, stack_segment, stack_offset, caller_return)
    return memory, regs, flags, game_ds, caller_return


def record_expected(memory, regs, case):
    """Independent formula plus live stack-overwrite routing for record reads."""
    horizontal = regs['ax']
    packed_vertical = regs['bx']
    control = ((horizontal >> 7) & 0x00c0) | 0x000f
    if control & 0x0040:
        control |= 0x0f00
    if horizontal & 0x8000:
        control |= 0x8000
    left = horizontal & 0x1fff
    signed_vertical = packed_vertical if packed_vertical < 0x8000 else packed_vertical - 0x10000
    top = ((signed_vertical >> 7) - 4) & 0xffff
    selector = packed_vertical & 0x3f
    record_offset = (GROUND + selector * 8) & 0xffff
    fields = {}
    if case.get('alias_record'):
        # PUSH SI, PUSH BX, PUSH AX overwrite the aliased six record bytes in
        # that order before the original loads them. Model only these writes.
        stack_writes = {}
        initial_sp = regs['sp']
        for offset, value in (((initial_sp - 2) & 0xffff, regs['si']),
                              ((initial_sp - 4) & 0xffff, top),
                              ((initial_sp - 6) & 0xffff, left)):
            p = physical(regs['ss'], offset)
            stack_writes[p] = value & 0xff
            stack_writes[(p + 1) & MEMORY_MASK] = (value >> 8) & 0xff
    else:
        stack_writes = {}
    record_address = physical(regs['ds'], record_offset)
    for byte in range(6):
        address = (record_address + byte) & MEMORY_MASK
        fields[byte] = stack_writes.get(address, memory[address])
    expected = dict(left=left, top=top, packed_height=0x0400 | fields[1],
        width=fields[0], source_cursor=fields[2] | (fields[3] << 8),
        destination_cursor=fields[4] | (fields[5] << 8), control=control,
        selector=selector)
    return expected


def original(case, memory, regs, flags):
    uc = Uc(UC_ARCH_X86, UC_MODE_16)
    uc.mem_map(0, 2 << 20)
    uc.mem_write(0, bytes(memory) * 2)
    for name, register in oracle.REG.items():
        uc.reg_write(register, regs[name])
    uc.reg_write(x.UC_X86_REG_EFLAGS, flags)
    canonical = bytearray(memory)
    events = []
    seen, edges = set(), set()
    previous = None
    stopped = False
    steps = 0

    def code(uc, pc, size, _):
        nonlocal previous, stopped, steps
        offset = (pc - (regs['cs'] << 4)) & 0xffff
        if previous in BRANCHES:
            edges.add((previous, offset))
        if offset == PREFIX_END:
            stopped = True
            uc.emu_stop()
            return
        if offset not in INS or uc.reg_read(oracle.REG['cs']) != regs['cs']:
            raise RuntimeError(f'{case["name"]}: original prefix escaped at {offset:04x}')
        steps += 1
        if steps > 100:
            raise RuntimeError(f'{case["name"]}: original instruction budget exceeded')
        seen.add(offset)
        previous = offset

    def wrap_reads(uc, access, address, size, value, _):
        for index in range(size):
            physical_address = address + index
            if physical_address >= MEMORY_SIZE:
                wrapped = physical_address & MEMORY_MASK
                uc.mem_write(physical_address, bytes((canonical[wrapped],)))

    def reads(uc, access, address, size, value, _):
        current_flags = uc.reg_read(x.UC_X86_REG_EFLAGS)
        for index in range(size):
            physical_address = (address + index) & MEMORY_MASK
            events.append(('read', physical_address, canonical[physical_address], current_flags))

    def writes(uc, access, address, size, value, _):
        current_flags = uc.reg_read(x.UC_X86_REG_EFLAGS)
        for index in range(size):
            raw_address = address + index
            physical_address = raw_address & MEMORY_MASK
            byte = (value >> (8 * index)) & 0xff
            events.append(('write', physical_address, byte, current_flags))
            canonical[physical_address] = byte
            if raw_address >= MEMORY_SIZE:
                uc.mem_write(physical_address, bytes((byte,)))

    uc.hook_add(UC_HOOK_CODE, code)
    uc.hook_add(UC_HOOK_MEM_READ, wrap_reads)
    uc.hook_add(UC_HOOK_MEM_READ, reads)
    uc.hook_add(UC_HOOK_MEM_WRITE, writes)
    uc.emu_start((regs['cs'] << 4) + START, 0, count=100)
    if not stopped:
        raise RuntimeError(f'{case["name"]}: original did not stop before child CALL')
    final_regs = {name: uc.reg_read(register) for name, register in oracle.REG.items()}
    final_flags = uc.reg_read(x.UC_X86_REG_EFLAGS)
    actual_memory = bytearray(uc.mem_read(0, MEMORY_SIZE))
    # The write observer maintains canonical aliases; use it for high-frame
    # writes that Unicorn exposed through its second mapped megabyte.
    actual_memory[:] = canonical
    return final_regs, final_flags, actual_memory, events, seen, edges


def library(directory, mutation=0):
    path = build(Path(directory) / f'terrain-drawing-m{mutation}.dll',
                 mutation, 'terrain_drawing')
    lib = ctypes.CDLL(str(path))
    lib.lmn_prepare_terrain_piece_core.argtypes = [
        MEM, ctypes.POINTER(TerrainCall), ctypes.POINTER(Bus)]
    lib.lmn_prepare_terrain_piece_core.restype = PlanarBitmapCall
    lib.lmn_prepare_terrain_piece_adapter.argtypes = [
        MEM, ctypes.POINTER(Regs), ctypes.c_uint16, ctypes.POINTER(Bus)]
    lib.lmn_prepare_terrain_piece_adapter.restype = None
    return lib


def native_callback(label):
    def fail(error):
        os.write(2, (f'terrain_inputs: {label}: {error}\n').encode(
            'utf-8', errors='backslashreplace'))
        os._exit(NATIVE_CALLBACK_EXIT)
    return fail


def run_native(lib, memory, call, with_bus=True):
    native_memory = bytearray(memory)
    events = []
    callback_error = native_callback(call['name'])

    @READ
    def read(context, mem, address, flags):
        if len(events) >= NATIVE_EVENT_LIMIT:
            os.write(2, (f'terrain_inputs: {call["name"]}: access budget exceeded\n').encode())
            os._exit(NATIVE_ACCESS_EXIT)
        try:
            address &= MEMORY_MASK
            value = mem[address]
            events.append(('read', address, value, flags))
            return value
        except Exception as error:
            callback_error(error)

    @WRITE
    def write(context, mem, address, value, flags):
        if len(events) >= NATIVE_EVENT_LIMIT:
            os.write(2, (f'terrain_inputs: {call["name"]}: access budget exceeded\n').encode())
            os._exit(NATIVE_ACCESS_EXIT)
        try:
            address &= MEMORY_MASK
            mem[address] = value
            native_memory[address] = value
            events.append(('write', address, value, flags))
        except Exception as error:
            callback_error(error)

    bus = Bus(None, read, write, OUT()) if with_bus else None
    memory_arg = (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(native_memory)
    call_arg = TerrainCall(call['ds'], call['game_ds'], call['ss'], call['sp'],
        call['cs'], call['ax'], call['bx'], call['si'], call['es'], call['flags'])
    result = lib.lmn_prepare_terrain_piece_core(
        memory_arg, ctypes.byref(call_arg), ctypes.byref(bus) if bus else None)
    return native_memory, result, events, bus


def compare(lib, case, *, adapter=False):
    memory, regs, flags, game_ds, caller_return = prepare(case)
    expected_fields = record_expected(memory, regs, case)
    final_regs, final_flags, original_memory, original_events, seen, edges = \
        original(case, memory, regs, flags)
    call = dict(name=case['name'], ds=regs['ds'], game_ds=game_ds, ss=regs['ss'],
        sp=regs['sp'], cs=regs['cs'], ax=regs['ax'], bx=regs['bx'], si=regs['si'],
        es=regs['es'], flags=flags)
    native_memory, result, native_events, bus = run_native(lib, memory, call)

    for name, expected in expected_fields.items():
        if name == 'selector':
            continue
        actual = getattr(result, name)
        if actual != expected:
            raise AssertionError(f'{case["name"]}: independent {name} {actual:04x}/{expected:04x}')
    if result.data_segment != regs['ds'] or result.game_data_segment != game_ds or \
       result.stack_segment != regs['ss'] or result.stack_offset != ((regs['sp'] - 2) & 0xffff) or \
       result.output_segment != regs['es']:
        raise AssertionError(f'{case["name"]}: prefix segment/stack contract differs')
    if final_regs['ip'] != PREFIX_END or final_regs['cs'] != regs['cs']:
        raise RuntimeError(f'{case["name"]}: original prefix continuation differs')
    for name, expected in final_regs.items():
        actual = getattr(result, {
            'ax': 'left', 'bx': 'top', 'cx': 'packed_height', 'dx': 'width',
            'si': 'source_cursor', 'di': 'destination_cursor', 'bp': 'control',
            'sp': 'stack_offset', 'ds': 'data_segment', 'es': 'output_segment',
        }.get(name, ''), None) if name in ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'sp', 'ds', 'es') else None
        if actual is not None and actual != expected:
            raise AssertionError(f'{case["name"]}: {name} core output {actual:04x}/{expected:04x}')
    if (result.flags ^ final_flags) & FLAG_MASK:
        raise AssertionError(f'{case["name"]}: core defined flags {result.flags:04x}/{final_flags:04x}')
    if native_memory != original_memory:
        address = next(i for i, (left, right) in enumerate(zip(native_memory, original_memory))
                       if left != right)
        raise AssertionError(f'{case["name"]}: RAM differs at{address:05x}')
    if len(native_events) != len(original_events):
        raise AssertionError(f'{case["name"]}: event count {len(native_events)}/{len(original_events)}')
    for index, (native_event, original_event) in enumerate(zip(native_events, original_events)):
        event_mask = 0xFD7 if index < 2 or index == 6 else 0xFC7
        if native_event[:3] != original_event[:3] or \
           ((native_event[3] ^ original_event[3]) & event_mask):
            raise AssertionError(f'{case["name"]}: ordered RAM event{index} differs '
                                 f'{native_event}/{original_event}')
    if any((native_memory[physical(regs['ds'], (GROUND + selector * 8 + byte) & 0xffff)] !=
            memory[physical(regs['ds'], (GROUND + selector * 8 + byte) & 0xffff)])
           for selector in range(64) for byte in (6, 7)):
        raise AssertionError(f'{case["name"]}: record +6/+7 bytes were modified')
    if get_word(native_memory, regs['ss'], regs['sp']) != caller_return:
        raise AssertionError(f'{case["name"]}: caller return word changed before7CBB')

    if adapter:
        adapter_memory = bytearray(memory)
        adapter_regs = Regs(**regs, flags=flags)
        adapter_events = []

        @READ
        def adapter_read(context, mem, address, event_flags):
            if len(adapter_events) >= NATIVE_EVENT_LIMIT:
                os.write(2, (f'terrain_inputs: {case["name"]}: adapter access budget exceeded\n').encode())
                os._exit(NATIVE_ACCESS_EXIT)
            try:
                address &= MEMORY_MASK
                value = mem[address]
                adapter_events.append(('read', address, value, event_flags))
                return value
            except Exception as error:
                native_callback(case['name'] + ' adapter')(error)

        @WRITE
        def adapter_write(context, mem, address, value, event_flags):
            if len(adapter_events) >= NATIVE_EVENT_LIMIT:
                os.write(2, (f'terrain_inputs: {case["name"]}: adapter access budget exceeded\n').encode())
                os._exit(NATIVE_ACCESS_EXIT)
            try:
                address &= MEMORY_MASK
                mem[address] = value
                adapter_memory[address] = value
                adapter_events.append(('write', address, value, event_flags))
            except Exception as error:
                native_callback(case['name'] + ' adapter')(error)

        adapter_bus = Bus(None, adapter_read, adapter_write, OUT())
        lib.lmn_prepare_terrain_piece_adapter(
            (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(adapter_memory),
            ctypes.byref(adapter_regs), game_ds,
            ctypes.byref(adapter_bus))
        for name, expected in final_regs.items():
            if getattr(adapter_regs, name) != expected:
                raise AssertionError(f'{case["name"]}: prefix adapter {name} '
                    f'{getattr(adapter_regs, name):04x}/{expected:04x}')
        if (adapter_regs.flags ^ final_flags) & FLAG_MASK:
            raise AssertionError(f'{case["name"]}: prefix adapter defined flags differ')
        if adapter_regs.ip != PREFIX_END or adapter_regs.cs != regs['cs']:
            raise AssertionError(f'{case["name"]}: prefix adapter continuation differs')
        if adapter_memory != original_memory or adapter_events != native_events:
            raise AssertionError(f'{case["name"]}: prefix adapter RAM/events differ')

    return seen, edges


def detect_mutations(directory, baseline, by_name):
    witnesses = ((1, 'selector-3f-bit6-1-flags-0'),
                 (2, 'packed-8000-ffff'),
                 (3, 'packed-0080-2000'))
    detected = []
    for mutation, name in witnesses:
        mutant = library(directory, mutation)
        case = by_name[name]
        try:
            compare(mutant, case, adapter=False)
        except AssertionError:
            detected.append(dict(mutation=mutation, case=name))
        else:
            raise AssertionError(f'terrain prefix mutation{mutation} survived witness {name}')
    return detected


def main():
    report = BUILD / 'terrain-inputs-differential.json'
    report.unlink(missing_ok=True)
    baseline = cases()
    base_library = library(LIBRARY_DIRECTORY)
    sites, edges = set(), set()
    by_name = {case['name']: case for case in baseline}
    adapters = 0
    for case in baseline:
        case_sites, case_edges = compare(base_library, case,
            adapter=case.get('adapter', False))
        sites |= case_sites
        edges |= case_edges
        adapters += int(case.get('adapter', False))
    if sites != set(INS):
        raise AssertionError(f'missing prefix sites {set(INS) - sites}')
    if edges != EDGES:
        raise AssertionError(f'missing prefix edges {EDGES - edges}/{edges - EDGES}')
    mutations = detect_mutations(LIBRARY_DIRECTORY, baseline, by_name)
    paths = ('c/terrain_drawing.c', 'c/terrain_drawing.h', 'c/drawing_render.h',
        'c/lemmings_sym.h', 'tools/cbuild.py', 'tools/bounded_process.py',
        'tests/terrain_inputs.py', 'tests/special_blit.py', 'tests/dat_io.py',
        'tests/dat_io_c.py', 'tools/unpack.py', 'metadata/symbols.json')
    write_json(report, dict(image='main', image_sha256=sha(IMAGE),
        prefix_start=START, prefix_end=PREFIX_END, prefix_sha256=sha(IMAGE[START:PREFIX_END]),
        prefix_bytes_hex=IMAGE[START:PREFIX_END].hex(), case_count=len(baseline),
        prefix_adapter_case_count=adapters, mutation_count=len(mutations),
        mutations_detected=mutations, executed_instruction_addresses=sorted(sites),
        branch_edges=sorted(edges), translated_code_bytes=78,
        input_hashes={path: sha((ROOT / path).read_bytes()) for path in paths},
        domain='7C67..7CB4 prefix; stop before the far child CALL at7CB5. '
            'Canonical DS/SS memory, live saved coordinates, ordered record/stack '
            'accesses, defined flags and all prefix sites/edges; actual child bodies '
            'remain the drawing_render core contract.'))
    print(f'PASS terrain inputs: {len(baseline)} cases, {len(sites)} sites, '
          f'{len(edges)} edges, {adapters} prefix-adapter probes; '
          f'{len(mutations)} compiled mutations detected')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--bounded-worker':
        LIBRARY_DIRECTORY = Path(sys.argv[2])
        main()
    elif len(sys.argv) == 1:
        BUILD.mkdir(parents=True, exist_ok=True)
        with temporary_build_directory(prefix='terrain-inputs-', parent=BUILD) as directory:
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--bounded-worker', directory], cwd=ROOT,
                        timeout=180, memory_mib=512)
    else:
        raise SystemExit('Unexpected terrain_inputs arguments')

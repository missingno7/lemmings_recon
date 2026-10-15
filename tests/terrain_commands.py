"""Bounded terrain command reader versus both original loop prefixes."""
import ctypes
import os
from pathlib import Path
import random
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import capstone
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE
from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import x86_const as x

from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, read_json, sha, write_json
from dat_io_c import Regs, MEM
from special_blit import READ, WRITE, OUT, Bus
from unpack import ASSET, unpack, relocated
import dat_io as oracle


IMAGE, ORACLE = unpack(ASSET.read_bytes())
SYMS = {row['symbol_name']: row for row in read_json(ROOT / 'metadata/symbols.json')}

SETUP_ENTRY = SYMS['DrawLevelTerrainStream']['address']
SETUP_COMMAND = SYMS['SetupTerrainCommand']['address']
SETUP_CALL = SYMS['SetupTerrainPieceCall']['address']
SETUP_EXIT = SYMS['PrepareLevelObjectState']['address']
REDRAW_ENTRY = SYMS['RedrawLevelTerrainStream']['address']
REDRAW_COMMAND = SYMS['RedrawTerrainCommand']['address']
REDRAW_CALL = SYMS['RedrawTerrainPieceCall']['address']
REDRAW_EXIT = SYMS['RedrawTerrainFinished']['address']
LEVEL_TERRAIN = SYMS['LevelTerrainDefinitions']['address']

MEMORY_SIZE = 1 << 20
MEMORY_MASK = MEMORY_SIZE - 1
EVENT_LIMIT = 64
ACCESS_EXIT = 86
CALLBACK_EXIT = 87
FLAG_MASK = 0x0fd7
DEFINED_CMP_FLAGS = 0x0fd7
FLAG_PATTERNS = tuple(0x0002 | (0x0010 if bits & 1 else 0) |
                      (0x0200 if bits & 2 else 0) |
                      (0x0400 if bits & 4 else 0)
                      for bits in range(8))
STATUS_PATTERNS = (0x0003, 0x0007, 0x0042, 0x0082,
                   0x0802, 0x0ad7, 0x0ed7, 0x0a97)
HORIZONTAL_VALUES = (0x0000, 0x7fff, 0x8000, 0xfffe, 0xffff)
VERTICAL_VALUES = (0x0000, 0x7fff, 0x8000, 0xfffe, 0xffff)
MEMORY_TEMPLATE = bytes((address * 37 + (address >> 8) * 13 + 0x5a) & 0xff
                        for address in range(MEMORY_SIZE))

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True


class TerrainCommand(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('packed_horizontal', 'packed_vertical', 'command_cursor',
                 'flags', 'end_of_stream')]


def physical(segment, offset):
    return (((segment << 4) + (offset & 0xffff)) & MEMORY_MASK)


def store_command(memory, segment, cursor, horizontal, vertical):
    values = ((horizontal >> 8) & 0xff, horizontal & 0xff,
              (vertical >> 8) & 0xff, vertical & 0xff)
    for index, value in enumerate(values):
        memory[physical(segment, (cursor + index) & 0xffff)] = value


def command_spans(redraw):
    if redraw:
        return REDRAW_ENTRY, REDRAW_COMMAND, REDRAW_CALL, REDRAW_EXIT
    return SETUP_ENTRY, SETUP_COMMAND, SETUP_CALL, SETUP_EXIT


def command_sites(redraw):
    _, start, stop_call, _ = command_spans(redraw)
    return {ins.address: ins for ins in MD.disasm(IMAGE[start:stop_call], start)}


def cases():
    out = []
    seed = 0
    for h_index, horizontal in enumerate(HORIZONTAL_VALUES):
        for v_index, vertical in enumerate(VERTICAL_VALUES):
            for flag_index, flags in enumerate(FLAG_PATTERNS):
                for redraw in (0, 1):
                    out.append(dict(name=f'matrix-{horizontal:04x}-{vertical:04x}-'
                                    f'flags-{flags:04x}-redraw-{redraw}',
                        seed=seed, horizontal=horizontal, vertical=vertical,
                        flags=flags, redraw=redraw))
                seed += 1

    for index, flags in enumerate(STATUS_PATTERNS):
        for redraw in (0, 1):
            out.append(dict(name=f'status-flags-{flags:04x}-redraw-{redraw}',
                seed=seed, horizontal=(0x1357 + index * 0x1111) & 0xffff,
                vertical=(0x2468 + index * 0x0101) & 0xffff,
                flags=flags, redraw=redraw))
        seed += 1

    for cursor_index, cursor in enumerate((0xffff, 0xfffe, 0xfffd,
                                            0xfffc, 0x0000)):
        for ds in (None, 0xffff):
            for redraw in (0, 1):
                out.append(dict(name=f'cursor-wrap-{cursor:04x}-ds-'
                                f'{"game" if ds is None else "ffff"}-redraw-{redraw}',
                    seed=seed, horizontal=0xfffe if cursor_index & 1 else 0xffff,
                    vertical=(0xabc0 + cursor_index) & 0xffff,
                    flags=FLAG_PATTERNS[(cursor_index + redraw) % len(FLAG_PATTERNS)],
                    cursor=cursor, ds=ds, redraw=redraw))
            seed += 1

    for index, cursor_delta in enumerate((-1, 0, 2, 7)):
        for redraw in (0, 1):
            out.append(dict(name=f'code-alias-{cursor_delta:+d}-redraw-{redraw}',
                seed=seed, horizontal=0, vertical=0,
                flags=FLAG_PATTERNS[index],
                cursor=(SETUP_COMMAND if not redraw else REDRAW_COMMAND) + cursor_delta,
                ds_mode='code', alias_image=True, redraw=redraw))
        seed += 1
    for redraw in (0, 1):
        command = REDRAW_COMMAND if redraw else SETUP_COMMAND
        out.append(dict(name=f'neighbor-segment-code-alias-redraw-{redraw}',
            seed=seed, horizontal=0, vertical=0, flags=0x0612,
            cursor=(command - 16) & 0xffff, ds_mode='code-neighbor',
            alias_image=True, redraw=redraw))
        seed += 1

    # Explicit witnesses keep each bounded reader mutation falsifiable.
    out.extend((
        dict(name='reverse-byte-order-witness', seed=seed,
             horizontal=0x1234, vertical=0x5678, flags=0x0202, redraw=0),
        dict(name='ah-ff-low-not-ff-witness', seed=seed + 1,
             horizontal=0xfffe, vertical=0x8012, flags=0x0412, redraw=1),
        dict(name='advance-four-across-si-wrap-witness', seed=seed + 2,
             horizontal=0x2345, vertical=0x89ab, flags=0x0612,
             cursor=0xfffc, ds=0xffff, redraw=0),
    ))
    return out


def prepare(case):
    seed = case['seed']
    load = (0x1010, 0x1213, 0x2345)[seed % 3]
    data_segment = case.get('ds')
    if data_segment is None:
        if case.get('ds_mode') == 'code':
            data_segment = load
        elif case.get('ds_mode') == 'code-neighbor':
            data_segment = (load + 1) & 0xffff
        else:
            data_segment = (load + 0x09a9) & 0xffff
    cursor = case.get('cursor', (0x2400 + seed * 29) & 0xffff)

    memory = bytearray(MEMORY_TEMPLATE)
    image = relocated(IMAGE, ORACLE['relocations'], load)
    memory[load << 4:(load << 4) + len(image)] = image
    if not case.get('alias_image'):
        store_command(memory, data_segment, cursor,
                      case['horizontal'], case['vertical'])

    rng = random.Random(0x3752 + seed)
    regs = {name: rng.randrange(0x10000) for name in oracle.REG_NAMES}
    entry, _, _, _ = command_spans(case['redraw'])
    regs.update(cs=load, ip=entry, ds=data_segment, es=0x6500,
                ss=0x7000, sp=0x8000, si=cursor)
    flags = case['flags'] | 2
    return memory, regs, flags, load


def bounded_original(memory, regs, flags, redraw, *, initialize=False):
    entry, command, stop_call, exit_target = command_spans(redraw)
    if initialize:
        start = entry
        stop_targets = {command}
        allowed = {entry: next(MD.disasm(IMAGE[entry:entry + 3], entry))}
    else:
        start = command
        stop_targets = {stop_call, exit_target}
        allowed = command_sites(redraw)
    branches = {pc for pc, ins in allowed.items()
                if ins.group(capstone.CS_GRP_JUMP) or
                ins.mnemonic.startswith('loop')}
    uc = Uc(UC_ARCH_X86, UC_MODE_16)
    uc.mem_map(0, 2 * MEMORY_SIZE)
    uc.mem_write(0, bytes(memory) * 2)
    for name, register in oracle.REG.items():
        uc.reg_write(register, regs[name])
    uc.reg_write(oracle.REG['ip'], start)
    uc.reg_write(x.UC_X86_REG_EFLAGS, flags)
    events = []
    seen = set()
    edges = set()
    canonical = bytearray(memory)
    previous = None
    stopped = False
    steps = 0
    failure = []

    def code(uc, pc, _size, _):
        nonlocal previous, stopped, steps
        offset = (pc - (regs['cs'] << 4)) & 0xffff
        if previous in branches:
            edges.add((previous, offset))
        if offset in stop_targets:
            stopped = True
            uc.emu_stop()
            return
        if offset not in allowed:
            failure.append(f'original escaped terrain prefix at{offset:04x}')
            uc.emu_stop()
            return
        steps += 1
        if steps > 16:
            failure.append('original terrain prefix exceeded its instruction budget')
            uc.emu_stop()
            return
        seen.add(offset)
        previous = offset

    def reads(uc, _access, address, size, _value, _):
        current_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xffff
        for index in range(size):
            physical_address = (address + index) & MEMORY_MASK
            events.append(('read', physical_address,
                           canonical[physical_address], current_flags))
            if len(events) > EVENT_LIMIT:
                raise RuntimeError('original terrain prefix exceeded its read budget')

    def writes(uc, _access, address, size, value, _):
        current_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xffff
        for index in range(size):
            physical_address = (address + index) & MEMORY_MASK
            byte = (value >> (8 * index)) & 0xff
            events.append(('write', physical_address, byte, current_flags))
            canonical[physical_address] = byte

    uc.hook_add(UC_HOOK_CODE, code)
    uc.hook_add(UC_HOOK_MEM_READ, reads)
    uc.hook_add(UC_HOOK_MEM_WRITE, writes)
    try:
        uc.emu_start((regs['cs'] << 4) + start, 0, count=32)
    except Exception as error:
        raise RuntimeError(f'original emulation failed at CS:IP '
            f'{uc.reg_read(oracle.REG["cs"]):04x}:{uc.reg_read(oracle.REG["ip"]):04x} '
            f'flags={uc.reg_read(x.UC_X86_REG_EFLAGS):04x} start={start:04x}') from error
    if failure:
        raise RuntimeError(f'{failure[0]}; start={start:04x} cs={regs["cs"]:04x} '
                           f'ip={uc.reg_read(oracle.REG["ip"]):04x}')
    if not stopped:
        raise RuntimeError('original terrain prefix did not reach a boundary')
    final_regs = {name: uc.reg_read(register) for name, register in oracle.REG.items()}
    final_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xffff
    if not initialize:
        # All mutations in this span are register-only. Preserve full canonical RAM.
        canonical = bytearray(memory)
    return final_regs, final_flags, canonical, events, seen, edges


def library(directory, mutation=0):
    path = build(Path(directory) / f'terrain-stream-{mutation}.dll',
                 mutation, 'terrain_stream')
    lib = ctypes.CDLL(str(path))
    lib.lmn_read_terrain_command_core.argtypes = [
        MEM, ctypes.c_uint16, ctypes.c_uint16, ctypes.c_uint16,
        ctypes.POINTER(Bus)]
    lib.lmn_read_terrain_command_core.restype = TerrainCommand
    lib.lmn_read_terrain_command_adapter.argtypes = [
        MEM, ctypes.POINTER(Regs), ctypes.c_uint,
        ctypes.POINTER(Bus)]
    lib.lmn_read_terrain_command_adapter.restype = None
    return lib


def native_bus(memory, label):
    events = []

    def fail(code, message):
        os.write(2, f'terrain_commands: {label}: {message}\n'.encode(
            'utf-8', errors='backslashreplace'))
        os._exit(code)

    @READ
    def read(_context, mem, address, flags):
        if len(events) >= EVENT_LIMIT:
            fail(ACCESS_EXIT, 'native RAM access budget exceeded')
        try:
            address &= MEMORY_MASK
            value = mem[address]
            events.append(('read', address, value, flags & 0xffff))
            return value
        except BaseException as error:
            fail(CALLBACK_EXIT, f'native read callback failed: {error}')

    @WRITE
    def write(_context, mem, address, value, flags):
        if len(events) >= EVENT_LIMIT:
            fail(ACCESS_EXIT, 'native RAM access budget exceeded')
        try:
            address &= MEMORY_MASK
            mem[address] = value
            events.append(('write', address, value, flags & 0xffff))
        except BaseException as error:
            fail(CALLBACK_EXIT, f'native write callback failed: {error}')

    return Bus(None, read, write, OUT()), events


def normalize_events(events):
    return [(kind, address, value, flags & FLAG_MASK)
            for kind, address, value, flags in events]


def compare(lib, case):
    memory, regs, flags, _load = prepare(case)
    redraw = case['redraw']
    _, command_start, stop_call, exit_target = command_spans(redraw)
    final_regs, final_flags, original_memory, original_events, sites, edges = \
        bounded_original(memory, regs, flags, redraw)
    expected_end = final_regs['ax'] == 0xffff
    expected_target = exit_target if expected_end else stop_call
    if final_regs['ip'] != expected_target:
        raise RuntimeError(f'{case["name"]}: oracle stopped at{final_regs["ip"]:04x}')
    source_bytes = [memory[physical(regs['ds'], (regs['si'] + i) & 0xffff)]
                    for i in range(4)]
    expected_horizontal = (source_bytes[0] << 8) | source_bytes[1]
    expected_vertical = (source_bytes[2] << 8) | source_bytes[3]
    expected_cursor = (regs['si'] + 4) & 0xffff
    expected_flags = oracle.arithmetic(flags, expected_horizontal, 0xffff)
    if (final_regs['ax'] != expected_horizontal or
            final_regs['bx'] != expected_vertical or
            final_regs['si'] != expected_cursor or
            ((final_flags ^ expected_flags) & DEFINED_CMP_FLAGS)):
        raise AssertionError(f'{case["name"]}: independent packed-command formula differs')

    native_memory = bytearray(memory)
    memory_arg = (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(native_memory)
    bus, native_events = native_bus(native_memory, case['name'] + ' core')
    command = lib.lmn_read_terrain_command_core(
        memory_arg, regs['ds'], regs['si'], flags, ctypes.byref(bus))
    if (command.packed_horizontal != expected_horizontal or
            command.packed_vertical != expected_vertical or
            command.command_cursor != expected_cursor or
            ((command.flags ^ final_flags) & DEFINED_CMP_FLAGS) or
            bool(command.end_of_stream) != expected_end):
        raise AssertionError(f'{case["name"]}: native command core differs')
    if native_memory != original_memory:
        raise AssertionError(f'{case["name"]}: native command core changed RAM')
    if normalize_events(native_events) != normalize_events(original_events):
        raise AssertionError(f'{case["name"]}: ordered command core reads differ')

    adapter_memory = bytearray(memory)
    adapter_arg = (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(adapter_memory)
    adapter_regs = Regs(**regs, flags=flags)
    adapter_bus, adapter_events = native_bus(
        adapter_memory, case['name'] + ' adapter')
    lib.lmn_read_terrain_command_adapter(
        adapter_arg, ctypes.byref(adapter_regs), redraw,
        ctypes.byref(adapter_bus))
    expected_registers = dict(final_regs)
    expected_registers['ip'] = expected_target
    for name, expected in expected_registers.items():
        actual = getattr(adapter_regs, name)
        if actual != expected:
            raise AssertionError(f'{case["name"]}: adapter {name} '
                                 f'{actual:04x}/{expected:04x}')
    if ((adapter_regs.flags ^ final_flags) & DEFINED_CMP_FLAGS):
        raise AssertionError(f'{case["name"]}: adapter defined flags differ')
    if adapter_memory != original_memory:
        raise AssertionError(f'{case["name"]}: adapter changed RAM')
    if normalize_events(adapter_events) != normalize_events(original_events):
        raise AssertionError(f'{case["name"]}: ordered adapter reads differ')
    return sites, edges


def check_initializers():
    cases_checked = 0
    seen_by_mode = {0: set(), 1: set()}
    for load in (0x1010, 0x1213, 0x2345):
        for flags in (0x0002, 0x0212, 0x0412, 0x0612):
            for redraw in (0, 1):
                seed = cases_checked
                memory = bytearray(MEMORY_TEMPLATE)
                image = relocated(IMAGE, ORACLE['relocations'], load)
                memory[load << 4:(load << 4) + len(image)] = image
                entry, command, _, _ = command_spans(redraw)
                rng = random.Random(0x374f + seed)
                regs = {name: rng.randrange(0x10000)
                        for name in oracle.REG_NAMES}
                regs.update(cs=load, ip=entry, ds=(load + 0x09a9) & 0xffff,
                            es=0x6500, ss=0x7000, sp=0x8000, si=0xbeef)
                final, final_flags, actual_memory, _, sites, edges = \
                    bounded_original(memory, regs, flags | 2, redraw,
                                     initialize=True)
                if final['si'] != LEVEL_TERRAIN or final['ip'] != command:
                    raise AssertionError('original terrain initialization MOV SI differs')
                if final_flags != ((flags | 2) & 0xffff):
                    raise AssertionError('terrain initialization MOV SI changed flags')
                for name in oracle.REG_NAMES:
                    expected = (LEVEL_TERRAIN if name == 'si' else
                                command if name == 'ip' else regs[name])
                    if final[name] != expected:
                        raise AssertionError(f'init {redraw}: {name} changed')
                if actual_memory != memory or sites != {entry} or edges:
                    raise AssertionError('terrain initialization prefix accounting differs')
                seen_by_mode[redraw] |= sites
                cases_checked += 1
    return cases_checked, seen_by_mode


def detect_mutations(directory, baseline, by_name):
    witnesses = ((1, 'reverse-byte-order-witness'),
                 (2, 'ah-ff-low-not-ff-witness'),
                 (3, 'advance-four-across-si-wrap-witness'))
    detected = []
    for mutation, name in witnesses:
        try:
            compare(library(directory, mutation), by_name[name])
        except AssertionError as error:
            detected.append(dict(mutation=mutation, case=name,
                                 reason=str(error)))
        else:
            raise AssertionError(f'TERRAIN_STREAM_MUTATION={mutation} survived')
    return detected


def main(directory):
    for start, end, expected_hash in (
        (SETUP_ENTRY, SETUP_EXIT,
         'bafd85725db0ea1282923fe487caf4e21e7ea4b8e34544cc4008fed8210e0781'),
        (REDRAW_ENTRY, REDRAW_EXIT,
         '9f020bf8d298a5bec587529e8f78cfd63ad79f5f4d8e11f5df321ea2303955cf'),
    ):
        if sha(IMAGE[start:end]) != expected_hash:
            raise RuntimeError(f'static terrain stream bytes changed at{start:04x}')

    baseline = cases()
    by_name = {case['name']: case for case in baseline}
    lib = library(directory)
    sites_by_mode = {0: set(), 1: set()}
    edges_by_mode = {0: set(), 1: set()}
    for case in baseline:
        sites, edges = compare(lib, case)
        redraw = case['redraw']
        sites_by_mode[redraw] |= sites
        edges_by_mode[redraw] |= edges

    expected_edges = {
        0: {(SETUP_COMMAND + 0x11, SETUP_CALL),
            (SETUP_COMMAND + 0x11, SETUP_EXIT)},
        1: {(REDRAW_COMMAND + 0x11, REDRAW_CALL),
            (REDRAW_COMMAND + 0x11, REDRAW_EXIT)},
    }
    for redraw in (0, 1):
        sites = set(command_sites(redraw))
        if sites_by_mode[redraw] != sites:
            raise AssertionError(f'missing command reader sites for redraw={redraw}')
        if edges_by_mode[redraw] != expected_edges[redraw]:
            raise AssertionError(f'command branch edges differ for redraw={redraw}: '
                                 f'{edges_by_mode[redraw]}')

    initializer_cases, init_sites = check_initializers()
    for redraw, sites in init_sites.items():
        entry, _, _, _ = command_spans(redraw)
        if sites != {entry}:
            raise AssertionError('MOV SI initializer site not covered exactly')
    mutations = detect_mutations(directory, baseline, by_name)
    input_paths = (
        'c/terrain_stream.c', 'c/terrain_stream.h', 'c/terrain_drawing.c',
        'c/terrain_drawing.h', 'c/drawing_render.h', 'c/drawing_plan.h',
        'c/drawing_inputs.h', 'c/drawing_source.h', 'c/special_blit.h',
        'c/regs.h', 'c/lemmings_sym.h', 'tests/terrain_commands.py',
        'tests/terrain_inputs.py', 'tests/dat_io.py', 'tests/dat_io_c.py',
        'tests/special_blit.py', 'tools/unpack.py', 'tools/cbuild.py',
        'tools/bounded_process.py', 'metadata/symbols.json')
    write_json(BUILD / 'terrain-commands-differential.json', dict(
        image='main', image_sha256=sha(IMAGE),
        ranges=[dict(start=SETUP_ENTRY, end_exclusive=SETUP_EXIT,
                     sha256=sha(IMAGE[SETUP_ENTRY:SETUP_EXIT]),
                     static_bytes=SETUP_EXIT - SETUP_ENTRY),
                dict(start=REDRAW_ENTRY, end_exclusive=REDRAW_EXIT,
                     sha256=sha(IMAGE[REDRAW_ENTRY:REDRAW_EXIT]),
                     static_bytes=REDRAW_EXIT - REDRAW_ENTRY)],
        case_count=len(baseline), initializer_case_count=initializer_cases,
        mutation_count=len(mutations), mutations_detected=mutations,
        executed_command_sites={str(redraw): sorted(sites)
                                for redraw, sites in sites_by_mode.items()},
        branch_edges={str(redraw): sorted(edges)
                      for redraw, edges in edges_by_mode.items()},
        translated_reader_bytes_per_loop=19,
        initializer_instruction_sites={str(mode): sorted(sites)
                                       for mode, sites in init_sites.items()},
        executed_instruction_addresses=sorted(set().union(
            *sites_by_mode.values(), *init_sites.values())),
        input_hashes={path: sha((ROOT / path).read_bytes())
                      for path in input_paths},
        domain=('Four separate big-endian byte loads, SI wrap and full CMP AX,FFFF '
                'flags for both 3752..3764 and3962..3974 prefixes. Original MOV SI '
                'entry instructions are checked separately. Child rendering and '
                'outer stream composition belong to terrain_drawing and the full '
                'terrain-stream connection suite.')))
    print(f'PASS terrain command reader: {len(baseline)} cases, '
          f'{sum(map(len, sites_by_mode.values()))} mode-sites, '
          f'{sum(map(len, edges_by_mode.values()))} edges, '
          f'{initializer_cases} init prefixes, {len(mutations)} reader mutants')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--bounded-worker':
        main(Path(sys.argv[2]))
    elif len(sys.argv) == 1:
        BUILD.mkdir(parents=True, exist_ok=True)
        (BUILD / 'terrain-commands-differential.json').unlink(missing_ok=True)
        with temporary_build_directory(prefix='terrain-commands-', parent=BUILD) as directory:
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--bounded-worker', directory], cwd=ROOT,
                        timeout=180, memory_mib=512)
    else:
        raise SystemExit('Unexpected terrain_commands arguments')

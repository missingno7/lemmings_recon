"""397D object drawing composed with the full native planar renderer."""
import ctypes
import gc
import sys
import time
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
import terrain_drawing as piece
import object_drawing_cases as fixtures
import drawing_caller_oracle as original_caller
from bounded_process import run_bounded, temporary_build_directory
from cbuild import compiler
from common import ROOT, BUILD, sha, write_json
from dat_io_c import Regs, MEM
from unpack import relocated

START, END, RETURN = 0x397d, 0x39ce, 0x39cd
LOCAL = {i.address: i for i in piece.MD.disasm(piece.IMAGE[START:END], START)}
INS = {p: i for p, i in piece.INS.items() if 0x8822 <= p < 0x9a90} | LOCAL
EDGES = {(p, i.operands[0].imm & 0xffff) for p, i in LOCAL.items()
         if i.group(piece.capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EDGES |= {(p, p + i.size) for p, i in LOCAL.items()
          if i.group(piece.capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
SOURCES = ('object_drawing', 'drawing_render', 'drawing_plan', 'drawing_inputs',
    'drawing_clip', 'drawing_dirty', 'drawing_dispatch', 'drawing_source',
    'aligned_opaque', 'aligned_masked', 'aligned_mask_effects', 'aligned_protected',
    'aligned_read_mask', 'shifted_mask_effects', 'shifted_opaque', 'shifted_masked',
    'shifted_protected', 'shifted_read_mask')
# Widths below8 become CL=0: the original word LOOP runs65,536 bytes per
# row, not256. The two-row fixture needs1,572,864 bus and1,048,576 VGA
# pixel events plus setup. Device order is streamed to keep memory bounded.
piece.common.MAX_BUS_EVENTS = 2_000_000
piece.common.MAX_VGA_EVENTS = 1_200_000


class Call(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint16) for n in ('data_segment', 'game_data_segment',
        'output_segment', 'code_segment', 'stack_segment', 'stack_offset',
        'second_source_cursor', 'width_state', 'control', 'flags')]


class Result(ctypes.Structure):
    _fields_ = [('state', piece.SourceState)] + [(n, ctypes.c_uint16) for n in
        ('data_segment', 'output_segment', 'code_segment', 'stopped', 'missing_provider',
         'changed_child_near', 'changed_far_return', 'ready_to_return')]


def library(directory, mutation=0):
    path = Path(directory) / f'object-drawing-{mutation}.dll'
    run_bounded([compiler(), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
        '-shared', '-DMUTATION=0', f'-DOBJECT_DRAWING_MUTATION={mutation}',
        '-I', str(ROOT / 'c'), *[str(ROOT / 'c' / (n + '.c')) for n in SOURCES],
        '-o', str(path)], timeout=60, memory_mib=256)
    lib = ctypes.CDLL(str(path))
    lib.lmn_draw_level_objects_adapter.argtypes = [MEM, ctypes.POINTER(Regs),
        ctypes.c_uint16, ctypes.POINTER(piece.common.RasterBus), ctypes.POINTER(piece.Ports)]
    lib.lmn_draw_level_objects_adapter.restype = None
    lib.lmn_draw_level_objects_core.argtypes = [MEM, ctypes.POINTER(Call),
        ctypes.POINTER(piece.common.RasterBus), ctypes.POINTER(piece.Ports)]
    lib.lmn_draw_level_objects_core.restype = Result
    return lib


def cases():
    out = fixtures.cases()

    def add(name, row=None, **kwargs):
        objects = () if row is None else (row,)
        independent = kwargs.pop('independent', False)
        out.append(dict(name=name, seed=len(out), real=False, objects=objects,
                        independent=independent, **kwargs))

    visible = (0, 16, 0, 0x0001, 8, 1, 0x1000, 0x7000)
    clipped = (0, 8191, 5, 0x000f, 8, 1, 0x1000, 0x7000)
    for effect in (0x20, 0x40):
        for backwards in (False, True):
            add(f'masked-effect-{effect:02x}-{backwards}',
                (0, 19, 3, effect | 3, 24, 3, 0x1000, 0x7000), df=backwards,
                independent=True)
    for sp in (0, 1, 0xffff):
        add(f'stack-wrap-{sp:04x}', visible, sp=sp)
    add('stack-physical-wrap', clipped, ss=0xffff, sp=0xffff)
    add('distinct-incoming-DS', visible, data_segment=0x6000)
    for backwards in (False, True):
        add(f'source-physical-wrap-{backwards}', visible,
            source_segment=0xffff, df=backwards)
    add('live-DS-vga-mirror-stack-alias', visible, sp=0x001a,
        expected_ds=0xff08)
    add('live-saved-count-and-outer-return', clipped, same_segments=True,
        sp=0x66fa, expected_ip=1, expected_si=0x17e7, expected_di=0x0ff3)
    add('changed-far-CS', (0, 8191, 5, 0x000f, 16, 1, 0x1000, 0x7000),
        same_segments=True, sp=0x66ff, load=0x1010,
        expected='changed-child-far', expected_cs=0x0210)
    add('changed-far-vga-mirror', visible, sp=0x0012,
        clear_mutant_definitions=True, expected='changed-child-far',
        expected_cs=0, expected_ip=0x0802)
    add('changed-dirty-near-return', (0, 16, 0, 0x000f, 8, 8, 0x1000, 0x7000),
        sp=0x480a, dirty=255, dirty_base=0x47fd,
        expected='changed-child-near', expected_ip=0x8801)
    for provider in ('none', 'missing-in', 'missing-out'):
        add(f'read-mask-provider-{provider}',
            (0, 19, 3, 0x4003, 24, 3, 0x1000, 0x7000),
            provider=provider, expected='provider-stop')
    return out


def prepare(case):
    memory, regs, flags, game_ds = fixtures.prepare(case)
    if 'data_segment' in case:
        previous = regs['ds']
        target = case['data_segment']
        snapshot = bytes(memory[(previous << 4):(previous << 4) + 0x10000])
        memory[target << 4:(target << 4) + 0x10000] = snapshot
        regs.update(ds=target, es=target)
    if case.get('same_segments'):
        regs['ss'] = regs['ds']
    else:
        regs['ss'] = case.get('ss', regs['ss'])
    regs['sp'] = case.get('sp', regs['sp'])
    piece.oracle.put16(memory, regs['ss'], regs['sp'], case.get('outer_ip', 0xeed1))
    for ds in {regs['ds'], game_ds}:
        if 'dirty' in case:
            memory[piece.oracle.at(ds, piece.field('DrawingDirtyCellsEnabledByte'))] = case['dirty']
        if 'dirty_base' in case:
            piece.oracle.put16(memory, ds, piece.field('DrawingDirtyCellMapOffset'), case['dirty_base'])
    if 'expected_ds' in case:
        for n in range(256):
            memory[piece.oracle.at(case['expected_ds'], piece.field('LevelObjectDefinitions') + n)] = 0
    if case.get('clear_mutant_definitions'):
        # If the far-return mutation hides SS:0008/000A mirror writes, the
        # live restored DI=FF08 advances toFF10. Make those remaining31 X
        # words inactive so that the faulty caller finishes under its budget.
        for n in range(31):
            for byte in (0, 1):
                memory[piece.oracle.at(regs['ds'], (0xff10 + n * 8 + byte) & 0xffff)] = 0
    return memory, regs, flags, game_ds


def compare(lib, case, *, core=False):
    memory, regs, flags, game_ds = prepare(case)
    c = piece.common.TraceDevice(bytearray(memory), case['seed'] + START)
    o = piece.common.TraceDevice(bytearray(memory), case['seed'] + START)
    c.vga.trace = original_caller.DeviceTrace()
    o.vga.trace = original_caller.DeviceTrace()
    ports = piece.byte_ports(c)
    provider = case.get('provider')
    if provider == 'none':
        ports = None
    elif provider == 'missing-in':
        ports = piece.Ports(None, ports.out_byte, piece.IN_BYTE())
    elif provider == 'missing-out':
        ports = piece.Ports(None, piece.OUT_BYTE(), ports.in_byte)
    pointer = None if ports is None else ctypes.byref(ports)
    state = Regs(**regs, flags=flags)
    start_time = time.monotonic()
    if core:
        call = Call(regs['ds'], game_ds, regs['es'], regs['cs'], regs['ss'], regs['sp'],
                    regs['bx'], regs['dx'], regs['bp'], flags)
        result = lib.lmn_draw_level_objects_core(
            (ctypes.c_uint8 * (1 << 20)).from_buffer(c.memory), ctypes.byref(call),
            ctypes.byref(c.bus), pointer)
        s = result.state
        state = Regs(s.work_value, s.second_source_cursor, s.packed_counts, s.width_state,
            s.source_cursor, s.destination_cursor, s.control, s.stack_offset,
            result.code_segment, result.data_segment, result.output_segment, regs['ss'],
            s.continuation, s.flags)
    else:
        lib.lmn_draw_level_objects_adapter(
            (ctypes.c_uint8 * (1 << 20)).from_buffer(c.memory), ctypes.byref(state),
            game_ds, ctypes.byref(c.bus), pointer)
    c.check(case['name'])
    pending = None
    independent_count = 0
    child_count = 0
    pending_fields = None
    body_families = {}

    def observe(off, cpu, device):
        nonlocal pending, independent_count, child_count, pending_fields
        if off == 0x398e and case.get('independent'):
            ds = cpu.reg_read(piece.oracle.REG['ds'])
            definition = cpu.reg_read(piece.oracle.REG['di'])
            slot = cpu.reg_read(piece.oracle.REG['si'])
            be = lambda offset: (device.memory[piece.oracle.at(ds, offset)] << 8) | device.memory[
                piece.oracle.at(ds, (offset + 1) & 0xffff)]
            x = be(definition)
            pending_fields = None if x == 0 else (ds, definition, slot, x)
        if off == 0x8822:
            child_count += 1
            if pending_fields is not None:
                ds, definition, slot, x = pending_fields
                be = lambda offset: (device.memory[piece.oracle.at(ds, offset)] << 8) | device.memory[
                    piece.oracle.at(ds, (offset + 1) & 0xffff)]
                source = piece.oracle.get16(device.memory, ds, (slot + 0x17) & 0xffff)
                mask = piece.oracle.get16(device.memory, ds, (slot + 8) & 0xffff)
                expected = dict(ax=x, bx=be(definition + 2), bp=be(definition + 6) & 0xfffe,
                    dx=device.memory[piece.oracle.at(ds, slot + 4)],
                    cx=0x0400 | device.memory[piece.oracle.at(ds, slot + 5)],
                    si=source, di=(mask + source) & 0xffff)
                for name, value in expected.items():
                    piece.common.require(cpu.reg_read(piece.oracle.REG[name]) == value,
                        f'{case["name"]}: independent renderer input {name}')
        if off in piece.FAMILIES:
            family = piece.FAMILIES[off]
            body_families[family] = body_families.get(family, 0) + 1
        if not case.get('independent'):
            return
        if off in piece.FAMILIES:
            entry = {n: cpu.reg_read(r) for n, r in piece.oracle.REG.items()}
            entry['flags'] = cpu.reg_read(piece.x.UC_X86_REG_EFLAGS)
            piece.bitmap.configure(piece.FAMILIES[off])
            pending = piece.render._independent_planes(device.vga.planes,
                device.memory, entry, game_ds)
        elif INS[off].mnemonic == 'retf' and pending is not None:
            piece.common.require(pending == device.vga.planes,
                                 f'{case["name"]}: independent object plane footprint')
            independent_count += 1
            pending = None

    stops = (0x969c,) if provider else ((RETURN,) if core else ())
    actual, mask, sites, edges, boundary, _child, _body = original_caller.original(
        case, o, regs, flags, instructions=INS, far_calls={0x39bd},
        continuations=stops, observe=observe, max_steps=3_000_000)
    for name in piece.oracle.REG_NAMES:
        piece.common.require(getattr(state, name) == actual[name],
            f'{case["name"]}:{name} C={getattr(state,name):04x}/ASM={actual[name]:04x};{boundary}')
    piece.common.require(not ((state.flags ^ actual['flags']) & mask),
                         f'{case["name"]}: defined boundary flags differ')
    piece.common.require(c.memory == o.memory, f'{case["name"]}: whole RAM differs')
    piece.common.compare_event_traces(c.events, o.events, case['name'])
    piece.common.require(c.vga.state() == o.vga.state(), f'{case["name"]}: VGA state differs')
    piece.common.require(c.vga.trace.signature() == o.vga.trace.signature(),
                         f'{case["name"]}: VGA order differs')
    expected_boundary = ('continuation' if core else 'outer-return')
    if provider:
        expected_boundary = 'continuation'
    elif 'expected' in case:
        expected_boundary = case['expected']
    piece.common.require(boundary[0] == expected_boundary, f'{case["name"]}: wrong boundary {boundary}')
    for key, name in (('expected_ds', 'ds'), ('expected_cs', 'cs'),
                      ('expected_si', 'si'), ('expected_di', 'di'), ('expected_ip', 'ip')):
        if key in case and not (core and key == 'expected_ip' and boundary[0] == 'continuation'):
            piece.common.require(actual[name] == case[key], f'{case["name"]}: live {name} fixture differs')
    if core:
        ready = boundary == ('continuation', regs['cs'], RETURN)
        piece.common.require(result.ready_to_return == ready and result.stopped == (not ready),
                             f'{case["name"]}: core boundary status differs')
        piece.common.require(result.missing_provider == bool(provider),
                             f'{case["name"]}: core provider status differs')
        piece.common.require(result.changed_far_return == (boundary[0] == 'changed-child-far'),
                             f'{case["name"]}: core far-return status differs')
        piece.common.require(result.changed_child_near == (boundary[0] == 'changed-child-near'),
                             f'{case["name"]}: core near-return status differs')
    for lo, hi in ((START, END), (0x8822, 0x9a90)):
        at = (regs['cs'] << 4) + lo
        expected_code = relocated(piece.IMAGE, piece.ORACLE['relocations'], regs['cs'])[lo:hi]
        if o.memory[at:at + hi - lo] != expected_code:
            raise piece.common.VerificationFailure(f'{case["name"]}: executing code modified')
    return dict(name=case['name'], boundary=boundary, child_calls=child_count,
        body_families=body_families,
        independently_checked_bodies=independent_count, bus_events=c.events.count,
        executed_instruction_addresses=sorted(sites), branch_edges=sorted(edges),
        seconds=round(time.monotonic() - start_time, 3))


def input_hashes():
    dependencies = {f'c/{name}{ext}' for name in SOURCES for ext in ('.c', '.h')}
    dependencies |= {'tests/object_drawing.py', 'tests/object_drawing_cases.py',
        'tests/drawing_caller_oracle.py', 'tests/terrain_drawing.py', 'tests/object_graphics.py',
        'tests/drawing_render.py', 'tests/drawing_bitmap.py', 'tests/drawing_aligned_render.py',
        'tests/drawing_masked_render.py', 'tests/drawing_shifted_render.py',
        'tests/aligned_masked.py', 'tests/aligned_read_mask.py', 'tests/dat_io.py',
        'tests/dat_io_c.py', 'tests/minimap_vga.py', 'tests/special_blit.py', 'tests/resource_rle.py',
        'c/regs.h', 'c/lemmings_sym.h', 'c/special_blit.h', 'metadata/symbols.json',
        'metadata/inputs.json', 'tools/cbuild.py', 'tools/bounded_process.py',
        'tools/unpack.py', 'tools/resources.py', 'tools/common.py', 'assets/vgalemmi.exe'}
    dependencies |= {f'assets/level{n:03d}.dat' for n in range(10)}
    dependencies |= {f'assets/ground{n}o.dat' for n in range(5)}
    return {p: sha((ROOT / p).read_bytes()) for p in sorted(dependencies)}


def worker(directory, selection=()):
    initial_hashes = input_hashes()
    baseline = cases()
    if selection:
        baseline = [case for case in baseline if case['name'] in selection]
        if len(baseline) != len(selection):
            raise RuntimeError('Unknown selected object case')
    lib = library(directory)
    results = []
    core_probes = 0
    for case in baseline:
        row = compare(lib, case)
        if not case.get('real'):
            compare(lib, case, core=True)
            core_probes += 1
        results.append(row)
        if not selection:
            write_json(BUILD / 'object-drawing-progress.json', dict(
                accepted=False, expected_case_count=len(baseline),
                input_hashes=initial_hashes, cases=results))
        print(f'PASS {row["name"]}: {row["child_calls"]} objects, {row["bus_events"]} events, '
              f'{row["seconds"]}s', flush=True)
        gc.collect()
    if selection:
        return
    sites = {p for row in results for p in row['executed_instruction_addresses']}
    edges = {tuple(edge) for row in results for edge in row['branch_edges']}
    piece.common.require(set(LOCAL) <= sites, f'Missing object caller sites: {set(LOCAL)-sites}')
    piece.common.require(EDGES <= edges, f'Missing object edges: {EDGES-edges}')
    families = {name for row in results for name in row['body_families']}
    piece.common.require({'opaque','masked','protected','read-mask','effect20','effect40'} <= families,
                         f'Missing ordinary aligned object bodies: {families}')
    mutations = []
    by_name = {c['name']: c for c in baseline}
    for mutation, name in ((1, 'opaque-bit0-cleared'),
                           (2, 'live-DS-vga-mirror-stack-alias'),
                           (3, 'changed-far-vga-mirror'),
                           (4, 'live-saved-count-and-outer-return')):
        try:
            compare(library(directory, mutation), by_name[name])
        except piece.common.Mismatch as error:
            mutations.append(dict(mutation=mutation, case=name, reason=str(error)))
        else:
            raise piece.common.VerificationFailure(f'Object drawing mutation{mutation} survived')
        gc.collect()
    if input_hashes() != initial_hashes:
        raise piece.common.VerificationFailure('Object drawing inputs changed during campaign')
    write_json(BUILD / 'object-drawing-differential.json', dict(
        image='main', image_sha256=sha(piece.IMAGE), case_count=len(results),
        core_boundary_case_count=core_probes, mutation_count=len(mutations),
        mutations_detected=mutations, cases=results, translated_code_bytes=END - START,
        caller_instruction_addresses=sorted(LOCAL), executed_instruction_addresses=sorted(sites),
        branch_edges=sorted(edges), routine=dict(start=START, end_exclusive=END,
            bytes=piece.IMAGE[START:END].hex(), sha256=sha(piece.IMAGE[START:END])),
        input_hashes=initial_hashes,
        limits=dict(worker_timeout_seconds=300,windows_process_commit_mib=512,
            windows_tree_commit_mib=768,bus_events=piece.common.MAX_BUS_EVENTS,
            vga_events=piece.common.MAX_VGA_EVENTS,instructions=3_000_000),
        body_families=sorted(families),
        domain='397D..39CD object loop directly composes native8822; constructed state, all80 '
            'LEVEL/GROUND object-copy entry states (378A modeled in setup), live DS/cursors/'
            'count/near/far returns, provider seams; '
            'full RAM/registers/defined flags/ordered bus/VGA and independent plane/input checks. '
            'Requires intact executing code; arbitrary providers, IRQ/timing and394F remain open.'))
    print(f'PASS object drawing:{len(results)} cases,{len(LOCAL)} caller/{len(sites)} integrated sites,'
          f'{len(edges)} edges,{core_probes} core probes,{len(mutations)} mutants', flush=True)


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2], sys.argv[3:])
    elif len(sys.argv) == 1 or sys.argv[1] == '--selected':
        BUILD.mkdir(exist_ok=True)
        if len(sys.argv) == 1:
            (BUILD / 'object-drawing-differential.json').unlink(missing_ok=True)
        with temporary_build_directory(prefix='object-drawing-', parent=BUILD) as directory:
            run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory,
                         *sys.argv[2:]], cwd=ROOT, timeout=300, memory_mib=512)
    else:
        raise SystemExit('Unexpected object_drawing arguments')

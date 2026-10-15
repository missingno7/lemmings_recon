"""Bounded 394F redraw composition, including declared special/DOS services."""
import ctypes
import gc
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
import object_drawing as objects
import level_drawing as initialize
import special_setup as special
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, sha, write_json, read_json

piece = objects.piece
oracle = piece.oracle
common = piece.common
START, END = 0x394f, 0x39ce
LOCAL = {i.address: i for lo, hi in ((START, 0x395e), (0x395f, END))
         for i in piece.MD.disasm(piece.IMAGE[lo:hi], lo)}
EDGES = {(p, i.operands[0].imm & 0xffff) for p,i in LOCAL.items()
         if i.group(piece.capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EDGES |= {(p, p+i.size) for p,i in LOCAL.items() if i.mnemonic != 'jmp'
          and (i.group(piece.capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop'))}
COPY = {i.address: i for i in piece.MD.disasm(piece.IMAGE[0x378a:0x37c2], 0x378a)}
INS = piece.INS | initialize.INS | COPY | LOCAL | special.INS
SOURCES = tuple(dict.fromkeys(('level_redraw', 'level_drawing', 'vga_clear',
    'drawing_layout', 'terrain_stream', 'terrain_drawing', 'object_graphics',
    *objects.SOURCES, 'special_setup', 'resource_rle', 'special_blit', 'dat_load',
    'dat_files', 'dat_cache', 'dat_section', 'dat_io', 'dat')))


class Call(ctypes.Structure):
    _fields_ = [('state', piece.SourceState)] + [(n, ctypes.c_uint16) for n in
        ('data_segment', 'output_segment', 'code_segment', 'stack_segment',
         'game_data_segment')]


class Services(ctypes.Structure):
    _fields_ = [('dat_segments', ctypes.c_void_p), ('special', ctypes.c_void_p),
                ('raster', ctypes.POINTER(common.RasterBus)),
                ('ports', ctypes.POINTER(piece.Ports))]


class DatSegments(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint16) for n in ('retry', 'lookup', 'read', 'failure')]


class Result(ctypes.Structure):
    _fields_ = ([('state', piece.SourceState)] + [(n, ctypes.c_uint16) for n in
        ('data_segment', 'output_segment', 'code_segment')] +
        [('status', ctypes.c_int)] + [(n, ctypes.c_uint16) for n in ('fatal',
         'missing_services', 'missing_provider', 'unported', 'changed_return',
         'ready_to_return')])


def library(directory, mutation=0):
    path = Path(directory) / f'level-redraw-{mutation}.dll'
    if not path.exists():
        build(path, mutation, 'level_redraw')
    lib = ctypes.CDLL(str(path))
    lib.lmn_redraw_level_adapter.argtypes = [objects.MEM, ctypes.POINTER(objects.Regs),
        ctypes.c_uint16, ctypes.POINTER(Services)]
    lib.lmn_redraw_level_adapter.restype = None
    lib.lmn_redraw_level_core.argtypes = [objects.MEM, ctypes.POINTER(Call),
                                        ctypes.POINTER(Services)]
    lib.lmn_redraw_level_core.restype = Result
    return lib


def command(x, y, control=0):
    return ((x & 8191) | ((control & 7) << 13), (((y + 4) & 511) << 7) | 2)


def cases():
    out = []

    def add(name, **kw):
        rows = kw.pop('objects', ())
        out.append(dict(name=name, seed=len(out), real=False, objects=rows, **kw))

    for df in (False, True):
        add(f'inactive-df{df}', df=df)
        for flags in (1, 3, 0x23, 0x43, 0x4003, 0x8003):
            add(f'object-{flags:04x}-df{df}', df=df,
                objects=((0, 19, 3, flags, 24, 3, 0x1000, 0x7000),))
        add(f'terrain-and-object-df{df}', df=df,
            commands=[command(131, 5), command(160, -2, 1)],
            objects=((31, 16, 0, 1, 8, 1, 0x1000, 0x7000),))
    for sp in (0, 1, 0xffff):
        add(f'stack-{sp:04x}', sp=sp, commands=[command(8191, 5)])
    add('stack-physical-wrap', ss=0xffff, sp=0xffff)
    add('distinct-DS', data_segment=0x6000, commands=[command(131, 5)])
    add('changed-clear-return', sp=12, expected='changed-child-near')
    add('changed-layout-return', same_segments=True, sp=0x66fc,
        expected='changed-child-far')
    add('changed-copy-return', same_segments=True, sp=0x17cd,
        objects=((0, 16, 0, 1, 8, 1, 0x1000, 0x7000),),
        expected='changed-child-near', expected_ip=0)
    add('live-terrain-DS', same_segments=True, sp=0x6710,
        commands=[command(131, 5)], source_fill=0xc0,
        terrain_width=8, terrain_height=1, returned_ds=0x0018)
    for selector in (1, 0x80, 0xff):
        add(f'special-service-stop-{selector:02x}', selector=selector,
            expected='continuation', expected_ip=0x1a7b)
    for missing in ('all', 'read', 'write', 'out'):
        add(f'raster-service-stop-{missing}', missing_raster=missing,
            expected='continuation', expected_ip=START)
    for missing in ('none', 'missing-in', 'missing-out'):
        add(f'byte-provider-stop-{missing}', provider=missing,
            objects=((0, 19, 3, 0x4003, 24, 3, 0x1000, 0x7000),),
            expected='continuation', expected_ip=0x969c)
    add('special-direct', special_execute=True)
    add('special-incoming-df', special_execute=True, df=True)
    add('special-close-carry', special_execute=True, close_error=True)
    add('special-close-df', special_execute=True, close_df=True)
    add('special-file-fatal', special_execute=True, attribute_errors=1,
        retry_enabled=0, fatal=1, expected='continuation', expected_ip=0x1949)
    for read_error in (0, 1, 2, 3):
        add(f'special-decode-fatal-{read_error}', special_execute=True,
            read_error=read_error, fatal=2, expected='continuation', expected_ip=0x04d0)
    for asset_case in special.cases():
        if 'assets' in asset_case:
            add('redraw-' + asset_case['name'], special_execute=True,
                **{k:v for k,v in asset_case.items() if k not in ('name','seed')})
    return out


def prepare(case):
    if case.get('special_execute'):
        memory, regs, flags, game_ds, _ = special.prepare(case)
        regs['ip'] = START
        # Retain the special input/heap preparation; post-setup definitions
        # are independently inactive, so random slots cannot invent objects.
        for byte in range(256):
            memory[oracle.at(regs['ds'], 0x0feb + byte)] = 0
        memory[oracle.at(regs['ds'], piece.field('LevelSpecialGraphicsSetByte'))] = 1
        oracle.put16(memory, regs['ds'], piece.field('DrawingPageByteOffset'), 0)
        memory[oracle.at(regs['ds'], piece.field('DrawingDirtyCellsEnabledByte'))] = 0
        return memory, regs, flags, game_ds
    memory, regs, flags, game_ds = objects.prepare(case)
    regs['ip'] = START
    ds = regs['ds']
    for frame in {ds, game_ds}:
        oracle.put16(memory, frame, piece.field('GraphicsResourceInputSegment'), 0x4fff)
        memory[oracle.at(frame, piece.field('LevelSpecialGraphicsSetByte'))] = case.get('selector', 0)
        piece.record(memory, frame, 2, case.get('terrain_width', 24),
                     case.get('terrain_height', 3), 0x2000, 0x4000)
        for n, words in enumerate([*case.get('commands', []), (0xffff, 0x57ad)]):
            for byte, value in enumerate(b''.join(w.to_bytes(2, 'big') for w in words)):
                memory[oracle.at(frame, 0x10eb + n * 4 + byte)] = value
    for row in case.get('objects', ()):
        index = row[0]
        definition = piece.field('LevelObjectDefinitions') + index * 8
        objects.fixtures._write_be16(memory, ds, definition + 4, index)
        slot = piece.field('LevelObjectGraphicsRecords') + index * 28
        ground = piece.field('GroundResourceBuffer') + index * 28
        for byte in range(28):
            memory[oracle.at(ds, ground + byte)] = memory[oracle.at(ds, slot + byte)]
        # The first word makes the return-alias witness redirect to0000.
        oracle.put16(memory, ds, ground, 0)
    if 'source_fill' in case:
        memory[0x50000:0x60000] = bytes((case['source_fill'],)) * 65536
    if 'returned_ds' in case:
        returned = case['returned_ds']
        for byte in range(256):
            memory[oracle.at(returned, 0x0feb + byte)] = 0
        for byte, value in enumerate(b'\xff\xff\x35\x9a'):
            memory[oracle.at(returned, 0x10ef + byte)] = value
    return memory, regs, flags, game_ds


def special_providers(case, memory, game_ds):
    # Declared DOS fixture shares this exact canonical physical memory image.
    packet = case.get('data', special.decoder.section([('literal', b'GRAPHICS')]) +
                      special.decoder.section([('literal', b'OBJECTS')]))
    return special.providers(case | dict(data=packet), memory, game_ds)


def native_special_services(case, device, regs, game_ds):
    file, query, read, retry, close, trace = special_providers(case, device.memory, game_ds)

    def guarded(function, output, *args):
        try:
            for (name, _), value in zip(output.contents._fields_, function(*args)):
                setattr(output.contents, name, value)
        except BaseException as error:
            common.exit_worker(common.NATIVE_CALLBACK_EXIT, f'redraw DOS callback failed: {error}')

    @special.FILE
    def opened(ctx, memory, segment, offset, flags, output):
        guarded(file, output, 0x3d, segment, offset, flags)

    @special.FILE
    def attributes(ctx, memory, segment, offset, flags, output):
        guarded(file, output, 0x43, segment, offset, flags)

    @special.QUERY
    def queried(ctx, memory, segment, offset, flags, output):
        guarded(query, output, segment, offset, flags)

    @special.READ
    def read_bytes(ctx, memory, handle, segment, offset, count, flags, output):
        guarded(read, output, handle, segment, offset, count, flags)

    @special.RETRY_FN
    def retried(ctx, memory, call, output):
        #4B1C remains an independently tested external UI seam in this domain.
        common.exit_worker(common.NATIVE_CALLBACK_EXIT, 'unexpected redraw retry UI')

    @special.CLOSE
    def closed(ctx, memory, handle, value, flags, output):
        guarded(close, output, handle, value, flags)

    files = special.Services(None, opened, attributes, retried)
    io = special.Io(None, queried, read_bytes)
    # Deliberately NULL:394F supplies its exact canonical raster bus locally.
    services = special.SetupServices(ctypes.pointer(files), ctypes.pointer(io), None, None, closed)
    segments = DatSegments(*[oracle.get16(device.memory, regs['cs'], offset) for offset in
        (piece.field('CheckDatFile') + 0x33, piece.field('SelectCachedDatFile') + 0x50,
         piece.field('ReadDatBytes') + 8, piece.field('DatReadFailure') + 1)])
    return services, segments, trace, (opened, attributes, queried, read_bytes, retried,
                                      closed, files, io)


def original_special_services(case, device, game_ds):
    file, query, read, retry, close, trace = special_providers(case, device.memory, game_ds)

    def interrupt(cpu, number, target):
        if number != 0x21:
            raise common.VerificationFailure(f'Unexpected redraw INT{number:02x}')
        value = cpu.reg_read(oracle.REG['ax'])
        function = value >> 8
        segment = cpu.reg_read(oracle.REG['ds'])
        offset = cpu.reg_read(oracle.REG['dx'])
        flags = cpu.reg_read(piece.x.UC_X86_REG_EFLAGS)
        if function in (0x3d, 0x43):
            value, count, returned_flags = file(function, segment, offset, flags)
        elif function == 0x23:
            value, returned_flags = query(segment, offset, flags)
        elif function == 0x3f:
            value, returned_flags = read(cpu.reg_read(oracle.REG['bx']), segment, offset,
                                        cpu.reg_read(oracle.REG['cx']), flags)
        elif function == 0x3e:
            value, returned_flags = close(cpu.reg_read(oracle.REG['bx']), value, flags)
        else:
            raise common.VerificationFailure(f'Unexpected redraw DOS{function:02x}')
        # External provider writes are separate from instruction bus events.
        # Synchronize CPU mappings from canonical RAM without changing planes.
        cpu.mem_write(0, bytes(target.memory) * 2)
        cpu.reg_write(oracle.REG['ax'], value)
        if function == 0x43:
            cpu.reg_write(oracle.REG['cx'], count)
        cpu.reg_write(piece.x.UC_X86_REG_EFLAGS, returned_flags)

    return interrupt, trace


def compare(lib, case, *, core=False):
    memory, regs, flags, game_ds = prepare(case)
    c = common.TraceDevice(bytearray(memory), START + case['seed'])
    o = common.TraceDevice(bytearray(memory), START + case['seed'])
    c.vga.trace = objects.original_caller.DeviceTrace()
    o.vga.trace = objects.original_caller.DeviceTrace()
    ports = piece.byte_ports(c)
    provider = case.get('provider')
    if provider == 'none':
        ports = None
    elif provider == 'missing-in':
        ports = piece.Ports(None, ports.out_byte, piece.IN_BYTE())
    elif provider == 'missing-out':
        ports = piece.Ports(None, piece.OUT_BYTE(), ports.in_byte)
    raster = c.bus
    missing = case.get('missing_raster')
    if missing and missing != 'all':
        raster = common.RasterBus(None,
            common.READ() if missing == 'read' else raster.read_byte,
            common.WRITE() if missing == 'write' else raster.write_byte,
            common.OUT() if missing == 'out' else raster.out_word)
    services = Services(None, None, None if missing == 'all' else ctypes.pointer(raster),
                        None if ports is None else ctypes.pointer(ports))
    c_service_trace = o_service_trace = []
    interrupt = trace_instruction = None
    if case.get('special_execute'):
        child_services, segments, c_service_trace, callbacks = native_special_services(
            case, c, regs, game_ds)
        services.special = ctypes.addressof(child_services)
        services.dat_segments = ctypes.addressof(segments)
        interrupt, o_service_trace = original_special_services(case, o, game_ds)
        # Special/DAT/RLE cores access ordinary RAM directly. Their effects
        # retain the whole-memory comparison; strip and parent/other-child
        # raster accesses retain the ordered bus and phase-flag comparison.
        direct_ram = set(special.INS) - set(special.blit.INS)
        # special_setup consumes each strip's8342 RET directly in RAM;
        # this new parent consumes the special caller's1B41 RET via its bus.
        direct_ram |= {p for p,i in special.blit.INS.items() if i.mnemonic == 'ret'}
        direct_ram -= {p for p,i in special.LOCAL.items() if i.mnemonic == 'ret'}
        trace_instruction = lambda pc: pc not in direct_ram
    state = objects.Regs(**regs, flags=flags)
    if core:
        call = Call(piece.SourceState(regs['ax'], regs['bx'], regs['cx'], regs['dx'],
            regs['si'], regs['di'], regs['bp'], regs['sp'], flags, START),
            regs['ds'], regs['es'], regs['cs'], regs['ss'], game_ds)
        result = lib.lmn_redraw_level_core(
            (ctypes.c_uint8 * (1 << 20)).from_buffer(c.memory), ctypes.byref(call),
            ctypes.byref(services))
        s = result.state
        state = objects.Regs(s.work_value, s.second_source_cursor, s.packed_counts,
            s.width_state, s.source_cursor, s.destination_cursor, s.control,
            s.stack_offset, result.code_segment, result.data_segment,
            result.output_segment, regs['ss'], s.continuation, s.flags)
    else:
        lib.lmn_redraw_level_adapter((ctypes.c_uint8 * (1 << 20)).from_buffer(c.memory),
            ctypes.byref(state), game_ds, ctypes.byref(services))
    c.check(case['name'])
    continuations = (START,) if missing else ((0x1a7b,) if case.get('selector') else ())
    if provider:
        continuations += (0x969c,)
    if case.get('special_execute'):
        continuations += (0x1949, 0x04d0)
    if core:
        continuations += (0x39cd,)
    actual, mask, sites, edges, boundary, *_ = objects.original_caller.original(
        case, o, regs, flags, instructions=INS, far_calls={0x36a0, 0x39bd, 0x7cb5},
        continuations=continuations, max_steps=10_000_000,
        interrupt=interrupt, trace_instruction=trace_instruction)
    for name in oracle.REG_NAMES:
        common.require(getattr(state, name) == actual[name],
            f'{case["name"]}:{name} C={getattr(state,name):04x}/ASM={actual[name]:04x};{boundary}')
    common.require(not ((state.flags ^ actual['flags']) & mask),
                   f'{case["name"]}: defined boundary flags differ')
    common.require(c.memory == o.memory, f'{case["name"]}: whole RAM differs')
    common.compare_event_traces(c.events, o.events, case['name'])
    common.require(c.vga.state() == o.vga.state(), f'{case["name"]}: VGA state differs')
    common.require(c.vga.trace.signature() == o.vga.trace.signature(),
                   f'{case["name"]}: device order differs')
    common.require(c_service_trace == o_service_trace, f'{case["name"]}: DOS service trace differs')
    expected = case.get('expected', 'continuation' if core else 'outer-return')
    common.require(boundary[0] == expected, f'{case["name"]}: wrong boundary {boundary}')
    if 'expected_ip' in case:
        common.require(actual['ip'] == case['expected_ip'], f'{case["name"]}: witness target differs')
    if 'returned_ds' in case:
        common.require(actual['ds'] == case['returned_ds'], f'{case["name"]}: DS alias did not fire')
    if core:
        ready = boundary == ('continuation', regs['cs'], 0x39cd)
        common.require(result.ready_to_return == ready, f'{case["name"]}: ready status differs')
        common.require(bool(result.changed_return) == boundary[0].startswith('changed-child'),
                       f'{case["name"]}: changed-return status differs')
        common.require(bool(result.missing_services) == bool(missing or case.get('selector')),
                       f'{case["name"]}: missing-service status differs')
        common.require(bool(result.missing_provider) == bool(provider),
                       f'{case["name"]}: missing-provider status differs')
        common.require(result.fatal == case.get('fatal', 0), f'{case["name"]}: fatal status differs')
        expected_status = (1 if missing or case.get('selector') else 2 if provider else
            4 if case.get('fatal') == 1 else 5 if case.get('fatal') == 2 else
            6 if boundary[0].startswith('changed-child') else 0 if ready else 3)
        common.require(result.status == expected_status, f'{case["name"]}: typed stop status differs')
    return dict(name=case['name'], boundary=boundary, bus_events=c.events.count,
        executed_instruction_addresses=sorted(sites), branch_edges=sorted(edges),
        core_status=({name:getattr(result,name) for name in ('status','fatal',
            'missing_services','missing_provider','changed_return','ready_to_return')}
            if core else None))


def input_hashes():
    dependencies = set(objects.input_hashes())
    dependencies |= {f'c/{name}{ext}' for name in SOURCES for ext in ('.c', '.h')}
    dependencies |= {'tests/level_redraw.py', 'tests/level_drawing.py', 'tests/special_setup.py',
        'tests/dat_load.py', 'tests/dat_files.py', 'tests/dat_section.py'}
    dependencies |= {asset for case in cases() for asset in case.get('assets', ())}
    return {p: sha((ROOT / p).read_bytes()) for p in sorted(dependencies)}


def case_worker(directory, index, mutation):
    case = cases()[index]
    lib = library(directory, mutation)
    path = Path(directory) / f'case-{index}-m{mutation}.json'
    if mutation:
        try:
            compare(lib, case)
        except common.Mismatch as error:
            write_json(path, dict(mutation=mutation, case=case['name'], reason=str(error)))
        else:
            raise common.VerificationFailure(f'Redraw mutation{mutation} survived')
        return
    row = compare(lib, case)
    core_row = compare(lib, case, core=True)
    row['core_boundary'] = core_row['boundary']
    row['core_status'] = core_row['core_status']
    write_json(path, row)
    print(f'PASS {row["name"]}: {row["boundary"]}, {row["bus_events"]} events', flush=True)


def run_case(directory, index, mutation=0):
    # Every case starts from a new process, including separate mutant witnesses.
    # A guard, crash or timeout propagates as failure, never as a mutant hit.
    path = Path(directory) / f'case-{index}-m{mutation}.json'
    path.unlink(missing_ok=True)
    run_bounded([sys.executable, str(Path(__file__).resolve()), '--case-worker',
                 directory, str(index), str(mutation)], cwd=ROOT, timeout=300,
                memory_mib=384)
    return read_json(path)


def worker(directory, selected=()):
    hashes = input_hashes()
    baseline = cases()
    if selected:
        baseline = [c for c in baseline if c['name'] in selected]
        if len(baseline) != len(selected):
            raise RuntimeError('Unknown redraw case selection')
    library(directory)
    rows = []
    for case in baseline:
        index = next(i for i,c in enumerate(cases()) if c['name'] == case['name'])
        row = run_case(directory, index)
        rows.append(row)
        gc.collect()
    if selected:
        return
    mutations = []
    for mutation, name in ((1, 'inactive-dfFalse'), (2, 'live-terrain-DS'),
                            (3, 'changed-copy-return')):
        library(directory, mutation)
        index = next(i for i,c in enumerate(cases()) if c['name'] == name)
        mutations.append(run_case(directory, index, mutation))
        gc.collect()
    if input_hashes() != hashes:
        raise common.VerificationFailure('Redraw inputs changed during verification')
    sites = {p for row in rows for p in row['executed_instruction_addresses']}
    edges = {tuple(e) for row in rows for e in row['branch_edges']}
    if set(LOCAL) - sites:
        raise common.VerificationFailure(f'Unexecuted redraw caller sites: {set(LOCAL)-sites}')
    if EDGES - edges:
        raise common.VerificationFailure(f'Unobserved redraw caller edges: {EDGES-edges}')
    write_json(BUILD / 'level-redraw-differential.json', dict(
        image='main', image_sha256=sha(piece.IMAGE), case_count=len(rows), core_boundary_case_count=len(rows),
        mutation_count=len(mutations), mutations_detected=mutations, cases=rows,
        caller_instruction_addresses=sorted(LOCAL), executed_instruction_addresses=sorted(sites),
        branch_edges=sorted(edges), caller_branch_edges=sorted(EDGES), input_hashes=hashes,
        native_code_ranges=[[START,0x395e],[0x395f,END]], translated_code_bytes=126,
        domain='394F normal and special resource/terrain/copy/object composition; declared DOS '
               'providers, ordinary-RAM special input/heap/stack, intact code/active special '
               'returns, no retry UI, IRQ or timing; ledger byte ranges exclude UNKNOWN395E.',
        limits=dict(case_worker_timeout_seconds=300, coordinator_timeout_seconds=15600,
                    windows_process_commit_mib=512, case_worker_commit_mib=384,
                    windows_tree_commit_mib=768, bus_events=common.MAX_BUS_EVENTS,
                    vga_events=common.MAX_VGA_EVENTS, instructions=10_000_000)))
    print(f'PASS redraw: {len(rows)} cases, {len(LOCAL)} caller/{len(sites)} integrated '
          f'sites, {len(edges)} edges, {len(mutations)} mutants', flush=True)


if __name__ == '__main__':
    if len(sys.argv) == 5 and sys.argv[1] == '--case-worker':
        case_worker(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    elif len(sys.argv) >= 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2], sys.argv[3:])
    elif len(sys.argv) == 1 or sys.argv[1] == '--selected':
        BUILD.mkdir(exist_ok=True)
        if len(sys.argv) == 1:
            (BUILD / 'level-redraw-differential.json').unlink(missing_ok=True)
        with temporary_build_directory(prefix='level-redraw-', parent=BUILD) as directory:
            run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory,
                         *sys.argv[2:]], cwd=ROOT, timeout=15600, memory_mib=512)
    else:
        raise SystemExit('Unexpected level_redraw arguments')

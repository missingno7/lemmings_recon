"""Pinned 5017/5019/7E76 background caller and native renderer composition."""
import ctypes
import gc
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
import text_glyph as glyph
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, sha, write_json

piece, common, caller, video = glyph.piece, glyph.common, glyph.caller, glyph.video
IMAGE, ORACLE = glyph.IMAGE, glyph.ORACLE
ENTRIES = (0x5017, 0x5019, 0x7e76)
RET = 0x7eb1
PREFIX = bytes.fromhex('33dbe95a2e')
TAIL = bytes.fromhex('a1ee1fa3e41fb9040053515333c0bd0c00ba4001b96802be00009a22880000b840015bbd0c00ba4001b96802be00009a22880000595b83c368e2cec3')
LOCAL = {i.address: i for b, p in ((PREFIX, ENTRIES[0]), (TAIL, ENTRIES[2]))
         for i in piece.MD.disasm(b, p)}
INS = LOCAL | {p: i for p, i in piece.INS.items() if 0x8822 <= p < 0x9a90}
EDGES = {(0x5019, 0x7e76), (0x7eaf, 0x7e7f), (0x7eaf, RET)}
REPORT = BUILD / 'background-drawing-differential.json'
ORIGINAL_REPORT = BUILD / 'background-drawing-contract-original.json'


def cases():
    rows = []
    def add(name, **kw):
        rows.append(dict(name=name, seed=len(rows), **kw))
    for entry in range(3):
        for df in (0, 1):
            add(f'entry-{entry}-df{df}', entry=entry, df=df, independent=True)
    for df in (0, 1):
        add(f'full-640x350-df{df}', screen_width=640, screen_height=350,
            df=df, independent=True)
    add('retry-row-78', entry=1, top=78, screen_width=640, screen_height=350, independent=True)
    add('page-offset-wrap', origin=0xfff8, independent=True)
    for top in (-104, -1, 78, 312, 350, 416, 0x7fff, 0xff98):
        add(f'row-{top}', entry=1, top=top, independent=True)
    for width, height in ((8, 8), (320, 104), (328, 105), (640, 208)):
        add(f'layout-{width}x{height}', screen_width=width, screen_height=height,
            independent=True)
    for sp in (0, 1, 0xfffe, 0xffff):
        add(f'stack-{sp:04x}', sp=sp, entry=1, top=416)
    add('stack-physical-wrap', ss=0xffff, sp=0xf, entry=1, top=416)
    add('distinct-DS', ds=0x3000, independent=True)
    add('source-A20', source_segment=0xffff, independent=True)
    add('source-VGA', source_segment=0xa000)
    add('stack-VGA', ss=0xa000, entry=1, top=416)
    # The dirty leaf writes exactly one byte at SS:base+1 for this layout.
    # Each witness changes a different caller save while leaving child frames intact.
    for name, delta, popped, value in (('live-second-row', -7, 0x7e99, 1),
            ('live-counter', -5, 0x7eab, 1), ('live-next-row', -3, 0x7eac, 1)):
        add(name, screen_width=16, screen_height=8, dirty=255,
            base=(0x8000 + delta) & 65535, pop_site=popped, pop_value=value)
    add('changed-first-far', screen_width=16, screen_height=8, dirty=255,
        base=0x7ff5, expected='changed-child-far', status=2)
    add('changed-inner-near', screen_width=16, screen_height=8, dirty=255,
        base=0x7ff3, expected='changed-child-near', status=1)
    return rows


def prepare(case):
    memory, regs, flags, game_ds = piece.prepare(case)
    regs.update(ip=ENTRIES[case.get('entry', 0)], bx=case.get('top', 0x1234) & 65535)
    for ds in {regs['ds'], game_ds}:
        for name, value in (('DrawingWidthPixels', case.get('screen_width', 64)),
                ('DrawingHeight', case.get('screen_height', 32)),
                ('DrawingPitchBytes', case.get('screen_width', 64) // 8),
                ('DrawingOrigin', case.get('origin', 0)), ('DrawingPageByteOffset', 0),
                ('UiGraphicsBufferSegment', case.get('source_segment', 0x5000))):
            piece.oracle.put16(memory, ds, piece.field(name), value)
    piece.oracle.put16(memory, regs['ss'], regs['sp'], 0xeed1)
    return memory, regs, flags, game_ds


def device_for(memory, seed):
    device = common.TraceDevice(bytearray(memory), 0x7e76 + seed)
    device.vga.trace = caller.DeviceTrace()
    return device


def original_case(case, core):
    memory, regs, flags, game_ds = prepare(case)
    device = device_for(memory, case['seed'])
    requests, returned, pending, pops, geometry = [], [], [], [], []
    def observe(pc, cpu, _device):
        state = None
        if pc == 0x8822 or pc in piece.FAMILIES:
            state = {k: cpu.reg_read(r) for k, r in piece.oracle.REG.items()}
            state['flags'] = cpu.reg_read(piece.x.UC_X86_REG_EFLAGS)
        if pc == 0x8822:
            requests.append((state['ax'], state['bx'], state['cx'], state['dx'],
                state['si'], state['bp'], state['ds']))
        if pc == case.get('pop_site'):
            pops.append(cpu.reg_read(piece.oracle.REG['cx' if pc == 0x7eab else 'bx']))
        if pc in piece.FAMILIES:
            geometry.append((state['cx'], state['dx'] >> 8))
        if case.get('independent') and pc in piece.FAMILIES:
            if pending: glyph.fail('Background body entered before previous return')
            pending.append((pc, state, bytes(device.memory), [bytearray(p) for p in device.vga.planes]))
        if pc in (0x7e95, 0x7eaa):
            returned.append(pc)
            if pending:
                address, entry, scratch, planes = pending.pop()
                glyph.bitmap.configure(piece.FAMILIES[address])
                if glyph.render._independent_planes(planes, scratch, entry, game_ds) != device.vga.planes:
                    glyph.fail(case['name'] + ': independent per-tile planes differ')
    result = caller.original(case, device, regs, flags, instructions=INS,
        far_calls={0x7e90, 0x7ea5}, stop_before=RET if core else None,
        max_steps=500000, observe=observe)
    actual, _mask, _sites, _edges, boundary, _child, _body = result
    if case.get('expected'):
        if boundary[0] != case['expected']:
            glyph.fail(case['name'] + ': wrong boundary ' + str(boundary))
    else:
        expected_boundary = 'ready-return' if core else 'outer-return'
        if boundary[0] != expected_boundary: glyph.fail(case['name'] + ': unexpected stop ' + str(boundary))
        if not case.get('pop_site'):
            top = 0 if case.get('entry', 0) == 0 else regs['bx']
            expected = [(column, (top + row * 104) & 65535, 0x268, 320, 0, 12)
                        for row in range(4) for column in (0, 320)]
            if [r[:6] for r in requests] != expected:
                glyph.fail(case['name'] + ': independent tile requests differ ' + str(requests))
            if returned != [0x7e95, 0x7eaa] * 4: glyph.fail('All eight tile returns were not observed')
    if case.get('pop_site') and (not pops or pops[0] != case['pop_value']):
        glyph.fail(case['name'] + ': live saved word was not exercised ' + str(pops))
    if case['name'].startswith('full-640x350'):
        expected_geometry = [((height << 8) | width, 2)
            for height in (104, 104, 104, 38) for width in (40, 39)]
        if geometry != expected_geometry:
            glyph.fail('Full-screen clipping geometry differs ' + str(geometry))
    if case['name'] == 'live-counter' and len(requests) != 2:
        glyph.fail('Live counter did not shorten the loop to one row')
    return memory, regs, flags, game_ds, device, result, requests


class Native:
    def __init__(self, directory, mutation=0):
        self.lib = ctypes.CDLL(str(build(Path(directory) / f'background-m{mutation}.dll', mutation, 'background_drawing')))
        self.core = self.lib.lmn_draw_background_core
        self.core.argtypes = [video.MEM, ctypes.c_uint16, ctypes.c_uint16,
            ctypes.POINTER(video.State), ctypes.c_int, ctypes.POINTER(common.RasterBus), ctypes.POINTER(piece.Ports)]
        self.core.restype = glyph.Result
        self.adapter = self.lib.lmn_draw_background_adapter
        self.adapter.argtypes = [video.MEM, ctypes.POINTER(piece.Regs), ctypes.c_uint16,
            ctypes.c_int, ctypes.POINTER(common.RasterBus), ctypes.POINTER(piece.Ports)]
        self.adapter.restype = None


def compare(native, case, core):
    memory, regs, flags, game_ds, original, result, requests = original_case(case, core)
    actual, mask, sites, edges, boundary, _child, _body = result
    if native is not None:
        device = device_for(memory, case['seed'])
        ports = piece.byte_ports(device)
        if core:
            r = native.core(video.buffer(device.memory), regs['cs'], game_ds,
                ctypes.byref(video.to_state(dict(regs, flags=flags))), case.get('entry', 0),
                ctypes.byref(device.bus), ctypes.byref(ports))
            got = dict(video.state_dict(r.state), cs=r.code_segment, ip=r.continuation)
            common.require(r.status == case.get('status', 0), case['name'] + ': status differs')
        else:
            r = piece.Regs(**regs, flags=flags)
            native.adapter(video.buffer(device.memory), ctypes.byref(r), game_ds,
                case.get('entry', 0), ctypes.byref(device.bus), ctypes.byref(ports))
            got = {k: getattr(r, k) for k in (*piece.oracle.REG_NAMES, 'flags')}
        for k in piece.oracle.REG_NAMES:
            common.require(got[k] == actual[k], case['name'] + f': {k} {got[k]:04x}!={actual[k]:04x}')
        common.require(not ((got['flags'] ^ actual['flags']) & mask), case['name'] + ': flags differ')
        common.require(device.memory == original.memory, case['name'] + ': whole RAM differs')
        common.compare_event_traces(device.events, original.events, case['name'])
        common.require(device.vga.state() == original.vga.state(), case['name'] + ': VGA state differs')
        common.require(device.vga.trace.signature() == original.vga.trace.signature(), case['name'] + ': device order differs')
    return dict(name=case['name'], core=core, entry=regs['ip'], sites=sorted(sites),
                edges=sorted(edges), boundary=boundary, tile_requests=len(requests))


def input_hashes(native=False):
    paths = set(glyph.input_hashes(native)) | {'tests/background_drawing.py'}
    if native: paths |= {'c/background_drawing.c', 'c/background_drawing.h'}
    return {p: sha((ROOT / p).read_bytes()) for p in sorted(paths)}


def worker(directory=None):
    common.MAX_BUS_EVENTS = 600000
    common.MAX_VGA_EVENTS = 200000
    before = input_hashes(directory is not None)
    if (IMAGE[0x5017:0x501c] != PREFIX or IMAGE[0x7e76:0x7eb2] != TAIL or len(LOCAL) != 26
        or not all(any(r['linear'] == p for r in ORACLE['relocations']) for p in (0x7e93, 0x7ea8))):
        glyph.fail('Background bytes/boundaries/relocations differ')
    native = Native(directory) if directory is not None else None
    rows = []
    for case in cases():
        for core in (False, True): rows.append(compare(native, case, core))
        gc.collect()
    sites = {p for row in rows for p in row['sites']}
    edges = {tuple(e) for row in rows for e in row['edges']}
    if not set(LOCAL) <= sites or not EDGES <= edges: glyph.fail('Background caller site/edge coverage incomplete')
    mutants = []
    if native is not None:
        for mutation, name in ((1, 'entry-0-df0'), (2, 'live-second-row'),
                (3, 'live-counter'), (4, 'full-640x350-df0'), (5, 'entry-0-df0'), (6, 'changed-first-far')):
            lib = Native(directory, mutation)
            case = next(c for c in cases() if c['name'] == name)
            try: compare(lib, case, True)
            except common.Mismatch as error:
                mutants.append(dict(mutation=mutation, case=name, reason=str(error)))
            else: glyph.fail(f'BACKGROUND_DRAWING_MUTATION={mutation} survived')
            gc.collect()
    if before != input_hashes(native is not None): glyph.fail('Background verification inputs changed')
    write_json(REPORT if native else ORIGINAL_REPORT, dict(image='main', image_sha256=sha(IMAGE),
        case_count=len(cases()), boundaries_each_case=2, caller_sites=26, caller_bytes=65,
        translated_code_bytes=65 if native else 0,
        native_code_ranges=[[0x5017, 0x501c], [0x7e76, 0x7eb2]] if native else [],
        caller_instruction_addresses=sorted(LOCAL), executed_instruction_addresses=sorted(sites),
        caller_branch_edges=sorted(EDGES), branch_edges=sorted(edges), cases=rows,
        mutation_count=len(mutants), mutations_detected=mutants, input_hashes=before,
        c_coverage_claimed=native is not None,
        limits=dict(worker_seconds=180, windows_process_mib=384, windows_tree_mib=640,
            original_steps_per_call=500000, bus_events_per_call=600000, vga_events_per_call=200000),
        domain='5017/5019/7E76 constructed background tile loop; full640x350 and clipping/DF/wrap/livecaller saves, actual far/near returns and independent per-tile planes. Intact code, quiescent IRQs and permissive20bit word bus; native device timing and stack-limit faults remain open.'))
    print(f'PASS background drawing {"C" if native else "original"}: {len(cases())} fixtures x2 boundaries,26 caller/{len(sites)} integrated sites,{len(EDGES)} caller edges,{len(mutants)} completed mutants', flush=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--worker': worker(sys.argv[2]); return
    if sys.argv[1:] == ['--original-worker']: worker(); return
    original = sys.argv[1:] == ['--original-only']
    if sys.argv[1:] and not original: raise SystemExit('Unexpected background arguments')
    report = ORIGINAL_REPORT if original else REPORT
    report.unlink(missing_ok=True)
    try:
        if original:
            run_bounded([sys.executable, str(Path(__file__).resolve()), '--original-worker'], cwd=ROOT, timeout=180, memory_mib=384)
        else:
            with temporary_build_directory(prefix='background-drawing-', parent=BUILD) as directory:
                run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory], cwd=ROOT, timeout=180, memory_mib=384)
    except BaseException:
        report.unlink(missing_ok=True)
        raise


if __name__ == '__main__': main()

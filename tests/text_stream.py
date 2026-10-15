"""Original 4D4D text records composed with the native glyph/renderer cores."""
import ctypes
import gc
import subprocess
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
import text_glyph as glyph
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, read_json, write_json, sha

piece, common, caller, video = glyph.piece, glyph.common, glyph.caller, glyph.video
IMAGE, ORACLE = glyph.IMAGE, glyph.ORACLE
START, END, RET = 0x4d4d, 0x4d78, 0x4d77
CODE = bytes.fromhex('ac22c074258ac8fec9ac8ae8ac22c07505bd0200eb0233edac3c0d74e3515356e808005e5b59fec1ebeec3')
LOCAL = {i.address: i for i in piece.MD.disasm(CODE, START)}
INS = LOCAL | glyph.INS
LOCAL_EDGES = {(p, i.operands[0].imm & 65535) for p, i in LOCAL.items()
               if i.group(piece.capstone.CS_GRP_JUMP)}
LOCAL_EDGES |= {(p, p+i.size) for p, i in LOCAL.items()
                if i.group(piece.capstone.CS_GRP_JUMP) and i.mnemonic != 'jmp'}
REPORT = BUILD / 'text-stream-differential.json'
ORIGINAL_REPORT = BUILD / 'text-stream-contract-original.json'


def record(column=1, row=1, style=0, text=b'A'):
    return bytes((column, row, style)) + text + b'\r'


def cases():
    rows = []
    def add(name, data, **kw):
        rows.append(dict(name=name, seed=len(rows), data=bytes(data), **kw))
    add('empty', b'\0', null=True)
    for style in range(256):
        add(f'style-{style:02x}', record(1 + style % 255, style, style, b'') + b'\0', null=True)
    for df in (0, 1):
        for style in (0, 1, 255):
            add(f'ordinary-{style}-df{df}', record(2, 1, style, b'A B') + b'\0',
                df=df, independent=True)
        add(f'embedded-NUL-df{df}', record(2, 1, 0, b'A\0B\n') + b'\0',
            df=df, independent=True)
        add(f'column-byte-wrap-df{df}', record(255, 0, 0, b'  ') + b'\0',
            df=df, null=True)
        add(f'multiple-records-df{df}', record(1, 1, 0, b'AB') +
            record(4, 2, 1, b'C') + record(9, 4, 0, b'') + b'\0',
            df=df, independent=True)
        for si in (0, 1, 0xfffe, 0xffff):
            add(f'cursor-{si:04x}-df{df}', record(1, 1, 1, b' ') + b'\0',
                df=df, si=si, ds=0x3000, null=True)
    for sp in (0, 1, 0xfffe, 0xffff):
        add(f'stack-{sp:04x}', record(text=b' ') + b'\0', sp=sp, null=True)
    add('stack-physical-wrap', record(text=b' ') + b'\0', ss=0xffff, sp=0xf, null=True)
    add('distinct-live-DS', record(text=b'AB') + b'\0', ds=0x3000,
        alternate=record(text=b'AC') + b'\0', independent=True)
    add('dirty-live-SI', record(1, 0, 0, b'AB') + b'\0',
        sp=0x4800, dirty=255, base=0x47f9, alias='si')
    add('dirty-live-BX', record(1, 0, 0, b'AB') + b'\0',
        sp=0x4800, dirty=255, base=0x47fb, alias='bx')
    add('dirty-live-CX', record(1, 0, 0, b'AB') + b'\0',
        sp=0x4800, dirty=255, base=0x47fd, alias='cx')
    add('changed-glyph-near', record(1, 0, 0) + b'\0',
        sp=0x4800, dirty=255, base=0x47f7, expected='changed-child-near', status=2)
    add('changed-renderer-near', record(1, 0, 0) + b'\0',
        sp=0x480e, dirty=255, base=0x47fd, expected='changed-child-near', status=1)
    add('changed-renderer-far', record(1, 0, 0) + b'\0', same_segments=True,
        load=0x1010, sp=0x6704, expected='changed-child-far', status=1)
    for offset in (0x4ad9, 0x4ba0, 0x4bc3, 0x4be5, 0x4ecf, 0x4def):
        data = IMAGE[0x9a90+offset:]
        # Header zeros end a stream, but row/style/text zeros do not. Decode
        # the pinned data grammar rather than splitting at the first NUL.
        n = 0
        while data[n]:
            n += 3
            while data[n] != 13: n += 1
            n += 1
            if n > 1024: glyph.fail('Pinned text record lacks a bounded terminator')
        add(f'pinned-record-{offset:04x}', data[:n+1], pinned_offset=offset,
            independent=True)
    return rows


def prepare(case):
    memory, regs, flags, game_ds = piece.prepare(case)
    regs.update(ip=START, si=case.get('si', 0x4000))
    for ds in {regs['ds'], game_ds}:
        for field, value in (('DrawingWidthPixels', 640), ('DrawingHeight', 350),
                ('DrawingPitchBytes', 80), ('DrawingOrigin', 0), ('DrawingPageByteOffset', 0)):
            piece.oracle.put16(memory, ds, piece.field(field), value)
        piece.oracle.put16(memory, ds, 0x1fee, 0x4000)
        if case.get('alias') == 'si':
            memory[piece.oracle.at(ds, 0x0101)] = 13
            memory[piece.oracle.at(ds, 0x0102)] = 0
        data = case.get('alternate', case['data']) if ds == game_ds else case['data']
        step = -1 if flags & 0x400 else 1
        for n, byte in enumerate(data):
            memory[piece.oracle.at(ds, (regs['si'] + n*step) & 65535)] = byte
        if flags & 0x400:
            # A DF-ignoring mutant gets a different, finite forward record.
            # It must finish and mismatch, rather than win credit via a guard.
            for n, byte in enumerate((1, 1, 32, 13, 0), 1):
                memory[piece.oracle.at(ds, (regs['si'] + n) & 65535)] = byte
    piece.oracle.put16(memory, regs['ss'], regs['sp'], 0xeed1)
    return memory, regs, flags, game_ds


def requests(data):
    rows, n = [], 0
    while data[n]:
        column, row, style = data[n:n+3]; n += 3
        column = (column-1) & 255
        while data[n] != 13:
            rows.append((data[n], (row << 8) | column, 0 if style else 2))
            column = (column+1) & 255; n += 1
        n += 1
    return rows


def defined_after(pc, prior):
    return (glyph.defined_after(pc, prior) if pc in glyph.INS else
            glyph.render._defined_mask(LOCAL[pc].mnemonic, prior))


def original_case(case, core):
    memory, regs, flags, game_ds = prepare(case)
    device = common.TraceDevice(bytearray(memory), START + case['seed'])
    observed, pending = [], []
    after_pop = {'si': [], 'bx': [], 'cx': []}
    def observe(pc, cpu, _device):
        if pc == 0x4d78:
            observed.append((cpu.reg_read(piece.oracle.REG['ax']) & 255,
                cpu.reg_read(piece.oracle.REG['cx']), cpu.reg_read(piece.oracle.REG['bp']),
                cpu.reg_read(piece.oracle.REG['ds'])))
        for site, register in ((0x4d71, 'si'), (0x4d72, 'bx'), (0x4d73, 'cx')):
            if pc == site:
                after_pop[register].append(cpu.reg_read(piece.oracle.REG[register]))
        if case.get('independent'):
            if pc in piece.FAMILIES and not pending:
                entry = {k: cpu.reg_read(r) for k, r in piece.oracle.REG.items()}
                entry['flags'] = cpu.reg_read(piece.x.UC_X86_REG_EFLAGS)
                pending.append((pc, entry, bytes(device.memory), [bytearray(p) for p in device.vga.planes]))
            if pc == 0x4dc0 and pending:
                address, entry, scratch, planes = pending.pop()
                glyph.bitmap.configure(piece.FAMILIES[address])
                if glyph.render._independent_planes(planes, scratch, entry, game_ds) != device.vga.planes:
                    glyph.fail(case['name'] + ': per-glyph independent planes differ')
    result = caller.original(case, device, regs, flags, instructions=INS,
        far_calls={glyph.CALL}, stop_before=RET if core else None,
        max_steps=300000, observe=observe, defined_mask_after=defined_after)
    actual, mask, sites, edges, boundary, _child, _body = result
    if not case.get('alias') and not case.get('expected'):
        data = case['data']
        expected = requests(data)
        if [x[:3] for x in observed] != expected:
            glyph.fail(case['name'] + f': record requests differ {observed}/{expected}')
    if case['name'] == 'distinct-live-DS' and any(x[3] != regs['ds'] for x in observed):
        glyph.fail('Distinct incoming DS was not preserved by ordinary glyph returns')
    if case.get('alias'):
        values = after_pop[case['alias']]
        if not values or values[0] != 0x0101:
            glyph.fail('Saved ' + case['alias'].upper() + ' alias was not exercised')
    if case.get('expected') and boundary[0] != case['expected']:
        glyph.fail(case['name'] + f': wrong boundary {boundary}')
    return memory, regs, flags, game_ds, device, result, observed


class Native:
    def __init__(self, directory, mutation=0, *, existing=False):
        path = Path(directory) / f'text-stream-m{mutation}.dll'
        self.lib = ctypes.CDLL(str(path if existing else build(path, mutation, 'text_stream')))
        self.core = self.lib.lmn_draw_text_stream_core
        self.core.argtypes = [video.MEM, ctypes.c_uint16, ctypes.c_uint16,
            ctypes.POINTER(video.State), ctypes.POINTER(common.RasterBus), ctypes.POINTER(piece.Ports)]
        self.core.restype = glyph.Result
        self.adapter = self.lib.lmn_draw_text_stream_adapter
        self.adapter.argtypes = [video.MEM, ctypes.POINTER(piece.Regs), ctypes.c_uint16,
            ctypes.POINTER(common.RasterBus), ctypes.POINTER(piece.Ports)]
        self.adapter.restype = None


def compare(native, case, core):
    memory, regs, flags, game_ds, original, result, observed = original_case(case, core)
    actual, mask, sites, edges, boundary, _child, _body = result
    if native is not None:
        for null in ((False, True) if case.get('null') else (False,)):
            device = common.TraceDevice(bytearray(memory), START + case['seed'])
            ports = piece.byte_ports(device)
            bus = None if null else ctypes.byref(device.bus)
            if core:
                r = native.core(video.buffer(device.memory), regs['cs'], game_ds,
                    ctypes.byref(video.to_state(dict(regs, flags=flags))), bus, ctypes.byref(ports))
                got = dict(video.state_dict(r.state), cs=r.code_segment, ip=r.continuation)
                common.require(r.status == case.get('status', 0), case['name'] + ': status differs')
            else:
                r = piece.Regs(**regs, flags=flags)
                native.adapter(video.buffer(device.memory), ctypes.byref(r), game_ds, bus, ctypes.byref(ports))
                got = {k: getattr(r, k) for k in (*piece.oracle.REG_NAMES, 'flags')}
            for k in piece.oracle.REG_NAMES:
                common.require(got[k] == actual[k], case['name'] + f': {k} {got[k]:04x}!={actual[k]:04x}')
            common.require(not ((got['flags'] ^ actual['flags']) & mask), case['name'] + ': flags differ')
            common.require(device.memory == original.memory, case['name'] + ': whole RAM differs')
            common.require(device.vga.state() == original.vga.state(), case['name'] + ': VGA state differs')
            if not null: common.compare_event_traces(device.events, original.events, case['name'])
            common.require(len(device.vga.trace) == len(original.vga.trace) and
                all(a[:3] == b[:3] and not ((a[3] ^ b[3]) & 0x600)
                    for a, b in zip(device.vga.trace, original.vga.trace)), case['name'] + ': device order differs')
    return dict(name=case['name'], core=core, sites=sorted(sites), edges=sorted(edges),
                boundary=boundary, glyph_requests=len(observed), null_repeat=case.get('null', False))


def input_hashes(native=False):
    paths = set(glyph.input_hashes(native)) | {'tests/text_stream.py', 'docs/text-stream.md'}
    if native: paths |= {'c/text_stream.c', 'c/text_stream.h'}
    return {p: sha((ROOT / p).read_bytes()) for p in sorted(paths)}


def runaway_probe(directory):
    common.MAX_BUS_EVENTS = 4096
    common.MAX_VGA_EVENTS = 32
    lib = Native(directory, existing=True)
    memory = bytearray(1 << 20)
    memory[0x30000:0x40000] = b' ' * 65536
    state = video.to_state(dict(ax=0, bx=0, cx=0, dx=0, si=0, di=0, bp=0,
        ds=0x3000, es=0, ss=0x7000, sp=0x8000, flags=2))
    device = common.TraceDevice(memory, START)
    lib.core(video.buffer(memory), 0x1010, 0x19b9, ctypes.byref(state), ctypes.byref(device.bus), None)
    glyph.fail('Unterminated space stream unexpectedly returned')


def worker(directory=None):
    common.MAX_BUS_EVENTS = 250000
    common.MAX_VGA_EVENTS = 75000
    before = input_hashes(directory is not None)
    if (IMAGE[START:END] != CODE or len(LOCAL) != 26 or
        sha(IMAGE) != 'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e' or
        sha(glyph.ASSET.read_bytes()) != '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d'):
        glyph.fail('Pinned text stream identity differs')
    native = Native(directory) if directory is not None else None
    rows = []
    for case in cases():
        for core in (False, True): rows.append(compare(native, case, core))
        gc.collect()
    sites = {p for row in rows for p in row['sites']}
    edges = {tuple(e) for row in rows for e in row['edges']}
    if not set(LOCAL) <= sites or not LOCAL_EDGES <= edges:
        glyph.fail('Text stream caller site/branch coverage incomplete')
    mutations = []
    if native is not None:
        for mutation, name in ((1, 'embedded-NUL-df0'), (2, 'ordinary-0-df1'),
                (3, 'dirty-live-SI'), (4, 'changed-glyph-near'), (5, 'column-byte-wrap-df0')):
            lib = Native(directory, mutation)
            case = next(c for c in cases() if c['name'] == name)
            try: compare(lib, case, True)
            except common.Mismatch as error:
                mutations.append(dict(mutation=mutation, case=name, reason=str(error)))
            else: glyph.fail(f'TEXT_STREAM_MUTATION={mutation} survived')
            gc.collect()
        probe = run_bounded([sys.executable, str(Path(__file__).resolve()), '--runaway-probe', directory],
            cwd=ROOT, timeout=15, memory_mib=384, check=False, stderr=subprocess.PIPE, text=True)
        if probe.returncode != 86 or 'trace guard exhausted' not in probe.stderr:
            glyph.fail(f'Text stream budget probe failed: {probe.returncode}/{probe.stderr}')
    if before != input_hashes(native is not None): glyph.fail('Text stream inputs changed')
    report = dict(image='main', image_sha256=sha(IMAGE), case_count=len(cases()),
        boundaries_each_case=2, null_bus_cases_each_boundary=sum(c.get('null', False) for c in cases()),
        caller_sites=26, caller_bytes=43, translated_code_bytes=43 if native else 0,
        native_code_ranges=[[START, END]] if native else [], executed_instruction_addresses=sorted(sites),
        caller_branch_edges=sorted(LOCAL_EDGES), branch_edges=sorted(edges), cases=rows,
        mutation_count=len(mutations), mutations_detected=mutations,
        budget_probe_exit=86 if native else None, input_hashes=before, c_coverage_claimed=native is not None,
        limits=dict(worker_seconds=120, windows_process_mib=384, windows_tree_mib=640,
            original_steps_per_call=300000, bus_events_per_call=250000, vga_events_per_call=75000),
        domain='4D4D live text record loop with native4D78/8822; constructed forward/backward streams and six pinned static record slices; zero-header/CR distinctions, byteCL wrap, live DS/SI/save-frame and changed returns; exact phase flags/fullRAM/ports/VGA/independent per-glyph footprints. Original loop has no game budget; hardware/IRQ/stack-limit domains remain open.')
    write_json(REPORT if native else ORIGINAL_REPORT, report)
    print(f'PASS text stream {"C" if native else "original"}: {len(cases())} fixtures x2 boundaries,26 caller/{len(sites)} integrated sites,{len(LOCAL_EDGES)} caller edges,{len(mutations)} completed mutants', flush=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--worker': worker(sys.argv[2]); return
    if len(sys.argv) == 3 and sys.argv[1] == '--runaway-probe': runaway_probe(sys.argv[2]); return
    if sys.argv[1:] == ['--original-worker']: worker(); return
    if sys.argv[1:] == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--original-worker'], cwd=ROOT, timeout=120, memory_mib=384)
        return
    if len(sys.argv) != 1: raise SystemExit('Unexpected text stream arguments')
    REPORT.unlink(missing_ok=True)
    try:
        with temporary_build_directory(prefix='text-stream-', parent=BUILD) as directory:
            run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory], cwd=ROOT, timeout=120, memory_mib=384)
    except BaseException:
        REPORT.unlink(missing_ok=True)
        raise


if __name__ == '__main__': main()

"""Pinned 4D78 glyph producer and its live 8822 renderer connection."""
import ast
import ctypes
import gc
import random
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
import drawing_caller_oracle as caller
import video_restore as video
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, read_json, write_json, sha
from unpack import ASSET, relocated

piece, common, render, bitmap = caller.piece, caller.common, caller.render, caller.piece.bitmap
IMAGE, ORACLE = piece.IMAGE, piece.ORACLE
START, END, CALL, AFTER, RET = 0x4d78, 0x4dc2, 0x4dbb, 0x4dc0, 0x4dc1
CODE = bytes.fromhex('3c2074452c2132e403c003c003c003c003c08bf003c003f081c6c05b8bfe83c7408b1eee1f81c30010891ee41f8add32ff8ac132e4b104d3e3d3e0b110b503ba1000559a228800005dc3')
LOCAL = {i.address: i for i in piece.MD.disasm(CODE, START)}
INS = LOCAL | {p: i for p, i in piece.INS.items() if 0x8822 <= p < 0x9a90}
REPORT = BUILD / 'text-glyph-differential.json'
ORIGINAL_REPORT = BUILD / 'text-glyph-contract-original.json'
SOURCES = ('text_glyph', 'drawing_render', 'drawing_plan', 'drawing_inputs',
    'drawing_clip', 'drawing_dirty', 'drawing_dispatch', 'drawing_source',
    'aligned_opaque', 'aligned_masked', 'aligned_mask_effects', 'aligned_protected',
    'aligned_read_mask', 'shifted_mask_effects', 'shifted_opaque', 'shifted_masked',
    'shifted_protected', 'shifted_read_mask')


class Result(ctypes.Structure):
    _fields_ = [('state', video.State), ('code_segment', ctypes.c_uint16),
               ('continuation', ctypes.c_uint16), ('status', ctypes.c_int)]


def fail(message):
    raise common.VerificationFailure(message)


def cases(prefix=False):
    rows = []
    def add(name, **kw):
        rows.append(dict(name=name, seed=len(rows), **kw))
    if prefix:
        for char in range(256):
            add(f'byte-{char:02x}', char=char, column=char, row=255-char,
                control=(char * 0x101) & 65535, df=char & 1)
        for n, kw in enumerate((dict(ds=0x3000), dict(ds=0xffff), dict(source_segment=0x000f),
                dict(same_segments=True, sp=0x1fe6), dict(ss=0xffff, sp=0xf),
                dict(sp=0), dict(sp=1), dict(sp=0xffff))):
            add(f'prefix-alias-{n}', char=0x21, **kw)
        return rows
    for char in (0, 0x1f, 0x20, 0x21, 0x22, 0x41, 0x7f, 0xff):
        add(f'character-{char:02x}', char=char, independent=True)
    for control in (0, 1, 2, 3, 0x20, 0x40, 0x8002, 0x4002, 0x82):
        for df in (0, 1):
            add(f'control-{control:04x}-df{df}', control=control, df=df,
                independent=True)
    for column, row in ((0, 0), (103, 0), (104, 0), (255, 0), (0, 10), (0, 255)):
        add(f'clipped-{column}-{row}', column=column, row=row, control=4,
            independent=True)
    for sp in (0, 1, 0xfffe):
        add(f'stack-{sp:04x}', sp=sp, column=255, control=4)
    add('stack-physical-wrap', ss=0xffff, sp=0xf, column=255, control=4)
    add('live-DS', ds=0x3000, independent=True)
    add('source-A20', source_segment=0xffff, independent=True)
    add('segment-add-wrap', source_segment=0x000f, independent=True)
    add('source-VGA', source_segment=0xa000)
    add('stack-VGA-abort', ss=0xa000, column=255, control=4)
    add('live-BP', same_segments=True, load=0x20, sp=0x66fc,
        column=255, control=4, expected='ready-return', expected_bp=2)
    add('changed-far', same_segments=True, load=0x1010, sp=0x66fc,
        column=255, control=4, expected='changed-child-far')
    add('changed-near', sp=0x4806, base=0x47fd, dirty=255,
        column=1, row=0, expected='changed-child-near')
    add('missing-byte-ports', control=0x4002, missing_ports=True,
        expected='continuation')
    return rows


def prepare(case):
    memory, regs, flags, game_ds = piece.prepare(case)
    rng = random.Random(START + case['seed'])
    regs.update(ip=START, ax=(rng.randrange(256) << 8) | case.get('char', 0x41),
                cx=(case.get('row', 1) << 8) | case.get('column', 2),
                bp=case.get('control', 2))
    source = case.get('source_segment', 0x5000)
    piece.oracle.put16(memory, regs['ds'], 0x1fee, (source - 0x1000) & 65535)
    # Preserve the caller's live outer word after all field construction.
    piece.oracle.put16(memory, regs['ss'], regs['sp'], 0xeed1)
    return memory, regs, flags, game_ds


def defined_after(pc, prior):
    # SHL r16,CL has count4 here: OF and AF are undefined. Child count-one
    # shifts keep their existing mask; no undefined bit is claimed as evidence.
    if pc in (0x4daf, 0x4db1):
        return 0x7c7
    return render._defined_mask(INS[pc].mnemonic, prior)


def run_original(case, device, regs, flags, *, mode):
    return caller.original(case, device, regs, flags, instructions=INS,
        far_calls={CALL}, stop_before=CALL if mode == 'prefix' else RET if mode == 'core' else None,
        continuations=(RET,) if mode == 'prefix' else (0x969c,) if case.get('missing_ports') else (), max_steps=100000,
        defined_mask_after=defined_after)


def check_prefix(case, memory, regs, flags, actual, device):
    char = regs['ax'] & 255
    if char == 0x20:
        # Prefix oracle stops at RET as well as CALL (handled below).
        expected = dict(regs, ip=RET)
    else:
        glyph = (0x5bc0 + 96 * ((char - 0x21) & 255)) & 65535
        expected = dict(regs, ax=(regs['cx'] & 255) * 16,
            bx=(regs['cx'] >> 8) * 16, cx=0x310, dx=16,
            si=glyph, di=(glyph + 64) & 65535,
            sp=(regs['sp'] - 2) & 65535, ip=CALL)
        segment = (piece.oracle.get16(memory, regs['ds'], 0x1fee) + 0x1000) & 65535
        if piece.oracle.get16(device.memory, regs['ds'], 0x1fe4) != segment and not case.get('same_segments'):
            fail(case['name'] + ': independent graphics segment differs')
        if piece.oracle.get16(device.memory, regs['ss'], expected['sp']) != regs['bp']:
            fail(case['name'] + ': independent saved BP differs')
    for k in piece.oracle.REG_NAMES:
        if actual[k] != expected[k]:
            fail(case['name'] + f': independent prefix {k} differs')
    if (actual['flags'] ^ flags) & 0x600:
        fail('Glyph prefix changed IF/DF')


def original_case(case, mode):
    memory, regs, flags, game_ds = prepare(case)
    device = common.TraceDevice(bytearray(memory), START + case['seed'])
    result = run_original(case, device, regs, flags, mode=mode)
    actual, mask, sites, edges, boundary, child, body = result
    if mode == 'prefix':
        check_prefix(case, memory, regs, flags, actual, device)
    else:
        if case.get('expected'):
            expected = case['expected']
            if mode == 'adapter' and expected == 'ready-return': expected = 'outer-return'
            if boundary[0] != expected: fail(case['name'] + f': boundary {boundary} != {expected}')
        if 'expected_bp' in case and actual['bp'] != case['expected_bp']:
            fail(case['name'] + ': live saved BP not exercised')
        if child is not None:
            char = regs['ax'] & 255
            glyph = (0x5bc0 + 96 * ((char - 0x21) & 255)) & 65535
            values = dict(ax=(regs['cx'] & 255) * 16, bx=(regs['cx'] >> 8) * 16,
                cx=0x310, dx=16, si=glyph, di=(glyph + 64) & 65535, bp=regs['bp'])
            if any(child[k] != v for k, v in values.items()):
                fail(case['name'] + ': independent renderer request differs')
        address, entry, scratch, planes = body
        if case.get('independent') and entry is not None:
            bitmap.configure(piece.FAMILIES[address])
            if render._independent_planes(planes, scratch, entry, game_ds) != device.vga.planes:
                fail(case['name'] + ': independent whole-plane footprint differs')
    return memory, regs, flags, game_ds, device, result


class Native:
    def __init__(self, directory, mutation=0):
        self.lib = ctypes.CDLL(str(build(Path(directory) / f'text-glyph-m{mutation}.dll', mutation, 'text_glyph')))
        self.prefix = self.lib.lmn_prepare_text_glyph_core
        self.prefix.argtypes = [video.MEM, ctypes.c_uint16, ctypes.POINTER(video.State), ctypes.POINTER(common.RasterBus)]
        self.prefix.restype = Result
        self.core = self.lib.lmn_draw_text_glyph_core
        self.core.argtypes = [video.MEM, ctypes.c_uint16, ctypes.c_uint16, ctypes.POINTER(video.State), ctypes.POINTER(common.RasterBus), ctypes.POINTER(piece.Ports)]
        self.core.restype = Result
        self.adapter = self.lib.lmn_draw_text_glyph_adapter
        self.adapter.argtypes = [video.MEM, ctypes.POINTER(piece.Regs), ctypes.c_uint16, ctypes.POINTER(common.RasterBus), ctypes.POINTER(piece.Ports)]
        self.adapter.restype = None


def compare(native, case, mode):
    memory, regs, flags, game_ds, original, result = original_case(case, mode)
    actual, mask, sites, edges, boundary, _child, body = result
    if native is not None:
        device = common.TraceDevice(bytearray(memory), START + case['seed'])
        ports = piece.byte_ports(device)
        state = video.to_state(dict(regs, flags=flags))
        if mode == 'adapter':
            r = piece.Regs(**regs, flags=flags)
            native.adapter(video.buffer(device.memory), ctypes.byref(r), game_ds,
                           ctypes.byref(device.bus), None if case.get('missing_ports') else ctypes.byref(ports))
            got = {k: getattr(r, k) for k in (*piece.oracle.REG_NAMES, 'flags')}
        else:
            args = [video.buffer(device.memory), regs['cs']]
            if mode == 'core': args.append(game_ds)
            args += [ctypes.byref(state), ctypes.byref(device.bus)]
            if mode == 'core': args.append(None if case.get('missing_ports') else ctypes.byref(ports))
            r = (native.prefix if mode == 'prefix' else native.core)(*args)
            got = dict(video.state_dict(r.state), cs=r.code_segment, ip=r.continuation)
            expected_status = (3 if mode == 'prefix' and boundary[2] == CALL else
                0 if mode == 'prefix' and boundary[2] == RET else
                0 if boundary[0] == 'ready-return' else
                2 if boundary[0] == 'changed-child-far' else 1)
            common.require(r.status == expected_status, case['name'] + ': native status differs')
        for k in piece.oracle.REG_NAMES:
            common.require(got[k] == actual[k], case['name'] + f'/{mode}: {k} {got[k]:04x}!={actual[k]:04x}')
        common.require(not ((got['flags'] ^ actual['flags']) & mask), case['name'] + f'/{mode}: flags differ')
        common.require(device.memory == original.memory, case['name'] + ': whole RAM differs')
        common.compare_event_traces(device.events, original.events, case['name'])
        common.require(device.vga.state() == original.vga.state(), case['name'] + ': VGA state differs')
        # The whole-bus trace above checks arithmetic flags with each original
        # phase mask, including undefined OF after SHL by4. The duplicate VGA
        # trace checks device order/value and IF/DF rather than reasserting OF.
        common.require(len(device.vga.trace) == len(original.vga.trace) and
            all(a[:3] == b[:3] and not ((a[3] ^ b[3]) & 0x600)
                for a, b in zip(device.vga.trace, original.vga.trace)),
            case['name'] + ': device order differs')
        if mode == 'prefix':
            plain = bytearray(memory)
            r = native.prefix(video.buffer(plain), regs['cs'], ctypes.byref(state), None)
            common.require(plain == original.memory, case['name'] + ': null-bus prefix RAM differs')
            got = dict(video.state_dict(r.state), cs=r.code_segment, ip=r.continuation)
            common.require(all(got[k] == actual[k] for k in piece.oracle.REG_NAMES)
                and not ((got['flags'] ^ actual['flags']) & mask), case['name'] + ': null-bus prefix state differs')
            common.require(r.status == expected_status, case['name'] + ': null-bus prefix status differs')
    return dict(name=case['name'], mode=mode, sites=sorted(sites), edges=sorted(edges),
                boundary=boundary, body=body[0])


def input_hashes(native=False):
    paths = set(video.input_hashes(False)) | {'tests/text_glyph.py'}
    pending = [ROOT / 'tests/text_glyph.py']
    while pending:
        for node in ast.walk(ast.parse(pending.pop().read_text(encoding='utf-8-sig'))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
            for name in names:
                for directory in ('tests', 'tools'):
                    p = ROOT / directory / (name.split('.')[0] + '.py')
                    key = p.relative_to(ROOT).as_posix()
                    if p.is_file() and key not in paths:
                        paths.add(key); pending.append(p)
    if native:
        paths |= {f'c/{n}{ext}' for n in SOURCES for ext in ('.c', '.h')}
        paths |= {'c/video_restore.h', 'c/regs.h', 'c/special_blit.h', 'c/lemmings_sym.h', 'tools/cbuild.py', 'tools/difftest.py', 'tools/coverage.py'}
    return {p: sha((ROOT / p).read_bytes()) for p in sorted(paths)}


def worker(directory=None):
    common.MAX_BUS_EVENTS = 100000
    common.MAX_VGA_EVENTS = 30000
    before = input_hashes(directory is not None)
    if IMAGE[START:END] != CODE or len(LOCAL) != 32 or not any(r['linear'] == 0x4dbe for r in ORACLE['relocations']):
        fail('Pinned glyph bytes/boundary/relocation differ')
    native = Native(directory) if directory is not None else None
    rows = []
    for prefix in (True, False):
        for case in cases(prefix):
            for mode in (('prefix',) if prefix else ('core', 'adapter')):
                rows.append(compare(native, case, mode))
            gc.collect()
    sites = {p for r in rows for p in r['sites']}
    edges = {tuple(e) for r in rows for e in r['edges']}
    if not set(LOCAL) <= sites or not {(0x4d7a, 0x4d7c), (0x4d7a, RET)} <= edges:
        fail('Glyph caller site/edge coverage incomplete')
    mutants = []
    if native is not None:
        for mutation, name in ((1, 'character-41'), (2, 'character-41'), (3, 'live-BP'), (4, 'changed-far')):
            lib = Native(directory, mutation)
            case = next(c for c in cases() if c['name'] == name)
            try: compare(lib, case, 'core')
            except common.Mismatch as error:
                mutants.append(dict(mutation=mutation, case=name, reason=str(error)))
            else: fail(f'TEXT_GLYPH_MUTATION={mutation} survived')
            gc.collect()
    if before != input_hashes(native is not None): fail('Glyph verification inputs changed')
    report = dict(image='main', image_sha256=sha(IMAGE), case_count=len(cases()),
        prefix_case_count=len(cases(True)), boundaries_each_case=2,
        translated_code_bytes=74 if native else 0, native_code_ranges=[[START, END]] if native else [],
        caller_instruction_addresses=sorted(LOCAL), executed_instruction_addresses=sorted(sites),
        branch_edges=sorted(edges), cases=rows, mutation_count=len(mutants), mutations_detected=mutants,
        input_hashes=before, c_coverage_claimed=native is not None,
        limits=dict(worker_seconds=120, windows_process_mib=384, windows_tree_mib=640,
            original_steps_per_call=100000, bus_events_per_call=100000, vga_events_per_call=30000),
        domain='Pinned4D78 caller/8822 renderer on constructed memory; all256 byte selectors at prefix, livefar/near/BP returns, ordered RAM/VGA/ports/definedflags; intact code and permissive20bit word bus; hardware stack-limit faults, native hardware/IRQ and full text producer remain open.')
    write_json(REPORT if native else ORIGINAL_REPORT, report)
    print(f'PASS text glyph {"C" if native else "original"}: {len(cases(True))} prefix/{len(cases())} integrated fixtures x2 boundaries,32 caller/{len(sites)} integrated sites,{len(mutants)} completed mutants', flush=True)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--worker': worker(sys.argv[2]); return
    if sys.argv[1:] == ['--original-worker']: worker(); return
    if sys.argv[1:] == ['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--original-worker'], cwd=ROOT, timeout=120, memory_mib=384)
        return
    if len(sys.argv) != 1: raise SystemExit('Unexpected text glyph arguments')
    REPORT.unlink(missing_ok=True)
    try:
        with temporary_build_directory(prefix='text-glyph-', parent=BUILD) as directory:
            run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory], cwd=ROOT, timeout=120, memory_mib=384)
    except BaseException:
        REPORT.unlink(missing_ok=True)
        raise


if __name__ == '__main__': main()

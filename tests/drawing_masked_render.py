"""Connected 8822 preparation through the default aligned masked VGA body."""
import ctypes
import gc
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
import drawing_render as render
from bounded_process import run_bounded, temporary_build_directory
from common import ROOT, BUILD, write_json, sha

ORACLE_CONFIG_KEYS = ('BODY_START', 'BODY_RETF', 'BODY_SPANS', 'BODY_INS',
                     'BODY_BRANCHES', 'BODY_EDGES', 'INS', 'BRANCHES',
                     'PREP_EXITS', '_independent_planes')
OPAQUE_CONFIG = {name: getattr(render, name) for name in ORACLE_CONFIG_KEYS}


def configure_original_body():
    # Reuse the instruction/bus oracle; select the separately maintained body.
    render.BODY_START, render.BODY_RETF = 0x93f6, 0x953d
    render.BODY_SPANS = ((0x93f6, 0x94c7), (0x94c8, 0x9507), (0x9508, 0x953e))
    render.BODY_INS = {}
    for start, end in render.BODY_SPANS:
        render.BODY_INS.update({i.address: i for i in render.MD.disasm(
            render.IMAGE[start:end], start)})
    render.BODY_BRANCHES = {pc for pc, i in render.BODY_INS.items()
        if i.group(render.capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
    render.BODY_EDGES = {(pc, i.operands[0].imm & 0xffff)
        for pc, i in render.BODY_INS.items() if pc in render.BODY_BRANCHES}
    render.BODY_EDGES |= {(pc, pc + i.size) for pc, i in render.BODY_INS.items()
        if pc in render.BODY_BRANCHES and i.mnemonic != 'jmp'}
    render.INS = render.PREP_INS | render.BODY_INS
    render.BRANCHES = render.PREP_BRANCHES | render.BODY_BRANCHES
    render.PREP_EXITS = set(render.plan.EXITS) - {0x93f6}
    render._independent_planes = independent_planes


def independent_planes(initial, memory, entry, data_segment):
    result = [bytearray(p) for p in initial]
    field, get = render.field, render.oracle.get16
    source_segment = get(memory, data_segment, field('GraphicsResourceSegment'))
    extent = get(memory, data_segment, field('DrawingSourcePlaneExtent'))
    source_row = get(memory, data_segment, field('DrawingSourceRowAdvance'))
    destination_row = get(memory, data_segment, field('DrawingActiveDestinationRowAdvance'))
    planes = entry['dx'] >> 8
    passes = planes if 1 <= planes <= 4 else 4
    rows = entry['cx'] >> 8 or 256
    count = entry['cx'] & 255 or 65536
    step = -1 if entry['flags'] & 0x400 else 1
    mask_cursor = entry['bx']
    for plane in range(passes):
        source = (entry['si'] + plane * extent) & 0xffff
        destination = entry['di']
        for _row in range(rows):
            for _byte in range(count):
                value = memory[((source_segment << 4) + source) & 0xfffff]
                if plane == 0:
                    mask = memory[((source_segment << 4) + mask_cursor) & 0xfffff]
                    mask_cursor = (mask_cursor + 1) & 0xffff
                    result[0][destination] = (value & mask) | (result[0][destination] & (~mask & 255))
                    for upper in range(1, 4):
                        result[upper][destination] &= ~mask & 255
                else:
                    result[plane][destination] |= value
                source = (source + step) & 0xffff
                destination = (destination + step) & 0xffff
            source = (source + source_row) & 0xffff
            destination = (destination + destination_row) & 0xffff
            if plane == 0:
                mask_cursor = (mask_cursor + source_row) & 0xffff
    return result


def cases():
    out = []
    for planes in (0, 1, 2, 3, 4, 5, 255):
        for width in (8, 16, 24):
            for df in (0, 1):
                for reverse in (0, 1):
                    out.append(dict(name=f'masked-{planes}-{width}-{df}-{reverse}',
                        seed=len(out), control=2 | (0x80 if reverse else 0),
                        left=16, top=1, width=width,
                        height=(planes << 8) | (1 + len(out) % 3),
                        dirty=0, df=df, independent=True))
    for control, left, top in ((6, -8, 1), (6, 1652, 1), (10, 16, -2),
                               (14, 1652, 162)):
        out.append(dict(name=f'clipped-{control}-{left}-{top}', seed=len(out),
            control=control, left=left & 65535, top=top & 65535, width=24,
            height=0x0408, dirty=0, df=0, independent=True))
    for df in (0, 1):
        out.append(dict(name=f'masked-dirty-{df}', seed=len(out), control=2,
            left=16, top=2, width=16, height=0x0402, dirty=255, df=df,
            independent=True))
        out.append(dict(name=f'masked-source-row-saved-bp-alias-{df}',
            seed=len(out), same_segments=True, sp=0x6704, control=0x82,
            left=16, top=2, width=16, height=0x0202, dirty=0, df=df,
            expected_boundary=('continuation', 0x969c)))
    return out


def library(mutation=0):
    lib = ctypes.CDLL(str(render.build(render.LIBRARY_DIRECTORY /
        f'masked-render-m{mutation}.dll', mutation, 'drawing_render')))
    adapter = lib.lmn_draw_prepared_planar_adapter
    adapter.argtypes = [render.MEM, ctypes.POINTER(render.Regs), ctypes.c_uint16,
                        ctypes.POINTER(render.Bus)]
    adapter.restype = None
    # The common oracle calls this attribute; the actual entry is the general API.
    lib.lmn_draw_prepared_aligned_opaque_adapter = adapter
    return lib


def main():
    path = BUILD / 'drawing-masked-render-differential.json'
    path.unlink(missing_ok=True)
    configure_original_body()
    masked_config = {name: getattr(render, name) for name in ORACLE_CONFIG_KEYS}
    render.fixture_vectors()
    lib = library()
    baseline = cases()
    sites, edges, prologue = set(), set(), set()
    body_cases = 0
    for case in baseline:
        seen, branches, original_prologue, boundary, ran = render.compare(lib, case)
        expected = case.get('expected_boundary', ('body-returned', 0x953d))
        if boundary != expected or ran != (expected[0] == 'body-returned'):
            raise AssertionError(f'{case["name"]}: expected {expected}, got {boundary}')
        body_cases += int(ran)
        sites |= seen
        edges |= branches
        prologue |= original_prologue
        gc.collect()
    if not set(render.BODY_INS) <= sites or not render.BODY_EDGES <= edges:
        raise AssertionError('Connected masked body site/edge coverage incomplete')
    masked_body_cases = body_cases
    opaque_cases = []
    for name, value in OPAQUE_CONFIG.items():
        setattr(render, name, value)
    for planes in (1, 4):
        for df in (0, 1):
            for reverse in (0, 1):
                case = dict(name=f'general-opaque-{planes}-{df}-{reverse}',
                    seed=len(baseline) + len(opaque_cases),
                    control=0x80 if reverse else 0, left=16, top=1,
                    width=16, height=(planes << 8) | 2, df=df, dirty=0,
                    independent=True)
                seen, branches, original_prologue, boundary, ran = render.compare(lib, case)
                if not ran or boundary != ('body-returned', 0x9966):
                    raise AssertionError(f'{case["name"]}: general opaque branch did not return')
                sites |= seen
                edges |= branches
                prologue |= original_prologue
                opaque_cases.append(case)
                gc.collect()
    baseline += opaque_cases
    for name, value in masked_config.items():
        setattr(render, name, value)
    mutations = []
    for mutation, name in ((1, 'masked-4-16-0-0'), (2, 'masked-4-16-1-1'),
                           (3, 'masked-1-8-0-0')):
        case = next(c for c in baseline if c['name'] == name)
        try:
            render.compare(library(mutation), case)
        except AssertionError:
            mutations.append(dict(mutation=mutation, case=name))
        else:
            raise AssertionError(f'RENDER_MUTATION={mutation} survived')
        finally:
            gc.collect()
    dependencies = tuple('c/' + p for p in (
        'drawing_render.c', 'drawing_render.h', 'aligned_masked.c', 'aligned_masked.h',
        'aligned_opaque.c', 'aligned_opaque.h', 'drawing_plan.c', 'drawing_plan.h',
        'aligned_protected.c', 'aligned_protected.h',
        'aligned_mask_effects.c', 'aligned_mask_effects.h',
        'aligned_read_mask.c', 'aligned_read_mask.h',
        'shifted_mask_effects.c', 'shifted_mask_effects.h',
        'drawing_inputs.c', 'drawing_inputs.h', 'drawing_clip.c', 'drawing_clip.h',
        'drawing_dirty.c', 'drawing_dirty.h', 'drawing_dispatch.c', 'drawing_dispatch.h',
        'drawing_source.c', 'drawing_source.h', 'lemmings_sym.h', 'regs.h', 'special_blit.h'))
    dependencies += ('tests/drawing_masked_render.py', 'tests/drawing_render.py',
        'tests/drawing_plan.py', 'tests/drawing_inputs.py', 'tests/minimap_vga.py',
        'tests/special_blit.py', 'tests/dat_io.py', 'tests/dat_io_c.py',
        'tools/cbuild.py', 'tools/difftest.py', 'tools/coverage.py',
        'tools/bounded_process.py', 'tools/unpack.py', 'metadata/symbols.json')
    write_json(path, dict(image='main', image_sha256=sha(render.IMAGE),
        case_count=len(baseline), cases=baseline, mutation_count=3,
        body_case_count=masked_body_cases + len(opaque_cases),
        masked_body_case_count=masked_body_cases, opaque_body_case_count=len(opaque_cases),
        mutations_detected=mutations, executed_instruction_addresses=sorted(sites),
        branch_edges=sorted(edges), body_instruction_addresses=sorted(render.BODY_INS),
        original_only_prologue_sites=sorted(prologue), translated_code_bytes=0,
        input_hashes={p: sha((ROOT / p).read_bytes()) for p in dependencies},
        domain='Constructed 8822 entry through original882D preparation and93F6 default masked body, plus eight general-API983B opaque cases; actual original953D/9966 RETF single-step with documented read-hook observation. Full RAM/register/defined-flag/bus/VGA state and independent plane footprints. Quiescent IRQ/intact code. Two savedBP aliases select969C explicitly; other effect/shift bodies remain seams.'))
    print(f'PASS masked render: {len(baseline)} cases, {len(sites)} integrated sites, '
          f'{len(edges)} branch edges; 3 compiled mutations detected')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--bounded-worker':
        render.LIBRARY_DIRECTORY = Path(sys.argv[2])
        main()
    elif len(sys.argv) == 1:
        (BUILD / 'drawing-masked-render-differential.json').unlink(missing_ok=True)
        with temporary_build_directory(prefix='masked-render-', parent=BUILD) as directory:
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--bounded-worker', directory], cwd=ROOT, timeout=180)
    else:
        raise SystemExit('Unexpected drawing_masked_render arguments')

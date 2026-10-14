"""Native preparation connected to shifted mask20/40, retaining other seams."""
import ctypes
import gc
import os
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
import drawing_render as render
import drawing_aligned_render as aligned
from aligned_read_mask import Ports, OUT_BYTE, IN_BYTE
from bounded_process import run_bounded, temporary_build_directory
from common import ROOT, BUILD, sha, write_json

SHIFTED = {
    'shifted20': (0x8ff7, 0x909b, ((0x8ff7, 0x909c),), 0x23),
    'shifted40': (0x909c, 0x913f, ((0x909c, 0x9140),), 0x43),
}


def configure(family, seam=False):
    aligned.FAMILIES.update(SHIFTED)
    aligned.configure(family, seam)
    if family in SHIFTED:
        render._independent_planes = independent_planes


def independent_planes(initial, memory, entry, data_segment):
    """Known RAM copy plus mathematical carry chain and plane truth table."""
    result = [bytearray(p) for p in initial]
    scratch = bytearray(memory)
    at = render.oracle.at
    count, rows = entry['cx'] & 255, (entry['cx'] >> 8) or 256
    direction = -1 if entry['flags'] & 0x400 else 1
    source_segment = render.oracle.get16(memory, data_segment,
                                        render.field('GraphicsResourceSegment'))
    source_row = render.oracle.get16(memory, data_segment,
                                    render.field('DrawingSourceRowAdvance'))
    dest_row = (render.oracle.get16(memory, data_segment,
                                   render.field('DrawingActiveDestinationRowAdvance')) - 1) & 65535
    base = render.field('DrawingMaskRowScratch')
    shifts = memory[at(data_segment, render.field('DrawingLeftBitShiftByte'))] or 256
    source, target = entry['bx'], entry['di']
    enables = (entry['bp'] >> 8) & 15
    clear = render.BODY_START == 0x909c
    # The connected matrix uses ordinary nonzero CL and separate source/stack.
    # Unchecked count and alias paths are covered by the standalone leaf suite.
    if not 0 < count < 255:
        raise RuntimeError('Independent connected footprint outside count domain')
    for _ in range(rows):
        for j in range(count):
            scratch[at(data_segment, (base + j * direction) & 65535)] = \
                scratch[at(source_segment, (source + j * direction) & 65535)]
        scratch[at(data_segment, (base + count * direction) & 65535)] = 0
        source = (source + count * direction + source_row) & 65535
        locations = [at(data_segment, (base + j) & 65535) for j in range(count + 1)]
        bits = int.from_bytes(bytes(scratch[p] for p in locations), 'big') >> shifts
        for p, value in zip(locations, bits.to_bytes(count + 1, 'big')):
            scratch[p] = value
        for j in range(count + 1):
            mask = scratch[at(data_segment, (base + j) & 65535)]
            for plane in range(4):
                if clear and enables & (1 << plane):
                    result[plane][target] &= ~mask & 255
                else:
                    result[plane][target] |= mask
            target = (target + direction) & 65535
        target = (target + dest_row) & 65535
    return result


def library(directory, mutation=0, missing_ports=False, aligned_only=False, entry_api=None):
    path = Path(directory) / f'shifted-render-{mutation}-{int(missing_ports)}-{int(aligned_only)}-{entry_api or 'default'}.dll'
    lib = ctypes.CDLL(str(render.build(path, mutation, 'drawing_render')))
    fn = (getattr(lib, entry_api) if entry_api else
          lib.lmn_draw_prepared_aligned_adapter if aligned_only else
          lib.lmn_draw_prepared_planar_effects_adapter)
    fn.argtypes = [render.MEM, ctypes.POINTER(render.Regs), ctypes.c_uint16,
                   ctypes.POINTER(render.Bus), ctypes.POINTER(Ports)]
    fn.restype = None

    def adapter(memory, regs, game_ds, bus):
        data = bus._obj.verification

        @OUT_BYTE
        def out(_ctx, _mem, port, value, flags):
            try:
                render.BYTE_PORT_FIXTURE.out_byte(data['vga'], port, value, flags)
                data['events'].append(('outb', port, value, flags))
            except BaseException as error:
                os.write(2, (str(error) + '\n').encode())
                os._exit(87)

        @IN_BYTE
        def inp(_ctx, _mem, port, flags):
            try:
                value = render.BYTE_PORT_FIXTURE.in_byte(data['vga'], port, flags, data['case'])
                data['events'].append(('inb', port, value, flags))
                return value
            except BaseException as error:
                os.write(2, (str(error) + '\n').encode())
                os._exit(87)

        ports = Ports(None, out, inp)
        fn(memory, regs, game_ds, bus, None if missing_ports else ctypes.byref(ports))

    lib.lmn_draw_prepared_aligned_opaque_adapter = adapter
    return lib


def cases(family):
    control = SHIFTED[family][3]
    result = []
    for shift in range(1, 8):
        for width in (8, 24):
            for df in (0, 1):
                for reverse in (0, 1):
                    for nibble in (0, 5, 15):
                        result.append(dict(name=f'{family}-{shift}-{width}-{df}-{reverse}-{nibble}',
                            seed=len(result), control=control | (reverse << 7) | (nibble << 8),
                            width=width, height=0x0100 | (1 + len(result) % 3),
                            left=16 + shift, top=1, df=df, dirty=0, independent=True))
    return result


def worker(directory):
    lib = library(directory)
    baseline = []
    seen, edges, prologue = set(), set(), set()
    counts = {}
    for family in SHIFTED:
        configure(family)
        local_sites, local_edges = set(), set()
        group = cases(family)
        for case in group:
            case['seed'] = len(baseline)
            sites, branches, original, boundary, entered = render.compare(lib, case)
            if not entered or boundary != ('body-returned', SHIFTED[family][1]):
                raise AssertionError(f'{case["name"]}: wrong shifted boundary {boundary}')
            local_sites |= sites
            local_edges |= branches
            seen |= sites
            edges |= branches
            prologue |= original
            baseline.append(case)
            gc.collect()
        if not set(render.BODY_INS) <= local_sites or not render.BODY_EDGES <= local_edges:
            raise RuntimeError(f'{family}: original body sites/edges incomplete')
        counts[family] = len(group)
    # Exercise the previously supported bodies through this expanded API.
    for family in ('opaque', 'masked', 'protected', 'read-mask', 'effect20', 'effect40'):
        configure(family)
        case = aligned.cases(family)[0]
        case['name'] = 'expanded-api-' + family
        case['seed'] = len(baseline)
        sites, branches, original, boundary, entered = render.compare(lib, case)
        if not entered or boundary != ('body-returned', aligned.FAMILIES[family][1]):
            raise AssertionError('Expanded API changed existing aligned body')
        seen |= sites
        edges |= branches
        prologue |= original
        baseline.append(case)
        gc.collect()
    seams = ((0x03, 0x890e), (0x8003, 0x8b42), (0x4003, 0x8d66), (0x01, 0x916b))
    for control, target in seams:
        configure('shifted20', True)
        case = dict(name=f'unported-shifted-seam-{target:04x}', seed=len(baseline),
                    control=control, left=17, top=1, width=16, height=0x0101, df=0, dirty=0)
        sites, branches, original, boundary, entered = render.compare(lib, case)
        if entered or boundary != ('continuation', target):
            raise AssertionError('Unported shifted seam changed')
        seen |= sites
        edges |= branches
        prologue |= original
        baseline.append(case)
        gc.collect()
    # The prior all-aligned API keeps both shifted effects as continuations.
    old = library(directory, aligned_only=True)
    for family in SHIFTED:
        configure(family, True)
        case = cases(family)[0]
        case.update(name='aligned-api-retains-' + family, seed=len(baseline), independent=False)
        sites, branches, original, boundary, entered = render.compare(old, case)
        if entered or boundary != ('continuation', SHIFTED[family][0]):
            raise AssertionError('Existing all-aligned API expanded unexpectedly')
        seen |= sites
        edges |= branches
        prologue |= original
        baseline.append(case)
        gc.collect()
    configure('read-mask', True)
    case = dict(name='expanded-api-missing-byte-provider', seed=len(baseline), control=0x4002,
                left=16, top=1, width=16, height=0x0101, df=0, dirty=0)
    sites, branches, original, boundary, entered = render.compare(library(directory, missing_ports=True), case)
    if entered or boundary != ('continuation', 0x969c):
        raise AssertionError('Missing byte provider seam changed')
    seen |= sites
    edges |= branches
    prologue |= original
    baseline.append(case)
    mutations = []
    configure('shifted20')
    witness = next(c for c in baseline if c['name'] == 'shifted20-3-24-1-1-5')
    for mutation in (1, 2, 3):
        try:
            render.compare(library(directory, mutation), witness)
        except AssertionError as error:
            mutations.append(dict(mutation=mutation, case=witness['name'], reason=str(error)))
        else:
            raise RuntimeError(f'RENDER_MUTATION={mutation} survived shifted connection')
        finally:
            gc.collect()
    sources = ('drawing_render', 'aligned_masked', 'aligned_opaque', 'aligned_protected',
               'aligned_mask_effects', 'aligned_read_mask', 'shifted_mask_effects', 'shifted_opaque',
               'shifted_masked', 'shifted_protected', 'shifted_read_mask', 'drawing_plan',
               'drawing_inputs', 'drawing_clip', 'drawing_dirty', 'drawing_dispatch', 'drawing_source')
    dependencies = tuple('c/' + n + ext for n in sources for ext in ('.c', '.h'))
    dependencies += ('c/special_blit.h', 'c/regs.h', 'c/lemmings_sym.h',
        'tests/drawing_shifted_render.py', 'tests/drawing_render.py', 'tests/drawing_aligned_render.py',
        'tests/drawing_masked_render.py', 'tests/drawing_plan.py', 'tests/drawing_inputs.py',
        'tests/aligned_read_mask.py', 'tests/aligned_masked.py', 'tests/minimap_vga.py',
        'tests/special_blit.py', 'tests/dat_io.py', 'tests/dat_io_c.py',
        'tools/cbuild.py', 'tools/difftest.py', 'tools/coverage.py', 'tools/bounded_process.py',
        'tools/unpack.py', 'metadata/symbols.json')
    write_json(BUILD / 'drawing-shifted-render-differential.json', dict(image='main',
        image_sha256=sha(render.IMAGE), case_count=len(baseline), cases=baseline,
        body_counts=counts, mutation_count=3, mutations_detected=mutations,
        executed_instruction_addresses=sorted(seen), branch_edges=sorted(edges),
        original_only_prologue_sites=sorted(prologue), translated_code_bytes=0,
        input_hashes={p: sha((ROOT / p).read_bytes()) for p in dependencies},
        domain='Constructed8822 entry through native882D preparation to shifted20/40 and all aligned bodies. All seven shift residues/DF/reverse/enable masks, mathematical scratch carry-chain and whole-plane checks, actual unchanged far returns. WholeRAM/registers/defined flags/orderedRAM/ports/VGA state; intactcode/quiescentIRQ. Other shifted bodies/missing byte provider/older API scopes remain explicit seams.'))
    print(f'PASS shifted render: {len(baseline)} cases, {len(seen)} integrated sites, '
          f'{len(edges)} edges; 3 mutants')


if __name__ == '__main__':
    (BUILD / 'drawing-shifted-render-differential.json').unlink(missing_ok=True)
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
    elif len(sys.argv) == 1:
        with temporary_build_directory(prefix='drawing-shifted-', parent=BUILD) as directory:
            run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                        cwd=ROOT, timeout=180)
    else:
        raise SystemExit('Unexpected drawing_shifted_render arguments')

"""Connected preparation and all six aligned bodies, with byte-port seams."""
import ctypes
import gc
import os
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
import drawing_render as render
import drawing_masked_render as masked
from aligned_read_mask import Ports, OUT_BYTE, IN_BYTE
from bounded_process import run_bounded, temporary_build_directory
from common import ROOT, BUILD, sha, write_json

FAMILIES = {
    'opaque': (0x983b, 0x9966, ((0x983b,0x98f4),(0x98f5,0x9932),(0x9933,0x9967)), 0),
    'masked': (0x93f6,0x953d,((0x93f6,0x94c7),(0x94c8,0x9507),(0x9508,0x953e)),2),
    'protected': (0x953e,0x969b,((0x953e,0x9659),(0x965a,0x969c)),0x8002),
    'read-mask': (0x969c,0x9736,((0x969c,0x9737),),0x4002),
    'effect20': (0x9737,0x97a3,((0x9737,0x97a4),),0x22),
    'effect40': (0x97a4,0x980f,((0x97a4,0x9810),),0x42),
}


class BytePortFixture:
    def out_byte(self, vga, port, value, flags):
        if port != 0x3ce or value != 5:
            raise RuntimeError('Unsupported byte selector')
        vga.gi = value
        vga.outcount += 1
        vga.trace.append(('outb', port, value, flags))

    def in_byte(self, vga, port, flags, case):
        if port != 0x3cf:
            raise RuntimeError('Unsupported byte read')
        value = case.get('mode_reply', vga.gc[vga.gi])
        vga.trace.append(('inb', port, value, flags))
        return value


def configure(family, missing_ports=False):
    start, ret, spans, _ = FAMILIES[family]
    render.BODY_START, render.BODY_RETF, render.BODY_SPANS = start, ret, spans
    render.BODY_INS = {}
    for lo, hi in spans:
        render.BODY_INS |= {i.address: i for i in render.MD.disasm(render.IMAGE[lo:hi],lo)}
    render.BODY_BRANCHES = {p for p,i in render.BODY_INS.items()
        if i.group(render.capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
    render.BODY_EDGES = {(p,i.operands[0].imm & 65535) for p,i in render.BODY_INS.items()
                        if p in render.BODY_BRANCHES}
    render.BODY_EDGES |= {(p,p+i.size) for p,i in render.BODY_INS.items()
                         if p in render.BODY_BRANCHES and i.mnemonic != 'jmp'}
    render.PREP_EXITS = set(render.plan.EXITS) - (set() if missing_ports else {start})
    render.INS = render.PREP_INS | render.BODY_INS
    render.BRANCHES = render.PREP_BRANCHES | render.BODY_BRANCHES
    render.BYTE_PORT_FIXTURE = BytePortFixture()
    if family == 'opaque':
        render._independent_planes = masked.OPAQUE_CONFIG['_independent_planes']
    elif family == 'masked':
        render._independent_planes = masked.independent_planes
    else:
        render._independent_planes = independent_planes


def independent_planes(initial, memory, entry, data_segment):
    start = render.BODY_START
    result = [bytearray(p) for p in initial]
    source_segment = render.oracle.get16(memory,data_segment,render.field('GraphicsResourceSegment'))
    source_row = render.oracle.get16(memory,data_segment,render.field('DrawingSourceRowAdvance'))
    dest_row = render.oracle.get16(memory,data_segment,render.field('DrawingActiveDestinationRowAdvance'))
    extent = render.oracle.get16(memory,data_segment,render.field('DrawingSourcePlaneExtent'))
    direction = -1 if entry['flags'] & 0x400 else 1
    count, rows = (entry['cx'] & 255) or 65536, (entry['cx'] >> 8) or 256
    limit = entry['dx'] >> 8
    passes = (limit if 1 <= limit <= 3 else 4) if start == 0x953e else 1
    mask_cursor = entry['bx']
    for plane in range(passes):
        source = (entry['si'] + plane*extent) & 65535
        target = entry['di']
        for _row in range(rows):
            for _ in range(count):
                value = memory[((source_segment<<4)+source)&0xfffff]
                mask = memory[((source_segment<<4)+mask_cursor)&0xfffff]
                if start == 0x953e:
                    selection = ~result[3][target] & 255
                    result[plane][target] |= value & selection
                elif start == 0x969c:
                    selection = result[3][target] & mask
                    keep = ~selection & 255
                    result[0][target] = (value & selection) | (result[0][target] & keep)
                    result[1][target] &= keep
                    result[2][target] |= selection
                    result[3][target] &= keep
                else:
                    enables = (entry['bp'] >> 8) & 15
                    for p in range(4):
                        if start == 0x97a4 and enables & (1<<p):
                            result[p][target] &= ~mask & 255
                        else:
                            result[p][target] |= mask
                source = (source + direction) & 65535
                target = (target + direction) & 65535
                mask_cursor = (mask_cursor + 1) & 65535
            source = (source + source_row) & 65535
            target = (target + dest_row) & 65535
            if start in (0x969c,0x97a4):
                mask_cursor = (mask_cursor + source_row) & 65535
    return result


def library(directory, mutation=0, missing_ports=False):
    lib = ctypes.CDLL(str(render.build(Path(directory)/f'aligned-render-{mutation}-{int(missing_ports)}.dll',
                                     mutation,'drawing_render')))
    fn = lib.lmn_draw_prepared_aligned_adapter
    fn.argtypes = [render.MEM,ctypes.POINTER(render.Regs),ctypes.c_uint16,
                   ctypes.POINTER(render.Bus),ctypes.POINTER(Ports)]
    fn.restype = None
    def adapter(memory, regs, game_ds, bus):
        data = bus._obj.verification
        @OUT_BYTE
        def out(_ctx,_mem,port,value,flags):
            try:
                render.BYTE_PORT_FIXTURE.out_byte(data['vga'],port,value,flags)
                data['events'].append(('outb',port,value,flags))
            except BaseException as error:
                os.write(2,(str(error)+'\n').encode());os._exit(87)
        @IN_BYTE
        def inp(_ctx,_mem,port,flags):
            try:
                value = render.BYTE_PORT_FIXTURE.in_byte(data['vga'],port,flags,data['case'])
                data['events'].append(('inb',port,value,flags))
                return value
            except BaseException as error:
                os.write(2,(str(error)+'\n').encode());os._exit(87)
        ports = Ports(None,out,inp)
        fn(memory,regs,game_ds,bus,None if missing_ports else ctypes.byref(ports))
    lib.lmn_draw_prepared_aligned_opaque_adapter = adapter
    return lib


def cases(family):
    out=[]
    control=FAMILIES[family][3]
    for limit in ((0,1,2,3,4,5,255) if family in ('opaque','masked','protected') else (1,)):
        for width in (8,24):
            for df in (0,1):
                for reverse in (0,1):
                    for nibble in ((0,5,15) if family.startswith('effect') else (0,)):
                        out.append(dict(name=f'{family}-{limit}-{width}-{df}-{reverse}-{nibble}',
                            seed=len(out),control=control|(0x80 if reverse else 0)|(nibble<<8),
                            width=width,height=(limit<<8)|(1+len(out)%3),left=16,top=1,
                            df=df,dirty=0,independent=True))
    if family=='read-mask':
        out.append(dict(name='read-mask-mode-check-nop',seed=len(out),control=control,
                        width=16,height=0x0102,left=16,top=1,df=0,mode_reply=9,independent=True))
    return out


def worker(directory):
    lib=library(directory)
    seen,edges,prologue=set(),set(),set()
    baseline=[]; counts={}
    for family in FAMILIES:
        configure(family)
        local_sites=set();local_edges=set()
        group=cases(family)
        for case in group:
            case['seed']=len(baseline)
            sites,branches,original,exit_at,ran=render.compare(lib,case)
            if not ran or exit_at!=('body-returned',FAMILIES[family][1]):
                raise AssertionError(f'{case["name"]}: wrong aligned boundary {exit_at}')
            seen|=sites;edges|=branches;prologue|=original
            local_sites|=sites;local_edges|=branches;baseline.append(case)
            gc.collect()
        if not set(render.BODY_INS)<=local_sites or not render.BODY_EDGES<=local_edges:
            raise AssertionError(f'{family}: body site/edge coverage incomplete')
        counts[family]=len(group)
    configure('read-mask',True)
    case=dict(name='missing-byte-port-provider-seam',seed=len(baseline),control=0x4002,
              width=16,height=0x0102,left=16,top=1,df=0,dirty=0)
    sites,branches,original,exit_at,ran=render.compare(library(directory,missing_ports=True),case)
    if ran or exit_at!=('continuation',0x969c):raise AssertionError('Missing provider seam changed')
    seen|=sites;edges|=branches;prologue|=original;baseline.append(case)
    mutations=[]
    for mutation in (1,2,3):
        configure('protected')
        witness=next(c for c in baseline if c['name']=='protected-4-24-1-1-0')
        try:render.compare(library(directory,mutation),witness)
        except AssertionError:mutations.append(dict(mutation=mutation,case=witness['name']))
        else:raise AssertionError(f'RENDER_MUTATION={mutation} survived aligned connection')
        finally:gc.collect()
    dependencies=tuple('c/'+n for n in ('drawing_render.c','drawing_render.h','aligned_masked.c',
        'aligned_masked.h','aligned_opaque.c','aligned_opaque.h','aligned_protected.c','aligned_protected.h',
        'aligned_mask_effects.c','aligned_mask_effects.h','aligned_read_mask.c','aligned_read_mask.h',
        'shifted_mask_effects.c','shifted_mask_effects.h',
        'shifted_opaque.c','shifted_opaque.h','shifted_masked.c','shifted_masked.h',
        'shifted_protected.c','shifted_protected.h','shifted_read_mask.c','shifted_read_mask.h',
        'drawing_plan.c','drawing_plan.h','drawing_inputs.c','drawing_inputs.h','drawing_clip.c','drawing_clip.h',
        'drawing_dirty.c','drawing_dirty.h','drawing_dispatch.c','drawing_dispatch.h','drawing_source.c',
        'drawing_source.h','special_blit.h','regs.h','lemmings_sym.h'))
    dependencies+=('tests/drawing_aligned_render.py','tests/drawing_render.py','tests/drawing_masked_render.py',
        'tests/aligned_read_mask.py','tests/aligned_masked.py','tests/drawing_plan.py','tests/drawing_inputs.py',
        'tests/minimap_vga.py','tests/special_blit.py','tests/dat_io.py','tests/dat_io_c.py','tools/cbuild.py',
        'tools/difftest.py','tools/coverage.py','tools/bounded_process.py','tools/unpack.py','metadata/symbols.json')
    write_json(BUILD/'drawing-aligned-render-differential.json',dict(image='main',image_sha256=sha(render.IMAGE),
        case_count=len(baseline),cases=baseline,body_counts=counts,mutation_count=3,mutations_detected=mutations,
        executed_instruction_addresses=sorted(seen),branch_edges=sorted(edges),translated_code_bytes=0,
        original_only_prologue_sites=sorted(prologue),missing_byte_provider_seam=True,
        input_hashes={p:sha((ROOT/p).read_bytes()) for p in dependencies},
        domain='Constructed8822 entry through native882D preparation and all six aligned bodies. Actual unmodified far returns; fullRAM/register/defined flags/orderedRAM/byte and word ports/VGA state/independent plane footprints. Quiescent IRQ/intact code. Shifted bodies remain seams;969C without byte provider stays explicit.'))
    print(f'PASS aligned render: {len(baseline)} cases, {len(seen)} integrated sites, {len(edges)} edges; 3 mutants')


if __name__=='__main__':
    (BUILD/'drawing-aligned-render-differential.json').unlink(missing_ok=True)
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2])
    elif len(sys.argv)==1:
        with temporary_build_directory(prefix='drawing-aligned-',parent=BUILD) as directory:
            run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',directory],cwd=ROOT,timeout=180)
    else:raise SystemExit('Unexpected drawing_aligned_render arguments')

"""Actual8822 entry connected to all twelve native planar drawing bodies."""
import gc
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
import drawing_render as render
import drawing_aligned_render as aligned
import drawing_shifted_render as effects
from bounded_process import run_bounded, temporary_build_directory
from common import ROOT, BUILD, sha, write_json

NEW = {
    'shifted-opaque': (0x916b, 0x939d, ((0x916b,0x9339),(0x933a,0x939e)), 1),
    'shifted-masked': (0x890e, 0x8b41, ((0x890e,0x8add),(0x8ade,0x8b42)), 3),
    'shifted-protected': (0x8b42,0x8d65,((0x8b42,0x8cf4),(0x8cf5,0x8d66)),0x8003),
    'shifted-read-mask': (0x8d66,0x8ff6,((0x8d66,0x8f8d),(0x8f8e,0x8ff7)),0x4003),
}
BASE_PREP = dict(render.PREP_INS)
ABORT = {i.address:i for i in render.MD.disasm(render.IMAGE[0x88ab:0x88ac],0x88ab)}


def configure(family, entry=True, seam=False):
    aligned.FAMILIES.update(effects.SHIFTED)
    aligned.FAMILIES.update(NEW)
    render.ENTRY_FROM_8822 = entry
    render.CONSUME_ABORT_RETURN = entry
    render.PREP_INS = BASE_PREP | (render.PROLOGUE | ABORT if entry else {})
    aligned.configure(family, seam)
    if family in NEW:
        render._independent_planes = independent_planes
    elif family in effects.SHIFTED:
        render._independent_planes = effects.independent_planes


def independent_planes(initial, memory, entry, data_segment):
    """Packed-bit scratch shifts plus plane truth tables, without CPU flags."""
    result = [bytearray(p) for p in initial]
    scratch = bytearray(memory)
    at = render.oracle.at
    count, rows = entry['cx'] & 255, (entry['cx'] >> 8) or 256
    if not 0 < count < 255:
        raise RuntimeError('Independent bitmap footprint outside ordinary count domain')
    direction = -1 if entry['flags'] & 0x400 else 1
    source_segment = render.oracle.get16(memory,data_segment,render.field('GraphicsResourceSegment'))
    source_row_field = render.field('DrawingSourceRowAdvance')
    dest_row_field = render.field('DrawingActiveDestinationRowAdvance')
    extent_field = render.field('DrawingSourcePlaneExtent')
    def word(field):
        return render.oracle.get16(scratch,data_segment,field)
    render.oracle.put16(scratch,data_segment,dest_row_field,(word(dest_row_field)-1)&65535)
    source_base = render.field('DrawingSourceRowScratch')
    mask_base = render.field('DrawingMaskRowScratch')
    shift_field = render.field('DrawingLeftBitShiftByte')
    limit = entry['dx'] >> 8
    passes = limit if 1 <= limit <= 3 else 4
    body = render.BODY_START

    def copy_row(source, base, fill=None):
        for j in range(count):
            scratch[at(data_segment,(base+j*direction)&65535)] = (fill if fill is not None else
                scratch[at(source_segment,(source+j*direction)&65535)])
        scratch[at(data_segment,(base+count*direction)&65535)] = 0

    def shift_row(base):
        shifts = scratch[at(data_segment,shift_field)] or 256
        locations = [at(data_segment,(base+j)&65535) for j in range(count+1)]
        bits = int.from_bytes(bytes(scratch[p] for p in locations),'big') >> shifts
        for p,value in zip(locations,bits.to_bytes(count+1,'big')):
            scratch[p] = value

    if body == 0x8d66:
        # The original caches all mask rows before drawing any plane. Cache
        # source/sentinel follow DF; protection sampling always moves DI forward.
        base, mask_source, target = mask_base, entry['bx'], entry['di']
        for _row in range(rows):
            copy_row(mask_source,base)
            shift_row(base)
            for j in range(count+1):
                p = at(data_segment,(base+j)&65535)
                scratch[p] &= result[3][(target+j)&65535]
            base = (base+(count+1)*direction)&65535
            mask_source = (mask_source+count*direction+word(source_row_field))&65535
            target = (target+count+1+word(dest_row_field))&65535

    for plane in range(passes):
        source = (entry['si']+plane*word(extent_field))&65535
        mask_source = entry['bx']
        target = entry['di']
        cached_mask = mask_base
        for _row in range(rows):
            copy_row(source,source_base)
            if plane == 0 and body in (0x916b,0x890e):
                copy_row(mask_source,mask_base,255 if body == 0x916b else None)
            shift_row(source_base)
            if plane == 0 and body in (0x916b,0x890e):
                shift_row(mask_base)  # Separate live shift-byte read.
            for j in range(count+1):
                value = scratch[at(data_segment,(source_base+j*direction)&65535)]
                if body == 0x8b42:
                    result[plane][target] |= value & (~result[3][target]&255)
                elif body == 0x8d66:
                    selection = scratch[at(data_segment,cached_mask)]
                    cached_mask = (cached_mask+1)&65535
                    if plane == 0:
                        result[0][target] = (value&selection)|(result[0][target]&(~selection&255))
                        for p in (1,2,3):result[p][target] &= ~selection&255
                    else:
                        result[plane][target] |= value&selection
                elif plane == 0:
                    selection = scratch[at(data_segment,(mask_base+j)&65535)]
                    result[0][target] = (value&selection)|(result[0][target]&(~selection&255))
                    for p in (1,2,3):result[p][target] &= ~selection&255
                else:
                    result[plane][target] |= value
                target = (target+direction)&65535
            source = (source+count*direction+word(source_row_field))&65535
            mask_source = (mask_source+count*direction+word(source_row_field))&65535
            target = (target+word(dest_row_field))&65535
    return result


def cases(family):
    out=[]
    for shift in range(1,8):
        for limit in (0,1,2,3,4,5,255):
            for width in (8,24):
                for df in (0,1):
                    for reverse in (0,1):
                        out.append(dict(name=f'{family}-{shift}-{limit}-{width}-{df}-{reverse}',
                            seed=len(out), control=NEW[family][3]|(reverse<<7), left=16+shift,
                            top=1,width=width,height=(limit<<8)|(1+len(out)%3),df=df,
                            dirty=0,independent=True))
    return out


def library(directory, mutation=0, entry=True, missing=False, older=False):
    api = ('lmn_draw_prepared_planar_effects_adapter' if older else
           'lmn_draw_planar_bitmap_adapter' if entry else 'lmn_draw_prepared_bitmap_adapter')
    return effects.library(directory,mutation,missing_ports=missing,entry_api=api)


def worker(directory):
    full = library(directory)
    prepared = library(directory,entry=False)
    baseline=[]
    seen,edges,prologue=set(),set(),set()
    counts={}

    def compare(lib,case,expected=None):
        case['seed']=len(baseline)
        sites,branches,original,boundary,entered=render.compare(lib,case)
        if expected is not None and boundary!=expected:
            raise AssertionError(f'{case["name"]}: wrong bitmap boundary {boundary}')
        seen.update(sites);edges.update(branches);prologue.update(original)
        baseline.append(case);gc.collect()
        return sites,branches,entered

    for family in NEW:
        configure(family)
        local_sites,local_edges=set(),set()
        group=cases(family)
        for case in group:
            sites,branches,entered=compare(full,case,('body-returned',NEW[family][1]))
            if not entered:raise AssertionError('Actual8822 entry skipped selected body')
            local_sites|=sites;local_edges|=branches
        if not set(render.BODY_INS)<=local_sites or not render.BODY_EDGES<=local_edges:
            raise RuntimeError(f'{family}: body site/edge coverage incomplete')
        counts[family]=len(group)
        configure(family,entry=False)
        case=group[0].copy();case['name']='prepared-api-'+family
        compare(prepared,case,('body-returned',NEW[family][1]))
    for family in effects.SHIFTED:
        configure(family)
        group=effects.cases(family)
        for case in group:compare(full,case,('body-returned',effects.SHIFTED[family][1]))
        counts[family]=len(group)
    for family in ('opaque','masked','protected','read-mask','effect20','effect40'):
        configure(family)
        group=aligned.cases(family)
        for case in group:compare(full,case,('body-returned',aligned.FAMILIES[family][1]))
        counts[family]=len(group)
    # The older effects API continues to expose the four newly translated paths.
    old=library(directory,entry=False,older=True)
    for family in NEW:
        configure(family,entry=False,seam=True)
        case=cases(family)[0];case.update(name='older-api-retains-'+family,independent=False)
        compare(old,case,('continuation',NEW[family][0]))
    configure('opaque')
    for case in (
        dict(name='full-entry-clip-fully-left',left=0xfff0,width=8,height=0x0101,control=4),
        dict(name='full-entry-clip-fully-above',top=0xfff0,width=8,height=0x0108,control=8),
        dict(name='full-entry-clip-zero-width',width=0,height=0x0108,control=12),
        dict(name='full-entry-clip-zero-height',width=24,height=0,control=12),
        dict(name='full-entry-source-pitch-overwrites-height-save',same_segments=True,sp=0x6700,
             width=64,height=0xaa10,control=12,restored_height=8,left=0xfff0,top=0xfff0),
        dict(name='full-entry-extent-overwrites-live-saves',same_segments=True,sp=0x66fc,
             width=64,height=16,control=12,restored_width=128,restored_left=8,top=0xfff0)):
        case.setdefault('left',16);case.setdefault('top',1);case.update(df=0,dirty=0,independent=False)
        # These live saves are changed by the prologue/preparation stores. The
        # extent alias selects a drawable aligned body despite the input top.
        return_site = 0x9966 if case['name']=='full-entry-extent-overwrites-live-saves' else 0x88ab
        compare(full,case,('body-returned',return_site))
    for original in render.plan.base_cases():
        if original['name'] not in ('dirty-near-return-low-byte-alias','dirty-near-return-high-byte-alias',
                                    'dirty-zero-width-live-save-overwrite'):continue
        case=original.copy();case['name']='full-entry-'+case['name'];case['independent']=False
        compare(full,case,('changed-child-return',case['return_ip']))
    configure('read-mask',seam=True)
    case=dict(name='actual-entry-missing-byte-provider',control=0x4002,left=16,top=1,
              width=16,height=0x0101,df=0,dirty=0,independent=False)
    compare(library(directory,missing=True),case,('continuation',0x969c))
    mutations=[]
    configure('shifted-opaque')
    witness=next(c for c in baseline if c['name']=='shifted-opaque-3-4-24-1-1')
    for mutation in (1,2,3):
        try:render.compare(library(directory,mutation),witness)
        except AssertionError as error:
            mutations.append(dict(mutation=mutation,case=witness['name'],reason=str(error)))
        else:raise RuntimeError(f'RENDER_MUTATION={mutation} survived full entry')
        finally:gc.collect()
    if not set(render.PROLOGUE)<=seen or 0x88ab not in seen:
        raise RuntimeError('Native actual-entry prologue/abort coverage incomplete')
    sources=('drawing_render','drawing_plan','drawing_inputs','drawing_clip','drawing_dirty',
        'drawing_dispatch','drawing_source','aligned_opaque','aligned_masked','aligned_protected',
        'aligned_read_mask','aligned_mask_effects','shifted_mask_effects','shifted_opaque','shifted_masked',
        'shifted_protected','shifted_read_mask')
    dependencies=tuple('c/'+n+ext for n in sources for ext in ('.c','.h'))
    dependencies+=('c/lemmings_sym.h','c/regs.h','c/special_blit.h','tests/drawing_bitmap.py',
        'tests/drawing_render.py','tests/drawing_aligned_render.py','tests/drawing_shifted_render.py',
        'tests/drawing_masked_render.py','tests/drawing_plan.py','tests/drawing_inputs.py',
        'tests/aligned_read_mask.py','tests/aligned_masked.py','tests/minimap_vga.py','tests/special_blit.py',
        'tests/dat_io.py','tests/dat_io_c.py','tools/cbuild.py','tools/difftest.py','tools/coverage.py',
        'tools/bounded_process.py','tools/unpack.py','metadata/symbols.json')
    write_json(BUILD/'drawing-bitmap-differential.json',dict(image='main',image_sha256=sha(render.IMAGE),
        case_count=len(baseline),cases=baseline,body_counts=counts,mutation_count=3,mutations_detected=mutations,
        executed_instruction_addresses=sorted(seen),branch_edges=sorted(edges),
        original_only_prologue_sites=sorted(prologue),translated_code_bytes=12,
        input_hashes={p:sha((ROOT/p).read_bytes()) for p in dependencies},
        domain='Actual8822 entry native prologue/preparation/all12bodies/88AB return; constructedintactcode/quiescentIRQ domains. FullRAM/register/definedflags/orderedbus/ports/VGA state and packedbit/whole-plane footprints. Changed child returns and absent969C byteprovider explicit seams; olderAPI scopes retained. UNKNOWN bytes remain excluded.'))
    print(f'PASS full bitmap: {len(baseline)} cases,{len(seen)} integrated sites,{len(edges)} edges;3mutants')


if __name__=='__main__':
    (BUILD/'drawing-bitmap-differential.json').unlink(missing_ok=True)
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2])
    elif len(sys.argv)==1:
        with temporary_build_directory(prefix='drawing-bitmap-',parent=BUILD) as directory:
            run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',directory],cwd=ROOT,timeout=180)
    else:raise SystemExit('Unexpected drawing_bitmap arguments')

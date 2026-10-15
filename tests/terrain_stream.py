"""Complete terrain command streams, native loops versus bounded original code."""
import ctypes
import gc
import hashlib
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'tools'),
                str(Path(__file__).resolve().parent)]
import terrain_drawing as piece
from terrain_drawing import common, oracle, Regs, MEM, Ports, IMAGE, ORACLE
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, sha, write_json, read_json
from resources import section_spans, decode_section
from unpack import relocated

RANGES = ((0x374f,0x376a),(0x395f,0x397a))
LOCAL = {i.address:i for lo,hi in RANGES
         for i in piece.MD.disasm(IMAGE[lo:hi],lo)}
piece.INS.update(LOCAL)
piece.BRANCHES.update(p for p,i in LOCAL.items()
    if i.group(piece.capstone.CS_GRP_JUMP))
piece.MAX_STEPS = 20_000_000
# At most 32 MiB of flag/mask bytes per trace. VGA order is streamed, never
# retained as a Python tuple per access. The enclosing job remains the ceiling.
common.MAX_BUS_EVENTS = 8_000_000
common.MAX_VGA_EVENTS = 3_000_000
CURSOR = piece.field('LevelTerrainDefinitions')
DEPENDENCIES = tuple(sorted({
    *('c/'+n+e for n in ('terrain_stream','terrain_drawing','drawing_render',
        'drawing_plan','drawing_inputs','drawing_clip','drawing_dirty',
        'drawing_dispatch','drawing_source','aligned_opaque','aligned_masked',
        'aligned_protected','aligned_read_mask','aligned_mask_effects',
        'shifted_opaque','shifted_masked','shifted_protected','shifted_read_mask',
        'shifted_mask_effects') for e in ('.c','.h')),
    'c/regs.h','c/special_blit.h','c/lemmings_sym.h','metadata/symbols.json',
    'tests/terrain_stream.py','tests/terrain_drawing.py','tests/drawing_render.py',
    'tests/drawing_bitmap.py','tests/drawing_aligned_render.py',
    'tests/drawing_masked_render.py','tests/drawing_shifted_render.py',
    'tests/drawing_plan.py','tests/drawing_inputs.py','tests/drawing_dispatch.py',
    'tests/drawing_source.py','tests/drawing_clip.py','tests/drawing_dirty.py',
    'tests/aligned_masked.py','tests/aligned_read_mask.py','tests/dat_io.py',
    'tests/dat_io_c.py','tests/minimap_vga.py','tests/special_blit.py',
    'tools/cbuild.py','tools/unpack.py','tools/common.py','tools/resources.py',
    'tools/bounded_process.py','tools/difftest.py','tools/coverage.py',
    'assets/vgalemmi.exe',
    *(f'assets/level{i:03d}.dat' for i in range(10)),
    *(f'assets/{n}' for n in piece.GROUND)}))


class Call(ctypes.Structure):
    _fields_=[(n,ctypes.c_uint16) for n in ('data_segment','game_data_segment',
        'code_segment','stack_segment','stack_offset','packed_counts',
        'width_state','mask_cursor','control','output_segment','flags')]


class Result(ctypes.Structure):
    _fields_=[('state',piece.SourceState)]+[(n,ctypes.c_uint16) for n in
        ('data_segment','output_segment','code_segment','stopped','changed_return')]


class DeviceTrace:
    """Constant-memory VGA order. Full phase-defined flags use the bus trace."""
    def __init__(self):
        self.count=0
        self.digest=hashlib.sha256()

    def append(self,item):
        if self.count>=common.MAX_VGA_EVENTS:
            raise common.GuardExhaustion('stream VGA event budget exhausted')
        kind,address,value,flags=item
        self.digest.update(struct.pack('<BIHH',{'read':0,'write':1,'out':2,'outb':3,'inb':4}[kind],
                                      address,value,flags&0x600))
        self.count+=1

    def __len__(self):return self.count

    def signature(self):return self.count,self.digest.hexdigest()


def command(x,y,index=2,control=0):
    return ((x&8191)|((control&7)<<13),(((y+4)&511)<<7)|index)


def cases():
    result=[]
    def add(name,**kw):result.append(dict(name=name,seed=len(result),**kw))
    for redraw in (0,1):
        add(f'empty-{redraw}',redraw=redraw,commands=[])
        for df in (0,1):
            add(f'multi-family-{redraw}-df{df}',redraw=redraw,df=df,
                commands=[command(128+s,5+n,2,control)
                    for n,control in enumerate(range(8)) for s in (0,3)],
                independent=True)
        add(f'full-ffff-only-{redraw}',redraw=redraw,
            commands=[(0xfffe,0x0202),command(131,5)],independent=True)
        add(f'past400-{redraw}',redraw=redraw,
            commands=[command(8191,5)]*401,independent=True)
        for sp in (0,1,3,0xfffe,0xffff):
            add(f'stack-{redraw}-{sp:04x}',redraw=redraw,sp=sp,
                commands=[command(8191,5)],independent=True)
        add(f'live-DS-{redraw}',redraw=redraw,ds=0x3000,
            commands=[command(131,5),command(140,6)],independent=True)
        add(f'changed-live-DS-{redraw}',redraw=redraw,same_segments=True,
            sp=0x6710,width=8,height=1,source_fill=0xc0,returned_ds=0x0018,
            commands=[command(131,5)])
        add(f'live-SI-{redraw}',redraw=redraw,same_segments=True,sp=0xa94d,
            load=0x0310,width=24,height=3,commands=[command(131,5)],
            extra_sentinel=0x1004,expected_si=0x1008)
        add(f'changed-far-{redraw}',redraw=redraw,same_segments=True,sp=0x66fd,
            load=0x1010,width=16,height=1,commands=[command(8191,5)],
            expected='changed-child-far')
        add(f'changed-near-{redraw}',redraw=redraw,sp=0x4808,base=0x47fd,
            dirty=255,width=8,height=8,commands=[command(16,0)],
            expected='changed-child-near')
        add(f'changed-piece-return-{redraw}',redraw=redraw,same_segments=True,
            sp=0x66fc,width=128,height=1,commands=[command(8191,5)],
            extra_sentinel=0x0010,expected_si=0x0010,expected='changed-child-near')
    for group in range(10):
        asset=f'assets/level{group:03d}.dat'
        packed=(ROOT/asset).read_bytes()
        spans=section_spans(packed)
        if len(spans)!=8:raise common.VerificationFailure('LEVEL section count')
        for section,(lo,hi) in enumerate(spans):
            level,_=decode_section(packed[lo:hi])
            if len(level)!=2048:raise common.VerificationFailure('LEVEL size')
            commands=[]
            for at in range(0x120,0x760,4):
                horizontal=int.from_bytes(level[at:at+2],'big')
                if horizontal==0xffff:break
                commands.append((horizontal,int.from_bytes(level[at+2:at+4],'big')))
            else:raise common.VerificationFailure('pinned LEVEL lacks sentinel')
            for redraw in (0,1):
                add(f'level-{group:03d}-{section}-{redraw}',redraw=redraw,
                    level_asset=asset,section=section,ground=f'ground{level[27]}o.dat',
                    commands=commands,independent=True)
    return result


def put_command(memory,ds,cursor,words):
    for n,value in enumerate(b''.join(v.to_bytes(2,'big') for v in words)):
        memory[oracle.at(ds,(cursor+n)&65535)]=value


def prepare(case):
    memory,regs,flags,game_ds=piece.prepare(case)
    regs['ip']=RANGES[case['redraw']][0]
    # Both entries overwrite incoming SI; seed it distinctly from the stream.
    regs['si']=0xa357
    if 'source_fill' in case:
        memory[0x50000:0x60000]=bytes((case['source_fill'],))*65536
    # The live DS may change after a draw. Both frames contain the same input
    # initially; every later fetch must still use the returned segment/cursor.
    for ds in {regs['ds'],game_ds}:
        if not case.get('ground'):
            piece.record(memory,ds,2,case.get('width',24),case.get('height',3),
                         0x2000,0x4000)
        for n,words in enumerate([*case['commands'],(0xffff,0x57ad)]):
            put_command(memory,ds,(CURSOR+4*n)&65535,words)
        if 'extra_sentinel' in case:
            put_command(memory,ds,case['extra_sentinel'],(0xffff,0xa35b))
    if 'returned_ds' in case:
        put_command(memory,case['returned_ds'],CURSOR+4,(0xffff,0x359a))
    return memory,regs,flags,game_ds


def library(directory,mutation=0,compile=False):
    path=Path(directory)/f'terrain-stream-{mutation}.dll'
    if compile:build(path,mutation,'terrain_stream')
    lib=ctypes.CDLL(str(path))
    lib.lmn_draw_terrain_stream_adapter.argtypes=[MEM,ctypes.POINTER(Regs),
        ctypes.c_uint16,ctypes.c_uint,ctypes.POINTER(common.RasterBus),ctypes.POINTER(Ports)]
    lib.lmn_draw_terrain_stream_adapter.restype=None
    lib.lmn_draw_terrain_stream_core.argtypes=[MEM,ctypes.POINTER(Call),ctypes.c_uint,
        ctypes.POINTER(common.RasterBus),ctypes.POINTER(Ports)]
    lib.lmn_draw_terrain_stream_core.restype=Result
    return lib


def compare(lib,case,core=False):
    memory,regs,flags,game_ds=prepare(case)
    c=common.TraceDevice(bytearray(memory),case['seed']+0x374f)
    o=common.TraceDevice(bytearray(memory),case['seed']+0x374f)
    c.vga.trace=DeviceTrace();o.vga.trace=DeviceTrace()
    ports=piece.byte_ports(c)
    state=Regs(**regs,flags=flags)
    start=time.monotonic()
    if core:
        call=Call(regs['ds'],game_ds,regs['cs'],regs['ss'],regs['sp'],
            regs['cx'],regs['dx'],regs['di'],regs['bp'],regs['es'],flags)
        result=lib.lmn_draw_terrain_stream_core(
            (ctypes.c_uint8*(1<<20)).from_buffer(c.memory),ctypes.byref(call),
            case['redraw'],ctypes.byref(c.bus),ctypes.byref(ports))
        s=result.state
        state=Regs(s.work_value,s.second_source_cursor,s.packed_counts,s.width_state,
            s.source_cursor,s.destination_cursor,s.control,s.stack_offset,
            result.code_segment,result.data_segment,result.output_segment,regs['ss'],
            s.continuation,s.flags)
    else:
        lib.lmn_draw_terrain_stream_adapter((ctypes.c_uint8*(1<<20)).from_buffer(c.memory),
            ctypes.byref(state),game_ds,case['redraw'],ctypes.byref(c.bus),ctypes.byref(ports))
    c.check(case['name'])
    native_seconds=time.monotonic()-start
    independent_count=0
    pending=None
    piece_count=0
    def observe(off,u,device):
        nonlocal pending,independent_count,piece_count
        if off==0x7c67:piece_count+=1
        if not case.get('independent'):return
        if off in piece.FAMILIES:
            entry={n:u.reg_read(r) for n,r in oracle.REG.items()}
            entry['flags']=u.reg_read(piece.x.UC_X86_REG_EFLAGS)
            piece.bitmap.configure(piece.FAMILIES[off])
            pending=piece.render._independent_planes(device.vga.planes,
                device.memory,entry,game_ds)
        elif piece.INS[off].mnemonic=='retf' and pending is not None:
            common.require(pending==device.vga.planes,
                f'{case["name"]}:piece{piece_count}: independent planes differ')
            independent_count+=1;pending=None
    actual,mask,seen,edges,boundary,_child,_body=piece.original(case,o,regs,flags,
        continuations=(RANGES[case['redraw']][1],),observe=observe)
    for name in oracle.REG_NAMES:
        common.require(getattr(state,name)==actual[name],
            f'{case["name"]}:{name} C={getattr(state,name):04x}/ASM={actual[name]:04x};{boundary}')
    common.require(not((state.flags^actual['flags'])&mask),f'{case["name"]}:flags differ')
    common.require(c.memory==o.memory,f'{case["name"]}:whole RAM differs')
    common.compare_event_traces(c.events,o.events,case['name'])
    common.require(c.vga.state()==o.vga.state(),f'{case["name"]}:VGA state differs')
    common.require(c.vga.trace.signature()==o.vga.trace.signature(),f'{case["name"]}:VGA order differs')
    common.require(boundary[0]==case.get('expected','continuation'),
        f'{case["name"]}:unexpected boundary {boundary}')
    if 'expected_si' in case:
        common.require(actual['si']==case['expected_si'],f'{case["name"]}:live SI differs')
    if 'returned_ds' in case:
        common.require(actual['ds']==case['returned_ds'],f'{case["name"]}:live DS differs')
    if core:
        common.require(result.stopped==int(boundary[0]!='continuation'),
                       f'{case["name"]}:core stopped status differs')
        common.require(result.changed_return==int(boundary[0].startswith('changed')),
                       f'{case["name"]}:core changed-return status differs')
    if not case.get('expected') and 'extra_sentinel' not in case:
        common.require(piece_count==len(case['commands']),f'{case["name"]}:piece count differs')
    for lo,hi in (*RANGES,(0x7c67,0x7cbc),(0x8822,0x9a90)):
        p=(regs['cs']<<4)+lo
        if o.memory[p:p+hi-lo]!=relocated(IMAGE,ORACLE['relocations'],regs['cs'])[lo:hi]:
            raise common.VerificationFailure('Executing code modified')
    o.check(case['name'])
    return dict(name=case['name'],seed=case['seed'],redraw=case['redraw'],
        commands=len(case['commands']),pieces_executed=piece_count,
        independently_checked_bodies=independent_count,boundary=boundary,
        bus_events=c.events.count,vga_events=len(c.vga.trace),
        native_seconds=round(native_seconds,3),total_seconds=round(time.monotonic()-start,3),
        executed_instruction_addresses=sorted(seen),branch_edges=sorted(edges))


def worker(directory,index):
    case=cases()[index]
    result=compare(library(directory),case)
    if not case.get('level_asset'):
        compare(library(directory),case,core=True)
    write_json(Path(directory)/f'case-{index}.json',result)
    print(f'PASS {case["name"]}: {result["pieces_executed"]} pieces, '
          f'{result["bus_events"]} events, {result["total_seconds"]}s',flush=True)
    gc.collect()


def mutation_worker(directory,mutation):
    name={4:'changed-live-DS-0',5:'changed-piece-return-0'}[mutation]
    case=next(c for c in cases() if c['name']==name)
    try:compare(library(directory,mutation),case)
    except common.Mismatch as error:
        write_json(Path(directory)/f'mutation-{mutation}.json',
            dict(mutation=mutation,case=name,reason=str(error)))
    else:raise common.VerificationFailure(f'TERRAIN_STREAM_MUTATION={mutation} survived')
    print(f'PASS stream mutation{mutation}: {name}',flush=True)


def campaign(directory,selected=None):
    report=BUILD/'terrain-stream-differential.json'
    progress=BUILD/'terrain-stream-progress.json'
    if selected is None:
        report.unlink(missing_ok=True)
        progress.unlink(missing_ok=True)
    group=cases()
    indices=list(range(len(group))) if selected is None else selected
    input_hashes={p:sha((ROOT/p).read_bytes()) for p in DEPENDENCIES}
    with ThreadPoolExecutor(max_workers=2) as executor:
        build(Path(directory)/'terrain-stream-0.dll',0,'terrain_stream')
        def run_case(index):
            run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',directory,str(index)],
                        cwd=ROOT,timeout=300,memory_mib=384)
            return read_json(Path(directory)/f'case-{index}.json')
        todo=iter(indices)
        pending={executor.submit(run_case,index):index for index in [next(todo,None),next(todo,None)]
                 if index is not None}
        completed={}
        while pending:
            done,_=wait(pending,return_when=FIRST_COMPLETED)
            for future in done:
                index=pending.pop(future)
                completed[index]=future.result()
                if selected is None:
                    # Retain bounded diagnostics outside the disposable DLL
                    # directory. This journal is never an acceptance report
                    # or a reason to skip original/native executions.
                    write_json(progress,dict(accepted=False,
                        input_hashes=input_hashes,expected_case_count=len(group),
                        cases=[completed[n] for n in sorted(completed)]))
                following=next(todo,None)
                if following is not None:
                    pending[executor.submit(run_case,following)]=following
        results=[completed[index] for index in indices]
        if selected is not None:return
        mutations=[]
        for mutation in (4,5):
            build(Path(directory)/f'terrain-stream-{mutation}.dll',mutation,'terrain_stream')
            run_bounded([sys.executable,str(Path(__file__).resolve()),'--mutation-worker',
                        directory,str(mutation)],cwd=ROOT,timeout=30,memory_mib=384)
            mutations.append(read_json(Path(directory)/f'mutation-{mutation}.json'))
        seen={p for r in results for p in r['executed_instruction_addresses']}
        if not set(LOCAL)<=seen:raise common.VerificationFailure('loop site coverage incomplete')
        edges={tuple(e) for r in results for e in r['branch_edges']}
        local_edges={(p,i.operands[0].imm&65535) for p,i in LOCAL.items()
                     if p in piece.BRANCHES}
        local_edges|={(p,p+i.size) for p,i in LOCAL.items()
                      if p in piece.BRANCHES and i.mnemonic!='jmp'}
        if not local_edges<=edges:
            raise common.VerificationFailure(
                f'loop edge coverage incomplete: missing={sorted(local_edges-edges)}')
        if input_hashes!={p:sha((ROOT/p).read_bytes()) for p in DEPENDENCIES}:
            raise common.VerificationFailure('Terrain campaign inputs changed while running')
        write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(results),
            mutation_count=len(mutations),mutations_detected=mutations,cases=results,
            translated_code_bytes=54,caller_instruction_addresses=sorted(LOCAL),
            ranges=[dict(start=lo,end_exclusive=hi,sha256=sha(IMAGE[lo:hi])) for lo,hi in RANGES],
            core_boundary_case_count=sum(not c.get('level_asset') for c in group),
            executed_instruction_addresses=sorted(seen),
            branch_edges=sorted(edges),
            input_hashes=input_hashes,
            limits=dict(worker_timeout_seconds=300,windows_process_commit_mib=384,
                bus_events=common.MAX_BUS_EVENTS,vga_events=common.MAX_VGA_EVENTS,
                instructions=piece.MAX_STEPS),
            domain='Both complete terrain loops with all80 pinned LEVEL streams twice, '
                'matching GROUND metadata and constructed graphics bytes; visible1664x164 '
                'viewport, allRAM/registers/definedflags/orderedbus/device-state comparisons. '
                'Wholeplane independent expectations for each ordinary body. Changed live '
                'SI/DS/near/far returns and empty sentinel preserve original contracts. '
                'No boot, no native400-command bound; platform/IRQ/allocation ownership open.'))
        print(f'PASS terrain streams: {len(results)} cases, {len(seen)} sites',flush=True)


if __name__=='__main__':
    if len(sys.argv)==4 and sys.argv[1]=='--worker':worker(sys.argv[2],int(sys.argv[3]))
    elif len(sys.argv)==4 and sys.argv[1]=='--mutation-worker':mutation_worker(sys.argv[2],int(sys.argv[3]))
    elif len(sys.argv)>=3 and sys.argv[1]=='--campaign-worker':
        campaign(sys.argv[2],None if len(sys.argv)==3 else [int(n) for n in sys.argv[3:]])
    elif len(sys.argv)==1 or (len(sys.argv)>=3 and sys.argv[1]=='--selected'):
        with temporary_build_directory(prefix='terrain-stream-',parent=BUILD) as directory:
            # This outer job bounds the combined coordinator/two-worker tree
            # at768 MiB, including every compiler and nested test child.
            run_bounded([sys.executable,str(Path(__file__).resolve()),'--campaign-worker',
                         directory,*sys.argv[2:]],cwd=ROOT,timeout=14_400,memory_mib=512)
    else:raise SystemExit('Unexpected terrain_stream arguments')

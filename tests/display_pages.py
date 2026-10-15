"""Pinned page-copy/clear instructions with independent planar results."""
import ctypes
import gc
import random
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
import text_glyph as glyph
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, read_json, write_json, sha

common, caller, piece, video = glyph.common, glyph.caller, glyph.piece, glyph.video
IMAGE, ORACLE = glyph.IMAGE, glyph.ORACLE
COPY_CODE = bytes.fromhex('bac403b8020f36a30800efbace03b8050136a30000ef1e8b36761f8b3e781fb800a08ed88ec0b9606df3a41fc3')
CLEAR_CODE = bytes.fromhex('bf0000b9606deb01')
COPY = {i.address:i for i in piece.MD.disasm(COPY_CODE,0x4dc2)}
CLEAR = {i.address:i for i in piece.MD.disasm(CLEAR_CODE,0x4def)}
TAIL = {i.address:i for i in piece.MD.disasm(IMAGE[0x4df8:0x4e37],0x4df8)}
INS = COPY | CLEAR | TAIL
REPORT = BUILD/'display-pages-differential.json'
ORIGINAL_REPORT = BUILD/'display-pages-contract-original.json'
PAGE = 0x6d60


class Result(ctypes.Structure):
    _fields_ = [('state',video.State),('continuation',ctypes.c_uint16),('status',ctypes.c_int)]


def cases():
    rows=[]
    def add(name,**kw): rows.append(dict(name=name,seed=len(rows),**kw))
    for df in (0,1):
        for source,dest in ((0,0x6d60),(0x6d5f,0xdabf),(0,1),(1,0),
                            (0xffff,0),(0,0xffff),(0xfffe,0x8000),(0x1234,0x1234)):
            add(f'copy-{source:04x}-{dest:04x}-df{df}',source=source,dest=dest,df=df)
    for sp in (0,1,0xffff): add(f'copy-stack-{sp:04x}',sp=sp)
    add('copy-stack-A20',ss=0xffff,sp=0xf)
    add('copy-data-A20',ds=0xffff)
    add('copy-push-alias-source',same_segments=True,sp=0x1f78)
    add('copy-push-alias-destination',same_segments=True,sp=0x1f7a)
    add('copy-OUT-changes-origins',effect=True)
    add('copy-VGA-stack',ss=0xa000,sp=0x8000)
    add('copy-VGA-data',ds=0xa000)
    for raw_read,raw_write in ((True,False),(False,True),(True,True)):
        add(f'copy-RAM-fallback-{raw_read}-{raw_write}',raw_read=raw_read,raw_write=raw_write)
    for missing in ('bus','port','dropped-port'): add('copy-missing-'+missing,missing=missing)
    for df in (0,1):
        add(f'clear-full-df{df}',clear=True,df=df)
        add(f'clear-VGA-stack-df{df}',clear=True,df=df,ss=0xa000,sp=0x20)
    for sp in (0,1,8,0xffff): add(f'clear-stack-{sp:04x}',clear=True,sp=sp)
    add('clear-stack-A20',clear=True,ss=0xffff,sp=0xf)
    for missing in ('bus','read','write','port'):
        add('clear-missing-'+missing,clear=True,missing=missing)
    return rows


def prepare(case):
    rng=random.Random(0x4dc2+case['seed'])
    load=(0x1010,0x1213,0x2345)[case['seed']%3]
    memory=bytearray(rng.randbytes(1<<20))
    memory[load<<4:(load<<4)+len(IMAGE)]=glyph.relocated(IMAGE,ORACLE['relocations'],load)
    regs={k:rng.randrange(65536) for k in piece.oracle.REG_NAMES}
    ds=case.get('ds',0x3000)
    regs.update(cs=load,ip=0x4def if case.get('clear') else 0x4dc2,ds=ds,es=0x6000,
                ss=ds if case.get('same_segments') else case.get('ss',0x7000),sp=case.get('sp',0x8000))
    flags=2|((case['seed']*0x95)&0xad5)
    flags=(flags&~0x400)|(0x400 if case.get('df') else 0)
    piece.oracle.put16(memory,ds,0x1f76,case.get('source',0))
    piece.oracle.put16(memory,ds,0x1f78,case.get('dest',0x6d60))
    piece.oracle.put16(memory,regs['ss'],regs['sp'],0xbeef)
    return memory,regs,flags


def device(memory,regs,case):
    d=common.TraceDevice(bytearray(memory),0x4dc2+case['seed'],read_map=case['seed']%4)
    add_event=d.events.add
    def observable_event(kind,*args):
        # A missing callback has no callback-visible event. Normal bus cases
        # retain every CPU byte access; RAM fallbacks compare full RAM/state
        # and the order/flags of whichever callbacks remain installed.
        if case.get('missing')=='bus':return
        if kind=='read' and case.get('raw_read'):return
        if kind=='write' and case.get('raw_write'):return
        add_event(kind,*args)
    d.events.add=observable_event
    d.pending_sync=False
    original_out=d.vga.out
    def output(port,value,flags):
        original_out(port,value,flags)
        if case.get('effect') and d.vga.outcount==1:
            piece.oracle.put16(d.memory,regs['ds'],0x1f76,0x2345)
            piece.oracle.put16(d.memory,regs['ds'],0x1f78,0x4321)
            d.pending_sync=True
        if case.get('missing')=='dropped-port' and d.vga.outcount==1:
            d.bus.out_word=common.OUT()
    d.vga.out=output
    if regs['ds']==0xa000:
        for plane in d.vga.planes:
            piece.oracle.put16(plane,0,0x1f76,case.get('source',0))
            piece.oracle.put16(plane,0,0x1f78,case.get('dest',0x6d60))
    if regs['ss']==0xa000:
        for plane in d.vga.planes: piece.oracle.put16(plane,0,regs['sp'],0xbeef)
    if case.get('raw_read'):
        d.vga.read=lambda mem,p,_flags:mem[p]
    if case.get('raw_write'):
        def raw_write(mem,p,value,_flags):mem[p]=value
        d.vga.write=raw_write
    return d


def ports_missing(case):
    return case.get('missing') in ('bus','port')


def boundary(case):
    if case.get('clear') and case.get('missing'): return 0x4df8,2
    if ports_missing(case): return 0x4dcc,1
    if case.get('missing')=='dropped-port': return 0x4dd7,1
    return (0x4e36 if case.get('clear') else 0x4dee),0


def planar_copy(planes,source,dest,step):
    expected=[bytearray(p) for p in planes]
    for plane in expected:
        s,t=source,dest
        for _ in range(PAGE):
            plane[t]=plane[s]
            s=(s+step)&65535;t=(t+step)&65535
    return expected


def model(case,memory,regs,flags,core):
    d=device(memory,regs,case);s=dict(regs,flags=flags);mask=0xfd7;sites=set()
    def mark(pc):sites.add(pc)
    def read(p):
        p&=0xfffff;v=d.vga.read(d.memory,p,s['flags']);d.events.add('read',p,v,s['flags'],mask);d.check('model read');return v
    def write(p,v):
        p&=0xfffff;d.vga.write(d.memory,p,v,s['flags']);d.events.add('write',p,v,s['flags'],mask);d.check('model write')
    def put(seg,off,v):
        p=piece.oracle.at(seg,off);write(p,v&255);write(p+1,v>>8)
    def word(seg,off):
        p=piece.oracle.at(seg,off);low=read(p);return low|read(p+1)<<8
    def pop():
        value=word(s['ss'],s['sp']);s['sp']=(s['sp']+2)&65535;return value
    def out():
        d.vga.out(s['dx'],s['ax'],s['flags']);d.events.add('out',s['dx'],s['ax'],s['flags'],mask);d.check('model out')
    stop,status=boundary(case)
    if case.get('clear'):
        mark(0x4def);s['di']=0;mark(0x4df2);s['cx']=PAGE;mark(0x4df5)
        if status:return d,dict(s,ip=stop),mask,sites,status
        sequence=((0x4df8,0x4dfb,0x4dfe,0x4e02,8,0x3c4,0x0f02),
            (0x4e03,0x4e06,0x4e08,0x4e0c,10,0x3ce,0),
            (None,0x4e0d,0x4e10,0x4e14,12,0x3ce,0x0f01),
            (None,0x4e15,0x4e18,0x4e1c,0,0x3ce,5),
            (None,0x4e1d,0x4e20,0x4e24,2,0x3ce,3),
            (None,0x4e25,0x4e28,0x4e2c,14,0x3ce,0xff08))
        for dxpc,axpc,storepc,outpc,offset,port,value in sequence:
            if dxpc:mark(dxpc);s['dx']=port
            mark(axpc);s['ax']=value
            if axpc==0x4e06:s['flags']=(s['flags']&~0x8d5)|0x44;mask=0xfc7
            mark(storepc);put(s['ss'],offset,value);mark(outpc);out()
        mark(0x4e2d);s['ax']=0xa000;mark(0x4e30);s['es']=0xa000
        mark(0x4e32);s['flags']=(s['flags']&~0x8d5)|0x44;mask=0xfc7
        planes=[bytearray(p) for p in d.vga.planes];step=-1 if flags&0x400 else 1
        mark(0x4e34)
        for n in range(PAGE):
            for plane in planes:plane[(n*step)&65535]=0
            write(0xa0000+s['di'],0);s['di']=(s['di']+step)&65535;s['cx']-=1
        if d.vga.planes!=planes:glyph.fail(case['name']+': independent clear footprint differs')
    else:
        mark(0x4dc2);s['dx']=0x3c4;mark(0x4dc5);s['ax']=0x0f02
        mark(0x4dc8);put(s['ss'],8,s['ax'])
        if stop==0x4dcc:return d,dict(s,ip=stop),mask,sites,status
        mark(0x4dcc);out();mark(0x4dcd);s['dx']=0x3ce;mark(0x4dd0);s['ax']=0x0105
        mark(0x4dd3);put(s['ss'],0,s['ax'])
        if stop==0x4dd7:return d,dict(s,ip=stop),mask,sites,status
        mark(0x4dd7);out();mark(0x4dd8);s['sp']=(s['sp']-2)&65535;put(s['ss'],s['sp'],s['ds'])
        mark(0x4dd9);s['si']=word(s['ds'],0x1f76);mark(0x4ddd);s['di']=word(s['ds'],0x1f78)
        mark(0x4de1);s['ax']=0xa000;mark(0x4de4);s['ds']=0xa000;mark(0x4de6);s['es']=0xa000
        mark(0x4de8);s['cx']=PAGE;step=-1 if flags&0x400 else 1
        planes=planar_copy(d.vga.planes,s['si'],s['di'],step)
        mark(0x4deb)
        for _ in range(PAGE):
            value=read(0xa0000+s['si']);write(0xa0000+s['di'],value)
            s['si']=(s['si']+step)&65535;s['di']=(s['di']+step)&65535;s['cx']-=1
        if not(case.get('raw_read') or case.get('raw_write')) and d.vga.planes!=planes:
            glyph.fail(case['name']+': independent four-plane sequential copy differs')
        mark(0x4ded);s['ds']=pop()
        if case['name']=='copy-VGA-stack' and s['ds']==regs['ds']:
            glyph.fail('Device-backed POP DS witness did not change DS')
    s['ip']=stop
    if not core:mark(stop);s['ip']=pop()
    return d,s,mask,sites,status


def original_case(case,core):
    memory,regs,flags=prepare(case)
    expected,s,mask,sites,status=model(case,memory,regs,flags,core)
    d=device(memory,regs,case);stop,_=boundary(case)
    def observe(_pc,cpu,_device):
        if d.pending_sync:
            cpu.mem_write(0,bytes(d.memory));cpu.mem_write(1<<20,bytes(d.memory));d.pending_sync=False
    result=caller.original(case,d,regs,flags,instructions=INS,far_calls=set(),
        continuations=(stop,) if status else (),stop_before=stop if core and not status else None,
        max_steps=PAGE+40,observe=observe)
    actual,actual_mask,seen,edges,bound,_child,_body=result
    label=case['name']+f'/core{core}'
    for k in piece.oracle.REG_NAMES:
        if actual[k]!=s[k]:glyph.fail(label+f': model {k} {actual[k]:04x}!={s[k]:04x}')
    if (actual['flags']^s['flags'])&mask:glyph.fail(label+': model flags differ')
    if (actual_mask,seen)!=(mask,sites):glyph.fail(label+f': original mask/sites differ {actual_mask:04x}/{mask:04x}, {seen^sites}')
    equal(d,expected,label,glyph.fail)
    return memory,regs,flags,d,actual,mask,seen,edges,bound,status


def equal(actual,expected,label,error):
    if actual.memory!=expected.memory:error(label+': RAM differs')
    if actual.vga.state()!=expected.vga.state():error(label+': VGA state differs')
    try:common.compare_event_traces(actual.events,expected.events,label)
    except common.Mismatch as failure:error(str(failure))
    if len(actual.vga.trace)!=len(expected.vga.trace) or any(a[:3]!=b[:3] or (a[3]^b[3])&0x600 for a,b in zip(actual.vga.trace,expected.vga.trace)):
        error(label+': device order differs')


class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ctypes.CDLL(str(build(Path(directory)/f'display-pages-m{mutation}.dll',mutation,'display_pages')))
        self.cores={};self.adapters={}
        for clear,name in ((False,'copy_drawing_page'),(True,'clear_full_drawing_page')):
            fn=getattr(self.lib,'lmn_'+name+'_core');fn.argtypes=[video.MEM,ctypes.POINTER(video.State),ctypes.POINTER(common.RasterBus)];fn.restype=Result;self.cores[clear]=fn
            fn=getattr(self.lib,'lmn_'+name+'_adapter');fn.argtypes=[video.MEM,ctypes.POINTER(piece.Regs),ctypes.POINTER(common.RasterBus)];fn.restype=None;self.adapters[clear]=fn


def compare(native,case,core):
    memory,regs,flags,original,actual,mask,seen,edges,bound,status=original_case(case,core)
    if native is not None:
        d=device(memory,regs,case)
        if case.get('raw_read') or case.get('missing')=='read':d.bus.read_byte=common.READ()
        if case.get('raw_write') or case.get('missing')=='write':d.bus.write_byte=common.WRITE()
        if case.get('missing')=='port':d.bus.out_word=common.OUT()
        bus=None if case.get('missing')=='bus' else ctypes.byref(d.bus)
        if core:
            r=native.cores[case.get('clear',False)](video.buffer(d.memory),ctypes.byref(video.to_state(dict(regs,flags=flags))),bus)
            got=dict(video.state_dict(r.state),ip=r.continuation,cs=regs['cs'])
            common.require(r.status==status,case['name']+': native status differs')
        else:
            r=piece.Regs(**regs,flags=flags);native.adapters[case.get('clear',False)](video.buffer(d.memory),ctypes.byref(r),bus)
            got={k:getattr(r,k) for k in (*piece.oracle.REG_NAMES,'flags')}
        for k in piece.oracle.REG_NAMES:
            common.require(got[k]==actual[k],case['name']+f': {k} {got[k]:04x}!={actual[k]:04x}')
        common.require(not((got['flags']^actual['flags'])&mask),case['name']+': native flags differ')
        equal(d,original,case['name'],lambda m:common.require(False,m))
    return dict(name=case['name'],core=core,sites=sorted(seen),edges=sorted(edges),boundary=bound,status=status)


def input_hashes(native=False):
    paths=set(glyph.input_hashes(False))|{'tests/display_pages.py','tests/test_vga_write_mode1.py','docs/minimap-vga.md','docs/display-pages.md'}
    if native:paths|={'c/display_pages.c','c/display_pages.h','c/vga_clear.c','c/vga_clear.h','c/video_restore.h','c/regs.h','c/special_blit.h','c/lemmings_sym.h','tools/cbuild.py','tools/difftest.py','tools/coverage.py'}
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def worker(directory=None):
    common.MAX_BUS_EVENTS=60000;common.MAX_VGA_EVENTS=60000
    before=input_hashes(directory is not None)
    if IMAGE[0x4dc2:0x4def]!=COPY_CODE or IMAGE[0x4def:0x4df7]!=CLEAR_CODE or len(COPY)!=18 or len(TAIL)!=25:
        glyph.fail('Pinned display page bytes/sites differ')
    if (sha(IMAGE)!='b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e' or
        sha(glyph.ASSET.read_bytes())!='5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d'):
        glyph.fail('Pinned main/executable identity differs')
    native=Native(directory) if directory is not None else None
    rows=[]
    for case in cases():
        for core in (False,True):rows.append(compare(native,case,core))
        gc.collect()
    sites={p for r in rows for p in r['sites']};edges={tuple(e) for r in rows for e in r['edges']}
    if sites!=set(INS) or edges!={(0x4df5,0x4df8)}:glyph.fail('Page caller/tail site or edge coverage incomplete')
    mutants=[]
    if native is not None:
        for mutation,name in ((1,'copy-push-alias-destination'),(2,'copy-0000-6d60-df1'),
                (3,'copy-0000-6d60-df0'),(4,'copy-VGA-stack'),(5,'clear-full-df0'),(6,'clear-full-df0')):
            lib=Native(directory,mutation);case=next(c for c in cases() if c['name']==name)
            try:compare(lib,case,True)
            except common.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,reason=str(error)))
            else:glyph.fail(f'DISPLAY_PAGES_MUTATION={mutation} survived')
            gc.collect()
    if before!=input_hashes(native is not None):glyph.fail('Display page inputs changed')
    write_json(REPORT if native else ORIGINAL_REPORT,dict(image='main',image_sha256=sha(IMAGE),case_count=len(cases()),boundaries_each_case=2,
        new_unique_caller_bytes=53,caller_sites=21,integrated_sites=46,executed_instruction_addresses=sorted(sites),branch_edges=sorted(edges),
        translated_code_bytes=53 if native else 0,native_code_ranges=[[0x4dc2,0x4df7]] if native else [],cases=rows,
        mutation_count=len(mutants),mutations_detected=mutants,input_hashes=before,c_coverage_claimed=native is not None,
        limits=dict(worker_seconds=120,windows_process_mib=384,windows_tree_mib=640,original_steps=PAGE+40,bus_events=60000,vga_events=60000),
        domain='4DC2 full6D60 sequentialVGA latchcopy plus4DEF fixedclear/native4DF8 tail;model/original/native,definedflags/fullRAM/orderedbus/VGA and independentplanes; providerseams explicit, hardwaretiming/IRQ/stacklimits remain open. UNKNOWN4DF7 unexecuted.'))
    print(f'PASS display pages {"C" if native else "original"}: {len(cases())} fixtures x2 boundaries,21 caller/46 integrated sites;{len(mutants)} completed mutants',flush=True)


def main():
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2]);return
    if sys.argv[1:]==['--original-worker']:worker();return
    if sys.argv[1:]==['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True);run_bounded([sys.executable,str(Path(__file__).resolve()),'--original-worker'],cwd=ROOT,timeout=120,memory_mib=384);return
    if len(sys.argv)!=1:raise SystemExit('Unexpected display pages arguments')
    REPORT.unlink(missing_ok=True)
    try:
        with temporary_build_directory(prefix='display-pages-',parent=BUILD) as directory:
            run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',directory],cwd=ROOT,timeout=120,memory_mib=384)
    except BaseException:
        REPORT.unlink(missing_ok=True);raise


if __name__=='__main__':main()

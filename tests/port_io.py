"""Bounded original/native port leaves; finite providers, no IRQ timing model."""
import copy
import ctypes as ct
import gc
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as base
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build
from common import BUILD,sha,write_json

SIZE,MASK,FLAGS=base.SIZE,base.MASK,base.FLAGS
IMAGE,IDS,REGS,Regs,MEM=base.IMAGE,base.REG_IDS,base.REG_NAMES,base.Regs,base.MEM
physical,put16,get16=base.physical,base.put16,base.get16
check,require,Failure,Mismatch=base.check,base.require,base.OracleFailure,base.Mismatch
START={'eoi':0x18B2,'low':0x4334,'high':0x4359,'axes':0x4386}
RET={'eoi':0x18B6,'low':0x4358,'high':0x4385,'axes':0x43CD}
NAMES={'eoi':'send_master_pic_eoi','low':'poll_port201_buttons_low',
       'high':'poll_port201_buttons_high','axes':'measure_port201_axes'}
RANGES={'eoi':[(0x18B2,0x18B7)],'low':[(0x4334,0x4359)],
        'high':[(0x4359,0x4386)],'axes':[(0x4386,0x4395),(0x4396,0x4398),(0x4399,0x43CE)]}
INS={i.address:i for spans in RANGES.values() for a,b in spans for i in base.MD.disasm(IMAGE[a:b],a)}
EDGES={(0x433C,0x4341),(0x433C,0x433E),(0x4361,0x436A),(0x4361,0x4363),
       (0x4393,0x4396),(0x4396,0x4399),(0x43C6,0x4399),(0x43C6,0x43C8)}
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=420,384,3_000_000,150_000
REPORT=BUILD/'port-io-differential.json';ORIGINAL=BUILD/'port-io-original-differential.json'
OUT8,IN8,Ports=base.OUT8,base.IN8,base.Ports


class Result(ct.Structure):
    _fields_=[('registers',Regs),('status',ct.c_uint16)]


def cases():
    rows=[dict(name='eoi-preserve-ah',kind='eoi'),dict(name='eoi-late-ret',kind='eoi',provider='outer-ret'),
          dict(name='eoi-missing',kind='eoi',missing_out=True,expected=1),
          dict(name='eoi-sp-ffff',kind='eoi',sp=0xFFFF),
          dict(name='eoi-physical-fffff',kind='eoi',ss=0xFFFF,sp=0xF),
          dict(name='eoi-vga-stack',kind='eoi',ss=0xA000,provider='outer-ret')]
    for mask in (0,1,2,4,8,3,12,15,0x80,0xFF):
        rows.append(dict(name=f'axes-mask-{mask:02x}',kind='axes',mask=mask,samples=(255,0)))
    rows += [dict(name='axes-zero-first',kind='axes',samples=(0,)),
             dict(name='axes-live-mask',kind='axes',mask=1,samples=(2,0),new_mask=2),
             dict(name='axes-negative-halves',kind='axes',mask=0xA,repeat=16384,sample=0xA),
             dict(name='axes-counter-wrap',kind='axes',mask=15,repeat=65536,sample=15),
             dict(name='axes-missing-out',kind='axes',missing_out=True,expected=1),
             dict(name='axes-missing-in',kind='axes',missing_in=True,expected=1),
             dict(name='axes-df-if',kind='axes',flags=0x06D7,samples=(15,5,0)),
             dict(name='axes-vga-mask',kind='axes',ds=0xA000,mask=3,samples=(3,2,0))]
    for kind in ('low','high'):
        for bits in range(4):
            shift=4 if kind=='low' else 6
            rows.append(dict(name=f'{kind}-buttons-{bits}',kind=kind,dx=0x12FF,
                             buttons=(~(bits<<shift))&255))
        rows += [dict(name=kind+'-measure',kind=kind,samples=(15,15,7,0),buttons=0xCF),
                 dict(name=kind+'-mask-call-alias',kind=kind,ss=0x3000,ds=0x3000,sp=0x53,
                      samples=(0x40 if kind=='low' else 0x60,0),buttons=0x80),
                 dict(name=kind+'-mask-outer-alias',kind=kind,ss=0x3000,ds=0x3000,sp=0x51,dx=0xABFF),
                 dict(name=kind+'-changed-child',kind=kind,provider='child-ret',expected=2),
                 dict(name=kind+'-missing-child-out',kind=kind,missing_out=True,expected=1),
                 dict(name=kind+'-missing-child-in',kind=kind,missing_in=True,expected=1),
                 dict(name=kind+'-missing-button-in',kind=kind,dx=0xFFFF,missing_in=True,expected=1),
                 dict(name=kind+'-df-if',kind=kind,flags=0x06D7,samples=(15,0),buttons=0)]
    for i,load in enumerate(base.LOADS):rows.append(dict(name=f'axes-load-{load:04x}',kind='axes',load=load,samples=(1,3,4,8,0)))
    return [dict(load=0x1010,seed=0x20100+i)|r for i,r in enumerate(rows)]


def setup(c):
    memory,device=base.initial_memory(c)
    r=base.default_regs(c['load'],c['seed'],ss=c.get('ss',0x5000),sp=c.get('sp',0x9000),
                        ds=c.get('ds',0x3000),flags=c.get('flags',0x00D7))
    r.update(ax=0xA53E,bx=0x1111,cx=0x2222,si=0x3333,di=0x4444,dx=c.get('dx',0x1234),ip=START[c['kind']])
    r['flags']=(r['flags']&0x7ED5)|2
    # Provider-driven VGA mask reads use the same explicit initial planes.
    address=physical(r['ds'],0x51);memory[address]=c.get('mask',15)
    if 0xA0000<=address<0xB0000:
        for p in device.planes:p[address-0xA0000]=memory[address]
    put16(memory,r['ss'],r['sp'],0xD00D,device)
    return memory,r,device


class Access(base.BusAccess):
    def __init__(self,c,memory,r,device):
        super().__init__(c,memory,r,device,max_events=MAX_EVENTS)
    def out(self,port,value,flags,mask=FLAGS):
        self.emit('out8',port,value,flags,mask)
        if self.c.get('provider')=='outer-ret' and 'outer-ret' not in self.providers:
            self.patch(self.r['ss'],self.r['sp'],0xBEEF,'outer-ret')
        if self.c.get('provider')=='child-ret' and 'child-ret' not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']-2)&0xFFFF,0xD234,'child-ret')
    def inp(self,port,flags,mask=FLAGS):
        c=self.c;take_axes=c['kind']=='axes' or (c['kind'] in ('low','high') and (self.r['dx']&255)!=255)
        if c.get('repeat') is not None:
            n=c['repeat'];value=c.get('sample',15) if self.cursor<n else 0
        else:
            seq=list(c.get('samples',(15,0))) if take_axes else []
            if c['kind'] in ('low','high'):seq.append(c.get('buttons',0xCF))
            value=seq[self.cursor] if self.cursor<len(seq) else 0
            if self.cursor>len(seq)+32:raise Failure('finite port provider budget exhausted')
        if self.cursor==0 and 'new_mask' in c:self.patch(self.r['ds'],0x51,c['new_mask'],'live-mask',False)
        self.cursor+=1;self.emit('in8',port,value,flags,mask);return value


class Machine(base.OriginalMachine):
    def __init__(self,c,memory,r,device,core):
        super().__init__(c,memory,r,device,core,instructions=INS,
                         access=Access(c,memory,r,device),outer_returns={RET[c['kind']]},
                         child_returns={0x43CD:{0x4341 if c['kind']=='low' else 0x4366}},
                         max_steps=MAX_STEPS,changed_return_status=2)


class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'ports-{mutation}.dll',mutation,'port_io')))
        self.functions={}
        for kind,name in NAMES.items():
            for core in (True,False):
                fn=getattr(self.lib,'lmn_'+name+('_core' if core else '_adapter'))
                fn.argtypes=[MEM,ct.POINTER(Regs),ct.POINTER(Ports),ct.POINTER(base.Bus)];fn.restype=Result
                self.functions[kind,core]=fn
    def run(self,c,memory,r,device,core):
        access=Access(c,memory,r,device)
        callbacks=base.NativeCallbacks(access,missing_in=c.get('missing_in'),missing_out=c.get('missing_out'))
        ram=(ct.c_uint8*SIZE).from_buffer(memory);reg=Regs(**r)
        result=self.functions[c['kind'],core](ram,ct.byref(reg),ct.byref(callbacks.ports),ct.byref(callbacks.bus))
        return dict(regs={n:getattr(result.registers,n) for n in REGS},status=result.status,
                    memory=memory,device=device,events=access.events,providers=access.providers,cursor=access.cursor)


def independent(c,r,ref,core):
    check(ref['status']==c.get('expected',0),c['name']+': declared stop differs')
    out=ref['regs'];kind=c['kind']
    if ref['status']!=0:return
    if kind=='eoi':
        check(out['ax']==((r['ax']&0xFF00)|0x20) and out['flags']==r['flags'],'EOI clobbers AH/FLAGS')
    else:
        check(out['flags']&0x200 and (out['flags']&0x400)==(r['flags']&0x400),'IF/DF contract differs')
        takes=kind=='axes' or (r['dx']&255)!=255
        mask=c.get('mask',15) if kind=='axes' else (3 if kind=='low' else 12)
        if kind in ('low','high') and takes and r['ds']==r['ss'] and r['sp']==0x53:mask=0x41 if kind=='low' else 0x66
        raw=([c.get('sample',15)]*c['repeat']+[0]) if 'repeat' in c else list(c.get('samples',(15,0)))
        totals=[0,0,0,0];samples=0
        if takes:
            for index,value in enumerate(raw):
                if index==0 and 'new_mask' in c:mask=c['new_mask']
                masked=value&mask;samples+=1
                for axis in range(4):totals[axis]=(totals[axis]+bool(masked&(1<<axis)))&0xFFFF
                if not masked:break
            else:raise Failure('independent finite input did not terminate')
            def signed_half(value):return ((value>>1)|(value&0x8000))&0xFFFF
            bx,cy,si,dy=totals
            cx=signed_half((cy*2)&0xFFFF);di=signed_half((dy*2)&0xFFFF)
            if kind=='high':bx,cx=si,di
            check((out['bx'],out['cx'],out['si'],out['di'])==(bx,cx,si,di),c['name']+': independent wrapped counters differ')
        elif kind=='high':check((out['bx'],out['cx'])==(r['bx'],r['cx']),'high skipped child changed BX/CX')
        if kind in ('low','high'):
            button=((~c.get('buttons',0xCF))>>(4 if kind=='low' else 6))&3
            check(out['ax']==button and get16(ref['memory'],r['ds'],0x14)==button,c['name']+': independent button bits differ')
            check((out['flags']&0x8C5)==0x44,'XOR AH flags must describe zero independently of AL')
        else:check(out['ax']==0 and out['bp']==0,'terminal measurement AX/BP differ')
        check(ref['cursor']==samples+(kind in ('low','high')),c['name']+': finite input consumption differs')
    if core:check(out['ip']==RET[kind] and out['sp']==r['sp'],'core RET boundary differs')
    else:
        check(out['sp']==((r['sp']+2)&0xFFFF),'adapter SP differs')
        expected=0xBEEF if c.get('provider')=='outer-ret' else (0xD003 if kind=='low' else 0xD00C) if c['name'].endswith('mask-outer-alias') else 0xD00D
        check(out['ip']==expected,c['name']+': actual outer RET differs')


def compare(native,c,core,reference=None):
    memory,r,device=setup(c)
    if reference is None:
        reference=Machine(c,bytearray(memory),r,copy.deepcopy(device),core).run()
        independent(c,r,reference,core)
    if native:
        actual=native.run(c,bytearray(memory),r,copy.deepcopy(device),core)
        base.compare_states(c['name'],actual,reference)
    return reference


def hashes():
    paths=('AGENTS.md','assets/vgalemmi.exe','metadata/oracle.json','metadata/inputs.json','metadata/toolchain-lock.json',
           'docs/executable.md','docs/minimap-vga.md','src/port201_input.asm','src/entry_services_after_timer.asm',
           'c/port_io.c','c/port_io.h','c/lemmings_sym.h','c/aligned_read_mask.h','c/special_blit.h','c/regs.h',
           'tests/port_io.py','tests/verification.py','tests/minimap_vga.py','tools/bounded_process.py',
           'tools/cbuild.py','tools/difftest.py','tools/common.py','tools/unpack.py')
    return {p:sha((ROOT/p).read_bytes()) for p in paths}


def worker(directory=None,snapshot=None):
    before=hashes()
    if snapshot:check(before==json.loads(Path(snapshot).read_text()),'input snapshot differs')
    native=Native(directory) if directory else None;rows=[];negative=None
    for c in cases():
        for core in (True,False):
            ref=compare(native,c,core)
            rows.append(dict(case=c['name'],kind=c['kind'],core=core,status=ref['status'],sites=sorted(ref['sites']),edges=sorted(ref['edges']),steps=ref['steps'],events=len(ref['events']),in_count=ref['cursor']))
            if c['name']=='axes-negative-halves' and core:negative=ref
        gc.collect();print('CHECKED '+c['name'],flush=True)
    mutations=None
    if native:
        mutations=[];lookup={c['name']:c for c in cases()}
        for number,name,core in ((1,'eoi-preserve-ah',True),(2,'eoi-late-ret',False),(3,'axes-live-mask',True),
            (4,'axes-negative-halves',True),(5,'axes-negative-halves',True),(6,'low-buttons-3',True),
            (7,'low-buttons-0',True),(8,'high-buttons-0',True),(9,'low-changed-child',True),(10,'high-buttons-1',True)):
            mutant=Native(directory,number)
            try:compare(mutant,lookup[name],core,negative if number in (4,5) else None)
            except Mismatch as e:mutations.append(dict(mutation=number,case=name,core=core,completed=True,mismatch=str(e)))
            else:raise Failure(f'mutant {number} survived')
            gc.collect()
    sites={p for r in rows for p in r['sites']};edges={tuple(e) for r in rows for e in r['edges']}
    check(sites==set(INS) and edges==EDGES,'port code sites/edges incomplete')
    check(before==hashes(),'campaign inputs changed')
    report=dict(image='main',image_sha256=sha(IMAGE),translated_code_bytes=157,physical_port201_bytes=154,unknown_port201_bytes=[0x4395,0x4398],
                case_count=len(cases()),comparison_count=len(rows),executed_instruction_addresses=sorted(sites),branch_edges=sorted(edges),
                instruction_steps=sum(r['steps'] for r in rows),ordered_events=sum(r['events'] for r in rows),
                original_only=not native,mutation_count=len(mutations or []),mutations=mutations or [],rows=rows,input_hashes=before,
                limits=dict(timeout_seconds=SECONDS,process_commit_mib=MEMORY_MIB,instructions=MAX_STEPS,events=MAX_EVENTS),
                scope='Original EOI/port201 known code and portable C on constructed finite providers; no UNKNOWN code, game boot, physical timing or IRQ scheduler')
    write_json(REPORT if native else ORIGINAL,report)
    print(f'PASS port I/O: {len(rows)} boundaries, {len(sites)} sites, {len(edges)} edges, {len(mutations or [])} mutants',flush=True)


def main():
    if sys.argv[1:]==['--original-worker']:worker();return
    if len(sys.argv)==4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3]);return
    if sys.argv[1:]==['--original-only']:
        run_bounded([sys.executable,__file__,'--original-worker'],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True);return
    if sys.argv[1:]:raise SystemExit('usage: port_io.py [--original-only]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='port-io-',parent=BUILD) as directory:
        p=Path(directory)/'input-hashes.json';p.write_text(json.dumps(hashes(),sort_keys=True))
        run_bounded([sys.executable,__file__,'--worker',directory,str(p)],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)


if __name__=='__main__':main()

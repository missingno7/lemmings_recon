"""Connected timer palette callers and sequential DAC writer; bounded native C."""
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

check,require=base.check,base.require
physical,put16,get16=base.physical,base.put16,base.get16
RANGES=((0x5473,0x54C4),(0x5533,0x5569),(0x5425,0x5447))
INS={i.address:i for lo,hi in RANGES for i in base.MD.disasm(base.IMAGE[lo:hi],lo)}
OWN={a:i for a,i in INS.items() if not 0x5425<=a<0x5447}
EDGES=base.direct_jump_edges(INS)
START={'before':0x5473,'after':0x553D,'direct':0x548C}
ENTRY={'before':0,'after':1,'direct':2}
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=420,384,1_000_000,450_000
REPORT=BUILD/'palette-timer-differential.json'


class Result(ct.Structure):
    _fields_=[('registers',base.Regs),('status',ct.c_uint16)]


def cases():
    rows=[]
    for entry in ('before','after'):
        for mode in (0,1,2,3,4,5,0x0102,0x0104,0x7FFF,0x8000,0xFFFF):
            rows.append(dict(name=f'{entry}-mode-{mode:04x}',entry=entry,mode=mode))
    for index in (0,1,8,16,0x7F,0x80,0xEF,0xF0,0xFF):
        rows.append(dict(name=f'direct-index-{index:02x}',entry='direct',index=index,count=2,df=index&1,
                         control=0 if index&2 else 0xFF))
    for count in (1,3,8,16,255):
        rows.append(dict(name=f'direct-count-{count}',entry='direct',count=count,index=0xFE,control=0))
    rows += [
        dict(name='direct-zero-forward',entry='direct',count=0,index=0x7F,core_only=True),
        dict(name='direct-zero-backward',entry='direct',count=0,index=0xF8,df=1,core_only=True),
        dict(name='direct-control-ff-to-zero',entry='direct',flip_control=0),
        dict(name='direct-control-zero-to-ff',entry='direct',control=0,flip_control=0xFF),
        dict(name='after-first-control-flip',entry='after',mode=4,flip_control=0,expected=3),
        dict(name='after-first-return-changed',entry='after',mode=4,child_return_patch=True,expected=3),
        dict(name='after-mode-changed-during-child',entry='after',mode=4,new_mode=2),
        dict(name='direct-late-source',entry='direct',source_patch=True),
        dict(name='direct-late-return',entry='direct',return_patch=True),
        dict(name='direct-late-saved-words',entry='direct',control=0,saved_patch=True),
        dict(name='direct-offset-wrap',entry='direct',si=0xFFFF,sp=1),
        dict(name='direct-physical-wrap',entry='direct',ds=0xFFFF,si=0xF,ss=0xFFFF,sp=0xF),
        dict(name='direct-df-if-clear',entry='direct',df=1,if_clear=True),
        dict(name='direct-df-if-set',entry='direct',df=1),
        dict(name='direct-missing-in',entry='direct',control=0,missing_in=True,expected=1),
        dict(name='direct-missing-in-not-reached',entry='direct',missing_in=True),
        dict(name='direct-missing-first-out',entry='direct',control=0,missing_out=True,expected=2),
        dict(name='direct-missing-index-out',entry='direct',missing_out=True,expected=2),
        dict(name='before-missing-ports-not-reached',entry='before',mode=0x104,missing_out=True),
        dict(name='after-missing-in',entry='after',mode=4,control=0,missing_in=True,expected=1),
        dict(name='after-missing-out',entry='after',mode=4,missing_out=True,expected=2),
        dict(name='before-attribute-missing-in',entry='before',mode=2,missing_in=True,expected=1),
    ]
    for entry in ('before','after'):
        rows.append(dict(name=entry+'-rgb-backward-blanked',entry=entry,mode=4,df=1,control=0))
        rows.append(dict(name=entry+'-attribute-backward',entry=entry,mode=2,df=1))
    for load in base.LOADS:
        rows.append(dict(name=f'after-load-{load:04x}',entry='after',mode=4,load=load))
    rows.append(dict(name='before-canonical-ds',entry='before',mode=4,ds=0x19B9))
    rows.append(dict(name='after-canonical-ds',entry='after',mode=4,ds=0x19B9))
    return [dict(load=0x1010,seed=0x548C+i,entry='direct',count=2,index=0x8F,control=0xFF)|r
            for i,r in enumerate(rows)]


def setup(c):
    memory,device=base.initial_memory(c)
    flags=(0x0202 if not c.get('if_clear') else 2)|(0x400 if c.get('df') else 0)
    r=base.default_regs(c['load'],c['seed'],ss=c.get('ss',0x5000),sp=c.get('sp',0x9000),
                        ds=c.get('ds',0x3000),flags=flags)
    r.update(ax=0xA53E,bx=0xB217,cx=((c['index']<<8)|c['count']),dx=0x3CE0,
             si=c.get('si',0x8800),di=0x42A7,bp=0x6D93,ip=START[c['entry']])
    base.put8(memory,r['ds'],0x200C,c['control'])
    put16(memory,r['ds'],0x1F7C,c.get('mode',4),device)
    put16(memory,r['ds'],0x1FDA,0x3D4,device)
    put16(memory,r['ss'],r['sp'],0xD00D,device)
    # Caller words are legitimate input when a changed control consumes them.
    for i,value in enumerate((0xA55A,0x0202,0x7123,0x3456),1):
        put16(memory,r['ss'],(r['sp']+2*i)&0xFFFF,value,device)
    return memory,r,device


class Access(base.BusAccess):
    def __init__(self,c,memory,r,device):
        super().__init__(c,memory,r,device,max_events=MAX_EVENTS)
    def inp(self,port,flags,mask=base.FLAGS):
        value=0x13 if port==0x3C5 else 8 if self.cursor==0 else 0
        self.cursor+=1;self.emit('in8',port,value,flags,mask);return value
    def out(self,port,value,flags,mask=base.FLAGS):
        self.emit('out8',port,value,flags,mask)
        if port==0x3C9 and 'payload-provider' not in self.providers:
            self.providers.add('payload-provider')
            if 'flip_control' in self.c:self.patch(self.r['ds'],0x200C,self.c['flip_control'],'control-flip',False)
            if 'new_mode' in self.c:self.patch(self.r['ds'],0x1F7C,self.c['new_mode'],'mode-flip')
            if self.c.get('source_patch'):
                self.patch(self.r['ds'],(self.r['si']+(-1 if self.c.get('df') else 1))&0xFFFF,0xA6,'source-live',False)
        if self.c.get('child_return_patch') and 'child-return' not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']-2)&0xFFFF,0xD234,'child-return')
        if self.c.get('return_patch') and 'outer-return' not in self.providers:
            self.patch(self.r['ss'],self.r['sp'],0xBEEF,'outer-return')
        if port==0x3C9 and self.c.get('saved_patch') and 'saved-words' not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']-4)&0xFFFF,0x3C7,'saved-words')
            self.patch(self.r['ss'],(self.r['sp']-2)&0xFFFF,0xABFF,'saved-AX')


class Machine(base.OriginalMachine):
    def __init__(self,c,memory,r,device,core):
        self.first_returned=False
        def before(m,ins):
            if ins.address==0x5555:m.first_returned=True
            if ins.mnemonic=='in' and c.get('missing_in'):m.stop(1);return True
            if ins.mnemonic=='out' and c.get('missing_out'):m.stop(2);return True
            return False
        def outer(m,off):
            if off!=0x54C3:return off in (0x5484,0x554A,0x5446)
            return c['entry']!='after' or c.get('mode')!=4 or m.first_returned
        super().__init__(c,memory,r,device,core,instructions=INS,
                         access=Access(c,memory,r,device),outer_returns=outer,
                         child_returns={0x54C3:{0x5555}},changed_return_status=3,
                         max_steps=MAX_STEPS,before=before)


class Native:
    def __init__(self,directory,mutation=0):
        self.library=ct.CDLL(str(build(Path(directory)/f'palette-timer-{mutation}.dll',mutation,'palette_timer')))
        self.functions={}
        for core in (True,False):
            fn=getattr(self.library,'lmn_timer_palette_'+('core' if core else 'adapter'))
            fn.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.c_int,ct.POINTER(base.Ports),ct.POINTER(base.Bus)]
            fn.restype=Result;self.functions[core]=fn
    def run(self,c,memory,r,device,core):
        memory=bytearray(memory);access=Access(c,memory,dict(r),copy.deepcopy(device))
        cb=base.NativeCallbacks(access,missing_in=c.get('missing_in',False),missing_out=c.get('missing_out',False))
        result=self.functions[core]((ct.c_uint8*base.SIZE).from_buffer(memory),ct.byref(base.Regs(**r)),
                                   ENTRY[c['entry']],ct.byref(cb.ports),ct.byref(cb.bus))
        return dict(regs={n:getattr(result.registers,n) for n in base.REG_NAMES},status=result.status,
                    memory=memory,device=access.device,events=access.events,providers=access.providers,cursor=access.cursor)


def independent(c,initial,r,ref,core):
    check(ref['status']==c.get('expected',0),c['name']+': independent stop differs')
    mode=c.get('mode',4)
    if ref['status'] or any(c.get(k) for k in ('flip_control','child_return_patch','source_patch','return_patch','saved_patch')) or 'flip_control' in c:
        return
    out=ref['regs'];ds=r['ds'];df=-1 if c.get('df') else 1
    if c['entry']!='direct' and mode not in (2,4):
        check(out['ax']==(r['ax'] if c['entry']=='before' else mode),c['name']+': whole-word mode/AX differs')
        check(all(out[k]==r[k] for k in ('bx','cx','dx','si','di','bp','ds','es','ss')),c['name']+': unsupported mode changed state')
        check(all(e[0]=='read' for e in ref['events']),c['name']+': unsupported mode wrote state')
        return
    packets=[]
    if c['entry']=='direct':packets=[(c['index'],c['count'] or 65536,r['si'])]
    elif mode==4:
        packets=[(16,8,0x2668)] if c['entry']=='before' else [(0,8,0x2638),(16,8,0x2650)]
    else:
        count,index,source=(8,8,0x2668) if c['entry']=='before' else (16,0,0x2638)
        writes=[e[2] for e in ref['events'] if e[0]=='out8']
        expected=[]
        for n in range(count):expected += [(index+n)&255,initial[physical(ds,(source+df*n)&0xFFFF)]]
        expected += [0x20]
        check(writes==expected,c['name']+': independent attribute packet differs')
        check(out['si']==(source+df*count)&0xFFFF,c['name']+': attribute cursor differs')
    if packets:
        stream=[(e[1],e[2]) for e in ref['events'] if e[0]=='out8' and e[1] in (0x3C8,0x3C9)]
        expected=[]
        for index,count,source in packets:
            expected.append((0x3C8,index))
            expected.extend((0x3C9,initial[physical(ds,(source+df*n)&0xFFFF)]) for n in range(count*3))
        check(stream==expected,c['name']+': independent sequential DAC stream differs')
        _,count,source=packets[-1]
        check(out['si']==(source+df*3*count)&0xFFFF and out['di']==r['di'],c['name']+': DAC cursor or untouched DI differs')
    check(out['sp']==(r['sp']+(0 if core else 2))&0xFFFF,c['name']+': inherited return frame changed')
    if not core:check(out['ip']==0xD00D,c['name']+': outer live RET differs')
    check(out['flags']&0x200,c['name']+': final STI absent')


def compare(native,c,core):
    memory,r,device=setup(c)
    ref=Machine(c,bytearray(memory),dict(r),copy.deepcopy(device),core).run()
    independent(c,memory,r,ref,core)
    if native:base.compare_states(c['name'],native.run(c,memory,r,device,core),ref)
    return ref


def hashes():
    paths=('AGENTS.md','assets/vgalemmi.exe','metadata/oracle.json','metadata/inputs.json','metadata/toolchain-lock.json',
           'src/palette_frontends.asm','c/palette_ports.c','c/palette_ports.h','c/video_restore.h','c/special_blit.h',
           'c/aligned_read_mask.h','c/regs.h','c/lemmings_sym.h','tests/palette_timer.py','tests/verification.py',
           'tests/minimap_vga.py','tools/unpack.py','tools/resources.py','tools/common.py','tools/cbuild.py',
           'tools/difftest.py','tools/bounded_process.py')
    return {p:sha((ROOT/p).read_bytes()) for p in paths}


def worker(directory=None,snapshot=None):
    before=hashes()
    if snapshot:check(before==json.loads(Path(snapshot).read_text()),'palette inputs changed before worker')
    native=Native(directory) if directory else None
    rows=[];sites=set();edges=set()
    for c in cases():
        for core in ((True,) if c.get('core_only') else (True,False)):
            ref=compare(native,c,core);sites.update(ref['sites']);edges.update(ref['edges'])
            rows.append(dict(case=c['name'],core=core,status=ref['status'],steps=ref['steps'],events=len(ref['events'])))
        gc.collect();print('CHECKED '+c['name'],flush=True)
    check(sites==set(INS),'palette sites missing: '+str(sorted(set(INS)-sites)))
    check(edges==EDGES,'palette outcomes missing: '+str(sorted(EDGES-edges)))
    mutations=[]
    if native:
        lookup={c['name']:c for c in cases()}
        for mutation,name in ((1,'direct-df-if-clear'),(2,'direct-control-ff-to-zero'),(3,'direct-df-if-set'),
                              (4,'direct-df-if-clear'),(5,'after-first-return-changed')):
            try:compare(Native(directory,mutation),lookup[name],True)
            except base.Mismatch as error:mutations.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
            else:raise base.OracleFailure(f'palette timer mutant {mutation} survived')
            gc.collect()
    check(before==hashes(),'palette inputs changed during campaign')
    write_json(REPORT if native else BUILD/'palette-timer-original-differential.json',dict(
        image='main',image_sha256=sha(base.IMAGE),own_known_bytes=135,known_connected_bytes=169,
        own_instruction_addresses=sorted(OWN),executed_instruction_addresses=sorted(sites),branch_edges=sorted(edges),
        case_count=len(cases()),comparison_count=len(rows),instruction_steps=sum(r['steps'] for r in rows),
        ordered_bus_events=sum(r['events'] for r in rows),mutation_count=len(mutations),mutations=mutations,rows=rows,
        input_hashes=before,limits=dict(timeout_seconds=SECONDS,process_commit_mib=MEMORY_MIB,instructions=MAX_STEPS,events=MAX_EVENTS),
        scope='548C sequential DAC and timer callers5473/553D with tested attribute child; canonical buffers, unchecked count/index and live frame/control effects; initialization, timing and broader source ownership remain separate'))
    print(f'PASS timer palettes: {len(rows)} comparisons,{len(sites)} sites,{len(edges)} outcomes,{len(mutations)} mutants',flush=True)


def main():
    if sys.argv[1:]==['--original-worker']:worker();return
    if len(sys.argv)==4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3]);return
    if sys.argv[1:]==['--original-only']:
        run_bounded([sys.executable,__file__,'--original-worker'],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True);return
    if sys.argv[1:]:raise SystemExit('usage: palette_timer.py [--original-only]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='palette-timer-',parent=BUILD) as directory:
        path=Path(directory)/'input-hashes.json';write_json(path,hashes())
        run_bounded([sys.executable,__file__,'--worker',str(directory),str(path)],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)


if __name__=='__main__':main()

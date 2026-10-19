"""Menu IRQ and direct vector installer over the shared bounded verifier."""
import copy
import ctypes as ct
import gc
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as base
import input_poll as poll
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build
from common import BUILD,sha,write_json

check,require=base.check,base.require
physical,put16,get16=base.physical,base.put16,base.get16
IRQ={i.address:i for lo,hi in ((0x4C47,0x4C65),(0x4C66,0x4C7E))
     for i in base.MD.disasm(base.IMAGE[lo:hi],lo)}
INSTALL={i.address:i for i in base.MD.disasm(base.IMAGE[0x5028:0x503B],0x5028)}
EOI={i.address:i for i in base.MD.disasm(base.IMAGE[0x18B2:0x18B7],0x18B2)}
OWN=IRQ|INSTALL;INS=OWN|EOI|poll.INS
EDGES=base.direct_jump_edges(OWN,external_transfers={0x4C6C})
MAX_STEPS,MAX_EVENTS,SECONDS,MEMORY_MIB=100_000,20_000,420,384
REPORT=BUILD/'menu-timer-differential.json'
BINDINGS={'mouse':(0x7100,0x200),'chain':(0x7400,0x500)}
HARDWARE=(0xD00D,0x6201,0x0247)


class Result(ct.Structure):
    _fields_=[('registers',base.Regs),('status',ct.c_uint16),
              ('child_status',ct.c_uint16),('service_status',ct.c_uint16)]


def cases():
    rows=[dict(name=f'irq-phase-{p:02x}',phase=p) for p in (0,1,2,3,0x7F,0xFE,0xFF)]
    rows += [
        dict(name='irq-keyboard-buttons',keymask=0x4010),
        dict(name='irq-mouse',phase=3,mode=0,mouse_buttons=3),
        dict(name='irq-mouse-unbound',phase=3,mode=0,no_mouse=True,expected=5,child_status=1),
        dict(name='irq-port-low',phase=3,mode=1,callback=0x4334,port_kind='low',buttons=0x3F),
        dict(name='irq-port-high',phase=3,mode=1,callback=0x4359,port_kind='high',buttons=0xCF),
        dict(name='irq-port-mouse',phase=3,mode=1,callback=0x4252,mouse_buttons=1),
        dict(name='irq-unknown-callback',phase=3,mode=1,callback=0x4111,expected=5,child_status=6),
        dict(name='irq-port-missing-input',phase=3,mode=1,callback=0x4334,missing_in=True,expected=5,child_status=5,service_status=1),
        dict(name='irq-eoi-missing-output',phase=3,missing_out=True,expected=5,child_status=1),
        dict(name='irq-eoi-return-changed',phase=3,eoi_patch=True,expected=4),
        dict(name='irq-input-return-changed',phase=3,input_patch=True,expected=4),
        dict(name='irq-chain-new-es',chain={'new_es':0x6A51}),
        dict(name='irq-chain-new-ds',chain={'new_ds':0x3600}),
        dict(name='irq-chain-new-stack',chain={'new_stack':(0x6500,0x7000),'new_ds':0x3600}),
        dict(name='irq-chain-saved-ds',chain={'saved_words':{6:0xBCA1}}),
        dict(name='irq-chain-outer-flags',chain={'saved_words':{26:0x0046}}),
        dict(name='irq-chain-unbound',no_chain=True,expected=1),
        dict(name='irq-chain-vector-mismatch',bad_vector=True,expected=1),
        dict(name='irq-chain-stop',chain={'status':0x5678},expected=2,service_status=0x5678),
        dict(name='irq-chain-changed-return',chain={'iret_ip':0xD234},expected=3),
        dict(name='irq-chain-late-vector',late_vector=True),
        dict(name='irq-if-set-df-set',flags=0x06D7),
        dict(name='irq-offset-wrap',sp=3),
        dict(name='irq-physical-wrap',ss=0xFFFF,sp=0x11),
        dict(name='irq-hardware-word-wrap',sp=0xFFFF),
        dict(name='irq-save-overlaps-phase',save_phase_alias=True),
        dict(name='irq-relocated-ds',runtime_ds=0x3800),
        dict(name='irq-late-ds-operand',runtime_ds=0x3800,late_operand=True),
    ]
    rows += [dict(name=f'irq-load-{v:04x}',load=v,phase=3) for v in base.LOADS]
    rows += [dict(name='install-'+n,entry='install',**kw) for n,kw in (
        ('ordinary',{}),('if-set',{'flags':0x02D7}),('df-set',{'flags':0x04D7}),
        ('saved-ds-at-vector-ip',{'ss':0,'sp':0x22}),
        ('saved-ds-at-vector-cs',{'ss':0,'sp':0x24}),
        ('saved-word-straddles-vector',{'ss':0,'sp':0x21}),
        ('offset-wrap',{'sp':1}),('physical-wrap',{'ss':0xFFFF,'sp':0x11}),
        ('outer-word-ffff',{'sp':0xFFFF}),('vga-stack',{'ss':0xA000}),
    )]
    rows += [dict(name=f'install-load-{v:04x}',entry='install',load=v) for v in base.LOADS]
    return [dict(entry='irq',load=0x1010,seed=0x4C47+i,mode=2,phase=0,flags=0x00D7)|c
            for i,c in enumerate(rows)]


def setup(c):
    ds=c.get('runtime_ds',(c['load']+0x09A9)&0xFFFF)
    spec=dict(c,entry='input',ds=ds)
    if c.get('save_phase_alias'):spec.update(ss=ds,sp=0x1FE5)
    memory,r,device,_=poll.setup(spec)
    # A second constructed frame supports a saved-handler returnedDS.
    for off in (0x10,0x12,0x14,0x16,0x18,0x1FC7,0x200B,0x2005,0x25A0,0x25A2,0x25A4):
        put16(memory,0x3600,off,get16(memory,ds,off))
    base.put8(memory,0x3600,0x25A6,c['mode'])
    r.update(ds=0x3200,ip=0x5028 if c['entry']=='install' else 0x4C47)
    put16(memory,c['load'],0x4C50,(c['load']+0x09A9)&0xFFFF if c.get('late_operand') else ds)
    for frame in (ds,0x3600):
        base.put8(memory,frame,0x1FE3,c['phase'])
        put16(memory,frame,0x1FBE,0x600 if c.get('bad_vector') or c.get('late_vector') else 0x500)
        put16(memory,frame,0x1FC0,0x6600 if c.get('bad_vector') or c.get('late_vector') else 0x7400)
    if c['entry']=='irq':
        for i,v in enumerate(HARDWARE):put16(memory,r['ss'],(r['sp']+2*i)&0xFFFF,v,device)
    else:put16(memory,r['ss'],r['sp'],0xD00D,device)
    return memory,r,device


def provider(name,c):
    if c.get('no_'+name):return None
    if name=='mouse':return poll.external
    spec=c.get('chain',{})
    def execute(access,r):
        begin=len(access.events);event={'name':name,'entry':dict(r)}
        check([get16(access.memory,r['ss'],(r['sp']+2*i)&0xFFFF) for i in range(3)]==
              [0x4C70,c['load'],r['flags']],'menu synthetic frame differs')
        if 'new_stack' in spec:
            words=[access.word_read(r['ss'],(r['sp']+2*i)&0xFFFF,r['flags']) for i in range(14)]
            r['ss'],r['sp']=spec['new_stack']
            for i,v in enumerate(words):access.word_write(r['ss'],(r['sp']+2*i)&0xFFFF,v,r['flags'])
        for n in ('ds','es','ax','bx','cx','dx','si','di','bp'):
            if 'new_'+n in spec:r[n]=spec['new_'+n]
        changes=dict(spec.get('saved_words',{}))
        for n,off in (('iret_ip',0),('iret_cs',2),('iret_flags',4)):
            if n in spec:changes[off]=spec[n]
        for off,v in changes.items():access.word_write(r['ss'],(r['sp']+int(off))&0xFFFF,v,r['flags'])
        event.update(status=spec.get('status',0),provider_events=len(access.events)-begin)
        access.service_events.append(event);return spec.get('status',0)
    return execute


class Access(poll.Access):
    def __init__(self,c,memory,r,device):
        super().__init__(c,memory,dict(r,dx=(r['dx']&0xFF00)|0xFF),device)
        self.max_events=MAX_EVENTS
    def access(self,kind,address,flags,mask=base.FLAGS,value=None):
        v=super().access(kind,address,flags,mask,value)
        if kind=='write' and self.c.get('late_operand') and 'live-operand' not in self.providers:
            self.patch(self.c['load'],0x4C50,self.c['runtime_ds'],'live-operand')
        if kind=='write' and self.c.get('late_vector') and address==physical(self.r['ss'],(self.r['sp']-22)&0xFFFF):
            ds=self.c.get('runtime_ds',(self.c['load']+0x09A9)&0xFFFF)
            self.patch(ds,0x1FBE,0x500,'late-vector-ip');self.patch(ds,0x1FC0,0x7400,'late-vector-cs')
        if kind=='read' and self.c.get('input_patch') and address==physical((self.c['load']+0x09A9)&0xFFFF,0x25A6):
            self.patch(self.r['ss'],(self.r['sp']-18)&0xFFFF,0xD234,'input-return')
        return v
    def out(self,port,value,flags,mask=base.FLAGS):
        super().out(port,value,flags,mask)
        if port==0x20 and self.c.get('eoi_patch'):
            self.patch(self.r['ss'],(self.r['sp']-18)&0xFFFF,0xD234,'eoi-return')


class Machine(base.OriginalMachine):
    def __init__(self,c,memory,r,device,core):
        self.child_status=0;self.callback_target=None
        def before(m,i):
            if poll._before(m,i):m.child_status=m.status;m.status=5;return True
            missing=(i.mnemonic=='in' and c.get('missing_in')) or (i.mnemonic=='out' and c.get('missing_out'))
            if missing:
                m.child_status=1 if i.address==0x18B4 else 5
                m.service_status=0 if i.address==0x18B4 else 1
                m.stop(5);return True
            return False
        def changed(m,off):
            if off in (0x4358,0x4385) or (off==0x42A0 and c['mode']==1):m.child_status=4;return (5,0)
            return (4,0)
        def interrupt(m,number):
            check(number==0x33,'unexpected menu interrupt')
            m.software_interrupt(number,m.state()['ip'],BINDINGS['mouse'],provider('mouse',c))
            if m.stopped:m.child_status=m.status;m.status=5
        returns={0x4251:{0x4C75},0x4333:{0x4C75},
                 0x42A0:lambda m,o:{0x42A7 if c['mode']==1 else 0x4C75},
                 0x4358:{0x42A7},0x4385:{0x42A7},0x43CD:{0x4341,0x4366},0x18B6:{0x4C63}}
        super().__init__(c,memory,r,device,core,instructions=INS,access=Access(c,memory,r,device),
            outer_returns={0x503A} if c['entry']=='install' else {0x4C7D},child_returns=returns,
            max_steps=MAX_STEPS,before=before,interrupt=interrupt,changed_return_status=changed,
            mutable_operands=((0x4C50,2),),far_calls={0x4C6C:(0x4C70,BINDINGS['chain'],provider('chain',c))})
    def run(self):
        out=super().run();out.update(child_status=self.child_status,service_status=self.service_status,
            services=self.access.service_events,transport_events=self.access.transport_events)
        return out


class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'menu-{mutation}.dll',mutation,'menu_timer')))
        self.functions={}
        for entry,prefix in (('irq','lmn_menu_timer'),('install','lmn_install_menu_timer')):
            for core in (True,False):
                fn=getattr(self.lib,prefix+('_core' if core else '_adapter'))
                fn.argtypes=[base.MEM,ct.POINTER(base.Regs)]+([ct.POINTER(base.InterruptService)]*2+[ct.POINTER(base.Ports)] if entry=='irq' else [])+[ct.POINTER(base.Bus)]
                fn.restype=Result;self.functions[entry,core]=fn
    def run(self,c,memory,r,device,core,*,copy_state=True):
        if copy_state:memory,device=bytearray(memory),copy.deepcopy(device)
        access=Access(c,memory,dict(r),device)
        cb=base.NativeCallbacks(access,missing_in=c.get('missing_in'),missing_out=c.get('missing_out'))
        keep=[];ptrs=[]
        if c['entry']=='irq':
            for name in ('mouse','chain'):
                body=provider(name,c)
                if body is None:ptrs.append(ct.POINTER(base.InterruptService)());continue
                fn=cb.interrupt(body);cs,ip=BINDINGS[name];service=base.InterruptService(None,fn,cs,ip)
                keep.extend((fn,service));ptrs.append(ct.pointer(service))
            ptrs.append(ct.byref(cb.ports))
        out=self.functions[c['entry'],core]((ct.c_uint8*base.SIZE).from_buffer(memory),ct.byref(base.Regs(**r)),*ptrs,ct.byref(cb.bus))
        return dict(regs={n:getattr(out.registers,n) for n in base.REG_NAMES},status=out.status,
            child_status=out.child_status,service_status=out.service_status,memory=memory,
            device=access.device,events=access.events,providers=access.providers,cursor=access.cursor,services=access.service_events)


def independent(c,memory,r,ref,core):
    out=ref['regs']
    if c['entry']=='install':
        expected=bytearray(memory);sp=(r['sp']-2)&0xFFFF
        put16(expected,r['ss'],sp,r['ds']);put16(expected,0,0x20,0x4C47);put16(expected,0,0x22,r['cs'])
        if r['ss']!=0xA000:
            check(ref['memory']==expected,c['name']+': independent IVT/saved memory differs')
            check(out['ds']==get16(expected,r['ss'],sp),c['name']+': live savedDS differs')
        check(get16(ref['memory'],0,0x20)==0x4C47 and get16(ref['memory'],0,0x22)==r['cs'],'IVT08 differs')
        check(out['ax']==0 and out['sp']==(r['sp']+(0 if core else 2))&0xFFFF,'installer register/SP differs')
        check(out['ip']==(0x503A if core else get16(expected,r['ss'],r['sp'])),'installer outerRET differs')
        check(out['flags']&0x200,'installer STI missing')
        return
    phase=((r['ax']&255) if c.get('save_phase_alias') else c['phase'])+1;phase&=3
    ds=c.get('runtime_ds',(c['load']+0x09A9)&0xFFFF)
    check(ref['memory'][physical(ds,0x1FE3)]==phase,'menu modulo phase differs')
    if ref['status']:return
    saved=dict(r)
    if c.get('save_phase_alias'):saved['ax']=(r['ax']&0xFF00)|phase
    saved['ds']=c.get('chain',{}).get('saved_words',{}).get(6,r['ds'])
    check(all(out[n]==saved[n] for n in ('ax','bx','cx','dx','si','di','bp','ds')),'menu saved registers differ')
    check(out['es']==c.get('chain',{}).get('new_es',r['es']),'menu must leave ES live')
    ss,sp=c.get('chain',{}).get('new_stack',(r['ss'],(r['sp']-22)&0xFFFF)) if phase else (r['ss'],(r['sp']-22)&0xFFFF)
    check(out['ss']==ss and out['sp']==(sp+22+(0 if core else 6))&0xFFFF,'menu frame extent differs')
    hardware=c.get('hardware',HARDWARE)
    check((out['ip'],out['cs'])==((0x4C7D,c['load']) if core else hardware[:2]),'menu hardware target differs')
    if not core:check(out['flags']==c.get('chain',{}).get('saved_words',{}).get(26,hardware[2]),'hardware FLAGS differs')


def compare(native,c,core):
    memory,r,device=setup(c)
    ref=Machine(c,bytearray(memory),dict(r),copy.deepcopy(device),core).run()
    check((ref['status'],ref['child_status'],ref['service_status'])==
          (c.get('expected',0),c.get('child_status',0),c.get('service_status',0)),c['name']+': unexpected stop')
    independent(c,memory,r,ref,core)
    if native:base.compare_states(c['name'],native.run(c,memory,r,device,core),ref)
    return ref


def handoff(native,load):
    """Actual installer output feeds the identified IRQ on the same RAM image.

    Hardware entry is constructed explicitly; no scheduler/IRQ-delivery proof.
    """
    c=dict(name=f'handoff-install-{load:04x}',entry='install',load=load,
           seed=load^0x5028,mode=2,phase=3,flags=0xD7)
    memory,r,device=setup(c)
    ref=Machine(c,bytearray(memory),dict(r),copy.deepcopy(device),False).run()
    independent(c,memory,r,ref,False)
    actual=native.run(c,memory,r,device,False) if native else None
    if actual:base.compare_states(c['name'],actual,ref)
    stages=[(c['name'],ref)]
    check((get16(ref['memory'],0,0x22),get16(ref['memory'],0,0x20))==(load,0x4C47),'handoff target differs')
    hardware=(ref['regs']['ip'],ref['regs']['cs'],ref['regs']['flags'])
    c=dict(c,name=f'handoff-irq-{load:04x}',entry='irq',hardware=hardware)
    def enter(state):
        regs=dict(state['regs'])
        for value in (regs['flags'],regs['cs'],regs['ip']):
            regs['sp']=(regs['sp']-2)&0xFFFF
            put16(state['memory'],regs['ss'],regs['sp'],value,state['device'])
        regs.update(cs=get16(state['memory'],0,0x22),ip=get16(state['memory'],0,0x20),flags=regs['flags']&~0x300)
        return regs
    r=enter(ref)
    irq=Machine(c,ref['memory'],dict(r),ref['device'],False).run()
    independent(c,memory,r,irq,False)
    if actual:
        actual_r=enter(actual)
        out=native.run(c,actual['memory'],actual_r,actual['device'],False,copy_state=False)
        base.compare_states(c['name'],out,irq)
    stages.append((c['name'],irq))
    return stages


def hashes():
    paths=set(poll.hashes())|{'tests/menu_timer.py','src/game_code_late_after_decimal.asm',
        'src/entry_services_after_timer.asm','c/timer_tail.c','c/timer_tail.h',
        'c/video_restore.h','tools/resources.py'}
    # The shared timer compilation also retains its full-game dependency closure.
    paths|={'c/'+name+suffix for name in ('ui_commands','view_visibility','vga_mirrors','palette_ports',
        'fixed_pattern_update','fixed_pattern_copy','fixed_pattern_draw') for suffix in ('.c','.h')}
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def worker(directory=None,snapshot=None):
    before=hashes()
    if snapshot:check(before==json.loads(Path(snapshot).read_text()),'menu input snapshot changed')
    native=Native(directory) if directory else None
    rows=[];sites=set();edges=set()
    for c in cases():
        for core in (True,False):
            ref=compare(native,c,core);sites.update(ref['sites']);edges.update(ref['edges'])
            rows.append(dict(case=c['name'],core=core,steps=ref['steps'],events=len(ref['events']),
                transport_events=ref['transport_events'],provider_events=sum(e.get('provider_events',0) for e in ref['services']),service_calls=len(ref['services'])))
        gc.collect();print('CHECKED '+c['name'],flush=True)
    for load in base.LOADS:
        for name,ref in handoff(native,load):
            sites.update(ref['sites']);edges.update(ref['edges'])
            rows.append(dict(case=name,core=False,steps=ref['steps'],events=len(ref['events']),
                transport_events=ref['transport_events'],provider_events=sum(e.get('provider_events',0) for e in ref['services']),service_calls=len(ref['services'])))
        gc.collect();print(f'CHECKED same-RAM installer/IRQ handoff{load:04x}',flush=True)
    check(set(OWN)<=sites,'menu own sites missing: '+str(sorted(set(OWN)-sites)))
    check(EDGES<=edges,'menu own branch outcomes missing')
    mutations=[]
    if native:
        lookup={c['name']:c for c in cases()}
        for m,name in ((1,'irq-phase-03'),(2,'irq-unknown-callback'),(3,'irq-chain-new-es'),
            (4,'irq-chain-new-stack'),(5,'irq-eoi-return-changed'),(6,'install-ordinary'),
            (7,'install-saved-ds-at-vector-ip'),(8,'install-ordinary')):
            try:compare(Native(directory,m),lookup[name],True)
            except base.Mismatch as error:mutations.append(dict(mutation=m,case=name,completed=True,mismatch=str(error)))
            else:raise base.OracleFailure(f'menu mutant{m} survived')
            gc.collect()
    check(before==hashes(),'menu campaign inputs changed')
    write_json(REPORT if native else BUILD/'menu-timer-original-differential.json',dict(
        image='main',image_sha256=sha(base.IMAGE),own_known_bytes=73,known_connected_bytes=sum(i.size for i in INS.values()),
        case_count=len(cases())+len(base.LOADS),single_case_count=len(cases()),handoff_count=len(base.LOADS),comparison_count=len(rows),executed_instruction_addresses=sorted(sites),
        own_executed_instruction_addresses=sorted(set(OWN)&sites),branch_edges=sorted(edges),own_branch_edges=sorted(EDGES),
        instruction_steps=sum(r['steps'] for r in rows),ordered_bus_events=sum(r['events'] for r in rows),
        declared_interrupt_transport_events=sum(r['transport_events'] for r in rows),
        declared_provider_events=sum(r['provider_events'] for r in rows),declared_service_calls=sum(r['service_calls'] for r in rows),
        mutation_count=len(mutations),mutations=mutations,input_hashes=before,rows=rows,
        limits=dict(timeout_seconds=SECONDS,process_commit_mib=MEMORY_MIB,instructions=MAX_STEPS,events=MAX_EVENTS),
        scope='Menu4C47 with native input/EOI, opaque savedINT08 seam and directIVT08 installer5028; UNKNOWN4C65, game installer1644, keyboard producers, asynchronous IRQ delivery and platform bodies remain open'))
    print(f'PASS menu timer: {len(rows)} comparisons,{len(OWN)} own sites,{len(EDGES)} own outcomes,{len(mutations)} mutants',flush=True)


def main():
    if sys.argv[1:]==['--original-worker']:worker();return
    if len(sys.argv)==4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3]);return
    if sys.argv[1:]==['--original-only']:
        run_bounded([sys.executable,__file__,'--original-worker'],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True);return
    if sys.argv[1:]:raise SystemExit('usage: menu_timer.py [--original-only]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='menu-timer-',parent=BUILD) as directory:
        snapshot=Path(directory)/'inputs.json';write_json(snapshot,hashes())
        run_bounded([sys.executable,__file__,'--worker',str(directory),str(snapshot)],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)


if __name__=='__main__':main()

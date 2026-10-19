"""Timer installation/cleanup lifecycle using shared bounded verification."""
import copy
import ctypes as ct
import gc
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as base
import menu_timer as menu
import game_timer as game
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build
from common import BUILD,sha,write_json

check=base.check
physical,put16,get16=base.physical,base.put16,base.get16
INSTALL={i.address:i for i in base.MD.disasm(base.IMAGE[0x1644:0x1696],0x1644)}
RESTORE={i.address:i for i in base.MD.disasm(base.IMAGE[0x16A9:0x16D4],0x16A9)}
INS=INSTALL|RESTORE;EDGES=base.direct_jump_edges(INS)
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=420,384,2000,2000
REPORT=BUILD/'timer-install-differential.json'
BINDINGS={0x21:(0x7100,0x210),0x1A:(0x7200,0x1A0)}


def cases():
    rows=[dict(name='install-'+n,**kw) for n,kw in (
        ('ordinary',{}),('byte-carry',{'crtc':0x03FC}),
        ('pit-zero',{'pit':0}),('pit-ffff',{'pit':0xFFFF}),
        ('repeated-waits',{'samples':(0,0,8,8,8,0)}),
        ('live-reload',{'late_pit':0x81A5}),
        ('live-sound-operand',{'sound_segment':0x4800,'late_operand':True}),
        ('returned-registers',{'first':{'regs':{'ds':0x3999,'es':0x4567,'bx':0xABCD,'si':0x5432,'di':0x9876,'bp':0x6789}}}),
        ('returned-saved-ds',{'first':{'saved_ds':0x3600}}),
        ('returned-first-stack',{'first':{'stack':(0x6500,0x7000),'saved_ds':0x3600}}),
        ('returned-second-stack',{'second':{'stack':(0x6600,0x8000),'saved_ds':0x3600,'outer_ip':0xBEEF,'regs':{'es':0x1234}}}),
        ('returned-flags',{'second':{'iret_flags':0x0ED7}}),
        ('first-stop',{'first':{'status':0x5678},'expected':2,'service_status':0x5678}),
        ('second-stop',{'second':{'status':0x1234},'expected':2,'service_status':0x1234}),
        ('first-changed-return',{'first':{'iret_ip':0xD234},'expected':3}),
        ('second-changed-return',{'second':{'iret_cs':0x6666},'expected':3}),
        ('unbound-dos',{'no_service':True,'expected':1}),
        ('second-unbound',{'first':{'unbind':True},'expected':1}),
        ('missing-input',{'missing_in':True,'expected':6}),
        ('missing-output',{'missing_out':True,'expected':7}),
        ('offset-wrap',{'sp':1}),('physical-wrap',{'ss':0xFFFF,'sp':0x11}),
        ('outer-word-ffff',{'sp':0xFFFF}),('vga-stack',{'ss':0xA000}),
        ('if-df-set',{'flags':0x06D7}),
    )]
    rows += [dict(name='restore-'+n,entry='restore',**kw) for n,kw in (
        ('ordinary',{}),('saved-ds-at-vector-ip',{'ss':0,'sp':0x22}),
        ('saved-ds-at-vector-cs',{'ss':0,'sp':0x24}),
        ('saved-ds-straddles-vector',{'ss':0,'sp':0x21}),
        ('push-overlaps-saved-vector',{'ss':0x3000,'sp':0x1FC0}),
        ('returned-stack',{'clock':{'stack':(0x6700,0x8100),'outer_ip':0xBCDE}}),
        ('returned-registers',{'clock':{'regs':{'ds':0x3999,'es':0x4567,'ax':0xABCD,'bx':0x5432,'cx':0x1111,'dx':0x2222,'si':0x9876,'di':0x7654,'bp':0x6789},'iret_flags':0x0CD7}}),
        ('changed-return',{'clock':{'iret_ip':0xD234},'expected':3}),
        ('provider-stop',{'clock':{'status':0x7654},'expected':2,'service_status':0x7654}),
        ('unbound-clock',{'no_service':True,'expected':1}),
        ('missing-output',{'missing_out':True,'expected':7}),
        ('offset-wrap',{'sp':1}),('physical-wrap',{'ss':0xFFFF,'sp':0x11}),
        ('outer-word-ffff',{'sp':0xFFFF}),('vga-stack',{'ss':0xA000}),
        ('if-df-set',{'flags':0x06D7}),
    )]
    rows += [dict(name=f'{entry}-load-{load:04x}',entry=entry,load=load)
             for entry in ('install','restore') for load in base.LOADS]
    return [dict(entry='install',load=0x1010,seed=0x1644+i,flags=0xD7)|c for i,c in enumerate(rows)]


def setup(c):
    memory,device=base.initial_memory(c)
    if c.get('irq_fixture'):
        memory,_,device=game.setup(dict(c,runtime_ds=0x3000,entry='input',mode=2,configuration=0,palette_mode=0,phase=0))
    r=base.default_regs(c['load'],c['seed'],ss=c.get('ss',0x5000),sp=c.get('sp',0x9000),
                        ds=0x3000,flags=c['flags'])
    r['ip']=0x1644 if c['entry']=='install' else 0x16A9
    # Extra frames cover live POPDS after IVT aliases and provider stack changes.
    for frame in (0x3000,0x3600,0x4C47,c['load'],(c['load']<<8|0x47)&0xFFFF):
        put16(memory,frame,0x1FDA,c.get('crtc',0x3D4))
        put16(memory,frame,0x1FC9,c.get('pit',0x3468))
        put16(memory,frame,0x1FBE,0x4C47);put16(memory,frame,0x1FC0,c['load'])
        put16(memory,frame,0x259C,0x1234);put16(memory,frame,0x259E,0x5678)
    for number,(cs,ip) in BINDINGS.items():
        put16(memory,0,number*4,ip);put16(memory,0,number*4+2,cs)
    put16(memory,0,0x20,0x4C47);put16(memory,0,0x22,c['load'])
    if not c.get('late_operand'):put16(memory,c['load'],0x1653,c.get('sound_segment',(c['load']+0x842)&0xFFFF))
    put16(memory,r['ss'],r['sp'],0xD00D,device)
    return memory,r,device


def provider(number,c):
    if c.get('no_service'):return None
    def execute(access,r):
        begin=len(access.events);index=len(access.service_events)
        spec=c.get('clock' if number==0x1A else 'first' if index==0 else 'second',{})
        event=dict(number=number,entry=dict(r))
        if number==0x21:
            check(r['ax']==(0x2508 if index==0 else 0x2560),'unexpected DOS request')
            vector=r['ax']&255
            access.word_write(0,vector*4,r['dx'],r['flags'])
            access.word_write(0,vector*4+2,r['ds'],r['flags'])
        else:
            check(r['ax']==0x100,'unexpected BIOS clock request')
            event['clock']=(r['cx'],r['dx'])
        if 'stack' in spec:
            # INT frame + savedDS (DOS) + actual nearRET, or INT + nearRET (BIOS).
            words=[access.word_read(r['ss'],(r['sp']+2*i)&0xFFFF,r['flags']) for i in range(5 if number==0x21 else 4)]
            r['ss'],r['sp']=spec['stack']
            for i,value in enumerate(words):access.word_write(r['ss'],(r['sp']+2*i)&0xFFFF,value,r['flags'])
        for name,value in spec.get('regs',{}).items():r[name]=value
        changes={off:spec[name] for name,off in (('iret_ip',0),('iret_cs',2),('iret_flags',4),('saved_ds',6),('outer_ip',8 if number==0x21 else 6)) if name in spec}
        for off,value in changes.items():access.word_write(r['ss'],(r['sp']+off)&0xFFFF,value,r['flags'])
        if spec.get('unbind'):access.word_write(0,0x84,0xD234,r['flags'])
        if number==0x21 and index==0 and c.get('late_operand'):
            access.patch(c['load'],0x1653,c['sound_segment'],'sound-operand')
        event.update(status=spec.get('status',0),provider_events=len(access.events)-begin)
        access.service_events.append(event);return spec.get('status',0)
    return execute


class Access(base.BusAccess):
    def __init__(self,c,memory,r,device):super().__init__(c,memory,r,device,max_events=MAX_EVENTS)
    def inp(self,port,flags,mask=base.FLAGS):
        samples=self.c.get('samples',(0,8,8,0))
        check(self.cursor<len(samples),'finite status samples exhausted')
        value=samples[self.cursor];self.cursor+=1
        self.emit('in',port,value,flags,mask)
        if self.cursor==len(samples) and 'late_pit' in self.c:
            self.patch(0x3000,0x1FC9,self.c['late_pit'],'live-reload')
        return value
    def out(self,port,value,flags,mask=base.FLAGS):self.emit('out8',port,value,flags,mask)


class Machine(base.OriginalMachine):
    def __init__(self,c,memory,r,device,core):
        def before(m,i):
            if i.mnemonic=='in' and c.get('missing_in'):m.stop(6);return True
            if i.mnemonic=='out' and c.get('missing_out'):m.stop(7);return True
            return False
        def interrupt(m,number):
            check(number==(0x21 if c['entry']=='install' else 0x1A),'unexpected interrupt')
            m.software_interrupt(number,m.state()['ip'],BINDINGS[number],provider(number,c))
        super().__init__(c,memory,r,device,core,instructions=INS,access=Access(c,memory,r,device),
            outer_returns={0x1695 if c['entry']=='install' else 0x16D3},
            max_steps=MAX_STEPS,before=before,interrupt=interrupt,mutable_operands=((0x1653,2),))
    def run(self):
        out=super().run();out.update(child_status=0,service_status=self.service_status,
            services=self.access.service_events,transport_events=self.access.transport_events)
        return out


class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'install-{mutation}.dll',mutation,'timer_install')))
        self.functions={}
        for entry,prefix in (('install','lmn_install_game_timer'),('restore','lmn_restore_timer_interrupt')):
            for core in (True,False):
                fn=getattr(self.lib,prefix+('_core' if core else '_adapter'))
                fn.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.POINTER(base.InterruptService),ct.POINTER(base.Ports),ct.POINTER(base.Bus)]
                fn.restype=menu.Result;self.functions[entry,core]=fn
        self.menu=self.lib.lmn_install_menu_timer_adapter
        self.menu.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.POINTER(base.Bus)]
        self.menu.restype=menu.Result
        self.irq=game.Native(directory,library=self.lib)
    def run(self,c,memory,r,device,core,*,copy_state=True):
        if copy_state:memory,device=bytearray(memory),copy.deepcopy(device)
        access=Access(c,memory,r,device);cb=base.NativeCallbacks(access,missing_in=c.get('missing_in'),missing_out=c.get('missing_out'))
        number=0x21 if c['entry']=='install' else 0x1A
        body=provider(number,c);fn=service=None;ptr=ct.POINTER(base.InterruptService)()
        if body:
            fn=cb.interrupt(body);service=base.InterruptService(None,fn,*BINDINGS[number]);ptr=ct.pointer(service)
        mem=(ct.c_uint8*base.SIZE).from_buffer(memory);regs=ct.byref(base.Regs(**r))
        out=self.menu(mem,regs,ct.byref(cb.bus)) if c['entry']=='menu' else self.functions[c['entry'],core](mem,regs,ptr,ct.byref(cb.ports),ct.byref(cb.bus))
        return dict(regs={n:getattr(out.registers,n) for n in base.REG_NAMES},status=out.status,
            child_status=out.child_status,service_status=out.service_status,memory=memory,
            device=access.device,events=access.events,providers=access.providers,cursor=access.cursor,services=access.service_events)


def independent(c,memory,r,ref,core):
    if ref['status']:return
    out=ref['regs'];events=ref['events']
    packets=[e for e in events if e[0]=='out8']
    pit=c.get('late_pit',c.get('pit',0x3468)) if c['entry']=='install' else 0
    check([e[:3] for e in packets]==[('out8',0x43,0x36),('out8',0x40,pit&255),('out8',0x40,pit>>8)],c['name']+': independent PIT packet differs')
    check(all(not e[3]&0x200 for e in packets),'PIT writes must retain CLI')
    if c['entry']=='install':
        check((get16(ref['memory'],0,0x20),get16(ref['memory'],0,0x22))==(0x17C7,r['cs']),'DOS vector08 differs')
        check((get16(ref['memory'],0,0x180),get16(ref['memory'],0,0x182))==(0x182,c.get('sound_segment',(c['load']+0x842)&0xFFFF)),'DOS vector60 differs')
        check(out['flags']&0x200,'installer STI missing')
        crtc=c.get('crtc',0x3D4);port=(crtc&0xFF00)|((crtc+6)&255)
        check(all(e[1]==port for e in events if e[0]=='in'),'status port must preserve DH')
    else:
        expected=bytearray(memory);saved=(r['sp']-2)&0xFFFF
        put16(expected,r['ss'],saved,r['ds'])
        pointer=(get16(expected,r['ds'],0x1FBE),get16(expected,r['ds'],0x1FC0))
        put16(expected,0,0x20,pointer[0]);put16(expected,0,0x22,pointer[1])
        restored_ds=get16(expected,r['ss'],saved)
        clock=(get16(expected,restored_ds,0x259C),get16(expected,restored_ds,0x259E))
        check(ref['services'][-1]['clock']==clock,'live restoredDS BIOS clock differs')
        # The later INT1A frame can overwrite IVT08 again when SS=0.
        writes=[e[:3] for e in events if e[0]=='write']
        packet=[('write',0x20,pointer[0]&255),('write',0x21,pointer[0]>>8),
                ('write',0x22,pointer[1]&255),('write',0x23,pointer[1]>>8)]
        check(writes[2:6]==packet,'cleanup IVT write packet differs')
    spec=c.get('second' if c['entry']=='install' else 'clock',{})
    outer=get16(expected,r['ss'],r['sp']) if c['entry']=='restore' else 0xD00D
    if not core:check(out['ip']==spec.get('outer_ip',outer),'actual nearRET differs')


def compare(native,c,core):
    memory,r,device=setup(c)
    ref=Machine(c,bytearray(memory),dict(r),copy.deepcopy(device),core).run()
    check((ref['status'],ref['service_status'])==(c.get('expected',0),c.get('service_status',0)),c['name']+': unexpected boundary')
    independent(c,memory,r,ref,core)
    if native:base.compare_states(c['name'],native.run(c,memory,r,device,core),ref)
    return ref


def handoff(native,load):
    """Menu installer -> game installer -> game IRQ -> cleanup on same RAM.

    Caller prepares a near-call frame between entries. No IRQ scheduling proof.
    """
    c=dict(name=f'lifecycle-{load:04x}',entry='install',load=load,seed=load,flags=0xD7,irq_fixture=True)
    memory,r,device=setup(c);stages=[]
    mc=dict(c,mode=2,phase=3)
    r['ip']=0x5028
    ref=menu.Machine(mc,bytearray(memory),dict(r),copy.deepcopy(device),False).run()
    actual=native.run(dict(mc,entry='menu'),memory,r,device,False) if native else None
    if actual:base.compare_states(c['name']+'-menu',actual,ref)
    stages.append((c['name']+'-menu',ref))
    for entry in ('install','restore'):
        c=dict(c,entry=entry)
        def call_frame(state):
            regs=dict(state['regs']);regs['sp']=(regs['sp']-2)&0xFFFF
            put16(state['memory'],regs['ss'],regs['sp'],regs['ip'],state['device'])
            regs['ip']=0x1644 if entry=='install' else 0x16A9
            return regs
        r=call_frame(ref)
        ref=Machine(c,ref['memory'],r,ref['device'],False).run()
        independent(c,memory,r,ref,False)
        if actual:
            nr=call_frame(actual)
            actual=native.run(c,actual['memory'],nr,actual['device'],False,copy_state=False)
            base.compare_states(c['name']+'-'+entry,actual,ref)
        stages.append((c['name']+'-'+entry,ref))
        if entry=='install':
            ic=dict(c,entry='input',mode=2,configuration=0,palette_mode=0,phase=0,runtime_ds=0x3000)
            def hardware_entry(state):
                regs=dict(state['regs'])
                for value in (regs['flags'],regs['cs'],regs['ip']):
                    regs['sp']=(regs['sp']-2)&0xFFFF
                    put16(state['memory'],regs['ss'],regs['sp'],value,state['device'])
                regs.update(cs=get16(state['memory'],0,0x22),ip=get16(state['memory'],0,0x20),flags=regs['flags']&~0x300)
                return regs
            saved=dict(ref['regs']);r=hardware_entry(ref)
            check((r['cs'],r['ip'])==(load,0x17C7),'installed IRQ target differs')
            ref=game.Machine(ic,ref['memory'],r,ref['device'],False).run()
            check(ref['status']==0 and ref['regs']==saved,'IRQ did not restore interrupted registers')
            if actual:
                nr=hardware_entry(actual)
                actual=native.irq.run(ic,actual['memory'],nr,actual['device'],False,copy_state=False)
                base.compare_states(c['name']+'-irq',actual,ref)
            stages.append((c['name']+'-irq',ref))
    check((get16(ref['memory'],0,0x20),get16(ref['memory'],0,0x22))==(0x4C47,load),'cleanup did not restore menu vector')
    return stages


def hashes():
    paths=set(menu.hashes())|set(game.hashes())|{'tests/timer_install.py','src/entry_services.asm'}
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def worker(directory=None,snapshot=None):
    before=hashes()
    if snapshot:check(before==json.loads(Path(snapshot).read_text()),'installer snapshot changed')
    native=Native(directory) if directory else None
    rows=[];sites=set();edges=set()
    def record(name,core,ref):
        sites.update(ref['sites']);edges.update(ref['edges'])
        rows.append(dict(case=name,core=core,steps=ref['steps'],events=len(ref['events']),transport_events=ref['transport_events'],
            provider_events=sum(e.get('provider_events',0) for e in ref['services']),service_calls=len(ref['services'])))
    for c in cases():
        for core in (True,False):record(c['name'],core,compare(native,c,core))
        gc.collect();print('CHECKED '+c['name'],flush=True)
    for load in base.LOADS:
        for name,ref in handoff(native,load):record(name,False,ref)
        gc.collect();print(f'CHECKED same-RAM lifecycle{load:04x}',flush=True)
    check(set(INS)<=sites,'installer/restore sites missing: '+str(sorted(set(INS)-sites)))
    check(EDGES<=edges,'installer outcomes missing: '+str(sorted(EDGES-edges)))
    mutations=[]
    if native:
        lookup={c['name']:c for c in cases()}
        for mutation,name in ((1,'install-live-sound-operand'),(2,'install-returned-saved-ds'),(3,'install-byte-carry'),(4,'install-ordinary'),(5,'restore-ordinary'),(6,'install-live-reload')):
            try:compare(Native(directory,mutation),lookup[name],True)
            except base.Mismatch as error:mutations.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
            else:raise base.OracleFailure(f'installer mutant{mutation} survived')
            gc.collect()
    check(before==hashes(),'installer inputs changed during campaign')
    write_json(REPORT if native else BUILD/'timer-install-original-differential.json',dict(
        image='main',image_sha256=sha(base.IMAGE),own_known_bytes=82,known_connected_bytes=sum(i.size for i in (INS|game.INS|menu.INSTALL).values()),
        case_count=len(cases())+len(base.LOADS),single_case_count=len(cases()),handoff_count=len(base.LOADS),comparison_count=len(rows),
        executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(INSTALL)&sites),
        branch_edges=sorted(edges),own_branch_edges=sorted(base.direct_jump_edges(INSTALL)),
        instruction_steps=sum(r['steps'] for r in rows),ordered_bus_events=sum(r['events'] for r in rows),
        declared_interrupt_transport_events=sum(r['transport_events'] for r in rows),declared_provider_events=sum(r['provider_events'] for r in rows),
        declared_service_calls=sum(r['service_calls'] for r in rows),mutation_count=len(mutations),mutations=mutations,input_hashes=before,rows=rows,
        limits=dict(timeout_seconds=SECONDS,process_commit_mib=MEMORY_MIB,instructions=MAX_STEPS,events=MAX_EVENTS,
            game_irq_instructions=game.MAX_STEPS,game_irq_events=game.MAX_EVENTS,
            menu_install_instructions=menu.MAX_STEPS,menu_install_events=menu.MAX_EVENTS),
        scope='Installer1644 and full-register INT1A cleanup16A9 with same-RAM direct-menu/game-install/game-IRQ/cleanup handoffs; finite DOS/BIOS providers, constructed hardware entry, no scheduler or opaque-body implementation. UNKNOWN1696..16A8 remains unresolved.'))
    print(f'PASS timer lifecycle: {len(rows)} comparisons,{len(INS)} own/restore sites,{len(EDGES)} outcomes,{len(mutations)} mutants',flush=True)


def main():
    if sys.argv[1:]==['--original-worker']:worker();return
    if len(sys.argv)==4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3]);return
    if sys.argv[1:]==['--original-only']:
        run_bounded([sys.executable,__file__,'--original-worker'],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True);return
    if sys.argv[1:]:raise SystemExit('usage: timer_install.py [--original-only]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='timer-install-',parent=BUILD) as directory:
        snapshot=Path(directory)/'inputs.json';write_json(snapshot,hashes())
        run_bounded([sys.executable,__file__,'--worker',str(directory),str(snapshot)],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)


if __name__=='__main__':main()

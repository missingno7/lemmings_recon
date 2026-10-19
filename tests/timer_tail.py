"""Bounded connected game-timer tail; no prefix, scheduler or external ISR body."""
import copy
import ctypes as ct
import gc
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tests'), str(ROOT/'tools')]
import verification as base
import input_poll as poll
import ui_commands as ui
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json

check, require = base.check, base.require
physical, put16, get16 = base.physical, base.put16, base.get16
TAIL = {i.address:i for i in base.MD.disasm(base.IMAGE[0x183E:0x18B2],0x183E)}
MIRRORS = {i.address:i for i in base.MD.disasm(base.IMAGE[0x587F:0x58D2],0x587F)}
EOI = {i.address:i for i in base.MD.disasm(base.IMAGE[0x18B2:0x18B7],0x18B2)}
INS = TAIL | poll.INS | ui.INS | MIRRORS | EOI
EDGES = base.direct_jump_edges(TAIL,external_transfers={0x1899})
MAX_STEPS, MAX_EVENTS, SECONDS, MEMORY_MIB = 100_000, 20_000, 420, 384
REPORT = BUILD/'timer-tail-differential.json'
BINDINGS = {'mouse':(0x7100,0x0200),'int60':(0x7200,0x0300),
            'int61':(0x7300,0x0400),'chain':(0x7400,0x0500)}
SAVED = [0x0246,0x1111,0x2222,0x3333,0x4444,0x5555,0x6666,
         0x7777,0x8888,0x9999,0xD00D,0x6201,0x0247]


class Result(ct.Structure):
    _fields_=[('registers',base.Regs),('status',ct.c_uint16),
              ('child_status',ct.c_uint16),('service_status',ct.c_uint16)]


def cases():
    rows=[dict(name=f'phase-{phase:02x}',phase=phase) for phase in (0,1,2,3,0xFE,0xFF)]
    rows += [
        dict(name='cadence-wrap-even',cadence=0xFF,sound_options=1),
        dict(name='sound-option-clear',sound_options=0),
        dict(name='external-sound-option-clear',external_sound=0xFF,sound_options=0),
        dict(name='timer-int60',sound_options=1),
        dict(name='timer-int61',external_sound=0xFF,sound_options=2),
        dict(name='timer-int61-even-cadence',external_sound=0xFF,sound_options=1,cadence=1),
        dict(name='timer-int60-returned-ds-enables-int61',sound_options=1,
             int60={'new_ds':0x3600},other_external=0xFF,other_options=2),
        dict(name='timer-int60-unbound',sound_options=1,no_int60=True,expected=1),
        dict(name='timer-int61-unbound',external_sound=0xFF,sound_options=1,no_int61=True,expected=1),
        dict(name='timer-int60-stop',sound_options=1,int60={'status':0x1234},expected=2,service_status=0x1234),
        dict(name='timer-int61-changed-return',external_sound=0xFF,sound_options=2,
             int61={'iret_ip':0xD234},expected=3),
        dict(name='chain-new-ds',phase=3,chain={'new_ds':0x3600}),
        dict(name='chain-new-stack-and-ds',phase=3,chain={'new_ds':0x3600,'new_stack':(0x6500,0x7000)}),
        dict(name='chain-unbound',phase=3,no_chain=True,expected=1),
        dict(name='chain-stop',phase=3,chain={'status':0x2468},expected=2,service_status=0x2468),
        dict(name='chain-changed-return',phase=3,chain={'iret_cs':0xFFFF},expected=3),
        dict(name='chain-late-vector',phase=3,late_vector=True),
        dict(name='eoi-changed-child-ret',eoi_ret_patch=True,expected=4),
        dict(name='eoi-missing-out',missing_out=True,expected=5,child_status=1),
        dict(name='mirrors-enabled',mirror_gate=0),
        dict(name='mouse-input',mode=0,mouse_buttons=0),
        dict(name='mouse-input-unbound',mode=0,no_mouse=True,expected=5,child_status=1),
        dict(name='port-input-low',mode=1,callback=0x4334,port_kind='low',samples=(3,0),buttons=0xFF),
        dict(name='port-input-high',mode=1,callback=0x4359,port_kind='high',samples=(12,0),buttons=0xFF),
        dict(name='input-unknown-callback-dh-preserved',mode=1,callback=0x4111,expected=5,child_status=6),
        dict(name='input-missing-in',mode=1,callback=0x4334,missing_in=True,
             expected=5,child_status=5,service_status=1),
        dict(name='command-toggle',scan=0x4E,fg_counter=2,toggle_snapshot=0),
        dict(name='command-release',scan=0x3B,release=0x20),
        dict(name='command-sound',scan=0x3D,external_sound=0xFF,sound_options=2),
        dict(name='command-int60-unbound',scan=0x3D,cadence=1,sound_options=1,
             no_int60=True,expected=5,child_status=1),
        dict(name='command-int60-returns-ds',scan=0x3D,cadence=1,sound_options=1,
             int60={'new_ds':0x3600}),
        dict(name='command-visibility',mode=0,mouse_buttons=1,mouse_x=0xE0,mouse_y=0xB8),
        dict(name='command-visibility-changed-ret',mode=0,mouse_buttons=1,mouse_x=0xE0,mouse_y=0xB8,
             view_ret_alias=True,sp=0x0100,dirty_a=0x00FC,expected=5,child_status=4),
        dict(name='stack-offset-wrap',sp=3),
        dict(name='stack-physical-wrap',ss=0xFFFF,sp=3),
        dict(name='chain-stack-wrap',ss=0xFFFF,sp=3,phase=3),
        dict(name='outer-iret-offset-ffff',sp=0xFFEB),
        dict(name='popf-normalizes-flags',saved_flags=0x8000),
        dict(name='df-if-live',flags=0x06D7,phase=3),
    ]
    rows += [dict(name=f'load-{load:04x}',load=load,phase=3,mirror_gate=0) for load in base.LOADS]
    return [dict(load=0x1010,seed=0x183E+i,entry='input',mode=2)|c for i,c in enumerate(rows)]


def setup(c):
    memory,r,device,_=poll.setup(c)
    r.update(ip=0x183E,dx=0xAB7E)
    if c.get('view_ret_alias'):r['ss']=(c['load']+0x143E)&0xFFFF
    # Only constructed state: the timer prefix is not run or inferred here.
    for ds in (r['ds'],0x3600):
        defaults={'origin_pixels':0,'origin_bytes':2,'dirty_a':0x42,'dirty_b':0x57,
                  'update_gate':0,'slot_bound':0x2A,'creation_limit':0x11,
                  'creation_reload':0x5C,'scan_request':0x17,'release_min':0x10,
                  'release':0x20,'release_refresh':0,'panel_latch':0,
                  'action_selector':0x55,'status_refresh':0,'scan':0x20,
                  'fg_counter':0,'toggle_snapshot':0,'action_counter':0,
                  'action_snapshot':0,'timer_chain':0,'external_sound':0,'sound_options':0}
        for name,value in defaults.items():
            value=c.get(name,value)
            if ds!=r['ds'] and name in ('external_sound','sound_options'):
                value=c.get('other_external' if name=='external_sound' else 'other_options',value)
            if name in ('origin_pixels','origin_bytes','dirty_a','dirty_b'):
                put16(memory,ds,ui.OFF[name],value,device)
            else:base.put8(memory,ds,ui.OFF[name],value)
        if ds!=r['ds']:
            for off,value in ((0x10,0x60),(0x12,0x30),(0x14,0)):
                put16(memory,ds,off,value,device)
        for off,value in ((0x1C,c.get('cadence',0)),(0x1FE3,c.get('phase',0)),
                          (0x1FCD,0xFF),(0x2002,c.get('mirror_gate',1))):
            base.put8(memory,ds,off,value)
        put16(memory,ds,0x1FBE,0x0600 if c.get('late_vector') else BINDINGS['chain'][1],device)
        put16(memory,ds,0x1FC0,0x6600 if c.get('late_vector') else BINDINGS['chain'][0],device)
    for name,number in (('mouse',0x33),('int60',0x60),('int61',0x61)):
        cs,ip=BINDINGS[name];put16(memory,0,number*4,ip,device);put16(memory,0,number*4+2,cs,device)
    words=list(SAVED);words[0]=c.get('saved_flags',words[0])
    for i,word in enumerate(words):put16(memory,r['ss'],(r['sp']+2*i)&0xFFFF,word,device)
    return memory,r,device


def provider(name,c):
    if c.get('no_'+name):return None
    if name=='mouse':return poll.external
    spec=c.get(name,{})
    def execute(access,r):
        before=len(access.events)
        event={'name':name,'entry':dict(r)}
        if name=='chain':
            check([get16(access.memory,r['ss'],(r['sp']+2*i)&0xFFFF) for i in range(3)]==
                  [0x189D,c['load'],r['flags']],'synthetic chain frame differs')
            check(not (r['flags']&0x200),'chain did not retain CLI')
        if spec.get('new_stack'):
            words=[access.word_read(r['ss'],(r['sp']+2*i)&0xFFFF,r['flags']) for i in range(32)]
            r['ss'],r['sp']=spec['new_stack']
            for i,word in enumerate(words):access.word_write(r['ss'],(r['sp']+2*i)&0xFFFF,word,r['flags'])
        for role in ('ds','es','ax','bx','cx','dx','si','di','bp'):
            if 'new_'+role in spec:r[role]=spec['new_'+role]
        for key,offset in (('iret_ip',0),('iret_cs',2),('iret_flags',4)):
            if key in spec:access.word_write(r['ss'],(r['sp']+offset)&0xFFFF,spec[key],r['flags'])
        event.update(provider_events=len(access.events)-before,status=spec.get('status',0))
        access.service_events.append(event)
        return spec.get('status',0)
    return execute


class Access(poll.Access):
    def __init__(self,c,memory,r,device):
        super().__init__(c,memory,r,device);self.max_events=MAX_EVENTS
    def access(self,kind,address,flags,mask=base.FLAGS,value=None):
        out=super().access(kind,address,flags,mask,value)
        if kind=='write' and self.c.get('late_vector') and address==physical(self.r['ss'],(self.r['sp']-6)&0xFFFF):
            self.patch(self.r['ds'],0x1FBE,0x0500,'late-saved-vector-ip')
            self.patch(self.r['ds'],0x1FC0,0x7400,'late-saved-vector-cs')
        return out
    def out(self,port,value,flags,mask=base.FLAGS):
        super().out(port,value,flags,mask)
        if port==0x20 and self.c.get('eoi_ret_patch'):
            self.patch(self.r['ss'],(self.r['sp']-2)&0xFFFF,0xD234,'eoi-child-return')
    def out_word(self,port,value,flags,mask=base.FLAGS):
        self.emit('out',port,value,flags,mask);self.device.out(port,value,flags)


class Machine(base.OriginalMachine):
    def __init__(self,c,memory,r,device,core,*,instructions=None,access=None,
                 before_extra=None,returns_extra=None,changed_extra=None,mutable_extra=()):
        self.child_status=0;self.callback_target=None
        if access is None:access=Access(c,memory,r,device)
        def before(machine,ins):
            if before_extra and before_extra(machine,ins):return True
            if poll._before(machine,ins):
                machine.child_status=machine.status;machine.status=5;return True
            missing=(ins.mnemonic=='out' and ins.operands[-1].size==1 and c.get('missing_out')) or (ins.mnemonic=='in' and c.get('missing_in'))
            if missing:
                machine.child_status=1 if ins.address==0x18B4 else 5
                machine.service_status=0 if ins.address==0x18B4 else 1
                machine.stop(5);return True
            return False
        def changed(machine,off):
            if changed_extra:
                outcome=changed_extra(machine,off)
                if outcome is not None:return outcome
            if off==0x43CD:machine.child_status=5;return (5,2)
            if off in (0x4358,0x4385,0x414E) or (off==0x42A0 and c['mode']==1):
                machine.child_status=4;return (5,0)
            return (4,0)
        def interrupt(machine,number):
            resume=machine.state()['ip']
            name={0x33:'mouse',0x60:'int60',0x61:'int61'}[number]
            machine.software_interrupt(number,resume,BINDINGS[name],provider(name,c))
            if machine.stopped and resume not in (0x1861,0x1874):
                machine.child_status=machine.status;machine.status=5
        returns={0x4251:{0x1843},0x4333:{0x1843},
                 0x42A0:lambda m,o:{0x42A7 if c['mode']==1 else 0x1843},
                 0x4358:{0x42A7},0x4385:{0x42A7},0x43CD:{0x4341,0x4366},
                 0x3FE8:{0x1877},0x3FEE:{0x1877},0x414E:{0x3FE1},
                 0x58D1:{0x1881},0x18B6:{0x1891}}
        returns.update(returns_extra or {})
        super().__init__(c,memory,r,device,core,instructions=INS if instructions is None else instructions,access=access,
            outer_returns={0x18B1},child_returns=returns,max_steps=MAX_STEPS,
            changed_return_status=changed,before=before,interrupt=interrupt,
            mutable_operands=((0x4137,2),(0x5884,2))+tuple(mutable_extra),
            far_calls={0x1899:(0x189D,BINDINGS['chain'],provider('chain',c))})
    def run(self):
        out=super().run()
        out.update(child_status=self.child_status,service_status=self.service_status,
                   services=self.access.service_events,transport_events=self.access.transport_events)
        return out


class Native:
    def __init__(self,directory,mutation=0,*,cluster='timer_tail',function_prefix='lmn_game_timer_tail',access_type=Access,library=None):
        self.access_type=access_type
        self.library=library if library is not None else ct.CDLL(str(build(Path(directory)/f'timer-{mutation}.dll',mutation,cluster)))
        self.functions={}
        for core in (True,False):
            fn=getattr(self.library,function_prefix+'_'+('core' if core else 'adapter'))
            fn.argtypes=[base.MEM,ct.POINTER(base.Regs)]+[ct.POINTER(base.InterruptService)]*4+[ct.POINTER(base.Ports),ct.POINTER(base.Bus)]
            fn.restype=Result;self.functions[core]=fn
    def run(self,c,memory,r,device,core,*,copy_state=True):
        if copy_state:memory,device=bytearray(memory),copy.deepcopy(device)
        access=self.access_type(c,memory,dict(r),device)
        cb=base.NativeCallbacks(access,missing_in=c.get('missing_in',False),missing_out=c.get('missing_out',False))
        if c.get('missing_word_out'):cb.bus.out_word=base.OUT()
        keep=[];ptrs=[]
        for name in ('mouse','int60','int61','chain'):
            body=provider(name,c)
            if body is None:ptrs.append(ct.POINTER(base.InterruptService)());continue
            callback=cb.interrupt(body);cs,ip=BINDINGS[name]
            service=base.InterruptService(None,callback,cs,ip)
            keep.extend((callback,service));ptrs.append(ct.pointer(service))
        result=self.functions[core]((ct.c_uint8*base.SIZE).from_buffer(memory),ct.byref(base.Regs(**r)),*ptrs,ct.byref(cb.ports),ct.byref(cb.bus))
        return dict(regs={n:getattr(result.registers,n) for n in base.REG_NAMES},
                    status=result.status,child_status=result.child_status,service_status=result.service_status,
                    memory=memory,device=access.device,events=access.events,providers=access.providers,
                    services=access.service_events,cursor=access.cursor)


def compare(native,c,core):
    memory,r,device=setup(c)
    ref=Machine(c,bytearray(memory),dict(r),copy.deepcopy(device),core).run()
    check((ref['status'],ref['child_status'],ref['service_status'])==
          (c.get('expected',0),c.get('child_status',0),c.get('service_status',0)),c['name']+': expected boundary differs')
    if ref['status']==0:
        out=ref['regs'];expected=dict(zip(('di','si','bp','bx','dx','cx','es','ds','ax'),SAVED[1:10]))
        check(all(out[n]==v for n,v in expected.items()),c['name']+': independently saved registers differ')
        entry_sp=c.get('chain',{}).get('new_stack',(r['ss'],r['sp']-6))[1]+6
        entry_ss=c.get('chain',{}).get('new_stack',(r['ss'],r['sp']))[0]
        check(out['sp']==(entry_sp+(20 if core else 26))&0xFFFF and out['ss']==entry_ss,c['name']+': live frame consumption differs')
        check(out['ip']==(0x18B1 if core else SAVED[10]) and out['cs']==(c['load'] if core else SAVED[11]),c['name']+': outer IRET target differs')
        flags=((c.get('saved_flags',SAVED[0])&0x7FD5)|2) if core else SAVED[12]
        check(out['flags']==flags,c['name']+': restored flags differ')
        active_ds=c.get('int60',{}).get('new_ds',r['ds'])
        frame=c.get('chain',{}).get('new_ds',active_ds)
        check(ref['memory'][physical(frame,0x1FCF)]==0xFF and ref['memory'][physical(frame,0x1FCD)]==0,c['name']+': returned DS stores differ')
        check(ref['memory'][physical(active_ds,0x1FE3)]==((c.get('phase',0)+1)&3),c['name']+': modulo-four phase differs')
    if native:base.compare_states(c['name'],native.run(c,memory,r,device,core),ref)
    return ref


def hashes():
    paths=['AGENTS.md','assets/vgalemmi.exe','metadata/oracle.json','metadata/inputs.json','metadata/toolchain-lock.json',
           'src/game_timer.asm','src/entry_services_after_timer.asm','src/game_code_late_after_palette.asm',
           'src/input_poll.asm','src/input_commands.asm','src/view_visibility.asm','src/port201_input.asm',
           'tests/timer_tail.py','tests/verification.py','tests/input_poll.py','tests/ui_commands.py','tests/port_io.py','tests/minimap_vga.py',
           'tools/bounded_process.py','tools/cbuild.py','tools/difftest.py','tools/common.py','tools/unpack.py','tools/resources.py',
           'c/lemmings_sym.h','c/regs.h','c/special_blit.h','c/aligned_read_mask.h']
    paths += ['c/'+name+suffix for name in ('timer_tail','input_poll','ui_commands','view_visibility','vga_mirrors','port_io','interrupt_service') for suffix in ('.c','.h')]
    return {p:sha((ROOT/p).read_bytes()) for p in paths}


def worker(directory=None,snapshot=None):
    before=hashes()
    if snapshot:check(before==json.loads(Path(snapshot).read_text()),'timer inputs changed before worker')
    native=Native(directory) if directory else None
    rows=[];sites=set();edges=set()
    for c in cases():
        for core in (True,False):
            r=compare(native,c,core);sites.update(r['sites']);edges.update(r['edges'])
            rows.append(dict(case=c['name'],core=core,status=r['status'],steps=r['steps'],events=len(r['events']),transport_events=r['transport_events'],
                             service_calls=len(r['services']),provider_events=sum(e['provider_events'] for e in r['services'])))
        gc.collect();print('CHECKED '+c['name'],flush=True)
    check(set(TAIL)<=sites,'timer own instruction sites missing: '+str(sorted(set(TAIL)-sites)))
    check(EDGES<={edge for edge in edges if edge[0] in TAIL},'timer direct outcomes missing: '+str(sorted(EDGES-edges)))
    mutations=[]
    if native:
        lookup={c['name']:c for c in cases()}
        for mutation,name in ((1,'input-unknown-callback-dh-preserved'),(2,'phase-03'),(3,'chain-new-ds'),(4,'chain-new-stack-and-ds'),(5,'eoi-changed-child-ret')):
            try:compare(Native(directory,mutation),lookup[name],True)
            except base.Mismatch as error:mutations.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
            else:raise base.OracleFailure(f'timer mutant {mutation} survived')
            gc.collect()
    check(before==hashes(),'timer campaign inputs changed')
    write_json(REPORT if native else BUILD/'timer-tail-original-differential.json',dict(image='main',image_sha256=sha(base.IMAGE),
        own_known_bytes=116,known_connected_bytes=sum(i.size for i in INS.values()),case_count=len(cases()),comparison_count=len(rows),
        executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(TAIL)&sites),branch_edges=sorted(edges),
        own_branch_edges=sorted(EDGES),instruction_steps=sum(r['steps'] for r in rows),ordered_bus_events=sum(r['events'] for r in rows),
        declared_interrupt_transport_events=sum(r['transport_events'] for r in rows),mutation_count=len(mutations),mutations=mutations,
        declared_provider_events=sum(r['provider_events'] for r in rows),declared_service_calls=sum(r['service_calls'] for r in rows),
        input_hashes=before,rows=rows,limits=dict(timeout_seconds=SECONDS,process_commit_mib=MEMORY_MIB,instructions=MAX_STEPS,events=MAX_EVENTS),
        scope='183E tail with actual native children, synthetic chain and hardware return frames; prefix, unknown callbacks, asynchronous scheduling and opaque ISR bodies remain open'))
    print(f'PASS timer tail: {len(rows)} comparisons, {len(set(TAIL)&sites)} own sites, {len(EDGES)} own outcomes, {len(mutations)} mutants',flush=True)


def main():
    if sys.argv[1:]==['--original-worker']:worker();return
    if len(sys.argv)==4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3]);return
    if sys.argv[1:]==['--original-only']:
        run_bounded([sys.executable,__file__,'--original-worker'],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True);return
    if sys.argv[1:]:raise SystemExit('usage: timer_tail.py [--original-only]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='timer-tail-',parent=BUILD) as directory:
        snapshot=Path(directory)/'input-hashes.json';write_json(snapshot,hashes())
        run_bounded([sys.executable,__file__,'--worker',str(directory),str(snapshot)],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)


if __name__=='__main__':main()

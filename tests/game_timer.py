"""Bounded full game timer composition using the shared verifier and tail fixtures."""
import copy
import ctypes as ct
import gc
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as base
import timer_tail as tail
import palette_timer as palette
from bounded_process import run_bounded,temporary_build_directory
from common import BUILD,sha,write_json

check,require=base.check,base.require
physical,put16,get16=base.physical,base.put16,base.get16
PREFIX={i.address:i for i in base.MD.disasm(base.IMAGE[0x17C7:0x183E],0x17C7)}
PATTERN={i.address:i for lo,hi in ((0x5827,0x587F),(0x715F,0x71CA),(0x7218,0x75EF))
         for i in base.MD.disasm(base.IMAGE[lo:hi],lo)}
OWN=PREFIX|tail.TAIL
INS=tail.INS|PREFIX|palette.INS|PATTERN
EDGES=base.direct_jump_edges(OWN,external_transfers={0x1899})
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=420,384,100_000,30_000
REPORT=BUILD/'game-timer-differential.json'
HARDWARE=(0xD00D,0x6201,0x0247)


def cases():
    # Reuse every tail seam without pretending that the skipped prefix ran.
    rows=[dict(c,name='skip-'+c['name'],configuration=0xFF) for c in tail.cases()
          if not c.get('view_ret_alias')]
    rows += [
        dict(name='prefix-mode-0',palette_mode=0),
        dict(name='prefix-packed',palette_mode=2),
        dict(name='prefix-rgb',palette_mode=4),
        dict(name='prefix-rgb-blanked',palette_mode=4,blanking=0),
        dict(name='prefix-whole-word-mode',palette_mode=0x104),
        dict(name='configuration-fe',configuration=0xFE),
        dict(name='configuration-0',configuration=0),
        dict(name='status-repeated-waits',samples_status=(0,0,8,8,8,0)),
        dict(name='crtc-byte-carry',crtc=0x03FC,origin=0xFFFD,page=0x8002),
        dict(name='crtc-word-overflow',origin=0xFFFF,page=1),
        dict(name='crtc-signed-overflow',origin=0x7FFE,page=1),
        dict(name='pit-zero',pit=0),
        dict(name='pit-ffff',pit=0xFFFF),
        dict(name='pit-provider-change',late_pit=0x81A5),
        dict(name='live-source-during-output',palette_mode=4,source_patch=True),
        dict(name='before-return-changed',before_return_patch=True,expected=4),
        dict(name='after-inner-return-changed',palette_mode=4,inner_return_patch=True,expected=5,child_status=3),
        dict(name='after-return-changed',palette_mode=4,after_return_patch=True,expected=4),
        dict(name='pattern-return-changed',pattern_return_patch=True,expected=4),
        dict(name='pattern-copy-return-changed',pattern_child_patch=True,expected=5,child_status=1),
        dict(name='missing-status-input',missing_in=True,expected=6),
        dict(name='missing-crtc-output',missing_word_out=True,expected=7),
        dict(name='missing-pit-output',missing_out=True,expected=7),
        dict(name='missing-before-dac-input',palette_mode=4,blanking=0,missing_in=True,expected=5,child_status=1),
        dict(name='missing-before-dac-output',palette_mode=4,missing_out=True,expected=5,child_status=2),
        dict(name='prefix-backwards',palette_mode=4,flags=0x0CD7),
        dict(name='prefix-if-set',flags=0x0AD7),
        dict(name='prefix-stack-offset-wrap',sp=3),
        dict(name='prefix-stack-physical-wrap',ss=0xFFFF,sp=3),
        dict(name='prefix-frame-after-ffff',sp=0xFFFF),
        dict(name='prefix-relocated-operand',runtime_ds=0x3800),
        dict(name='prefix-entry-segment-trap',entry_ds=0x3600,entry_gate_trap=True),
        dict(name='prefix-late-relocated-operand',runtime_ds=0x3800,late_operand=True),
        dict(name='prefix-live-saved-di',palette_mode=4,saved_di_patch=True),
        dict(name='crtc-origin-changed-after-load',crtc_origin_patch=0x5678),
        dict(name='pit-memory-changed-after-load',pit_write_patch=0xC71A),
        dict(name='prefix-chain-returned-ds',phase=3,chain={'new_ds':0x3600}),
        dict(name='prefix-chain-returned-stack',phase=3,chain={'new_ds':0x3600,'new_stack':(0x6500,0x7000)}),
        dict(name='prefix-mouse-and-commands',mode=0,mouse_buttons=1,mouse_x=0xE0,mouse_y=0xB8),
        dict(name='prefix-port-low',mode=1,callback=0x4334,port_kind='low',samples=(3,0),buttons=0xFF),
        dict(name='prefix-port-high',mode=1,callback=0x4359,port_kind='high',samples=(12,0),buttons=0xFF),
        dict(name='prefix-pattern-selected',selection=0xFF),
        dict(name='prefix-pattern-selection-fe',selection=0xFE),
    ]
    rows += [dict(name=f'prefix-load-{load:04x}',load=load,palette_mode=4) for load in base.LOADS]
    return [dict(load=0x1010,seed=0x17C7+i,entry='input',mode=2,configuration=0,
                 palette_mode=0,flags=0x08D7)|c for i,c in enumerate(rows)]


def setup(c):
    runtime_ds=c.get('runtime_ds',(c['load']+0x09A9)&0xFFFF)
    memory,r,device=tail.setup(dict(c,ds=runtime_ds))
    # Full entry owns only the supplied hardware frame. Ten saves are executed.
    r.update(ip=0x17C7,ds=c.get('entry_ds',0x3200))
    for i,value in enumerate(HARDWARE):put16(memory,r['ss'],(r['sp']+2*i)&0xFFFF,value,device)
    put16(memory,c['load'],0x17D2,(c['load']+0x09A9)&0xFFFF if c.get('late_operand') else runtime_ds)
    base.put8(memory,runtime_ds,0x200E,c['configuration'])
    if c.get('entry_gate_trap'):base.put8(memory,r['ds'],0x200E,0xFF)
    put16(memory,runtime_ds,0x1F7C,c['palette_mode'])
    put16(memory,runtime_ds,0x1FDA,c.get('crtc',0x3D4))
    put16(memory,runtime_ds,0x1F78,c.get('origin',0x1200))
    put16(memory,runtime_ds,0x1F7A,c.get('page',0x3456))
    put16(memory,runtime_ds,0x1FC9,c.get('pit',0x3468))
    base.put8(memory,runtime_ds,0x200C,c.get('blanking',0xFF))
    # Constructed generated-bank state; this does not claim startup generation.
    put16(memory,runtime_ds,0x1FEA,0x6000)
    base.put8(memory,runtime_ds,0x1FE0,3)
    base.put8(memory,runtime_ds,0x1A,c.get('selection',0))
    for offset,value in ((8,0x3000),(0xA,0x4000),(0xC,0x5000),(0xE,0x6000)):
        put16(memory,runtime_ds,offset,value)
    return memory,r,device


class Access(tail.Access):
    def __init__(self,c,memory,r,device):
        active_ds=c.get('runtime_ds',(c['load']+0x09A9)&0xFFFF)
        # Existing tail providers address its inherited save frame at entrySP-20.
        super().__init__(c,memory,dict(r,ds=active_ds,sp=(r['sp']-20)&0xFFFF),device)
        self.max_events=MAX_EVENTS;self.status_cursor=0;self.port_cursor=0
    def access(self,kind,address,flags,mask=base.FLAGS,value=None):
        result=super().access(kind,address,flags,mask,value)
        if kind=='write' and self.c.get('late_operand') and 'late-data-operand' not in self.providers:
            self.patch(self.c['load'],0x17D2,self.r['ds'],'late-data-operand')
        if kind=='read':
            ds=self.r['ds'];ss=self.r['ss'];sp=self.r['sp']
            if address==physical(ds,0x1F7D) and self.c.get('before_return_patch') and 'before-ret' not in self.providers:
                self.patch(ss,(sp-2)&0xFFFF,0xD234,'before-ret')
            if address==physical(ds,0x2638) and self.c.get('inner_return_patch') and 'inner-ret' not in self.providers:
                self.patch(ss,(sp-4)&0xFFFF,0xD234,'inner-ret')
            if address==physical(ds,0x2650) and self.c.get('after_return_patch') and 'after-ret' not in self.providers:
                self.patch(ss,(sp-2)&0xFFFF,0xD234,'after-ret')
        return result
    def inp(self,port,flags,mask=base.FLAGS):
        if port==0x201:
            total=self.cursor;self.cursor=self.port_cursor
            value=super().inp(port,flags,mask)
            self.port_cursor=self.cursor;self.cursor=total+1
            return value
        if port==0x3C5:value=0x13
        else:
            samples=self.c.get('samples_status',(0,8,8,0,0,8,8,0))
            check(self.status_cursor<len(samples),'finite status samples exhausted')
            value=samples[self.status_cursor];self.status_cursor+=1
            if 'late_pit' in self.c:self.patch(self.r['ds'],0x1FC9,self.c['late_pit'],'late-pit')
        self.cursor+=1;self.emit('in8',port,value,flags,mask);return value
    def out(self,port,value,flags,mask=base.FLAGS):
        super().out(port,value,flags,mask)
        if port==0x3C9 and self.c.get('source_patch') and 'late-rgb-source' not in self.providers:
            self.patch(self.r['ds'],0x2669,0x2B,'late-rgb-source',word=False)
        if port==0x3C9 and self.c.get('saved_di_patch') and 'saved-di' not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']+2)&0xFFFF,0xABCD,'saved-di')
        if port==0x43 and 'pit_write_patch' in self.c:
            self.patch(self.r['ds'],0x1FC9,self.c['pit_write_patch'],'pit-after-load')
        if port==0x20 and 'saved_flags' in self.c:
            self.patch(self.r['ss'],self.r['sp'],self.c['saved_flags'],'live-saved-flags')
    def out_word(self,port,value,flags,mask=base.FLAGS):
        if port in (0x3C4,0x3CE):super().out_word(port,value,flags,mask)
        else:
            check(port==self.c.get('crtc',0x3D4),'unexpected constructed word port')
            self.emit('out',port,value,flags,mask)
            if 'crtc_origin_patch' in self.c:
                self.patch(self.r['ds'],0x1F78,self.c['crtc_origin_patch'],'origin-after-load')
        if port==0x3C4 and value==0x0F02:
            if self.c.get('pattern_return_patch'):
                self.patch(self.r['ss'],(self.r['sp']-2)&0xFFFF,0xD234,'pattern-ret')
            if self.c.get('pattern_child_patch'):
                self.patch(self.r['ss'],(self.r['sp']-4)&0xFFFF,0xD234,'pattern-child-ret')


class Machine(tail.Machine):
    def __init__(self,c,memory,r,device,core):
        self.palette_phase='before';self.after_first=False
        def before(machine,ins):
            if ins.address==0x1838:machine.palette_phase='after';machine.after_first=False
            if ins.address==0x5555:machine.after_first=True
            missing=(ins.mnemonic=='in' and c.get('missing_in')) or (ins.mnemonic=='out' and c.get('missing_out') and ins.operands[-1].size==1)
            if ins.mnemonic=='out' and ins.operands[-1].size==2 and c.get('missing_word_out'):missing=True
            if not missing:return False
            if ins.address in PREFIX:
                machine.stop(6 if ins.mnemonic=='in' else 7);return True
            if ins.address in palette.INS:
                machine.child_status=1 if ins.mnemonic=='in' else 2
                machine.stop(5);return True
            return False
        def palette_return(machine,off):
            if machine.palette_phase=='before':return {0x17E0}
            if off==0x54C3 and not machine.after_first:return {0x5555}
            return {0x183B}
        def changed(machine,off):
            if off==0x54C3 and machine.palette_phase=='after' and not machine.after_first:
                machine.child_status=3;return (5,0)
            if off in (0x71C9,0x75EE):machine.child_status=1;return (5,0)
            return None
        returns={off:palette_return for off in (0x5484,0x54C3,0x554A,0x5446)}
        returns.update({0x71C9:{0x582A},0x75EE:{0x5869},0x587E:{0x183E}})
        super().__init__(c,memory,r,device,core,instructions=INS,access=Access(c,memory,r,device),
            before_extra=before,returns_extra=returns,changed_extra=changed,mutable_extra=((0x17D2,2),))


class Native(tail.Native):
    def __init__(self,directory,mutation=0):
        super().__init__(directory,mutation,cluster='game_timer',function_prefix='lmn_game_timer',access_type=Access)


def compare(native,c,core):
    memory,r,device=setup(c)
    ref=Machine(c,bytearray(memory),dict(r),copy.deepcopy(device),core).run()
    check((ref['status'],ref['child_status'],ref['service_status'])==
          (c.get('expected',0),c.get('child_status',0),c.get('service_status',0)),c['name']+': expected boundary differs')
    if ref['status']==0:
        out=ref['regs']
        restored=dict(r,di=0xABCD) if c.get('saved_di_patch') else r
        check(all(out[n]==restored[n] for n in ('ax','bx','cx','dx','si','di','bp','ds','es')),c['name']+': saved registers differ')
        frame_ss,frame_sp=c.get('chain',{}).get('new_stack',(r['ss'],(r['sp']-26)&0xFFFF))
        # A relocated provider stack begins at its synthetic frame, 26 below entry.
        entry_sp=(frame_sp+26)&0xFFFF
        check(out['ss']==frame_ss and out['sp']==(entry_sp+(0 if core else 6))&0xFFFF,c['name']+': frame extent differs')
        check((out['ip'],out['cs'])==((0x18B1,c['load']) if core else HARDWARE[:2]),c['name']+': hardware return target differs')
        check(out['flags']==(((c.get('saved_flags',r['flags'])&0x7FD5)|2) if core else HARDWARE[2]),c['name']+': saved flags differ')
    if c['configuration']!=0xFF and not c.get('missing_word_out') and not c.get('before_return_patch') and not (c.get('palette_mode')==4 and (c.get('missing_in') or c.get('missing_out'))):
        crtc=c.get('crtc',0x3D4);position=(c.get('origin',0x1200)+c.get('page',0x3456)+2)&0xFFFF
        packets=[e[:3] for e in ref['events'] if e[0]=='out' and e[1]==crtc]
        check(packets[:2]==[('out',crtc,(position&0xFF00)|0xC),('out',crtc,((position&255)<<8)|0xD)],c['name']+': CRTC packet differs')
        if not c.get('missing_in') and not c.get('missing_out'):
            pit=c.get('late_pit',c.get('pit',0x3468))
            writes=[e for e in ref['events'] if e[0]=='out8' and e[1] in (0x40,0x43)]
            check([e[:3] for e in writes]==[('out8',0x43,0x36),('out8',0x40,pit&255),('out8',0x40,pit>>8)],c['name']+': PIT packet differs')
            check(all(not e[3]&0x200 for e in writes),c['name']+': PIT did not retain CLI')
    if native:base.compare_states(c['name'],native.run(c,memory,r,device,core),ref)
    return ref


def hashes():
    paths=set(tail.hashes())|set(palette.hashes())|{'tests/game_timer.py','src/fixed_pattern_drawing.asm'}
    paths|={'c/'+name+suffix for name in ('fixed_pattern_update','fixed_pattern_copy','fixed_pattern_draw') for suffix in ('.c','.h')}
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def worker(directory=None,snapshot=None):
    before=hashes()
    if snapshot:check(before==json.loads(Path(snapshot).read_text()),'timer inputs changed before worker')
    native=Native(directory) if directory else None
    rows=[];sites=set();edges=set()
    for c in cases():
        for core in (True,False):
            ref=compare(native,c,core);sites.update(ref['sites']);edges.update(ref['edges'])
            rows.append(dict(case=c['name'],core=core,status=ref['status'],steps=ref['steps'],events=len(ref['events']),
                transport_events=ref['transport_events'],service_calls=len(ref['services']),provider_events=sum(e['provider_events'] for e in ref['services'])))
        gc.collect();print('CHECKED '+c['name'],flush=True)
    check(set(OWN)<=sites,'timer sites missing: '+str(sorted(set(OWN)-sites)))
    check(EDGES<=edges,'timer outcomes missing: '+str(sorted(EDGES-edges)))
    mutations=[]
    if native:
        lookup={c['name']:c for c in cases()}
        for mutation,name in ((1,'prefix-entry-segment-trap'),(2,'crtc-byte-carry'),(3,'pit-provider-change'),(4,'prefix-mode-0'),(5,'before-return-changed')):
            try:compare(Native(directory,mutation),lookup[name],True)
            except base.Mismatch as error:mutations.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
            else:raise base.OracleFailure(f'full timer mutant{mutation} survived')
            gc.collect()
    check(before==hashes(),'timer campaign inputs changed')
    write_json(REPORT if native else BUILD/'game-timer-original-differential.json',dict(image='main',image_sha256=sha(base.IMAGE),
        own_known_bytes=235,new_known_bytes=119,known_connected_bytes=sum(i.size for i in INS.values()),case_count=len(cases()),comparison_count=len(rows),
        executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(OWN)&sites),branch_edges=sorted(edges),own_branch_edges=sorted(EDGES),
        instruction_steps=sum(r['steps'] for r in rows),ordered_bus_events=sum(r['events'] for r in rows),mutation_count=len(mutations),mutations=mutations,
        declared_interrupt_transport_events=sum(r['transport_events'] for r in rows),declared_provider_events=sum(r['provider_events'] for r in rows),
        declared_service_calls=sum(r['service_calls'] for r in rows),rows=rows,input_hashes=before,
        limits=dict(timeout_seconds=SECONDS,process_commit_mib=MEMORY_MIB,instructions=MAX_STEPS,events=MAX_EVENTS),
        scope='Full17C7 timer with canonical save/hardware frames, tested palette/pattern/input/command/mirror children and opaque ISR seams; generated-bank initialization, unknown callback domains and asynchronous IRQ timing remain open'))
    print(f'PASS full timer: {len(rows)} comparisons,{len(OWN)} sites,{len(EDGES)} own outcomes,{len(mutations)} mutants',flush=True)


def main():
    if sys.argv[1:]==['--original-worker']:worker();return
    if len(sys.argv)==4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3]);return
    if sys.argv[1:]==['--original-only']:
        run_bounded([sys.executable,__file__,'--original-worker'],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True);return
    if sys.argv[1:]:raise SystemExit('usage: game_timer.py [--original-only]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='game-timer-',parent=BUILD) as directory:
        snapshot=Path(directory)/'inputs.json';write_json(snapshot,hashes())
        run_bounded([sys.executable,__file__,'--worker',str(directory),str(snapshot)],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)


if __name__=='__main__':main()

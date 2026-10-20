"""46EB result operation and two tail helpers on the shared bounded engine.

Poll fixtures declare only foreground-visible button/key deliveries, with IF
honoured. They do not claim hardware menu-IRQ delivery or arbitrary preemption.
Display/BIOS providers and intact resource banks retain their owning domains.
"""
import copy
import ctypes as ct
import gc
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as v
import main_menu as menus
import level_briefing as briefing
import cbuild
from bounded_process import run_bounded,temporary_build_directory
from common import BUILD,sha,write_json

OWN_RANGES=((0x46EB,0x4728),(0x4729,0x482F),(0x48BD,0x4955))
OWN={i.address:i for a,b in OWN_RANGES for i in v.MD.disasm(v.IMAGE[a:b],a)}
INS=menus.INS|briefing.INS|OWN
for p in (0x4401,0x4551):INS[p]=next(v.MD.disasm(v.IMAGE[p:p+16],p))
EDGES=v.direct_jump_edges(OWN)
POLLS={0x47A9,0x47B1,0x47BE,0x480A,0x4812}
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=2040,512,2_000_000,1_500_000
REPORT=BUILD/'level-result-differential.json'
class Services(ct.Structure):
    _fields_=[('ports',ct.POINTER(v.Ports)),('bus',ct.POINTER(v.Bus)),
        ('video',ct.POINTER(menus.VideoServices)),('poll',ct.POINTER(v.ForegroundPoll)),
        ('game_data_segment',ct.c_uint16)]
class Result(ct.Structure):
    _fields_=[('registers',v.Regs)]+[(n,ct.c_uint16) for n in ('status','child_entry','child_status','service_status')]

def cases():
    rows=[]
    for mode in range(3):
        for passed in (False,True):
            rows.append(dict(name=f'{"pass" if passed else "fail"}-mode{mode}',input_mode=mode,
                completion=80 if passed else 10,leave='button0' if passed else 'button1'))
        rows.append(dict(name=f'last-mode{mode}',selection=0x77,input_mode=mode))
    for name,kw in (
        ('equal',dict(completion=50)),('signed-negative',dict(completion=0x80)),
        ('signed-requirement',dict(completion=10,required=0xFF)),
        ('time-up',dict(time_zero=True)),('all-out',{}),
        ('key20',dict(leave='key20')),('key40',dict(leave='key40')),
        ('release-delayed',dict(release=(7,1,0),choice_delay=2)),
        ('final-button',dict(selection=0x77,leave='button0')),
        ('final-key20',dict(selection=0x77,leave='key20')),
        ('final-delayed',dict(selection=0x77,choice_delay=2)),
        ('selection-wrap',dict(selection=255)),
        ('group-boundary',dict(selection=29)),
        ('null-release',dict(null_poll=True,initial_buttons=1,expected=3)),
        ('null-choice',dict(null_poll=True,expected=3)),
        ('null-final',dict(selection=0x77,null_poll=True,expected=3)),
        ('null-existing-key',dict(null_poll=True,initial_keys=0x20)),
        ('poll-stop',dict(poll_stop=0x47BE,expected=4)),
        ('poll-stop-final',dict(selection=0x77,poll_stop=0x4812,expected=4)),
        ('changed-return',dict(return_patch=0x46EE,expected=6,child_entry=0x4DEF)),
        ('missing-video',dict(missing_video=True,expected=5,child_status=1,child_entry=0x4BE7)),
    ):rows.append(dict(name=name,**kw))
    for load in v.LOADS[1:]:rows.append(dict(name=f'load-{load:04X}',load=load))
    for mode in range(3):rows.append(dict(name=f'fields-mode{mode}',entry=0x48BD,input_mode=mode))
    # Each table category plus adjacent equality boundaries, including the
    # signed word subtractions for low requirements and the special100 case.
    for required,values in ((50,(0,1,24,25,44,45,48,49,50,51,69,70,99,100,255)),(0,(1,100)),(255,(127,128,249,250,253,254,255))):
        for value in values:rows.append(dict(name=f'message-{required}-{value}',entry=0x48F6,completion=value,required=required))
    rows += [dict(name='helper-core',entry=0x48BD,core=True),dict(name='message-core',entry=0x48F6,core=True),
             dict(name='helper-stack-wrap',entry=0x48BD,sp=0),dict(name='message-stack-ffff',entry=0x48F6,sp=0xFFFF),
             dict(name='cs-table',entry=0x48F6,completion=0,wrong_ds_table=True)]
    return [dict(load=v.LOADS[0],seed=0x46EB+i,flags=0xAD7,input_mode=0,completion=80,required=50,
        selection=37,leave='key40',entry=0x46EB,release=(1,0),choice_delay=0)|c for i,c in enumerate(rows)]

def setup(c):
    memory,r,device=briefing.setup(dict(c,kind='briefing',group=1,mode=2,total=80,minutes=5,
        value=71,leave=0x40))
    r['ip']=c['entry']
    for off,value in ((0x40,c['completion']),(0x41,c['required']),(0x1F6B,c['selection']),
        (0x1F6D,0xA5),(0x1F6E,c['selection']//30),(0x25A6,c['input_mode']),
        (0x20A7,0x30 if c.get('time_zero') else 0x31),(0x20A9,0x30),(0x20AA,0x30)):
        v.sync_memory_byte(memory,device,r['ds'],off,value)
    v.put16(memory,r['ds'],0x14,c.get('initial_buttons',0),device)
    v.put16(memory,r['ds'],0x1FC7,c.get('initial_keys',0),device)
    # Explicit alternative data in DS distinguishes CS table ownership without
    # sending a mutant into unbounded random text. Both are valid streams.
    if c.get('wrong_ds_table'):v.put16(memory,r['ds'],0x4955,0x4F77,device)
    return memory,r,device

class Access(briefing.Access):
    def __init__(self,c,memory,r,device):
        # Avoid the briefing's input-read provider: only declared poll deliveries
        # may mutate result input in this suite.
        super().__init__(dict(c,kind='result'),memory,r,device)
        self.counts={};self.polls=[]
    def access(self,kind,address,flags,mask=v.FLAGS,value=None):
        got=super().access(kind,address,flags,mask,value)
        target=self.c.get('return_patch')
        if target and 'result-return' not in self.providers and kind=='write':
            at=v.physical(self.r['ss'],(self.r['sp']-2)&65535)
            if address==(at+1)&v.MASK and value==target>>8 and self.memory[at]==target&255:
                self.patch(self.r['ss'],(self.r['sp']-2)&65535,0xD234,'result-return')
        return got
    def poll(self,r,site):
        n=self.counts.get(site,0)+1;self.counts[site]=n
        v.check(sum(self.counts.values())<=32,'result poll budget exhausted')
        self.polls.append((site,n,r['flags']))
        if self.c.get('poll_stop')==site:return 0xCA11
        if not r['flags']&0x200:return 0
        button=key=None
        if site==0x47A9:button=self.c['release'][min(n-1,len(self.c['release'])-1)]
        if site in (0x47B1,0x480A):
            button=0
            if n>self.c['choice_delay']:
                button={'button0':1,'button1':2}.get(self.c['leave'],0)
        if site in (0x47BE,0x4812):
            key=0 if n<=self.c['choice_delay'] else {'key20':0x20,'key40':0x40}.get(self.c['leave'],0)
            # The key40 witness later delivers key20 as a real second input;
            # a broken key40 consumer still exits normally, never by a budget.
            if self.c['name']=='key40' and n>=2:key=0x20
        for offset,value in ((0x14,button),(0x1FC7,key)):
            if value is not None:
                self.patch(r['ds'],offset,value,f'poll-{site:04X}-{n}')
                self.emit('poll-store',v.physical(r['ds'],offset),value,r['flags'])
        return 0

class Machine(v.OriginalMachine):
    def __init__(self,c,memory,r,device):
        frames=[];failed=[];diagnostics=dict(child_entry=0,child_status=0,service_status=0)
        access=Access(c,memory,r,device);seen={};self.text_starts=[];self.table_indices=[]
        def before(m,i):
            if i.address in (0x4401,0x4551):m.stop(1 if i.address==0x4401 else 2);return True
            if i.address in POLLS:
                if c.get('null_poll'):
                    # Execute the first predicates literally, then stop at the
                    # first repeated loop head with its live prior-test flags.
                    if i.address in (0x47A9,0x47B1,0x480A) and seen.get(i.address):m.stop(3);return True
                    seen[i.address]=True
                elif access.poll(m.state(),i.address):
                    diagnostics['service_status']=0xCA11;m.stop(4);return True
            if i.address==0x4BF2 and c.get('missing_video'):
                diagnostics.update(child_entry=0x4BE7,child_status=1);m.stop(5);return True
            if i.address==0x4D4D:self.text_starts.append(m.state()['si'])
            if i.address==0x494D:self.table_indices.append(m.state()['bx']//2)
            if i.mnemonic in ('call','lcall'):
                frames.append(dict(owner=i.address,resume=i.address+i.size,far=i.mnemonic=='lcall',
                    target=i.operands[-1].imm))
            return False
        def expected(m,off):
            v.check(bool(frames),'undeclared result return');frame=frames.pop();failed[:]=[frame]
            return {(c['load'],frame['resume'])} if frame['far'] else {frame['resume']}
        def changed(m,off):
            v.check(failed[-1]['owner'] in OWN,'unscoped changed nested result return')
            diagnostics['child_entry']=failed[-1]['target'];return 6
        def interrupt(m,number):
            v.check(number==0x10,'unexpected result interrupt')
            state=m.state();out=menus.video_provider(access,{n:state[n] for n in menus.animation.FIELDS})
            state.update(out);m.set_state(state);m.mask=v.FLAGS;m.flags=state['flags']
        super().__init__(c,memory,r,device,c.get('core',False),instructions=INS,access=access,
            outer_returns=lambda m,p:c['entry'] in (0x48BD,0x48F6) and not frames and p==0x4D77,
            child_returns={p:expected for p,i in INS.items() if i.mnemonic=='ret'},
            far_returns={p:expected for p,i in INS.items() if i.mnemonic=='retf'},
            before=before,interrupt=interrupt,changed_return_status=changed,max_steps=MAX_STEPS)
        self.diagnostics=diagnostics
    def run(self):
        out=super().run();out.update(self.diagnostics,services=self.access.service_events,polls=self.access.polls,
            text_starts=self.text_starts,table_indices=self.table_indices);return out

class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(cbuild.build(Path(directory)/f'level-result-{mutation}.dll',mutation,'level_result')))
        self.functions={}
        for core in (True,False):
            fn=getattr(self.lib,'lmn_level_result_'+('core' if core else 'adapter'));fn.restype=Result
            fn.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.POINTER(Services)];self.functions[core]=fn
    def run(self,c,memory,r,device):
        memory,device=bytearray(memory),copy.deepcopy(device);access=Access(c,memory,r,device)
        cb=v.NativeCallbacks(access);mem=(ct.c_uint8*v.SIZE).from_buffer(memory)
        @menus.VIDEO
        def mode(_,binding,incoming,outgoing):
            try:
                v.check(ct.addressof(binding.contents)==ct.addressof(mem),'result video RAM differs')
                state=menus.video_provider(access,{n:getattr(incoming.contents,n) for n in menus.animation.FIELDS})
                for n,value in state.items():setattr(outgoing.contents,n,value)
            except BaseException as error:v.callback_failure(error)
        video=menus.VideoServices(None,mode,menus.VIDEO())
        callback=cb.foreground(lambda a,r,site:a.poll(r,site));poll=v.ForegroundPoll(None,callback)
        services=Services(ct.pointer(cb.ports),ct.pointer(cb.bus),None if c.get('missing_video') else ct.pointer(video),
            None if c.get('null_poll') else ct.pointer(poll),(c['load']+0x9A9)&65535)
        result=self.functions[c.get('core',False)](mem,ct.byref(v.Regs(**r)),ct.byref(services))
        return dict(regs={n:getattr(result.registers,n) for n in v.REG_NAMES},
            **{n:getattr(result,n) for n in ('status','child_entry','child_status','service_status')},
            memory=memory,device=device,events=access.events,providers=access.providers,cursor=access.cursor,
            services=access.service_events,polls=access.polls)

def independent(c,r,ref):
    expected=c.get('expected',0 if c['entry']!=0x46EB else 2 if c['leave']=='button0' and c['selection']!=0x77 else 1)
    v.check(ref['status']==expected,c['name']+': unexpected result status')
    v.check(ref['child_status']==c.get('child_status',0) and ref['child_entry']==c.get('child_entry',0),c['name']+': child diagnostic differs')
    if c['entry']==0x46EB and ref['status'] in (1,2,3,4):
        passed=((c['completion']^128)-128)>=((c['required']^128)-128)
        ds=r['ds'];mem=ref['memory'];selection=(c['selection']+int(passed))&255
        final=passed and selection>=120
        v.check(mem[v.physical(ds,0x1F6D)]==(255 if passed else 0),'signed result decision differs')
        if ref['status'] in (1,2) and final:selection=0
        v.check(mem[v.physical(ds,0x1F6B)]==selection,'selection progression/reset differs')
        v.check((0x4C19 if c.get('time_zero') else 0x4C2E) in ref['text_starts'],'0:00 text choice differs')
        if final:v.check(0x51CB in ref['text_starts'],'final screen text absent')
    if c['entry']==0x48BD and not ref['status']:
        v.check(v.get16(ref['memory'],r['ds'],0x21)==(0x4C77,0x4C9D,0x4CB9)[min(c['input_mode'],2)],'prompt owner differs')

def compare(native,c):
    memory,r,device=setup(c)
    ref=Machine(c,bytearray(memory),dict(r),copy.deepcopy(device)).run();independent(c,r,ref)
    actual=native.run(c,memory,r,device);v.compare_states(c['name'],actual,ref)
    v.require(actual['child_entry']==ref['child_entry'],c['name']+': child entry differs')
    v.require(actual['polls']==ref['polls'],c['name']+': poll schedule differs')
    return ref

def hashes():
    paths=set(briefing.hashes())|{'c/level_result.c','c/level_result.h','tests/level_result.py'}
    for p in cbuild.source_files('level_result'):
        paths.add(p.relative_to(ROOT).as_posix())
        if p.with_suffix('.h').is_file():paths.add(p.with_suffix('.h').relative_to(ROOT).as_posix())
    paths.add('c/game_foreground_internal.h');paths.add('c/foreground_poll.h')
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}

def table_evidence():
    out=[]
    for index in range(9):
        p=0x4955+2*index;target=int.from_bytes(v.IMAGE[p:p+2],'little');at=0x9A90+target
        cursor=at;lines=[];valid=True
        # 4D4D reads column (zero ends), row, style; characters end at CR.
        # A zero style is part of a header, not a stream terminator.
        while cursor<at+512 and v.IMAGE[cursor]:
            column,row,style=v.IMAGE[cursor:cursor+3];cursor+=3
            end=v.IMAGE.index(13,cursor,at+512);text=v.IMAGE[cursor:end]
            valid=valid and 1<=column<=40 and row<25 and style in (0,1) and all(32<=b<=126 for b in text)
            lines.append(dict(column=column,row=row,style=style,text=text.decode('ascii')));cursor=end+1
        valid=valid and cursor<at+512 and v.IMAGE[cursor]==0 and bool(lines)
        stream=v.IMAGE[at:cursor+1]
        out.append(dict(index=index,table_offset=p,target=target,image_offset=at,
            end_offset=target+len(stream),valid_text_stream_start=valid,lines=lines))
    return out

def worker(directory,names=()):
    start=time.monotonic();before=hashes();builds=[];original_build=cbuild.run_bounded
    def logged(argv,**kw):
        row=dict(argv=list(map(str,argv)));builds.append(row)
        try:result=original_build(argv,**kw);row['exit_code']=result.returncode;return result
        except BaseException as error:row['error']=str(error);raise
    cbuild.run_bounded=logged
    native=Native(directory);sites=set();edges=set();rows=[];saved={}
    selected=[c for c in cases() if not names or c['name'] in names]
    v.check(not names or set(names)=={c['name'] for c in selected},'unknown focused case')
    for c in selected:
        ref=compare(native,c);sites|=ref['sites'];edges|=ref['edges'];saved[c['name']]=c
        rows.append(dict(name=c['name'],status=ref['status'],steps=ref['steps'],events=len(ref['events']),
            own_sites=len(ref['sites']&set(OWN)),polls=ref['polls'],text_starts=ref['text_starts'],table_indices=ref['table_indices']))
        print('PASS '+c['name'],flush=True);del ref;gc.collect()
    mutants=[]
    for mutation,name in {1:'signed-negative',2:'last-mode0',3:'release-delayed',4:'key40',5:'time-up',6:'pass-mode0',7:'cs-table',8:'changed-return'}.items():
        if name not in saved:continue
        mutant=Native(directory,mutation)
        try:compare(mutant,saved[name])
        except v.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,mismatch=str(error),completed=True))
        else:raise v.OracleFailure(f'result mutant{mutation} survived')
        del mutant;gc.collect()
    v.check(before==hashes(),'result inputs changed during campaign')
    write_json(REPORT.with_name('level-result-focused.json') if names else REPORT,dict(code_ranges=OWN_RANGES,own_bytes=sum(i.size for i in OWN.values()),
        executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(OWN)&sites),
        branch_edges=sorted(edges),own_branch_edges=sorted(edges&EDGES),unexecuted_own_sites=sorted(set(OWN)-sites),
        unexecuted_own_edges=sorted(EDGES-edges),cases=rows,mutations=mutants,builds=builds,
        table_evidence=table_evidence(),runtime_seconds=time.monotonic()-start,input_hashes=before,
        limits=dict(seconds=SECONDS,memory_mib=MEMORY_MIB,steps=MAX_STEPS,events=MAX_EVENTS)))
    print(f'PASS level result: {len(rows)} cases, {len(set(OWN)&sites)}/{len(OWN)} sites, {len(EDGES&edges)}/{len(EDGES)} outcomes, {len(mutants)} mutants',flush=True)

def main():
    if len(sys.argv)>=3 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3:]);return
    v.check(not sys.argv[1:] or sys.argv[1]=='--cases','use --cases NAME [NAME ...]')
    with temporary_build_directory(prefix='level-result-',parent=BUILD) as directory:
        run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',str(directory),*sys.argv[2:]],cwd=ROOT,
            timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)
if __name__=='__main__':main()

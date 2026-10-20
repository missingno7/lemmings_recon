"""Connected briefing and small wrappers, using the shared bounded verifier."""
import copy
import ctypes as ct
import gc
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as v
import main_menu as menus
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build,source_files
from common import BUILD,sha,write_json

OWN_RANGES=((0x4566,0x469A),(0x469B,0x46A2),(0x4B5C,0x4B68),
            (0x4C17,0x4C20),(0x5447,0x5469),(0x546A,0x5473))
# Pinned identified domains, independent from ledger acceptance annotations.
INS_RANGES=(
    (0x1550,0x1562),(0x1A7B,0x1A7C),(0x368E,0x36B6),(0x378A,0x37C2),
    (0x394F,0x395E),(0x395F,0x39CE),(0x4401,0x4407),(0x4566,0x469A),
    (0x469B,0x46EB),(0x4B5C,0x4BC2),(0x4C07,0x4C47),(0x4D4D,0x4DF7),
    (0x4DF8,0x4E37),(0x5019,0x501C),(0x5329,0x536C),(0x53CA,0x53E6),
    (0x53E7,0x53FB),(0x53FE,0x5417),(0x5418,0x5424),(0x5425,0x5469),
    (0x546A,0x5473),(0x548C,0x5507),(0x5569,0x55B6),(0x563E,0x5726),
    (0x7C67,0x7CBC),(0x7E76,0x80FD),(0x8808,0x88AA),(0x88AB,0x8ADD),
    (0x8ADE,0x8CF4),(0x8CF5,0x8F8D),(0x8F8E,0x9339),(0x933A,0x94C7),
    (0x94C8,0x9507),(0x9508,0x9659),(0x965A,0x98F4),(0x98F5,0x9932),
    (0x9933,0x9996),(0x9997,0x9A8F),
)
INS={i.address:i for a,b in INS_RANGES for i in v.MD.disasm(v.IMAGE[a:b],a)}
OWN={i.address:i for a,b in OWN_RANGES for i in v.MD.disasm(v.IMAGE[a:b],a)}
EDGES=v.direct_jump_edges(OWN)
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=900,384,4_000_000,2_000_000
REPORT=BUILD/'level-briefing-differential.json'
class Result(ct.Structure):
    _fields_=[('registers',v.Regs),('status',ct.c_uint16),('child_status',ct.c_uint16)]
class Services(ct.Structure):
    _fields_=[('redraw',ct.c_void_p),('ports',ct.POINTER(v.Ports)),('bus',ct.POINTER(v.Bus))]

def cases():
    out=[dict(name=f'percent-{n}',kind='percent',value=n) for n in range(256)]
    for name,kw in (('df',dict(flags=0x6D7)),('cursor-wrap',dict(si=0xFFFF)),
                    ('physical-wrap',dict(ds=0xFFFF,si=0xF)),('stack-wrap',dict(sp=0)),
                    ('stack-word-ffff',dict(sp=0xFFFF)),('changed-child',dict(patch='percent-ret',expected=2)),
                    ('outer-ret',dict(patch='outer-ret'))):
        out.append(dict(name='percent-'+name,kind='percent',value=255,**kw))
    for mode in (0,2,4,0x104,0xFFFF):
        out.append(dict(name=f'base-{mode:04x}',kind='base',mode=mode))
    for name,kw in (('mode-live',dict(mode=0,patch='mode-live')),
                    ('source-live',dict(mode=4,patch='base-source')),
                    ('changed-child',dict(mode=4,patch='base-ret',expected=2)),
                    ('df',dict(mode=4,flags=0x6D7)),
                    ('missing-input',dict(mode=2,missing_in=True,expected=1,child_status=1)),
                    ('missing-output',dict(mode=4,missing_out=True,expected=1,child_status=2))):
        out.append(dict(name='base-'+name,kind='base',**kw))
    for name,kw in (('normal',{}),('df',dict(flags=0x6D7)),('stack-wrap',dict(sp=0)),
                    ('missing-bus',dict(missing_clear=True,expected=1,child_status=2))):
        out.append(dict(name='clear-'+name,kind='clear',**kw))
    for load in v.LOADS:out.append(dict(name=f'briefing-{load:04x}',kind='briefing',load=load))
    for name,kw in (('palette-phases',dict(changing_palettes=True)),
                    ('mode4',dict(mode=4,input_mode=1)),('mode0104',dict(mode=0x104,input_mode=2)),
                    ('cancel',dict(leave=0x20)),('button',dict(button=True)),('idle',dict(idle=True)),
                    ('terrain',dict(terrain=True)),('singular',dict(minutes=1)),
                    ('unchecked-group',dict(group=255,selection=255)),
                    ('division-zero',dict(total=0,expected=3)),('division-overflow',dict(total=1,required=255,expected=3)),
                    ('df-prefix',dict(flags=0x6D7,missing_clear=True,expected=1,child_status=2)),
                    ('changed-pair',dict(patch='pair-ret',expected=2)),
                    ('special-stop',dict(special=1,expected=1,child_status=1))):
        out.append(dict(name='briefing-'+name,kind='briefing',**kw))
    return [dict(load=v.LOADS[0],seed=0x4566+i,flags=0xAD7,group=1,selection=37,mode=2,
                 total=80,required=40,minutes=5,leave=0x40,input_mode=0)|c for i,c in enumerate(out)]

def setup(c):
    mc=dict(c,kind='menu',entry=0,option=0,toggle=0,driver=255,keys=(0x80,),pinned=c['kind']=='briefing')
    memory,r,device=menus.setup(mc);ds=c.get('ds',r['ds']);r.update(ds=ds,ss=c.get('ss',r['ss']),sp=c.get('sp',r['sp']))
    r['ip']={'briefing':0x4566,'percent':0x4B5C,'clear':0x4C17,'base':0x5447}[c['kind']]
    r.update(ax=0xB000|c.get('value',71),si=c.get('si',0x6000))
    for off,val in ((0x1F7C,c['mode']),(0x1F76,0),(0x1F78,0),(0x1F7A,0),(0x1FDA,0x3D4),(0x1FF4,0x4FFF)):
        v.put16(memory,ds,off,val,device)
    for off,val in ((0x200C,255),(0x1F6E,c['group']),(0x1F6B,c['selection']),
                    (0xFCE,c['total']),(0xFD0,c['required']),(0xFCC,99),(0xFD2,c['minutes']),
                    (0xFE8,c.get('special',0)),(0x25A6,c['input_mode'])):
        v.sync_memory_byte(memory,device,ds,off,val)
    for off in range(0xFEB,0x10EB):v.sync_memory_byte(memory,device,ds,off,0)
    for i,b in enumerate(b'\xff\xff\x57\xad'):v.sync_memory_byte(memory,device,ds,0x10EB+i,b)
    for i,b in enumerate(b'CONSTRUCTED LEVEL TITLE         '):v.sync_memory_byte(memory,device,ds,0x17AB+i,b)
    for start in (0x2638,0x2608,0x4920,0x4930,0x1F13,0x1F3B,0x25E8,0x25F0,0x1F0B,0x1F23,0x25A8,0x25B8,0x2668):
        for i in range(48):v.sync_memory_byte(memory,device,ds,start+i,0)
    if c.get('changing_palettes'):
        for off in (0x2638,0x2668,0x4920,0x1F13):
            for i in range(16):v.sync_memory_byte(memory,device,ds,off+i,1)
    if c['group']==255:
        for i,b in enumerate(b'RAWXYZ'):v.sync_memory_byte(memory,device,ds,0x4C01+255*6+i,b)
    if c['kind']=='base':
        for i in range(48):v.sync_memory_byte(memory,device,ds,0x2608+i,(i*7+3)&63)
    if c.get('terrain'):
        # One independently constructed normal type2,24x3 terrain record.
        at=0x1D0B+16
        for i,b in enumerate(bytes((24,3,0,0,0,0x20,0,0x40))):v.sync_memory_byte(memory,device,ds,at+i,b)
        data=(131).to_bytes(2,'big')+(((5+4)<<7)|2).to_bytes(2,'big')+b'\xff\xff\x57\xad'
        for i,b in enumerate(data):v.sync_memory_byte(memory,device,ds,0x10EB+i,b)
        memory[0x50000:0x60000]=bytes((0xFF,))*65536
    v.put16(memory,r['ss'],r['sp'],0xD00D,device)
    device.trace=menus.PackedVgaTrace(MAX_EVENTS)
    return memory,r,device

class Access(v.BusAccess):
    def __init__(self,c,memory,r,device):
        super().__init__(c,memory,r,device,max_events=MAX_EVENTS,packed_events=True)
        self.port_index=0;self.button_reads=0;self.key_reads=0;self.mode_reads=0
    def access(self,kind,address,flags,mask=v.FLAGS,value=None):
        patch=self.c.get('patch');ds=self.r['ds']
        if kind=='read' and address==v.physical(ds,0x14) and self.c['kind']=='briefing':
            self.button_reads+=1;v.check(self.button_reads<=12,'finite briefing button schedule exhausted')
            b=1 if self.button_reads==1 or self.c.get('button') and self.button_reads>2 else 0
            self.patch(ds,0x14,b,'buttons-'+str(self.button_reads))
        if kind=='read' and address==v.physical(ds,0x1FC7) and self.c['kind']=='briefing':
            self.key_reads+=1;v.check(self.key_reads<=4,'finite briefing key schedule exhausted')
            key=0 if self.c.get('idle') and self.key_reads==1 else self.c['leave']
            self.patch(ds,0x1FC7,key,'key-'+str(self.key_reads))
        if kind=='read' and address==v.physical(ds,0x1F7C):
            self.mode_reads+=1
            if patch=='mode-live' and self.mode_reads==2:self.patch(ds,0x1F7C,2,patch)
        got=super().access(kind,address,flags,mask,value)
        if patch not in self.providers:
            if kind=='write' and patch in ('percent-ret','pair-ret') and address==v.physical(ds,0x6000 if patch=='percent-ret' else 0x4B13):
                self.patch(self.r['ss'],(self.r['sp']-2)&65535,0xD234,patch)
            if kind=='write' and patch=='outer-ret' and address==v.physical(ds,0x6000):
                self.patch(self.r['ss'],self.r['sp'],0xBEAD,patch)
            if kind=='read' and patch in ('base-ret','base-source') and address==v.physical(ds,0x261F):
                if patch=='base-ret':self.patch(self.r['ss'],(self.r['sp']-2)&65535,0xD234,patch)
                else:self.patch(ds,0x2608,0x31,patch,word=False)
        return got
    def inp(self,port,flags,mask=v.FLAGS):
        if port==0x3C5:value=0x93
        else:
            v.check(port==0x3DA,'undeclared briefing status input')
            value=(0,9,9,0)[self.port_index%4];self.port_index+=1
            v.check(self.port_index<24000,'finite briefing raster schedule exhausted')
        self.cursor+=1;self.emit('in',port,value,flags,mask);return value
    def out(self,port,value,flags,mask=v.FLAGS):
        v.check(port in (0x3C0,0x3C4,0x3C5,0x3C8,0x3C9),'undeclared briefing byte output')
        self.emit('out8',port,value,flags,mask)
    def out_word(self,port,value,flags,mask=v.FLAGS):
        self.emit('out',port,value,flags,mask)
        if port in (0x3C4,0x3CE):self.device.out(port,value,flags)
        else:v.check(port==0x3D4,'undeclared briefing word output')

class Machine(v.OriginalMachine):
    def __init__(self,c,memory,r,device,core):
        self.child_status=0;frames=[];failed=[]
        def before(m,i):
            if i.address==0x4401:m.stop(0);return True
            if i.address==0x459C:
                q=m.state();divisor=q['cx']&255
                if not divisor or q['ax']//divisor>255:m.stop(3);return True
            if c.get('missing_clear') and i.address==0x4DF8:m.child_status=2;m.stop(1);return True
            if i.address==0x1A7B:m.child_status=1;m.stop(1);return True
            if i.mnemonic in ('in','out') and c.get('missing_in' if i.mnemonic=='in' else 'missing_out'):
                m.child_status=1 if i.mnemonic=='in' else 2;m.stop(1);return True
            if i.mnemonic in ('call','lcall'):
                frames.append(dict(owner=i.address,resume=i.address+i.size,far=i.mnemonic=='lcall'))
            return False
        def expected(m,off):
            v.check(bool(frames),'undeclared briefing child return');frame=frames.pop();failed[:]=[frame]
            return {(c['load'],frame['resume'])} if frame['far'] else {frame['resume']}
        def changed(m,off):
            if failed[-1]['owner'] in OWN:return 2
            raise v.OracleFailure('unscoped nested briefing return change')
        def outer(m,off):
            return not frames and off in ({0x4B67} if c['kind']=='percent' else {0x5455,0x5446,0x54C3} if c['kind']=='base' else {0x4E36})
        super().__init__(c,memory,r,device,core,instructions=INS,access=Access(c,memory,r,device),
            outer_returns=outer,child_returns={p:expected for p,i in INS.items() if i.mnemonic=='ret'},
            far_returns={p:expected for p,i in INS.items() if i.mnemonic=='retf'},
            changed_return_status=changed,before=before,max_steps=MAX_STEPS)
    def run(self):
        out=super().run();out['child_status']=self.child_status;return out

class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'level-briefing-{mutation}.dll',mutation,'level_briefing')))
        self.functions={}
        for kind in ('helper','full'):
            for core in (True,False):
                name='lmn_briefing_helper_' if kind=='helper' else 'lmn_show_level_briefing_'
                fn=getattr(self.lib,name+('core' if core else 'adapter'));fn.restype=Result
                fn.argtypes=[v.MEM,ct.POINTER(v.Regs)]+([ct.c_int,ct.POINTER(v.Ports),ct.POINTER(v.Bus)] if kind=='helper' else [ct.c_uint16,ct.POINTER(Services)])
                self.functions[kind,core]=fn
    def run(self,c,memory,r,device,core):
        memory,device=bytearray(memory),copy.deepcopy(device)
        access=Access(c,memory,r,device);cb=v.NativeCallbacks(access,missing_in=c.get('missing_in'),missing_out=c.get('missing_out'))
        if c.get('missing_clear'):cb.bus.out_word=v.OUT()
        mem=(ct.c_uint8*v.SIZE).from_buffer(memory);regs=v.Regs(**r)
        if c['kind']=='briefing':
            services=Services(None,ct.pointer(cb.ports),ct.pointer(cb.bus))
            out=self.functions['full',core](mem,ct.byref(regs),(c['load']+0x9A9)&65535,ct.byref(services))
        else:out=self.functions['helper',core](mem,ct.byref(regs),{'percent':0,'clear':1,'base':2}[c['kind']],ct.byref(cb.ports),ct.byref(cb.bus))
        return dict(regs={n:getattr(out.registers,n) for n in v.REG_NAMES},status=out.status,child_status=out.child_status,
            memory=memory,device=device,events=access.events,providers=access.providers,cursor=access.cursor)

def compare(native,c,core):
    memory,r,device=setup(c);ref=Machine(c,bytearray(memory),dict(r),copy.deepcopy(device),core).run()
    v.check((ref['status'],ref['child_status'])==(c.get('expected',0),c.get('child_status',0)),c['name']+': unexpected stop')
    if c.get('patch'):v.check(c['patch'] in ref['providers'],c['name']+': provider unused')
    if c['kind']=='percent' and not ref['status'] and not c.get('patch'):
        digits=str(c['value']).encode()+b'%'
        v.check(bytes(ref['memory'][v.physical(r['ds'],(r['si']+i)&65535)] for i in range(len(digits)))==digits,'percentage independent digits differ')
    if c['kind']=='briefing' and not ref['status']:
        ds=r['ds'];v.check(ref['memory'][v.physical(ds,0x41)]==c['required']*100//c['total'],'briefing percentage differs')
        def field(offset,count):return bytes(ref['memory'][v.physical(ds,(offset+i)&65535)] for i in range(count))
        value=(c['selection']+1-30*c['group'])&255
        expected=(bytes((48+value//10,48+value%10)) if value>=10 else bytes((48+value,32)))
        v.check(field(0x4B13,2)==expected,'wrapped selection/group field differs')
        v.check(field(0x4B50,3)==str(c['total']).encode().ljust(3,b' '),'population field differs')
        v.check(field(0x4B19,32)==bytes(memory[v.physical(ds,0x17AB+i)] for i in range(32)),'live title copy differs')
        v.check(field(0x4B98,6)==bytes(memory[v.physical(ds,0x4C01+6*c['group']+i)] for i in range(6)),'unchecked group row differs')
        v.check(field(0x4B8B,1)==(b' ' if ((c['minutes']+48)&255)==49 else b's'),'time plural byte differs')
        v.check(ref['regs']['ip']==(0x4401 if c['leave']==0x20 and not c.get('button') else 0x4E36 if core else 0xD00D),'briefing exit differs')
    if native:v.compare_states(c['name'],native.run(c,memory,r,device,core),ref)
    return ref

def hashes():
    paths={'tests/level_briefing.py','tests/verification.py','tests/minimap_vga.py',
        'tools/cbuild.py','tools/difftest.py','tools/bounded_process.py','tools/common.py','tools/unpack.py',
        'metadata/oracle.json','metadata/toolchain-lock.json','assets/vgalemmi.exe','assets/main.dat',
        'src/input_menu_and_retry.asm','src/decimal_fields.asm','src/game_code_late_after_decimal.asm','src/palette_frontends.asm','src/image_tail.asm'}
    # Only fixture construction/font banks/storage are borrowed from menus;
    # identified instruction ranges above do not read ledger annotation fields.
    for module in tuple(sys.modules.values()):
        name=getattr(module,'__file__',None)
        if name:
            path=Path(name).resolve()
            if path.is_relative_to(ROOT) and path.suffix=='.py' and path.parts[-2] in ('tests','tools'):paths.add(path.relative_to(ROOT).as_posix())
    for path in source_files('level_briefing'):
        paths.add(path.relative_to(ROOT).as_posix());paths.add(path.with_suffix('.h').relative_to(ROOT).as_posix())
    paths|={'c/lemmings_sym.h','c/regs.h'}
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}

MUTANTS=((1,'percent-changed-child'),(2,'clear-normal'),(3,'base-0004'),(4,'briefing-df-prefix'),(5,'briefing-cancel'))
def worker(directory,snapshot,selected):
    before=hashes();v.check(before==json.loads(Path(snapshot).read_text()),'briefing inputs changed')
    native=Native(directory);sites=set();edges=set();rows=[]
    for c in cases():
        if selected and c['name'] not in selected:continue
        for core in (True,False):
            ref=compare(native,c,core);sites.update(ref['sites']);edges.update(ref['edges'])
            rows.append(dict(case=c['name'],core=core,steps=ref['steps'],events=len(ref['events']),status=ref['status']))
            del ref;gc.collect()
        print('CHECKED '+c['name'],flush=True)
    v.check(bool(rows),'empty briefing selection')
    if selected:return
    v.check(set(OWN)<=sites,'briefing own sites missing: '+str(sorted(set(OWN)-sites)))
    v.check(EDGES<=edges,'briefing own outcomes missing: '+str(sorted(EDGES-edges)))
    mutants=[];lookup={c['name']:c for c in cases()}
    for mutation,name in MUTANTS:
        try:compare(Native(directory,mutation),lookup[name],True)
        except v.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
        else:raise v.OracleFailure(f'briefing mutant{mutation} survived')
        gc.collect()
    v.check(before==hashes(),'briefing inputs changed')
    write_json(REPORT,dict(image='main',image_sha256=sha(v.IMAGE),case_count=len(cases()),comparison_count=len(rows),
        own_known_bytes=sum(i.size for i in OWN.values()),known_connected_bytes=sum(i.size for i in INS.values()),native_code_ranges=[list(r) for r in OWN_RANGES],
        executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(OWN)&sites),branch_edges=sorted(edges),own_branch_edges=sorted(EDGES),
        instruction_steps=sum(r['steps'] for r in rows),ordered_bus_events=sum(r['events'] for r in rows),
        mutation_count=len(mutants),mutations=mutants,input_hashes=before,rows=rows,
        limits=dict(worker_seconds=SECONDS,process_tree_commit_mib=MEMORY_MIB,instructions_each=MAX_STEPS,events_each=MAX_EVENTS),
        domain='Connected4566 briefing plus4B5C/4C17/5447 wrappers. Original instructions/shared native children on canonical RAM. Constructed ordinary redraw and one terrain record,pinned UI/fonts,finite raster/input,explicit DIV fault and special service stops. Remaining454C/resource/game/platform and inherited child/provider domains remain open.'))
    print(f'PASS level briefing: {len(rows)} comparisons,{len(set(OWN)&sites)} own sites,{len(EDGES)} outcomes,{len(mutants)} mutants',flush=True)

def main():
    if len(sys.argv)>=4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3],sys.argv[4:]);return
    selected=sys.argv[2:] if len(sys.argv)>1 and sys.argv[1]=='--focus' else []
    if sys.argv[1:] and not selected:raise SystemExit('usage: level_briefing.py [--focus CASE ...]')
    if not selected:REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='level-briefing-',parent=BUILD) as directory:
        snapshot=Path(directory)/'inputs.json';write_json(snapshot,hashes())
        run_bounded([sys.executable,__file__,'--worker',str(directory),str(snapshot),*selected],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)
if __name__=='__main__':main()

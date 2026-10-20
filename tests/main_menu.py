"""Connected main menu over shared original execution and native callbacks."""
import copy
import ctypes as ct
import gc
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as base
import keyboard_input as keyboard
import menu_scroll as scroll
import menu_animation as animation
import menu_cache as cache
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build,source_files
from common import BUILD,sha,write_json
check=base.check
physical,put16,get16=base.physical,base.put16,base.get16
ENTRIES=(0x4401,0x4453,0x445B,0x4478)
CODE_ENTRIES=(0x5042,0x51A2)
EDITOR_RANGES=((0x488C,0x48B0),(0x4967,0x4A01),(0x4C7E,0x4D1A),(0x503B,0x5042))
CODE_RANGES=((0x5042,0x52D4),)
PUBLISH_ENTRIES=(0x53F6,0x53FC,0x53FE,0x5401)
MENU_RANGES=((0x4401,0x44A3),(0x44A4,0x44AA),(0x44AB,0x44E9),(0x44EC,0x454C))
PUBLISH_RANGES=((0x53F6,0x53FB),(0x53FC,0x5417),(0x5418,0x5424))
RANGES=EDITOR_RANGES+CODE_RANGES+MENU_RANGES+PUBLISH_RANGES+((0x43F2,0x4401),(0x4AC5,0x4B1C))
OWN={i.address:i for a,b in RANGES for i in base.MD.disasm(base.IMAGE[a:b],a)}
EXITS=(0x4D0,0x4967,0x4A01,0x454C)
BOUNDARY={p:next(base.MD.disasm(base.IMAGE[p:p+16],p)) for p in EXITS}
PAGES={i.address:i for a,b in ((0x4DC2,0x4DF7),(0x4DF8,0x4E37)) for i in base.MD.disasm(base.IMAGE[a:b],a)}
INS=keyboard.DOMAINS['reader']|keyboard.DISPLAY|keyboard.SWAP|PAGES|keyboard.text.INS|keyboard.background.INS|keyboard.palette.INS|scroll.INS|animation.INS|cache.INS|OWN|BOUNDARY
EXTRA={i.address:i for a,b in ((0x4BE7,0x4C17),(0x8808,0x8822),(0x5028,0x503B)) for i in base.MD.disasm(base.IMAGE[a:b],a)}
INS|=EXTRA|{i.address:i for i in base.MD.disasm(base.IMAGE[0x4B68:0x4BBE],0x4B68)}
EDGES=base.direct_jump_edges(OWN,external_transfers=(0x4D18,))|{(0x4D18,0x503B)}
REPORT=BUILD/'main-menu-differential.json'
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=1200,384,4_000_000,2_000_000
DOS_BINDING=(0x7100,0x210)
FIXTURES=set()
for module in tuple(sys.modules.values()):
    name=getattr(module,'__file__',None)
    if not name:continue
    path=Path(name).resolve()
    if path.suffix=='.py' and path.is_relative_to(ROOT) and path.parts[-2] in ('tests','tools'):FIXTURES.add(path.relative_to(ROOT).as_posix())
class Result(ct.Structure):
    _fields_=[('registers',base.Regs),('status',ct.c_uint16),('child_status',ct.c_uint16)]
class PublishResult(ct.Structure):
    _fields_=[('registers',base.Regs),('status',ct.c_uint16)]
VIDEO=ct.CFUNCTYPE(None,ct.c_void_p,base.MEM,ct.POINTER(animation.State),ct.POINTER(animation.State))
class VideoServices(ct.Structure):
    _fields_=[('context',ct.c_void_p),('set_mode',VIDEO),('set_page',VIDEO)]

class PackedVgaTrace:
    """Fixture storage adapter; the shared packed sequence retains all4 fields."""
    def __init__(self,limit):self.events=base.PackedEvents();self.limit=limit
    def append(self,row):
        check(len(self)<self.limit,'VGA observation budget exhausted');self.events.append((*row,0))
    def __len__(self):return len(self.events)
    def __iter__(self):return (e[:4] for e in self.events)
    def __getitem__(self,index):
        if isinstance(index,slice):return [e[:4] for e in self.events[index]]
        return self.events[index][:4]
    def clear(self):self.events=base.PackedEvents()

# Independent bit layout; this fixture formula does not model instruction flags,
# register intermediates, memory access order or native execution.
TEMPLATE=b'AJHLDHBBCJ'
def expected_code(selection,payload,completion,template=TEMPLATE):
    v=[template[0]|((selection&1)<<3)|((payload&1)<<1)|((completion&1)<<2),
       template[1]|((selection&2)<<1)|((completion&2)>>1),
       template[2]|(selection&4)|((payload&2)>>1)|((completion&4)>>1),
       template[3]|((selection&8)>>3)|((completion&8)>>2),
       template[4]|((selection&16)>>3)|((payload&4)>>2)|((completion&16)>>1),
       template[5]|((selection&32)>>5)|((payload&8)>>2)|((completion&32)>>3),
       template[6]|((selection&192)>>4)|((completion&64)>>6),
       (template[7]+(selection&15))&255,(template[8]+(selection>>4))&255]
    v.append((template[9]+(sum(v)&15))&255)
    count=(8-(selection&7))%7
    if count:v[:7]=v[7-count:7]+v[:7-count]
    return bytes(v)

def code_cases():
    rows=[]
    for selection in range(256):
        values=dict(selection=selection,payload=(selection*7)&255,completion=(selection*29)&255)
        for kind in ('encode','decode'):
            rows.append(dict(name=f'code-{kind}-{selection:03}',kind=kind,entry=0,**values))
    for load in base.LOADS:
        for kind in ('encode','decode'):
            rows.append(dict(name=f'code-{kind}-load-{load:04x}',kind=kind,entry=0,load=load,selection=119,payload=15,completion=100))
    for name,kw in (
        ('core',dict(core=True)),('df',dict(flags=0x6D7)),('sp-wrap',dict(sp=0)),('sp-ffff',dict(sp=65535)),
        ('distinct-ds',dict(code_ds=0x3A21)),('physical-wrap',dict(code_ds=0xFFFF)),
        ('template-live',dict(template=bytes((0xFF,0x35,0x9A,0,0x11,0x27,0xC1,0xFE,0xFF,0xFA)))),
        ('stack-input',dict(stack_alias='input')),('stack-template',dict(stack_alias='template')),
        ('saved-si',dict(patch='code-saved-si'))):
        for kind in ('encode','decode'):
            if kind=='encode' and name=='saved-si':continue
            rows.append(dict(name=f'code-{kind}-'+name,kind=kind,entry=0,selection=127,payload=0xFA,completion=0xE3,**kw))
    # Every prefix comparison must take both outcomes. The latch is intentionally
    # independent of final code acceptance and never cleared for other inputs.
    special=b'BILLANDTED'
    for i in range(6):
        value=bytearray(special)
        if i<5:value[2*i]^=1
        rows.append(dict(name=f'code-special-{i}',kind='decode',entry=0,input=bytes(value)))
    rows += [dict(name='code-checksum-fail',kind='decode',entry=0,corrupt='checksum'),
             dict(name='code-selection-fail',kind='decode',entry=0,corrupt='selection',initial_selection=0xA5)]
    return rows

def editor_cases():
    rows=[dict(name=f'format-{n:03}',kind='format',entry=0,selection=n) for n in range(256)]
    rows += [dict(name='format-saved-cx',kind='format',entry=0,selection=59,patch='format-saved-cx'),dict(name='format-core',kind='format',entry=0,selection=29,core=True),
             dict(name='format-stack-wrap',kind='format',entry=0,selection=255,sp=1),
             dict(name='format-live-selection',kind='format',entry=0,selection=29,patch='format-live'),
             dict(name='format-stack-alias',kind='format',entry=0,selection=255,format_alias=True)]
    for name,kw in (
        ('empty',{}),('core',dict(core=True)),('bounds',dict(editor_keys=(0x40,0x41,0x5A,0x5B,0x80,0xFE,13))),
        ('last-slot',dict(editor_keys=tuple(b'ABCDEFGHIJK')+(13,))),
        ('backspace',dict(editor_keys=(0x7F,65,66,0x7F,0x7F,13))),
        ('blink',dict(editor_keys=(None,)*40+(13,))),('initial',dict(initial_input=b'ABCDEFGHIJ')),
        ('stack-wrap',dict(sp=0)),('changed-wait',dict(patch='editor-wait-return',expected=2)),
        ('unknown-call',dict(patch='editor-call-bp',expected=6)),('unknown-tail',dict(patch='editor-tail-bp',expected=6)),
        ('end-pointer',dict(patch='editor-end-pointer',editor_keys=(65,13))),
        ('missing-input',dict(missing_in=True,expected=1,child_status=1)),('bx-bound',dict(patch='editor-bx-bound',editor_keys=(65,90,13))),('signed-bound',dict(patch='editor-signed-bound',editor_keys=(65,13)))):
        rows.append(dict(name='editor-'+name,kind='editor',entry=0,**kw))
    for load in base.LOADS:
        rows.append(dict(name=f'editor-load-{load:04x}',kind='editor',entry=0,load=load,editor_keys=(65,90,13)))
        rows.append(dict(name=f'code-screen-valid-{load:04x}',kind='code_screen',entry=0,load=load,selection=59,payload=3,completion=97,pinned=True))
    for name,kw in (('empty',dict(editor_keys=(13,),invalid=True)),('special',dict(editor_keys=tuple(b'BILLANDTED')+(13,),invalid=True)),
                    ('button',dict(leave=1)),('key20',dict(leave=0x20)),('key40',dict(leave=0x40)),
                    ('unknown-call',dict(patch='editor-call-bp',expected=6)),('changed-wait',dict(patch='editor-wait-return',expected=2)),
                    ('selection-wrap',dict(selection=255,rating_row=b'WRAP!!')),('df',dict(flags=0x6D7,blank_text=True))):
        rows.append(dict(name='code-screen-'+name,kind='code_screen',entry=0,payload=15,completion=100,**(dict(selection=119)|kw)))
    rows += [dict(name='code-text',kind='code_text',entry=0),dict(name='code-text-core',kind='code_text',entry=0,core=True)]
    return rows

def cases():
    rows=[dict(name='frame-button',entry=2,keys=(None,)),dict(name='release-waits',entry=1,keys=(None,),release_samples=(1,3,8))]
    for key in (0x80,0x81,0x83,0x1B,0,0x42,0x8A,0x60,0x8B,0x2D,0x82):
        rows.append(dict(name=f'key-{key:02x}',keys=(key,0x80)))
    for name,kw in (
        ('blocked',dict(sound_cache=2)),('driver-ff',dict(driver=0xFF,option=2)),
        ('driver-fe',dict(driver=0xFE,option=1)),('driver-zero',dict(driver=0,option=1)),
        ('unexpected-index',dict(option=7)),('index-wrap',dict(option=255)),
        ('toggle-byte',dict(toggle=0x35)),('live-table',dict(patch='table'))):
        rows.append(dict(name='sound-'+name,keys=(0x82,0x80),**kw))
    for key in (0x8A,0x8B):
        for name,kw in (('blocked',dict(group_cache=4)),('zero',dict(group=0)),('three',dict(group=3)),('unexpected',dict(group=7)),('wrap',dict(group=255))):
            rows.append(dict(name=f'group-{key:02x}-'+name,keys=(key,0x80),**kw))
    for load in base.LOADS:
        rows.append(dict(name=f'refresh-{load:04x}',entry=0,keys=(None,),load=load,pinned=True))
        rows.append(dict(name=f'connected-input-{load:04x}',entry=2,load=load,pinned=True,group=1,
                         keys=(0x8A,0x8B,0x82,0x42,0x80)))
    rows += [dict(name='frame-if-df',entry=2,keys=(None,),flags=0x6D7),
             dict(name='frame-stack-wrap',entry=2,keys=(None,),sp=0),
             dict(name='keyboard-word-ffff',entry=3,keys=(0x80,),sp=1),
             dict(name='wait-return',entry=2,keys=(None,),patch='wait-return',expected=2),
             dict(name='scroll-far-return',entry=2,keys=(None,),patch='scroll-far',expected=1,child_status=2),
             dict(name='keyboard-return',entry=3,keys=(0x80,),patch='keyboard-return',expected=2),
             dict(name='missing-status-input',entry=2,keys=(None,),missing_in=True,expected=1,child_status=1),
             dict(name='refresh-display-return',entry=0,keys=(None,),patch='display-return',expected=2),
             dict(name='late-group',keys=(0x8A,0x80),patch='group'),
             dict(name='frame-both-caches',entry=2,keys=(0x80,),sound_cache=2,group_cache=4)]
    for entry in range(4):
        for mode in (2,4,0x104):
            for index in (0,2,7,255):rows.append(dict(name=f'publish-e{entry}-m{mode}-i{index}',kind='publish',entry=entry,mode=mode,index=index,count=0xA503))
    rows += [dict(name='publish-df',kind='publish',entry=2,mode=4,index=1,flags=0x6D7),
             dict(name='publish-core',kind='publish',entry=1,mode=4,index=0,core=True),
             dict(name='publish-zero-attribute',kind='publish',entry=3,mode=2,index=0,count=0x7F00),
             dict(name='publish-zero-mapped',kind='publish',entry=3,mode=4,index=0,count=0xFE00),
             dict(name='publish-no-input',kind='publish',entry=1,mode=2,missing_in=True,expected=1),
             dict(name='publish-no-output',kind='publish',entry=1,mode=4,missing_out=True,expected=2)]
    for name,kw in (
        ('skip',dict(media=0)),('media-fe',dict(media=0xFE,critical=0xFD)),
        ('success',{}),('open-retry',dict(fail_open=1)),('close-retry',dict(fail_close=1)),
        ('latch',dict(probe_wait='latch')),('waits',dict(probe_wait='delayed')),
        ('returned-ds',dict(close_ds=0x6100)),('returned-stack',dict(close_stack=(0x6200,0x8000))),
        ('iret-flags',dict(iret_flags=0x8000)),('unbound',dict(no_service=True,expected=3)),
        ('provider-stop',dict(provider_stop=0x27,expected=4,child_status=0x27)),
        ('changed-iret',dict(iret_ip=0xD234,expected=5)),('core',dict(core=True)),
        ('changed-outer',dict(patch='probe-parent',expected=0,outer_ip=0xD234))):
        rows.append(dict(name='probe-'+name,kind='probe',entry=0,media=0xFD,**kw) if 'media' not in kw else dict(name='probe-'+name,kind='probe',entry=0,**kw))
    for load in base.LOADS:rows.append(dict(name=f'startup-{load:04x}',kind='startup',entry=0,load=load,keys=(None,),pinned=True))
    rows += [dict(name='startup-resource',kind='startup',entry=0,keys=(None,),media=0xFD,pinned=True),
             dict(name='startup-no-mode',kind='startup',entry=0,missing_mode=True,expected=1,child_status=1),
             dict(name='startup-mode-ds',kind='startup',entry=0,mode_ds=0x3600,missing_out=True,expected=1,child_status=2)]
    return [dict(name='case',kind='menu',entry=3,load=0x1010,seed=0x4401+i,flags=0xD7,group=1,option=0,toggle=0,driver=0xFF,keys=(0x80,))|c for i,c in enumerate(rows+code_cases()+editor_cases())]

def setup(c):
    memory,device=base.initial_memory(c);ds=(c['load']+0x9A9)&65535
    r=base.default_regs(c['load'],c['seed'],ds=ds,ss=c.get('ss',0x6000),sp=c.get('sp',0x9000),flags=c['flags']);r['ip']=ENTRIES[c['entry']]
    for off,value in ((0x1FEE,0x4000),(0x1FF0,0x7000),(0x1FE4,0x5000),(0x1F76,0),(0x1F78,0x6D60),(0x1F7A,0),
                      (0x1FDA,0x3D4),(0x66F0,350),(0x66F2,640),(0x66F4,80),(0x26,0x2000),
                      (0x1D,0x49CE),(0x1F,0x49CE),(0x21,4),(0x23,100),(0x1F7C,2),(0x14,0)):
        put16(memory,ds,off,value,device)
    for off,value in ((0x2A,0),(0x1F6E,c['group']),(0x1F6F,c.get('group_cache',c['group'])),(0x1F70,c['toggle']),
                      (0x1F71,c['option']),(0x1F72,c.get('sound_cache',c['toggle'])),(0x2010,c['driver']),(0x25A7,3),(0x200C,0xFF),(0x1F73,0)):
        base.sync_memory_byte(memory,device,ds,off,value)
    for start,value in ((0x2638,0),(0x2608,1),(0x4920,2)):
        for i in range(64):base.sync_memory_byte(memory,device,ds,start+i,value)
    for i in range(83):base.sync_memory_byte(memory,device,ds,0xF78+i,0)
    for i,v in enumerate(keyboard.PINNED_CHARACTERS):base.sync_memory_byte(memory,device,ds,0x202E+i,v)
    if c['entry']==3:
        base.sync_memory_byte(memory,device,ds,0xF79,0x94);base.sync_memory_byte(memory,device,ds,0x202F,c['keys'][0])
    for i in range(10):
        for j,v in enumerate((0xFFFF if i==0 else 0x8000,0x8000,64+32*i,80,0x100)):
            put16(memory,ds,0x4960+11*i+2*j,v,device)
    if c.get('pinned'):
        for segment,data in zip((0x4000,0x4F21),animation.resource_banks()):
            for i,v in enumerate(data):base.sync_memory_byte(memory,device,segment,i,v)
    else:base.sync_memory_byte(memory,device,ds,0x4AD9,0)
    put16(memory,r['ss'],r['sp'],0xD00D,device)
    device.trace=PackedVgaTrace(c.get('reference_events',MAX_EVENTS))
    if c['kind'] in ('encode','decode'):
        ds=c.get('code_ds',ds);r['ds']=ds;r['ip']=CODE_ENTRIES[c['kind']=='decode']
        selection=c.get('selection',37);payload=c.get('payload',6);completion=c.get('completion',83);template=c.get('template',TEMPLATE)
        value=c.get('input',expected_code(selection,payload,completion,template));value=bytearray(value)
        if c.get('corrupt')=='checksum':value[9]^=1
        if c.get('corrupt')=='selection':value[(8-(selection&7))%7]^=8;value[9]=(template[9]+(sum(value[:9])&15))&255
        for start,data in ((0x4913,template),(0x4DF2,value),(0x4D68,b'0123456789\r')):
            for i,v in enumerate(data):base.sync_memory_byte(memory,device,ds,start+i,v)
        for off,v in ((0x491D,payload),(0x40,completion),(0x1F6B,c.get('initial_selection',selection)),(0x1F74,0x39)):
            base.sync_memory_byte(memory,device,ds,off,v)
        if c.get('stack_alias'):r['ss']=ds;r['sp']=0x4DF4 if c['stack_alias']=='input' else 0x4915
        put16(memory,r['ss'],r['sp'],0xD00D,device)
    if c['kind'] in ('format','editor','code_screen','code_text'):
        r['ip']={'format':0x488C,'editor':0x4C7E,'code_screen':0x4967,'code_text':0x503B}[c['kind']]
        base.sync_memory_byte(memory,device,ds,0x1F6B,c.get('selection',37))
        base.sync_memory_byte(memory,device,ds,0x491D,c.get('payload',6))
        put16(memory,ds,0x1FC7,0xFFFF,device)
        base.sync_memory_byte(memory,device,ds,0x1F74,0x39)
        if c.get('blank_text'):
            for off in (0x4DE1,0x4DEF,0x4DFE,0x4E27):base.sync_memory_byte(memory,device,ds,off,0)
        if c.get('rating_row'):
            for i,v in enumerate(c['rating_row']):base.sync_memory_byte(memory,device,ds,0x51FB+i,v)
        for i,v in enumerate(c.get('initial_input',b'.'*10)):base.sync_memory_byte(memory,device,ds,0x4DF2+i,v)
        if c.get('format_alias'):r['ss']=ds;r['sp']=0x1F6D;put16(memory,r['ss'],r['sp'],0xD00D,device)
        if c.get('patch')=='editor-end-pointer':base.sync_memory_byte(memory,device,ds,0x4DFD,13)
    if c['kind']=='publish':
        r.update(ip=PUBLISH_ENTRIES[c['entry']],ax=0xBE00|c.get('index',1),cx=c.get('count',0xAD05))
    elif c['kind']=='probe':r['ip']=0x4AC5
    elif c['kind']=='startup':r['ip']=0x43F2
    put16(memory,ds,0x1F7C,c.get('mode',2),device)
    base.sync_memory_byte(memory,device,ds,0x1FDE,c.get('media',0))
    base.sync_memory_byte(memory,device,ds,0x1FDF,c.get('critical',0x79))
    if not c.get('pinned'):base.sync_memory_byte(memory,device,ds,0x4F00,0)
    for frame in dict.fromkeys(v for v in (c.get('close_ds'),c.get('mode_ds')) if v is not None):
        for a,b in ((0x14,0x16),(0x1D,0x2B),(0xF78,0xFCB),(0x1F6B,0x2012),(0x202E,0x2081),
                    (0x2534,0x2540),(0x25A6,0x25A8),(0x2608,0x2680),(0x4920,0x49CE),(0x4F00,0x5000),(0x66F0,0x66F6)):
            for off in range(a,b):base.sync_memory_byte(memory,device,frame,off,memory[physical(ds,off)])
    put16(memory,0,0x84,DOS_BINDING[1],device);put16(memory,0,0x86,DOS_BINDING[0],device)
    return memory,r,device

class Access(base.BusAccess):
    def __init__(self,c,memory,r,device):
        super().__init__(c,memory,r,device,max_events=c.get('reference_events',MAX_EVENTS),packed_events=True)
        self.editor_cursor=0;self.validation_cursor=0;self.format_reads=0
        self.display_cursor=0;self.input_index=int(c['entry']==3);self.release_cursor=0
        self.probe_active=c['kind'] in ('probe','startup') and c.get('media',0)==0xFD
        self.wait_reads=0;self.open_count=0;self.close_count=0;self.handles=set();self.live_ds=r['ds']
    def access(self,kind,address,flags,mask=base.FLAGS,value=None):
        if self.c.get('patch')=='code-saved-si' and 'code-saved-si' not in self.providers and kind=='read' and address==physical(self.r['ss'],(self.r['sp']-2)&65535):
            self.patch(self.r['ss'],(self.r['sp']-2)&65535,0x4D68,'code-saved-si')
        if self.c.get('patch')=='format-saved-cx' and 'format-saved-cx' not in self.providers and kind=='read' and address==physical(self.r['ss'],(self.r['sp']-2)&65535):self.patch(self.r['ss'],(self.r['sp']-2)&65535,0x1234,'format-saved-cx')
        phase=self.c.get('patch')
        if phase=='format-live' and kind=='read' and address==physical(self.r['ds'],0x1F6B):
            self.format_reads+=1
            if self.format_reads==2:self.patch(self.r['ds'],0x1F6B,255,'format-second-read',word=False)
        if kind=='read' and address==physical(self.live_ds,0x14) and (self.probe_active or self.c['kind']=='probe'):
            self.wait_reads+=1;check(self.wait_reads<=16,'finite resource wait schedule exhausted')
            mode=self.c.get('probe_wait','button')
            value=0 if mode=='latch' and self.wait_reads==1 or mode=='delayed' and self.wait_reads<3 else 1
            self.patch(self.live_ds,0x14,value,'probe-button-'+str(self.wait_reads))
            if mode=='latch' and self.wait_reads==1:self.patch(self.live_ds,0x1FD0,0x77,'probe-latch',word=False)
        if kind=='read' and address==physical(self.r['ds'],0x14) and self.release_cursor<len(self.c.get('release_samples',())):
            v=self.c['release_samples'][self.release_cursor];self.release_cursor+=1
            self.patch(self.r['ds'],0x14,v,'release-'+str(self.release_cursor))
        got=super().access(kind,address,flags,mask,value)
        if kind=='write' and value==0 and address in {physical(ds,0x1FDF) for ds in (self.r['ds'],self.live_ds)}:
            self.probe_active=False
            if self.c['kind']=='startup':self.patch(self.live_ds,0x14,0,'probe-input-release')
        if phase=='probe-parent' and kind=='write' and address==physical(self.live_ds,0x1FDF) and phase not in self.providers:
            self.patch(self.r['ss'],self.r['sp'],0xD234,phase)
        if phase in self.providers:return got
        if phase=='keyboard-return' and kind=='read' and address==physical(self.r['ds'],0xF78):
            self.patch(self.r['ss'],(self.r['sp']-2)&65535,0xD234,phase)
        if phase=='group' and kind=='read' and address==physical(self.r['ds'],0xF79):self.patch(self.r['ds'],0x1F6E,7,phase,word=False)
        if phase=='table' and kind=='write' and address==physical(self.r['ds'],0x1F71):self.patch(self.c['load'],0x44E9+value,0x55,phase,word=False)
        return got
    def inp(self,port,flags,mask=base.FLAGS):
        check(port==0x3DA,'unexpected main-menu byte input')
        v=(0,8,8,0)[self.display_cursor%4];self.display_cursor+=1;self.cursor+=1
        check(self.display_cursor<=4096,'finite display input schedule exhausted')
        self.emit('in',port,v,flags,mask)
        root=get16(self.memory,self.r['ss'],(self.r['sp']-2)&65535)
        if self.c.get('patch')=='wait-return' and 'wait-return' not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']-2)&65535,0xD234,'wait-return')
        if self.display_cursor%4==0 and self.c['kind'] in ('editor','code_screen'):
            bias=2 if self.c['kind']=='code_screen' else 0
            editing=(self.c['kind']=='editor' or root==0x4999) and get16(self.memory,self.r['ss'],(self.r['sp']-24-bias)&65535)==0x4CA8
            if editing:
                keys=self.c.get('editor_keys',(13,) if self.c['kind']=='editor' else tuple(expected_code(self.c.get('selection',37),self.c.get('payload',6),self.c.get('completion',83)))+(13,))
                check(self.editor_cursor<len(keys),'finite editor input schedule exhausted')
                key=keys[self.editor_cursor];self.editor_cursor+=1
                self.patch(self.r['ds'],0xF79,0 if key is None else 0x94,'editor-state-'+str(self.editor_cursor),word=False)
                if key is not None:self.patch(self.r['ds'],0x202F,key,'editor-key-'+str(self.editor_cursor),word=False)
                phase=self.c.get('patch')
                if phase not in self.providers:
                    if phase=='editor-wait-return':self.patch(self.r['ss'],(self.r['sp']-24-bias)&65535,0xD234,phase)
                    if phase=='editor-call-bp':self.patch(self.r['ss'],(self.r['sp']-22-bias)&65535,0xD234,phase)
                    if phase=='editor-tail-bp':self.patch(self.r['ss'],(self.r['sp']-12-bias)&65535,0xD234,phase)
                    if phase=='editor-signed-bound':self.patch(self.r['ss'],(self.r['sp']-6-bias)&65535,0x5A80,phase)
                    if phase=='editor-bx-bound':self.patch(self.r['ss'],(self.r['sp']-6-bias)&65535,0x5A5A,phase)
                    if phase=='editor-end-pointer':self.patch(self.r['ss'],(self.r['sp']-4-bias)&65535,0x4DFC,phase)
            if root==0x49D2:
                self.validation_cursor+=1;leave=self.c.get('leave',0)
                self.patch(self.r['ds'],0x14,1 if leave==1 else 0,'validation-button-'+str(self.validation_cursor))
                self.patch(self.r['ds'],0x1FC7,leave if leave!=1 else 0,'validation-key-'+str(self.validation_cursor))
        if self.display_cursor%4==0 and root==0x445E:
            check(self.input_index<len(self.c['keys']),'finite menu key schedule exhausted')
            key=self.c['keys'][self.input_index];self.input_index+=1
            self.patch(self.r['ds'],0x14,1 if key is None else 0,'buttons-'+str(self.input_index))
            self.patch(self.r['ds'],0xF79,0 if key is None else 0x94,'key-state-'+str(self.input_index),word=False)
            if key is not None:self.patch(self.r['ds'],0x202F,key,'key-char-'+str(self.input_index),word=False)
        return v
    def out(self,port,value,flags,mask=base.FLAGS):
        check(port in (0x3C0,0x3C8,0x3C9),'unexpected main-menu byte output');self.emit('out8',port,value,flags,mask)
    def out_word(self,port,value,flags,mask=base.FLAGS):
        self.emit('out',port,value,flags,mask)
        if port in (0x3C4,0x3CE):self.device.out(port,value,flags)
        else:check(port==0x3D4,'unexpected main-menu word output')
        phase=self.c.get('patch')
        if phase in self.providers:return
        if phase=='display-return' and port==0x3D4:self.patch(self.r['ss'],(self.r['sp']-2)&65535,0xD234,phase)
        if phase=='scroll-far' and port in (0x3C4,0x3CE):self.patch(self.r['ss'],(self.r['sp']-6)&65535,0xD234,phase)

def dos_provider(access,r):
    """Finite DOS file service; transport and IRET belong to verification.py."""
    c=access.c;entry=dict(r);operation=r['ax']>>8
    check(len(access.service_events)<32,'finite DOS request budget exhausted')
    if operation==0x3D:
        check((r['ax']&255)==0 and r['dx']==0x2534,'unexpected resource open request')
        name=[]
        for i in range(64):
            v=access.access('read',physical(r['ds'],(r['dx']+i)&65535),r['flags']);name.append(v)
            if not v:break
        check(name==list(b'vgagr0.dat\0'),'resource filename differs')
        access.open_count+=1;failed=access.open_count<=c.get('fail_open',0)
        r['ax']=5 if failed else 0x1233+access.open_count
        if not failed:access.handles.add(r['ax'])
    else:
        check(operation==0x3E,'unexpected resource DOS function')
        access.close_count+=1
        failed=r['bx'] not in access.handles or access.close_count<=c.get('fail_close',0)
        if not failed:access.handles.remove(r['bx'])
        r['ax']=6 if failed else 0
        if 'close_ds' in c:r['ds']=c['close_ds'];access.live_ds=r['ds']
        if 'close_stack' in c:
            words=[access.word_read(r['ss'],(r['sp']+2*i)&65535,r['flags']) for i in range(4)]
            r['ss'],r['sp']=c['close_stack']
            for i,v in enumerate(words):access.word_write(r['ss'],(r['sp']+2*i)&65535,v,r['flags'])
    flags=access.word_read(r['ss'],(r['sp']+4)&65535,r['flags'])
    flags=c.get('iret_flags',flags)
    access.word_write(r['ss'],(r['sp']+4)&65535,(flags&~1)|int(failed),r['flags'])
    if 'iret_ip' in c:access.word_write(r['ss'],r['sp'],c['iret_ip'],r['flags'])
    access.service_events.append(dict(kind='dos',entry=entry,returned=dict(r),failed=failed))
    return c.get('provider_stop',0)

def video_provider(access,incoming):
    """Existing display-setup logical INT10 boundary; no invented CPU frame."""
    check(incoming['ax']==0x90,'unexpected setup mode request')
    out=dict(incoming)
    if 'mode_ds' in access.c:out['ds']=access.c['mode_ds'];access.live_ds=out['ds']
    access.service_events.append(dict(kind='video',entry=dict(incoming),returned=dict(out)))
    return out

class Machine(base.OriginalMachine):
    def __init__(self,c,memory,r,device):
        self.child_status=0;frames=[];failed=[];self.calls=[]
        def before(m,i):
            if c['kind']=='code_screen' and i.address==0x4401:m.stop(0);return True
            if i.address in (0x4CC9,0x4D18) and m.state()['bp']!=0x503B:m.stop(6);return True
            if c['kind'] in ('menu','startup') and i.address in EXITS:m.stop(0);return True
            if c.get('missing_mode') and i.address==0x4BF2:m.child_status=1;m.stop(1);return True
            missing_in=c.get('missing_in') and i.mnemonic=='in'
            missing_out=c.get('missing_out') and i.mnemonic=='out' and i.operands[-1].size==1
            if missing_in or missing_out:
                status=1 if missing_in else 2
                m.child_status=0 if c['kind']=='publish' else status
                m.stop(status if c['kind']=='publish' else 1);return True
            if i.mnemonic in ('call','lcall'):
                own=i.address in OWN;root=(m.state()['bp'] if i.address==0x4CC9 else i.operands[0].imm) if own else frames[-1]['root'] if frames else None
                frames.append(dict(owner=i.address,root=root,resume=i.address+i.size,far=i.mnemonic=='lcall'))
                if own:self.calls.append((i.address,root))
            return False
        def expected(m,off):
            check(bool(frames),'undeclared main-menu return');frame=frames.pop();failed[:]=[frame]
            return {(c['load'],frame['resume'])} if frame['far'] else {frame['resume']}
        def changed(m,off):
            frame=failed[-1]
            if frame['owner'] in OWN:self.child_status=0;return 2
            if off in animation.RENDER and animation.RENDER[off].mnemonic!='retf':self.child_status=1
            elif frame['root'] in (0x4F96,0x4FF8,0x4EEF,0x4F2B):self.child_status=2 if INS[off].mnemonic=='retf' else 3
            else:self.child_status=2
            return 1
        access=Access(c,memory,r,device)
        def interrupt(m,number):
            if number==0x10:
                state=m.state();out=video_provider(access,{n:state[n] for n in animation.FIELDS})
                state.update(out);m.set_state(state);m.mask=base.FLAGS;m.flags=state['flags'];return
            check(number==0x21,'unexpected menu startup interrupt')
            m.software_interrupt(number,m.state()['ip'],DOS_BINDING,None if c.get('no_service') else dos_provider)
            if m.stopped:m.status={1:3,2:4,3:5}[m.status]
        outer={0x51A1 if c['kind']=='encode' else 0x52D3} if c['kind'] in ('encode','decode') else {0x4B1B} if c['kind']=='probe' else {0x5446,0x5506} if c['kind']=='publish' else set()
        if c['kind']=='format':outer={0x48AF}
        if c['kind'] in ('editor','code_text'):outer=lambda m,off:off==0x4D77 and not frames
        super().__init__(c,memory,r,device,c.get('core',False),instructions=INS,access=access,outer_returns=outer,max_steps=c.get('reference_steps',MAX_STEPS),
            before=before,child_returns={p:expected for p,i in INS.items() if i.mnemonic=='ret'},
            far_returns={p:expected for p,i in INS.items() if i.mnemonic=='retf'},changed_return_status=changed,
            interrupt=interrupt if c['kind'] in ('probe','startup') else None)
    def run(self):
        out=super().run();out['child_status']=self.child_status or self.service_status;out['service_status']=0;out['calls']=self.calls;out['services']=self.access.service_events;out['transport_events']=self.access.transport_events;return out

class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'main-menu-{mutation}.dll',mutation,'main_menu')))
        self.run_menu=self.lib.lmn_run_main_menu;self.run_menu.restype=Result
        self.run_menu.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.c_uint16,ct.c_int,ct.POINTER(base.Ports),ct.POINTER(base.Bus)]
        self.editor={}
        for kind,name in (('format','format_selected_level'),('editor','read_code_input'),('code_text','draw_code_input')):
            for core,suffix in ((True,'core'),(False,'adapter')):
                fn=getattr(self.lib,'lmn_'+name+'_'+suffix);fn.restype=Result
                fn.argtypes=[base.MEM,ct.POINTER(base.Regs)]+([] if kind=='format' else [ct.c_uint16,ct.POINTER(base.Ports)])+[ct.POINTER(base.Bus)]
                self.editor[kind,core]=fn
        self.screen=self.lib.lmn_show_code_entry;self.screen.restype=Result
        self.screen.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.c_uint16,ct.POINTER(base.Ports),ct.POINTER(base.Bus)]
        self.publish={};self.probe={};self.code={}
        for kind in ('encode','decode'):
            for core,suffix in ((True,'core'),(False,'adapter')):
                fn=getattr(self.lib,'lmn_'+kind+'_level_code_'+suffix);fn.restype=Result
                fn.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.POINTER(base.Bus)];self.code[kind,core]=fn
        for core,suffix in ((True,'core'),(False,'adapter')):
            fn=getattr(self.lib,'lmn_publish_palette_'+suffix);fn.restype=PublishResult
            fn.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.c_int,ct.POINTER(base.Ports),ct.POINTER(base.Bus)];self.publish[core]=fn
            fn=getattr(self.lib,'lmn_check_menu_resource_'+suffix);fn.restype=Result
            fn.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.c_uint16,ct.POINTER(base.InterruptService),ct.POINTER(base.Ports),ct.POINTER(base.Bus)];self.probe[core]=fn
        self.startup=self.lib.lmn_enter_main_menu;self.startup.restype=Result
        self.startup.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.c_uint16,ct.POINTER(VideoServices),ct.POINTER(base.InterruptService),ct.POINTER(base.Ports),ct.POINTER(base.Bus)]
    def run(self,c,memory,r,device,*,copy_state=True):
        if copy_state:memory,device=bytearray(memory),copy.deepcopy(device)
        access=Access(c,memory,r,device)
        cb=base.NativeCallbacks(access,missing_in=c.get('missing_in',False),missing_out=c.get('missing_out',False));mem=(ct.c_uint8*base.SIZE).from_buffer(memory)
        @VIDEO
        def mode(_,binding,incoming,outgoing):
            try:
                check(ct.addressof(binding.contents)==ct.addressof(mem),'video canonical memory binding differs')
                state=video_provider(access,{n:getattr(incoming.contents,n) for n in animation.FIELDS})
                for n,v in state.items():setattr(outgoing.contents,n,v)
            except BaseException as error:base.callback_failure(error)
        video=VideoServices(None,mode,VIDEO())
        callback=cb.interrupt(dos_provider);service=base.InterruptService(None,callback,*DOS_BINDING)
        dos=None if c.get('no_service') else ct.byref(service)
        regs=ct.byref(base.Regs(**r));game_ds=(c['load']+0x9A9)&65535;tail=[ct.byref(cb.ports),ct.byref(cb.bus)]
        if c['kind']=='format':out=self.editor['format',c.get('core',False)](mem,regs,ct.byref(cb.bus))
        elif c['kind'] in ('editor','code_text'):out=self.editor[c['kind'],c.get('core',False)](mem,regs,game_ds,*tail)
        elif c['kind']=='code_screen':out=self.screen(mem,regs,game_ds,*tail)
        elif c['kind'] in ('encode','decode'):out=self.code[c['kind'],c.get('core',False)](mem,regs,ct.byref(cb.bus))
        elif c['kind']=='publish':out=self.publish[c.get('core',False)](mem,regs,c['entry'],*tail)
        elif c['kind']=='probe':out=self.probe[c.get('core',False)](mem,regs,game_ds,dos,*tail)
        elif c['kind']=='startup':out=self.startup(mem,regs,game_ds,None if c.get('missing_mode') else ct.byref(video),dos,*tail)
        else:out=self.run_menu(mem,regs,game_ds,c['entry'],*tail)
        return dict(regs={n:getattr(out.registers,n) for n in base.REG_NAMES},status=out.status,child_status=0 if c['kind']=='publish' else out.child_status,service_status=0,
                    memory=memory,device=access.device,events=access.events,providers=access.providers,cursor=access.cursor,services=access.service_events)

def independent(c,r,ref):
    check(ref['status']==c.get('expected',0) and ref['child_status']==c.get('child_status',0),c['name']+': unexpected stop')
    if ref['status']:return
    if c['kind'] in ('format','editor','code_text','code_screen'):
        if c['kind']=='format':
            if not c.get('format_alias') and c.get('patch')!='format-live':
                selection=c.get('selection',37);value=(selection+1)&255;group,level=divmod(value,30)
                if level==0:level=30;group=(group-1)&255
                check(ref['regs']['ax']==group*256+level,'formatter byte wrap/group differs')
            if c.get('patch')=='format-live':check(ref['regs']['ax']==0x1E2,'formatter elided live second selection read')
            check(ref['regs']['cx']==(0x1234 if c.get('patch')=='format-saved-cx' else r['cx']) or c.get('format_alias'),'formatter did not restore live CX')
        if c['kind'] in ('editor','code_screen'):
            if c['kind']=='editor':
                expected={'editor-empty':b'.'*10,'editor-bounds':b'AZ........','editor-last-slot':b'ABCDEFGHIK',
                    'editor-backspace':b'A.........','editor-initial':b'.BCDEFGHIJ','editor-blink':b'.'*10,'editor-bx-bound':b'Z.........','editor-signed-bound':b'A.........'}.get(c['name'])
                at=physical(r['ds'],0x4DF2)
                if expected:check(bytes(ref['memory'][at:at+10])==expected,'editor cursor/overwrite/backspace differs')
                if c['name']=='editor-blink':check(ref['memory'][physical(r['ds'],0x491E)]==19,'cursor blink period differs')
            if c['kind']=='code_screen':
                if c.get('invalid'):check(ref['memory'][physical(r['ds'],0x1F74)]==(255 if c['name']=='code-screen-special' else 0x39),'invalid screen changed special latch')
                else:
                    check(ref['memory'][physical(r['ds'],0x1F6B)]==c.get('selection',37),'screen lost decoded selection')
                    check(ref['memory'][physical(r['ds'],0x1F6E)]==c.get('selection',37)//30,'screen lost decoded group')
                    if c.get('rating_row'):
                        at=physical(r['ds'],0x4E1F);check(bytes(ref['memory'][at:at+6])==c['rating_row'],'screen clamped unchecked rating row')
            check(get16(ref['memory'],r['ds'],0x1FC7)==(c.get('leave',0) if c['kind']=='code_screen' and not c.get('invalid') and c.get('leave')!=1 else 0),'editor submit/action word differs')
            if c['kind']=='code_screen':check(ref['regs']['ip']==0x4401,'code screen did not JMP refresh')
        return
    if c['kind'] in ('encode','decode'):
        ds=r['ds'];mem=ref['memory'];at=lambda off:physical(ds,off)
        end=(0x51A1 if c['kind']=='encode' else 0x52D3) if c.get('core') else 0xD00D
        check(ref['regs']['ip']==end,'code actual return differs')
        if c.get('stack_alias') or c.get('patch')=='code-saved-si':return
        selection=c.get('selection',37);payload=c.get('payload',6);completion=c.get('completion',83);template=c.get('template',TEMPLATE)
        if c['kind']=='encode':
            check(bytes(mem[at(0x4D68):at(0x4D68)+10])==expected_code(selection,payload,completion,template),'encoded bit layout differs')
            check(mem[at(0x4D72)]==13,'encoder changed trailing terminator')
        else:
            value=c.get('input',expected_code(selection,payload,completion,template));value=bytearray(value)
            if c.get('corrupt')=='checksum':value[9]^=1
            if c.get('corrupt')=='selection':value[(8-(selection&7))%7]^=8;value[9]=(template[9]+(sum(value[:9])&15))&255
            latch=255 if value==b'BILLANDTED' else 0x39
            check(mem[at(0x1F74)]==latch,'special latch ordering differs')
            checksum=((value[9]-(sum(value[:9])&15))&255)==template[9]
            if not checksum:
                check(not ref['regs']['flags']&64 and bytes(mem[at(0x4DF2):at(0x4DF2)+10])==value,'checksum failure changed code')
                check(mem[at(0x1F6B)]==selection,'checksum failure changed selection')
            elif template==TEMPLATE and not c.get('corrupt') and 'input' not in c:
                check(ref['regs']['flags']&64,'valid code rejected')
                check(mem[at(0x1F6B)]==selection and mem[at(0x1F6E)]==selection//30,'decoded selection/group differs')
                check(mem[at(0x491D)]==(payload&15),'decoded payload differs')
            if c.get('corrupt')=='selection':
                check(not ref['regs']['flags']&64,'duplicate selection corruption accepted')
                check(mem[at(0x1F6B)]==selection,'late failure rolled back selected level')
                check(bytes(mem[at(0x4DF2):at(0x4DF2)+10])!=value,'late failure rolled back input rotation')
        return
    if c['kind']=='publish':
        mode=c.get('mode',2);index=2 if c['entry']==1 else c.get('index',1)
        table=0x52E4 if mode==4 else 0x52D4;at=physical(r['cs'],table+2*index)
        reads=[e[1] for e in ref['events'] if e[0]=='read']
        check(reads[2:4]==[at,(at+1)&base.MASK],'live CS palette selector differs')
        count=8 if c['entry']==0 else 16 if c['entry']!=3 else c.get('count',0xAD05)&255
        count=count or 65536
        outputs=[e for e in ref['events'] if e[0]=='out8']
        check(len(outputs)==(4*count if mode==4 else 2*count+1),'palette publication count differs')
        check(ref['regs']['ip']==((0x5506 if mode==4 else 0x5446) if c.get('core') else 0xD00D),'palette inherited return differs')
        return
    if c['kind']=='probe':
        check(ref['regs']['ip']==(0x4B1B if c.get('core') else c.get('outer_ip',0xD00D)),'resource probe return differs')
        calls=[e for e in ref['services'] if e['kind']=='dos']
        if c.get('media',0)!=0xFD:
            check(not calls and ref['memory'][physical(r['ds'],0x1FDF)]==c.get('critical',0x79),'non-FD probe changed critical state')
        else:
            expected=[0x3D]*c.get('fail_open',0)+[op for _ in range(c.get('fail_close',0)) for op in (0x3D,0x3E)]+[0x3D,0x3E]
            check([e['entry']['ax']>>8 for e in calls]==expected,'resource retry/open/close order differs')
            ds=ref['regs']['ds'];check(ref['memory'][physical(ds,0x1FDF)]==0,'successful probe did not clear live critical flag')
            check(ref['memory'][physical(r['ds'],0x1FDE)]==c['media'],'probe changed startup FAT ID')
            if ds!=r['ds']:check(ref['memory'][physical(r['ds'],0x1FDF)]==c.get('critical',0x79),'probe cleared entry DS critical flag')
        return
    if c['kind']=='startup':
        check(ref['calls'][:5]==[(0x43F2,0x4BE7),(0x43F5,0x4DEF),(0x43F8,0x5028),(0x43FB,0x53FC),(0x43FE,0x4AC5)],'startup child order differs')
        check((get16(ref['memory'],0,0x20),get16(ref['memory'],0,0x22))==(0x4C47,c['load']),'startup did not install menu vector')
        check(ref['regs']['ip']==0x454C,'startup did not reach level transition')
        return
    first=c['keys'][0];dest={0x80:0x454C,0x81:0x4967,0x83:0x4A01,0x1B:0x4D0}.get(first,0x454C)
    check(ref['regs']['ip']==dest,'menu destination differs')
    if c['entry']==3 and first==0x82 and c.get('sound_cache',c['toggle'])!=2:
        index=(c['option']+1)&255
        if index==(3 if c['driver']==255 else 2):index=0
        check(ref['memory'][physical(r['ds'],0x1F71)]==index,'sound option exact wrap differs')
        check(ref['memory'][physical(r['ds'],0x1F70)]==(c['toggle']^255),'sound toggle full byte differs')
        value=0x55 if c.get('patch')=='table' else base.IMAGE[0x44E9+index]
        check(ref['memory'][physical(r['ds'],0x25A7)]==value,'live CS sound option value differs')
    if c['entry']==3 and first==0x82 and c.get('sound_cache',c['toggle'])==2:
        check(ref['memory'][physical(r['ds'],0x1F70)]==c['toggle'] and ref['memory'][physical(r['ds'],0x1F71)]==c['option'],'blocked sound action changed state')
    if c['entry']==3 and first in (0x8A,0x60,0x8B,0x2D):
        group=7 if c.get('patch')=='group' else c['group']
        if c.get('group_cache',c['group'])!=4:
            changed=False
            if first in (0x8A,0x60) and group!=3:group=(group+1)&255;changed=True
            if first in (0x8B,0x2D) and group!=0:group=(group-1)&255;changed=True
            if changed:
                check(ref['memory'][physical(r['ds'],0x1F6B)]==((30*group)&255),'group-to-resource selection differs')
        check(ref['memory'][physical(r['ds'],0x1F6E)]==group,'group byte guard/wrap differs')
    if c['entry'] in (1,2):check(ref['calls'][:6]==[(0x445B,0x1550),(0x445E,0x7D0D),(0x4461,0x4F96),(0x4464,0x4EA2),(0x4467,0x4E37),(0x446A,0x4C20)],'menu child order differs')
    if c['entry']==0:
        check([p for p,_ in ref['calls'][:15]]==[0x4413,0x4425,0x4428,0x442B,0x442E,0x4431,0x4434,0x4437,0x443E,0x4441,0x4444,0x4447,0x444A,0x444D,0x4450],'menu refresh child order differs')
        check((get16(ref['memory'],r['ds'],0x1F76),get16(ref['memory'],r['ds'],0x1F78),get16(ref['memory'],r['ds'],0x1F7A))==(0x6D60,0,0),'refresh/display page ownership differs')

def compare(native,c):
    memory,r,device=setup(c)
    case=c|dict(missing_port_status=1,missing_service_status=1)
    ref=Machine(case,bytearray(memory),dict(r),copy.deepcopy(device)).run();independent(c,r,ref)
    if native:base.compare_states(c['name'],native.run(c,memory,r,device),ref)
    return ref

def hashes():
    paths=set(keyboard.hashes())|set(scroll.hashes())|set(animation.hashes())|set(cache.hashes())|FIXTURES
    paths|={'c/main_menu.c','c/main_menu.h','tests/main_menu.py','src/input_menu_and_retry.asm','tools/cbuild.py','tools/difftest.py'}
    for p in source_files('main_menu'):
        paths.add(p.relative_to(ROOT).as_posix())
        if p.with_suffix('.h').is_file():paths.add(p.with_suffix('.h').relative_to(ROOT).as_posix())
    paths|={'src/palette_frontends.asm','src/entry_services.asm'}
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}

def input_handoff(native,record):
    c=next(c for c in cases() if c['name']=='key-83')|dict(pinned=True)
    memory,r,device=setup(c);actual_memory,actual_device=bytearray(memory),copy.deepcopy(device);actual_regs=dict(r)
    ref=Machine(c,memory,dict(r),device).run();independent(c,r,ref)
    actual=native.run(c,actual_memory,actual_regs,actual_device,copy_state=False);base.compare_states('handoff-to-input',actual,ref)
    record('handoff-to-input',ref)
    memory,r,device=ref['memory'],ref['regs'],ref['device'];actual_memory,actual_regs,actual_device=actual['memory'],actual['regs'],actual['device']
    for dev in (device,actual_device):dev.trace.clear()
    del ref,actual
    gc.collect()
    # This is the actual JMP4A01, not a constructed CALL/RET. Reuse the existing
    # shared-verifier input-screen fixture provider and the compiled C core.
    screen=dict(c,name='handoff-input-screen',entry='screen',selection_chars=(0x33,),crtc=0x3D4)
    ref=keyboard.Machine(screen,memory,dict(r),device,False).run()
    fn=native.lib.lmn_show_input_selection;fn.restype=keyboard.Result
    fn.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.POINTER(base.Ports),ct.POINTER(base.Bus)]
    access=keyboard.Access(screen,actual_memory,actual_regs,actual_device);cb=base.NativeCallbacks(access)
    result=fn((ct.c_uint8*base.SIZE).from_buffer(actual_memory),ct.byref(base.Regs(**actual_regs)),ct.byref(cb.ports),ct.byref(cb.bus))
    actual=dict(regs={n:getattr(result.registers,n) for n in base.REG_NAMES},status=result.status,child_status=result.child_status,service_status=result.service_status,
                memory=actual_memory,device=access.device,events=access.events,providers=access.providers,cursor=access.cursor,services=access.service_events)
    base.compare_states('handoff-input-screen',actual,ref)
    check(ref['status']==0 and ref['regs']['ip']==0x4401 and ref['memory'][physical(r['ds'],0x25A6)]==2,'input selection did not reach refresh')
    record('handoff-input-screen',ref)
    memory,r,device=ref['memory'],ref['regs'],ref['device'];actual_memory,actual_regs,actual_device=actual['memory'],actual['regs'],actual['device']
    for dev in (device,actual_device):dev.trace.clear()
    del ref,actual,access,cb,result
    gc.collect()
    c=dict(c,name='handoff-menu-refresh',entry=0,keys=(None,))
    ref=Machine(c,memory,dict(r),device).run();independent(c,r,ref)
    actual=native.run(c,actual_memory,actual_regs,actual_device,copy_state=False);base.compare_states('handoff-menu-refresh',actual,ref)
    check(ref['regs']['ip']==0x454C and ref['memory'][physical(r['ds'],0x25A6)]==2,'configured mode did not reach level transition')
    record('handoff-menu-refresh',ref);gc.collect()
    print('CHECKED menu/input/refresh handoff',flush=True)

def code_handoffs(native,record):
    for load in base.LOADS:
        c=next(c for c in cases() if c['name']==f'code-encode-load-{load:04x}')
        memory,r,device=setup(c);actual_memory,actual_device=bytearray(memory),copy.deepcopy(device)
        ref=Machine(c,memory,dict(r),device).run();independent(c,r,ref)
        actual=native.run(c,actual_memory,dict(r),actual_device,copy_state=False)
        base.compare_states('code-handoff-encode',actual,ref);record('code-handoff-encode-'+hex(load),ref)
        for outcome in (ref,actual):
            # Declared external code submission. The keyboard editor remains a
            # separate frontier; no translated routine is replaced by this step.
            mem,regs=outcome['memory'],outcome['regs'];ds=regs['ds']
            for n in range(10):base.sync_memory_byte(mem,outcome['device'],ds,0x4DF2+n,mem[physical(ds,0x4D68+n)])
            regs['sp']=(regs['sp']-2)&65535;put16(mem,regs['ss'],regs['sp'],0xD00D,outcome['device'])
            regs['ip']=0x51A2;outcome['device'].trace.clear()
        c=dict(c,kind='decode',name='code-handoff-decode-'+hex(load))
        r=dict(ref['regs']);decoded=Machine(c,ref['memory'],r,ref['device']).run();independent(c,r,decoded)
        actual=native.run(c,actual['memory'],actual['regs'],actual['device'],copy_state=False)
        base.compare_states(c['name'],actual,decoded);record(c['name'],decoded)
        check(decoded['regs']['flags']&64,'generated code did not roundtrip')
        del ref,actual,decoded;gc.collect()
    print('CHECKED three same-memory code handoffs',flush=True)

def editor_handoffs(native,record):
    for load in base.LOADS:
        c=next(c for c in cases() if c['name']=='key-81')|dict(load=load,pinned=True)
        memory,r,device=setup(c);actual_memory,actual_device=bytearray(memory),copy.deepcopy(device)
        ref=Machine(c,memory,dict(r),device).run();independent(c,r,ref)
        actual=native.run(c,actual_memory,dict(r),actual_device,copy_state=False)
        base.compare_states('editor-handoff-enter',actual,ref);record('editor-handoff-enter-'+hex(load),ref)
        check(ref['regs']['ip']==0x4967,'menu did not enter code screen')
        for outcome in (ref,actual):outcome['device'].trace.clear()
        screen=dict(c,name='editor-handoff-screen-'+hex(load),kind='code_screen',entry=0,selection=59,payload=3,completion=97,leave=0x20)
        r=dict(ref['regs']);next_ref=Machine(screen,ref['memory'],r,ref['device']).run();independent(screen,r,next_ref)
        next_actual=native.run(screen,actual['memory'],actual['regs'],actual['device'],copy_state=False)
        base.compare_states(screen['name'],next_actual,next_ref);record(screen['name'],next_ref)
        del ref,actual
        for outcome in (next_ref,next_actual):outcome['device'].trace.clear()
        c=dict(c,name='editor-handoff-refresh-'+hex(load),kind='menu',entry=0,keys=(None,))
        r=dict(next_ref['regs']);ref=Machine(c,next_ref['memory'],r,next_ref['device']).run();independent(c,r,ref)
        actual=native.run(c,next_actual['memory'],next_actual['regs'],next_actual['device'],copy_state=False)
        base.compare_states(c['name'],actual,ref);record(c['name'],ref)
        check(ref['regs']['ip']==0x454C and ref['memory'][physical(r['ds'],0x1F6B)]==59,'code selection did not reach level transition')
        del ref,actual,next_ref,next_actual;gc.collect()
    print('CHECKED three menu/editor/validation/refresh handoffs',flush=True)

EDITOR_MUTANTS=((301,'format-255'),(302,'format-live-selection'),(303,'editor-blink'),
    (304,'editor-empty'),(305,'editor-backspace'),(306,'editor-last-slot'),(307,'editor-signed-bound'),
    (308,'editor-unknown-call'),(309,'editor-unknown-tail'),(310,'editor-empty'),(311,'code-screen-button'),
    (312,'code-screen-df'),(313,'code-screen-selection-wrap'),(314,'code-screen-key40'),(315,'format-saved-cx'))

CODE_MUTANTS=((201,'code-encode-000'),(202,'code-encode-template-live'),(203,'code-decode-037'),
    (204,'code-special-5'),(205,'code-selection-fail'),(206,'code-decode-037'),
    (207,'code-decode-119'),(208,'code-decode-037'),(209,'code-checksum-fail'),(210,'code-decode-saved-si'))

def worker(directory,snapshot):
    before=hashes();check(before==json.loads(Path(snapshot).read_text()),'main menu snapshot changed');native=Native(directory)
    sites=set();edges=set();rows=[]
    def record(name,ref):
        sites.update(ref['sites']);edges.update(ref['edges'])
        rows.append(dict(case=name,steps=ref['steps'],events=len(ref['events']),far_return_events=ref['far_return_events'],transport_events=ref.get('transport_events',0),service_calls=len(ref.get('services',[]))))
    for c in cases():
        ref=compare(native,c);record(c['name'],ref)
        gc.collect();print('CHECKED '+c['name'],flush=True)
    input_handoff(native,record)
    code_handoffs(native,record)
    editor_handoffs(native,record)
    check(set(OWN)<=sites,'main menu sites missing: '+str(sorted(set(OWN)-sites)))
    check(EDGES<=edges,'main menu outcomes missing: '+str(sorted(EDGES-edges)))
    mutants=[];lookup={c['name']:c for c in cases()}
    for mutation,name in ((1,'sound-blocked'),(2,'sound-driver-fe'),(3,'sound-unexpected-index'),(4,'key-82'),(5,'group-8a-unexpected'),(6,'key-8a'),(7,'key-80'),(8,'wait-return'),(9,'key-82'),(11,'probe-media-fe'),(12,'probe-open-retry'),(13,'probe-close-retry'),(14,'probe-returned-ds'),(15,'probe-latch'),(16,'probe-success'),(17,'probe-media-fe'),(101,'publish-e0-m2-i0'),(102,'publish-e0-m2-i2'),(103,'publish-e2-m260-i7'),(104,'publish-e1-m2-i0'),(105,'publish-e1-m2-i0'))+CODE_MUTANTS+EDITOR_MUTANTS:
        try:compare(Native(directory,mutation),lookup[name])
        except base.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
        else:raise base.OracleFailure(f'main menu mutant{mutation} survived')
        gc.collect()
    check(before==hashes(),'main menu inputs changed')
    write_json(REPORT,dict(image='main',image_sha256=sha(base.IMAGE),own_known_bytes=sum(i.size for i in OWN.values()),known_connected_bytes=sum(i.size for p,i in INS.items() if p not in BOUNDARY),
        entry_code_ranges=[list(r) for r in RANGES],case_count=len(cases())+7,comparison_count=len(rows),handoff_count=7,
        executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(OWN)&sites),branch_edges=sorted(edges),own_branch_edges=sorted(EDGES),
        instruction_steps=sum(r['steps'] for r in rows),ordered_bus_events=sum(r['events'] for r in rows),declared_far_return_events=sum(r['far_return_events'] for r in rows),declared_interrupt_transport_events=sum(r['transport_events'] for r in rows),service_calls=sum(r['service_calls'] for r in rows),
        mutation_count=len(mutants),mutations=mutants,input_hashes=before,rows=rows,
        limits=dict(timeout_seconds=SECONDS,outer_timeout_seconds=1260,process_commit_mib=MEMORY_MIB,instructions=MAX_STEPS,events=MAX_EVENTS),
        scope='488C live wrap formatter,503B text tail,4C7E editor with declared known503B BP target and explicit unsupported alternatives,4967 validation screen to actual4401 JMP; three native menu/editor/validation/refresh handoffs. 5042 encoder/51A2 decoder and earlier same-RAM code-submission handoffs. Connected43F2 startup,4AC5 FAT-ID-gated resource retry,53F6/53FC/53FE/5401 palette selectors and4401..454B controller. Real near/far/INT21/IRET frames,existing logical display-setup INT10 ABI,returned segments and actual JMP exits. Destination bodies,native scheduling/opaque services and inherited reference limits remain open.'))
    print(f'PASS main menu: {len(rows)} comparisons,{len(set(OWN)&sites)} own sites,{len(EDGES)} outcomes,{len(mutants)} mutants',flush=True)
def main():
    if len(sys.argv)==4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3]);return
    if sys.argv[1:]:raise SystemExit('usage: main_menu.py')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='main-menu-',parent=BUILD) as directory:
        snapshot=Path(directory)/'inputs.json';write_json(snapshot,hashes())
        run_bounded([sys.executable,__file__,'--worker',str(directory),str(snapshot)],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)
if __name__=='__main__':main()

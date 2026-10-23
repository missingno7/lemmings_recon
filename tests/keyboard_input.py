"""Keyboard helpers, IRQ producer and installer over the shared verifier."""
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
import text_stream as text
import background_drawing as background
import palette_transition as palette
import entity_create as spill
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build
from common import BUILD,sha,write_json

check=base.check
physical,put16,get16=base.physical,base.put16,base.get16
RANGES={'irq':(0x16D4,0x17B4),'command':(0x17B4,0x17BE),'wait':(0x17BE,0x17C7),'install':(0x1562,0x1582),
        'reader':(0x4D1A,0x4D4D),'scale':(0x4A9F,0x4AB5),
        'choice':(0x43CE,0x43F2),'controller':(0x4A4E,0x4ABD),'mode':(0x4A2E,0x4AC5),'screen':(0x4A01,0x4AC5)}
DOMAINS={n:{i.address:i for i in base.MD.disasm(base.IMAGE[a:b],a)} for n,(a,b) in RANGES.items()}
EOI={i.address:i for i in base.MD.disasm(base.IMAGE[0x18B2:0x18B7],0x18B2)}
DISPLAY={i.address:i for i in base.MD.disasm(base.IMAGE[0x1550:0x1562],0x1550)}
BOUNDARY={i.address:i for i in base.MD.disasm(base.IMAGE[0x4401:0x4407],0x4401)}
SWAP={i.address:i for i in base.MD.disasm(base.IMAGE[0x4C20:0x4C47],0x4C20)}
OWN={a:i for domain in DOMAINS.values() for a,i in domain.items()}
BASE_INS=OWN|EOI|DISPLAY|BOUNDARY
SCREEN_INS={i.address:i for a,b in ((0x4BF5,0x4C17),(0x8808,0x8822),(0x4DC2,0x4DF7),(0x4DF8,0x4E37)) for i in base.MD.disasm(base.IMAGE[a:b],a)}
INS=BASE_INS|SWAP|poll.INS|text.INS|SCREEN_INS|background.INS|palette.INS
EDGES=base.direct_jump_edges(OWN)
RET={'irq':0x17B3,'command':0x17BD,'wait':0x17C6,'install':0x1581,'reader':0x4D4C,'scale':0x4401,'choice':0x43ED,'controller':0x4401,'mode':0x4401,'screen':0x4401}
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=420,384,500_000,150_000
REPORT=BUILD/'keyboard-input-differential.json'
BINDING=(0x7100,0x210);HARDWARE=(0xD00D,0x6201,0x246)
BINDINGS=(0x48,0x50,0x4B,0x4D,0x39,0x52,0x11,0x1E,0x20,0x2E,0x10,0x2C,0x19,0x2D,0x26,0)
PINNED_BINDINGS=tuple(base.IMAGE[0xBAAF:0xBABF])
PINNED_CHARACTERS=tuple(base.IMAGE[0xBABE:0xBB11])
# Instruction maps come from maintained fixture modules; execution/bus/returns
# still belong exclusively to verification.py. Pin their imported source closure.
FIXTURE_SOURCES=set()
for module in tuple(sys.modules.values()):
    name=getattr(module,'__file__',None)
    if not name:continue
    path=Path(name).resolve()
    if path.suffix=='.py' and path.is_relative_to(ROOT):
        rel=path.relative_to(ROOT)
        if rel.parts[0] in ('tests','tools'):FIXTURE_SOURCES.add(rel.as_posix())


class Result(ct.Structure):
    _fields_=[('registers',base.Regs),('status',ct.c_uint16),('child_status',ct.c_uint16),('service_status',ct.c_uint16)]
class PortResult(ct.Structure):
    _fields_=[('registers',base.Regs),('status',ct.c_uint16)]


def cases():
    rows=[dict(name=f'irq-scan-{raw:02x}-gate-{gate:02x}',entry='irq',raw=raw,suppression=gate)
          for gate in (0,0xFF) for raw in range(256)]
    rows += [dict(name='irq-'+n,entry='irq',**kw) for n,kw in (
        ('controller',{'controller':0xFF,'samples':(2,0,2,2,0)}),
        ('controller-gate-one',{'controller':1}),
        ('suppression-fe',{'raw':0x7D,'suppression':0xFE}),
        ('pinned-binding-make',{'raw':0x10,'bindings':PINNED_BINDINGS,'keymask':0}),
        ('pinned-binding-break',{'raw':0x90,'bindings':PINNED_BINDINGS,'keymask':0xFFFF}),
        ('special-zero-lookup',{'raw':0xFD,'suppression':0xFF,'keymask':0}),
        ('binding-first-match',{'raw':0x20,'bindings':(0x20,)*16,'keymask':0}),
        ('binding-all-disabled',{'bindings':(0xFF,)*16}),
        ('binding-live-second-read',{'raw':0x20,'bindings':(0x21,)+(0xFF,)*15,'late_binding':True}),
        ('late-controller-enable',{'late_controller':0xFF}),
        ('late-controller-disable',{'controller':0xFF,'late_controller':0}),
        ('relocated-ds',{'runtime_ds':0x3800}),
        ('late-ds-operand',{'runtime_ds':0x3800,'late_operand':True}),
        ('raw-save-changed',{'raw_save':0xB1FD,'suppression':0xFF}),
        ('eoi-return-changed',{'patch':'eoi','expected':4}),
        ('command-return-changed',{'controller':1,'patch':'command','expected':4}),
        ('wait-return-changed',{'controller':1,'patch':'wait','expected':3,'child_status':2}),
        ('missing-input',{'missing_in':True,'expected':1}),
        ('missing-output',{'missing_out':True,'expected':2}),
        ('missing-command-input',{'controller':1,'missing_in':True,'expected':3,'child_status':1}),
        ('missing-command-output',{'controller':1,'missing_out':True,'expected':3,'child_status':1}),
        ('offset-wrap',{'sp':3}),('physical-wrap',{'ss':0xFFFF,'sp':0x11}),
        ('hardware-word-ffff',{'sp':0xFFFF}),('vga-stack',{'ss':0xA000}),
        ('save-overlaps-keymask',{'ss':0x3000,'sp':0x1FC9}),
        ('save-overlaps-bindings',{'ss':0x3000,'sp':0x2021}),
        ('if-df-set',{'flags':0x6D7}),
    )]
    rows += [dict(name=entry+'-'+n,entry=entry,**kw) for entry in ('wait','command') for n,kw in (
        ('clear',{}),('waits',{'samples':(2,2,0)}),
        ('counter-exhausted',{'busy':True}),
        ('missing-input',{'missing_in':True,'expected':1}),
        ('offset-wrap',{'sp':1}),('physical-wrap',{'ss':0xFFFF,'sp':0x11}),
        ('outer-word-ffff',{'sp':0xFFFF}),('vga-stack',{'ss':0xA000}),
    )]
    rows += [dict(name='command-'+n,entry='command',**kw) for n,kw in (
        ('missing-output',{'missing_out':True,'expected':1}),
        ('changed-wait-return',{'patch':'wait','expected':2}),
        ('saved-ax-changed',{'patch':'saved-ax'}),
    )]
    rows += [dict(name='install-'+n,entry='install',**kw) for n,kw in (
        ('ordinary',{}),('query-returned-ds',{'first':{'regs':{'ds':0x3600}}}),
        ('query-returned-registers',{'first':{'regs':{'ax':0xABCD,'cx':0x5678,'si':0x2345,'di':0xDEAD,'bp':0xBEAD},'iret_flags':0x6D7}}),
        ('query-returned-stack',{'first':{'stack':(0x6500,0x7000),'saved_ds':0x3600,'saved_es':0x4321}}),
        ('set-returned-stack',{'second':{'stack':(0x6600,0x8000),'saved_ds':0x3600,'saved_es':0x4321,'outer_ip':0xBEEF}}),
        ('set-returned-registers',{'second':{'regs':{'ax':0xABCD,'bx':0x1234,'cx':0x5678,'dx':0xBEAD,'si':0x2345,'di':0xDEAD,'bp':0x6789,'ds':0x7777,'es':0x8888},'iret_flags':0x4D7}}),
        ('unbound',{'no_service':True,'expected':5}),
        ('first-stop',{'first':{'status':0x1234},'expected':6,'service_status':0x1234}),
        ('second-stop',{'second':{'status':0x5678},'expected':6,'service_status':0x5678}),
        ('first-changed-return',{'first':{'iret_ip':0xD234},'expected':7}),
        ('second-changed-return',{'second':{'iret_cs':0x6666},'expected':7}),
        ('second-unbound',{'first':{'unbind':True},'expected':5}),
        ('saved-es-vector-alias',{'ss':0x3000,'sp':0x1FC0}),
        ('ivt-stack-alias',{'ss':0,'sp':0x28}),
        ('offset-wrap',{'sp':1}),('physical-wrap',{'ss':0xFFFF,'sp':0x11}),
        ('outer-word-ffff',{'sp':0xFFFF}),('vga-stack',{'ss':0xA000}),
    )]
    rows += [dict(name=f'reader-byte-{value:02x}',entry='reader',states={3:value}) for value in range(256)]
    rows += [dict(name=f'reader-index-{index:02x}',entry='reader',states={index:0x94}) for index in range(83)]
    rows += [dict(name='reader-'+n,entry='reader',**kw) for n,kw in (
        ('empty',{}),('reload',{'states':{3:0x81}}),('zero-underflow',{'states':{3:0x80}}),
        ('all-held-deferred',{'states':dict.fromkeys(range(83),0x82)}),
        ('earliest-ready',{'states':{0:0x82,3:0x94,5:0x94}}),
        ('live-second-read',{'states':{3:0x94},'reader_late':0x81}),
        ('binding-overlap',{'states':{0:0x94},'character_zero':0xA7}),
        ('translated-ff',{'states':{3:0x94},'character_override':{3:0xFF}}),
        ('outer-return-alias',{'states':{3:0x94},'ss':0x3000,'sp':0xF7B}),
        ('offset-wrap',{'sp':0xFFFF}),('physical-wrap',{'ss':0xFFFF,'sp':0xF}),
        ('data-physical-wrap',{'runtime_ds':0xFFFF}),('vga-data',{'runtime_ds':0xA000}),
    )]
    rows += [dict(name='scale-'+n,entry='scale',**kw) for n,kw in (
        ('one',{'selection_chars':(0x31,)}),('four',{'selection_chars':(0x34,)}),
        ('lower-then-two',{'selection_chars':(0x30,0x32)}),
        ('upper-then-three',{'selection_chars':(0x35,0x33)}),
        ('ff-zero-four',{'selection_chars':(0xFF,0,0x34)}),
        ('display-port-carry',{'selection_chars':(0x32,),'crtc':0x3FC}),
        ('missing-input',{'missing_in':True,'expected':3,'child_status':1}),
        ('wait-return-changed',{'selection_chars':(0x31,),'scale_patch':'wait','expected':4}),
        ('reader-return-changed',{'selection_chars':(0x31,),'scale_patch':'reader','expected':4}),
        ('offset-wrap',{'sp':1,'selection_chars':(0x32,)}),
        ('physical-wrap',{'ss':0xFFFF,'sp':0x11,'selection_chars':(0x33,)}),
    )]
    rows += [dict(name=f'choice-byte-{v:02x}',entry='choice',choice_samples=(v,0xEF)) for v in range(256)]
    rows += [dict(name='choice-'+n,entry='choice',**kw) for n,kw in (
        ('keyboard',{'latch':0x77}),('other-latch',{'latch':0x76}),
        ('late-latch',{'choice_samples':(0xFF,),'late_choice_latch':0x77}),
        ('missing-input',{'missing_in':True,'expected':1}),
        ('offset-wrap',{'sp':0xFFFF}),('physical-wrap',{'ss':0xFFFF,'sp':0xF}),
        ('vga-stack',{'ss':0xA000}),
    )]
    rows += [dict(name='controller-'+n,entry='controller',**kw) for n,kw in (
        ('keyboard',{'latch':0x77}),('low',{}),('high',{'choice_samples':(0xBF,)}),
        ('asymmetric-low',{'axis_samples':(3,1,1,0)}),
        ('asymmetric-high',{'choice_samples':(0xBF,),'axis_samples':(12,8,8,0)}),
        ('text-spaces',{'menu_text':bytes((1,1,0,32,32,13,0))}),
        ('text-glyph',{'menu_text':bytes((1,1,0,33,13,0))}),
        ('pinned-text',{'pinned_text':True}),
        ('text-return-changed',{'controller_patch':'text','expected':4}),
        ('glyph-return-changed',{'menu_text':bytes((1,1,0,33,13,0)),'controller_patch':'glyph','expected':3,'child_status':2}),
        ('swap-return-changed',{'controller_patch':'swap','expected':4}),
        ('choice-return-changed',{'controller_patch':'choice','expected':4}),
        ('sample-return-changed',{'controller_patch':'sample','expected':4}),
        ('axes-return-changed',{'controller_patch':'axes','expected':3,'child_status':2}),
        ('missing-word-output',{'missing_word_out':True,'expected':3,'child_status':1}),
        ('missing-input',{'missing_in':True,'expected':3,'child_status':1}),
        ('offset-wrap',{'sp':1}),('physical-wrap',{'ss':0xFFFF,'sp':0x11}),
    )]
    rows += [dict(name='mode-'+n,entry='mode',**kw) for n,kw in (
        ('mouse',{'selection_chars':(0x31,),'mode_expected':0}),
        ('mouse-gate-fe',{'selection_chars':(0x31,0x33),'mouse_gate':0xFE,'mode_expected':0}),
        ('mouse-gate-ff',{'selection_chars':(0x31,0x33),'mouse_gate':0xFF}),
        ('keyboard',{'selection_chars':(0x33,)}),
        ('escape',{'selection_chars':(0x1B,),'initial_mode':1,'mode_expected':1}),
        ('invalid-then-keyboard',{'selection_chars':(0,0xFF,0x30,0x34,0x33)}),
        ('controller-low',{'selection_chars':(0x32,0x34),'mode_expected':1}),
        ('controller-high',{'selection_chars':(0x32,0x31),'choice_samples':(0xBF,),'mode_expected':1}),
        ('controller-keyboard',{'selection_chars':(0x32,),'latch':0x77}),
        ('missing-input',{'missing_in':True,'expected':3,'child_status':1}),
        ('offset-wrap',{'selection_chars':(0x33,),'sp':1}),
    )]
    rows += [dict(name='screen-'+n,entry='screen',**kw) for n,kw in (
        ('keyboard',{}),('no-mouse',{'mouse_gate':0xFF}),
        ('mouse-fe',{'mouse_gate':0xFE,'menu_text':bytes((1,1,0,33,13,0))}),
        ('rgb',{'palette_mode':4}),('pinned-text',{'pinned_text':True}),
        ('layout-far-changed',{'screen_patch':'layout','expected':3,'child_status':2}),
        ('palette-return-changed',{'screen_patch':'palette','expected':4}),
        ('background-far-changed',{'screen_patch':'background','expected':3,'child_status':2}),
        ('text-return-changed',{'screen_patch':'text','expected':4}),
        ('copy-return-changed',{'screen_patch':'copy','expected':4}),
        ('status-return-changed',{'screen_patch':'wait','expected':4}),
        ('display-return-changed',{'screen_patch':'display','expected':4}),
        ('late-mouse-disabled',{'screen_gate':0xFF}),
        ('late-mouse-enabled',{'mouse_gate':0xFF,'screen_gate':0}),
        ('stack-offset-wrap',{'sp':1}),('stack-physical-wrap',{'ss':0xFFFF,'sp':0x11,'expected':4}),('controller',{'selection_chars':(0x32,0x34),'mode_expected':1}),
        ('clear-return-changed',{'screen_patch':'clear','expected':4}),
        ('missing-word-output',{'missing_word_out':True,'expected':3,'child_status':2}),
        ('missing-palette-input',{'missing_in':True,'expected':3,'child_status':1}),
        ('missing-palette-output',{'missing_out':True,'expected':3,'child_status':2}),
    )]
    rows += [dict(name=f'{entry}-load-{load:04x}',entry=entry,load=load) for entry in RANGES for load in base.LOADS]
    rows += spill_irq_rows()
    return [dict(load=0x1010,seed=0x16D4+i,raw=0x20,suppression=0,controller=0,flags=0xD7,
                 selection_chars=(0x33,) if c['entry'] in ('mode','screen') else (0x32,))|c for i,c in enumerate(rows)]


# Row-54 spill: records 54..56 occupy the key-state bytes 0F78..0FCA
# (entity_create.spill_state, records 00..62 appended). Make/break of scans
# 15/16 and 42/43 rewrite the +14 callback bytes of records 55 and 56; scan 27
# rewrites record 55's +26 skip gate. Canonical DS 19B9 and the pinned
# bindings; every other key byte is the record byte it overlaps.
SPILL_DS=0x19B9
SPILL_SCANS={0x15:(0x0F79,0x14),0x16:(0x0F79,0x15),0x42:(0x0FA6,0x14),0x43:(0x0FA6,0x15),0x27:(0x0F79,0x26)}
def spill_irq_rows():
    return [dict(name=f'irq-row54-scan-{scan:02x}-{"break" if release else "make"}',entry='irq',
                 raw=scan|(0x80 if release else 0),runtime_ds=SPILL_DS,spill=True,
                 bindings=PINNED_BINDINGS,keymask=0)
            for scan in SPILL_SCANS for release in (False,True)]


def spill_expected(c,ref):
    """Characterized record bytes after the IRQ store (creation contract 30A6)."""
    scan=c['raw']&0x7F;record,field=SPILL_SCANS[scan];value=0 if c['raw']&0x80 else 0x94
    check(0xF78+scan==record+field and ref['memory'][physical(SPILL_DS,record+field)]==value,
          c['name']+': IRQ key byte did not land on the characterized record field')
    if field in (0x14,0x15):
        word=get16(ref['memory'],SPILL_DS,record+0x14)
        expected=(0x6100|value) if field==0x14 else ((value<<8)|0x70)
        check(word==expected,c['name']+f': record +14 {word:04X}, expected {expected:04X}')


def setup(c):
    memory,device=base.initial_memory(c)
    ds=c.get('runtime_ds',(c['load']+0x9A9)&0xFFFF if c['entry'] in ('controller','mode','screen') else 0x3000)
    r=base.default_regs(c['load'],c['seed'],ds=ds,ss=c.get('ss',0x5000),sp=c.get('sp',0x9000),flags=c['flags'])
    r['ip']=RANGES[c['entry']][0]
    for frame in (ds,0x3600):
        base.put8(memory,frame,0x200A,c['controller']);base.put8(memory,frame,0x200B,c['suppression'])
        put16(memory,frame,0x1FC7,c.get('keymask',0xA55A));put16(memory,frame,0x14,c.get('buttons',0xBEEF))
        base.put8(memory,frame,0x1FD0,c.get('latch',0 if c['entry'] in ('choice','controller','mode','screen') else 0x91))
        base.put8(memory,frame,0x1F73,c.get('mouse_gate',0))
        for i,v in enumerate(c.get('bindings',BINDINGS)):base.put8(memory,frame,0x201F+i,v)
        for i in range(0x53):base.sync_memory_byte(memory,device,frame,0xF78+i,c.get('states',{}).get(i,0 if c['entry'] in ('reader','scale','controller','mode','screen') else 0x37))
        if c['entry'] in ('reader','scale','controller','mode','screen') or c.get('character_fixture'):
            for i,v in enumerate(PINNED_CHARACTERS):base.sync_memory_byte(memory,device,frame,0x202E+i,c.get('character_override',{}).get(i,v))
            if 'character_zero' in c:base.sync_memory_byte(memory,device,frame,0x202E,c['character_zero'])
        put16(memory,frame,0x1FDA,c.get('crtc',0x3D4),device)
        for off,v in ((0x1F76,0x1200),(0x1F78,0x3400),(0x1F7A,0x100),(0x1FEE,0x4000)):
            put16(memory,frame,off,v,device)
        for off,v in ((0x66F0,350),(0x66F2,1664),(0x66F4,208),(0x26,0x1000)):
            put16(memory,frame,off,v,device)
        base.put8(memory,frame,0x2A,0)
        for start,size in ((0x4E3A,52),(0x4E6E,23),(0x4E85,36),(0x4EA9,38)):
            stream=base.IMAGE[0x9A90+start:0x9A90+start+size] if c.get('pinned_text') else c.get('menu_text',b'\0')
            for i,v in enumerate(stream):base.sync_memory_byte(memory,device,frame,start+i,v)
        for off,v in ((0x10,0x60),(0x12,0x30),(0x16,0x10),(0x18,0x10)):put16(memory,frame,off,v)
        base.put8(memory,frame,0x25A6,c.get('initial_mode',2))
    if c['entry']=='screen':
        put16(memory,ds,0x1F7C,c.get('palette_mode',2),device)
        base.put8(memory,ds,0x200C,0xFF)
        for start,value in ((0x2638,0),(0x2608,1),(0x4920,2)):
            for i in range(64):base.sync_memory_byte(memory,device,ds,start+i,value)
    if c.get('spill'):spill.spill_state(memory,SPILL_DS)
    put16(memory,0,0x84,BINDING[1]);put16(memory,0,0x86,BINDING[0])
    put16(memory,0,0x24,0xD123);put16(memory,0,0x26,0x6800)
    put16(memory,c['load'],0x16D9,(c['load']+0x9A9)&0xFFFF if c.get('late_operand') else ds)
    for i,v in enumerate(HARDWARE if c['entry']=='irq' else (0xD00D,)):
        put16(memory,r['ss'],(r['sp']+2*i)&0xFFFF,v,device)
    return memory,r,device


def dos_provider(c):
    if c.get('no_service'):return None
    def execute(access,r):
        start=len(access.events);index=len(access.service_events);spec=c.get('first' if index==0 else 'second',{})
        event=dict(entry=dict(r),index=index)
        check(r['ax']==(0x3509 if index==0 else 0x2509),'unexpected keyboard DOS request')
        if index==0:
            r['bx']=access.word_read(0,0x24,r['flags']);r['es']=access.word_read(0,0x26,r['flags'])
            event['queried_vector']=(r['bx'],r['es'])
        else:
            access.word_write(0,0x24,r['dx'],r['flags']);access.word_write(0,0x26,r['ds'],r['flags'])
        if 'stack' in spec:
            words=[access.word_read(r['ss'],(r['sp']+2*i)&0xFFFF,r['flags']) for i in range(6)]
            r['ss'],r['sp']=spec['stack']
            for i,v in enumerate(words):access.word_write(r['ss'],(r['sp']+2*i)&0xFFFF,v,r['flags'])
        r.update(spec.get('regs',{}))
        for name,off in (('iret_ip',0),('iret_cs',2),('iret_flags',4),('saved_es',6),('saved_ds',8),('outer_ip',10)):
            if name in spec:access.word_write(r['ss'],(r['sp']+off)&0xFFFF,spec[name],r['flags'])
        if spec.get('unbind'):access.word_write(0,0x84,0xD234,r['flags'])
        event.update(status=spec.get('status',0),provider_events=len(access.events)-start,returned=dict(r))
        access.service_events.append(event);return spec.get('status',0)
    return execute


class Access(base.BusAccess):
    def __init__(self,c,memory,r,device):
        super().__init__(c,memory,r,device,max_events=600_000 if c['entry']=='screen' else MAX_EVENTS)
        self.choice_cursor=0;self.axis_cursor=0;self.charged=False
        self.display_cursor=0;self.selection_cursor=0
    def access(self,kind,address,flags,mask=base.FLAGS,value=None):
        v=super().access(kind,address,flags,mask,value)
        if kind=='write' and self.c.get('late_operand') and 'operand' not in self.providers:
            self.patch(self.c['load'],0x16D9,self.c['runtime_ds'],'operand')
        if kind=='read' and address==physical(self.r['ds'],0x201F) and self.c.get('late_binding') and 'binding' not in self.providers:
            self.patch(self.r['ds'],0x201F,0x20,'binding',word=False)
        if kind=='read' and address==physical(self.r['ds'],0xF7B) and 'reader_late' in self.c and 'reader-byte' not in self.providers:
            self.patch(self.r['ds'],0xF7B,self.c['reader_late'],'reader-byte',word=False)
        if kind=='read' and address==physical(self.r['ds'],0x202F) and self.c.get('scale_patch')=='reader' and 'scale-return' not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']-2)&0xFFFF,0xD234,'scale-return')
        if kind=='read' and address==physical(self.r['ds'],0x4E85) and self.c.get('controller_patch')=='text' and 'controller-return' not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']-2)&0xFFFF,0xD234,'controller-return')
        if self.c['entry']=='screen':
            phase=self.c.get('screen_patch')
            triggers={'layout':('write',0x66F0,-6),'palette':('read',0x2608,-2),
                'background':('read',0x1FE4,-12),'text':('read',0x4E3A,-2),'copy':('read',0x1F78,-2)}
            if phase in triggers and 'screen-return' not in self.providers:
                op,off,delta=triggers[phase]
                # Copy's origin read occurs after its PUSH DS. Earlier reads
                # at layout/background are excluded by the live outer frame.
                frame=get16(self.memory,self.r['ss'],(self.r['sp']-2)&0xFFFF)
                if kind==op and address==physical(self.r['ds'],off) and (phase!='copy' or frame==0x4A25):
                    self.patch(self.r['ss'],(self.r['sp']+delta)&0xFFFF,0xD234,'screen-return')
            if kind=='read' and address==physical(self.r['ds'],0x4E3A) and 'screen_gate' in self.c and 'screen-gate' not in self.providers:
                self.patch(self.r['ds'],0x1F73,self.c['screen_gate'],'screen-gate',word=False)
        return v
    def inp(self,port,flags,mask=base.FLAGS):
        if port==0x64:
            samples=self.c.get('samples',(0,0))
            if self.c.get('busy'):check(self.cursor<65536,'busy sample budget exhausted');v=2
            else:check(self.cursor<len(samples),'finite status samples exhausted');v=samples[self.cursor]
            self.cursor+=1
        elif port==0x60:v=self.c['raw']
        elif port==0x61:v=self.c.get('ack',0x35)
        elif port==0x201:
            if self.charged:
                seq=(*self.c.get('axis_samples',(15,0)),self.c.get('axis_buttons',0xCF))
                check(self.axis_cursor<len(seq),'finite calibration samples exhausted');v=seq[self.axis_cursor];self.axis_cursor+=1
            else:
                seq=self.c.get('choice_samples',(0xEF,))
                check(self.choice_cursor<len(seq),'finite choice samples exhausted');v=seq[self.choice_cursor];self.choice_cursor+=1
            self.cursor+=1
            if self.c.get('late_choice_latch'):self.patch(self.r['ds'],0x1FD0,self.c['late_choice_latch'],'choice-latch',word=False)
            phase=self.c.get('controller_patch')
            delta=2 if phase in ('choice','sample') else 4 if phase=='axes' else None
            if delta is not None and 'controller-return' not in self.providers and ((phase=='choice' and not self.charged) or (phase=='sample' and self.axis_cursor==len(seq)) or (phase=='axes' and self.charged)):
                self.patch(self.r['ss'],(self.r['sp']-delta)&0xFFFF,0xD234,'controller-return')
        elif self.c['entry'] in ('scale','controller','mode','screen'):
            crtc=self.c.get('crtc',0x3D4)
            check(port==((crtc&0xFF00)|((crtc+6)&255)),'unexpected display-status byte port')
            count=self.display_cursor;self.display_cursor+=1
            samples=(0,8,8,0);v=samples[count%4];self.cursor+=1
            if self.c.get('selection_from_state'):
                check(self.cursor<=76,'finite held-key repeat schedule exhausted')
                self.emit('in',port,v,flags,mask);return v
            if self.c.get('screen_patch')=='wait' and get16(self.memory,self.r['ss'],(self.r['sp']-2)&0xFFFF)==0x4A28 and 'screen-return' not in self.providers:
                self.patch(self.r['ss'],(self.r['sp']-2)&0xFFFF,0xD234,'screen-return')
            active=self.c['entry']!='screen' or get16(self.memory,self.r['ss'],(self.r['sp']-2)&0xFFFF) in (0x4A31,0x4AA2)
            if count%4==3 and active:
                chars=self.c.get('selection_chars',(0x32,));index=self.selection_cursor;self.selection_cursor+=1
                check(index<len(chars),'finite menu input exhausted')
                self.patch(self.r['ds'],0xF79,0x94,'scale-state',word=False)
                self.patch(self.r['ds'],0x202F,chars[index],'scale-character',word=False)
                if self.c.get('scale_patch')=='wait':self.patch(self.r['ss'],(self.r['sp']-2)&0xFFFF,0xD234,'scale-return')
        else:raise base.OracleFailure('unexpected keyboard IN')
        self.emit('in',port,v,flags,mask)
        if port==0x64 and self.c.get('patch')=='wait' and 'return' not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']-(14 if self.c['entry']=='irq' else 4))&0xFFFF,0xD234,'return')
        if port==0x64 and self.c.get('patch')=='saved-ax':self.patch(self.r['ss'],(self.r['sp']-2)&0xFFFF,0xABCD,'saved-ax')
        return v
    def out(self,port,v,flags,mask=base.FLAGS):
        self.emit('out8',port,v,flags,mask)
        if port==0x201:self.charged=True
        if port==0x61 and 'raw_save' in self.c:self.patch(self.r['ss'],(self.r['sp']-10)&0xFFFF,self.c['raw_save'],'raw-save')
        if port==0x20 and 'late_controller' in self.c:self.patch(self.r['ds'],0x200A,self.c['late_controller'],'controller',word=False)
        if ((port==0x20 and self.c.get('patch')=='eoi') or (port==0x64 and self.c.get('patch')=='command')) and 'return' not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']-10)&0xFFFF,0xD234,'return')
    def out_word(self,port,v,flags,mask=base.FLAGS):
        self.emit('out',port,v,flags,mask)
        if self.c.get('screen_patch')=='clear' and 'screen-return' not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']-2)&0xFFFF,0xD234,'screen-return')
        if self.c.get('screen_patch')=='display' and port==self.c.get('crtc',0x3D4) and 'screen-return' not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']-2)&0xFFFF,0xD234,'screen-return')
        if port in (0x3C4,0x3CE):self.device.out(port,v,flags)
        else:check(port==self.c.get('crtc',0x3D4),'unexpected constructed CRTC port')
        if port in (0x3C4,0x3CE) and self.c.get('controller_patch')=='glyph' and 'controller-return' not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']-10)&0xFFFF,0xD234,'controller-return')
        if self.c.get('controller_patch')=='swap' and 'controller-return' not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']-2)&0xFFFF,0xD234,'controller-return')


class Machine(base.OriginalMachine):
    def __init__(self,c,memory,r,device,core):
        self.child_status=0;far_frames=[]
        def far_expected(m,off):
            check(bool(far_frames),'unexpected far return')
            return {(c['load'],far_frames.pop())}
        def before(m,i):
            if c['entry']=='screen' and c.get('missing_word_out') and i.address==0x4DF8:
                m.child_status=2;m.stop(3);return True
            if i.mnemonic=='lcall':far_frames.append(i.address+i.size)
            if c['entry'] in ('scale','controller','mode','screen') and i.address==0x4401:m.stop(0);return True
            if i.mnemonic=='out' and i.operands[-1].size==2 and c.get('missing_word_out'):
                m.child_status=1;m.stop(3);return True
            missing=(i.mnemonic=='in' and c.get('missing_in')) or (i.mnemonic=='out' and i.operands[-1].size==1 and c.get('missing_out'))
            if not missing:return False
            if c['entry'] in ('wait','command'):m.stop(1)
            elif c['entry']=='screen' and i.address in palette.INS:
                m.child_status=1 if i.mnemonic=='in' else 2;m.stop(3)
            elif i.address in (0x17C0,0x17BA,0x18B4,0x1557,0x155C) or c['entry'] in ('controller','mode','screen'):m.child_status=1;m.stop(3)
            else:m.stop(1 if i.mnemonic=='in' else 2)
            return True
        def changed(m,off):
            if off==0x8821:m.child_status=2;return (3,0)
            if off==0x7EB1:return (4,0)
            if c['entry']=='screen' and off in palette.INS and off not in (0x5600,0x563D) and m.state()['sp']!=r['sp']:
                m.child_status=5;return (3,0)
            if off==0x17C6:
                if c['entry']=='irq':m.child_status=2;return (3,0)
                return (2,0)
            if off==0x43CD:m.child_status=2;return (3,0)
            if off==0x4C46:
                if c['entry']=='screen' and m.state()['sp']==r['sp']:return (4,0)
                m.child_status=2;return (3,0)
            if off==0x4DC1:m.child_status=2;return (3,0)
            if off in INS and INS[off].mnemonic=='retf':
                m.child_status=2 if c['entry']=='screen' else 1;return (3,0)
            if off in (0x99E7,0x9A0B,0x9A14,0x9A8E):m.child_status=1;return (3,0)
            return (4,0)
        def interrupt(m,number):
            check(number==0x21,'unexpected keyboard interrupt')
            m.software_interrupt(number,m.state()['ip'],BINDING,dos_provider(c))
            if m.stopped:m.status={1:5,2:6,3:7}[m.status]
        super().__init__(c,memory,r,device,core,instructions=INS if c['entry'] in ('controller','mode','screen') else BASE_INS,access=Access(c,memory,r,device),
            outer_returns={0x4D2D,0x4D4C} if c['entry']=='reader' else {RET[c['entry']]},
            child_returns={0x17C6:{0x17B9},0x17BD:{0x16E9,0x17AF},0x18B6:{0x17A3},0x1561:{0x4AA2,0x4A31,0x4A28,0x55F1,0x55F4,0x55F7,0x5634},0x4D2D:{0x4AA5,0x4A34},0x4D4C:{0x4AA5,0x4A34},
                0x43ED:{0x4A5B},0x4358:{0x4A73},0x4385:{0x4A8B},0x43CD:{0x4341,0x4366},0x4D77:{0x4A55,0x4A9C,0x4A14,0x4A22},
                0x4DC1:{0x4D70},0x4C46:{0x4C27,0x4A2B},0x4C31:{0x4A58,0x4A9F},
                0x99E7:{0x884F},0x9A0B:{0x884F},0x9A14:{0x884F},0x9A8E:{0x885E},0x4E36:{0x4A04},0x4C16:{0x4A07},0x4DEE:{0x4A25},0x7EB1:{0x4A0D},0x5600:{0x4A0A,0x4A2E},0x563D:{0x4A0A,0x4A2E},
                0x5446:{0x55E4},0x5506:{0x5627},0x566B:{0x55EC},0x570B:{0x562F},
                0x5684:{0x564E},0x5695:{0x5657},0x56E1:{0x5660,0x567C,0x5691},0x571E:{0x56ED,0x56F8,0x5703},0x5725:{0x56ED,0x56F8,0x5703}},
            max_steps=2_000_000 if c['entry']=='screen' else MAX_STEPS,before=before,interrupt=interrupt,changed_return_status=changed,mutable_operands=((0x16D9,2),),
            far_returns={p:far_expected for p,i in INS.items() if i.mnemonic=='retf'} if c['entry'] in ('controller','mode','screen') else None)
    def run(self):
        out=super().run();out.update(child_status=self.child_status,service_status=self.service_status,
            services=self.access.service_events,transport_events=self.access.transport_events)
        return out


class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'keyboard-{mutation}.dll',mutation,'keyboard_input')))
        self.functions={}
        for entry,prefix in (('irq','lmn_keyboard_irq'),('install','lmn_install_keyboard'),('wait','lmn_wait_keyboard_controller'),('command','lmn_send_keyboard_command')):
            for core in (True,False):
                fn=getattr(self.lib,prefix+('_core' if core else '_adapter'))
                fn.argtypes=[base.MEM,ct.POINTER(base.Regs)]+([ct.POINTER(base.InterruptService)] if entry=='install' else [ct.POINTER(base.Ports)])+[ct.POINTER(base.Bus)]
                fn.restype=Result if entry in ('irq','install') else PortResult;self.functions[entry,core]=fn
        self.poll=poll.Native(directory,library=self.lib)
        for core in (True,False):
            fn=getattr(self.lib,'lmn_read_keyboard_character'+('_core' if core else '_adapter'))
            fn.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.POINTER(base.Bus)];fn.restype=Result
            self.functions['reader',core]=fn
            fn=self.lib.lmn_select_input_scale
            fn.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.POINTER(base.Ports),ct.POINTER(base.Bus)];fn.restype=Result
            self.functions['scale',core]=fn
            fn=getattr(self.lib,'lmn_choose_input_controller'+('_core' if core else '_adapter'))
            fn.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.POINTER(base.Ports),ct.POINTER(base.Bus)];fn.restype=Result
            self.functions['choice',core]=fn
            fn=self.lib.lmn_select_input_controller
            fn.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.POINTER(base.Ports),ct.POINTER(base.Bus)];fn.restype=Result
            self.functions['controller',core]=fn
            fn=self.lib.lmn_select_input_mode
            fn.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.POINTER(base.Ports),ct.POINTER(base.Bus)];fn.restype=Result
            self.functions['mode',core]=fn
            fn=self.lib.lmn_show_input_selection
            fn.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.POINTER(base.Ports),ct.POINTER(base.Bus)];fn.restype=Result
            self.functions['screen',core]=fn
    def run(self,c,memory,r,device,core,*,copy_state=True):
        if copy_state:memory,device=bytearray(memory),copy.deepcopy(device)
        access=Access(c,memory,r,device);cb=base.NativeCallbacks(access,missing_in=c.get('missing_in'),missing_out=c.get('missing_out'))
        if c.get('missing_word_out'):cb.bus.out_word=base.OUT()
        ptr=ct.byref(cb.ports);fn=service=None
        if c['entry']=='install':
            ptr=ct.POINTER(base.InterruptService)();body=dos_provider(c)
            if body:fn=cb.interrupt(body);service=base.InterruptService(None,fn,*BINDING);ptr=ct.pointer(service)
        args=[(ct.c_uint8*base.SIZE).from_buffer(memory),ct.byref(base.Regs(**r))]
        if c['entry']!='reader':args.append(ptr)
        out=self.functions[c['entry'],core](*args,ct.byref(cb.bus))
        return dict(regs={n:getattr(out.registers,n) for n in base.REG_NAMES},status=out.status,
            child_status=getattr(out,'child_status',0),service_status=getattr(out,'service_status',0),
            memory=memory,device=access.device,events=access.events,providers=access.providers,cursor=access.cursor,services=access.service_events)


def independent(c,memory,r,ref,core):
    if ref['status']:return
    out=ref['regs'];entry=c['entry'];ds=r['ds']
    if entry in ('mode','screen'):
        check(out['ip']==0x4401 and out['sp']==r['sp'] and ref['memory'][physical(ds,0x25A6)]==c.get('mode_expected',2),'input mode/continuation/frame differs')
        if entry=='screen':
            check((get16(ref['memory'],ds,0x66F0),get16(ref['memory'],ds,0x66F2),get16(ref['memory'],ds,0x66F4))==(350,640,80),'screen layout fields differ')
            if c.get('mode_expected',2)==2:
                check((get16(ref['memory'],ds,0x1F76),get16(ref['memory'],ds,0x1F78),get16(ref['memory'],ds,0x1F7A))==(0,0x6D60,0),'screen page origins differ')
                check(all(plane[:0x6D60]==plane[0x6D60:0xDAC0] for plane in ref['device'].planes),'screen copy did not preserve all four planes')
            if 'screen_gate' in c:check('screen-gate' in ref['providers'],'live prompt gate provider was not consumed')
        return
    if entry=='choice':
        latch=c.get('latch',0);seq=c.get('choice_samples',(0xEF,))
        if latch==0x77 or c.get('late_choice_latch'):
            selected=2;v=0x77;count=0 if latch==0x77 else 1
        else:
            count=next(i+1 for i,b in enumerate(seq) if (~b)&0xF0)
            v=(~seq[count-1])&255;selected=0 if v&0x30 else 1
        check(out['cx']==((r['cx']&0xFF00)|selected) and out['ax']==((r['ax']&0xFF00)|v) and ref['cursor']==count,'choice AL/CH/CL/count differs')
        if count:check(out['flags']&0x200 and out['dx']==0x201,'choice STI/DX differs')
        return
    if entry=='controller':
        check(out['ip']==0x4401 and out['sp']==r['sp'],'controller continuation/frame differs')
        keyboard=c.get('latch')==0x77
        check(ref['memory'][physical(ds,0x25A6)]==(2 if keyboard else 1),'controller mode differs')
        if not keyboard:
            high=not ((~c.get('choice_samples',(0xEF,))[0])&0x30)
            check(get16(ref['memory'],ds,0x25A0)==(0x4359 if high else 0x4334),'controller callback differs')
            samples=c.get('axis_samples',(15,0));bits=(4,8) if high else (1,2)
            totals=tuple(sum(bool(v&bit) for v in samples) for bit in bits)
            check((get16(ref['memory'],ds,0x25A2),get16(ref['memory'],ds,0x25A4))==totals,'calibration baselines differ')
        return
    if entry=='scale':
        value=next(v for v in c.get('selection_chars',(0x32,)) if 0x31<=v<=0x34)
        check(ref['memory'][physical(ds,0x2005)]==value-0x30 and out['ip']==0x4401 and
              out['sp']==r['sp'],'menu scale value/continuation/frame differs')
        return
    if entry=='reader':
        expected=bytearray(memory);selected=None
        for i in range(83):
            at=physical(ds,0xF78+i);v=expected[at]
            if not v&128:continue
            if i==3 and 'reader_late' in c:v=c['reader_late']
            countdown=((v&127)-1)&255
            expected[at]=0x86 if countdown==0 else countdown|128
            if countdown in (0,0x13):selected=i;break
        if ds!=0xA000:
            check(all(ref['memory'][physical(ds,0xF78+i)]==expected[physical(ds,0xF78+i)] for i in range(83)),'independent repeat array differs')
            value=255 if selected is None else expected[physical(ds,0x202E+selected)]
            check(out['ax']==(r['ax']&0xFF00)|value,'reader AL/AH differs')
            check(out['cx']==(0 if selected is None else 83-selected),'reader scan extent differs')
        check(out['si']==0xF78 and out['bx']==(83 if selected is None else 0x202E),'reader cursors differ')
        if not core:check(out['ip']==get16(ref['memory'],r['ss'],r['sp']) and out['sp']==(r['sp']+2)&65535,'reader actual RET differs')
        return
    if entry in ('wait','command'):
        count=65536 if c.get('busy') else next(i+1 for i,v in enumerate(c.get('samples',(0,0))) if not v&2)
        check(ref['cursor']==count and out['cx']==(-count)&0xFFFF,'LOOPNE count/CX differs')
        if entry=='command':
            value=0xABCD if c.get('patch')=='saved-ax' else r['ax']
            check(out['ax']==value and out['flags']&0x200,'actual savedAX/unconditionalSTI differs')
        return
    if entry=='install':
        first=ref['services'][0];frame=first['returned']['ds'];ip,cs=first['queried_vector']
        writes=[e[:3] for e in ref['events'] if e[0]=='write']
        # The query provider can own additional frame writes before these stores.
        packet=[('write',physical(frame,0x1FBC)+d,(cs>>(8*d))&255) for d in range(2)]
        packet += [('write',physical(frame,0x1FBA)+d,(ip>>(8*d))&255) for d in range(2)]
        check(any(writes[i:i+4]==packet for i in range(len(writes)-3)),'query vector stores must use returnedDS, segment first')
        check(get16(ref['memory'],0,0x24)==0x16D4 and get16(ref['memory'],0,0x26)==r['cs'],'installed IVT09 differs')
        check(out['flags']&0x200,'installer STI differs');return
    packets=[e[:3] for e in ref['events'] if e[0]=='out8'];ack=c.get('ack',0x35)
    expected=[('out8',0x61,ack|0x80),('out8',0x61,ack&0x7F),('out8',0x20,0x20)]
    if c['controller']:expected.insert(0,('out8',0x64,0xAD))
    if c.get('late_controller',c['controller']):expected.append(('out8',0x64,0xAE))
    check(packets==expected,'keyboard acknowledge/command packet differs')
    if not c.get('ss')==ds:
        raw=c.get('raw_save',c['raw'])&255;scan=raw&127;release=bool(raw&128)
        special=c['suppression']==255 and scan in (125,126)
        lookup=0 if special else scan;lookup_release=False if special else release
        mapping=list(c.get('bindings',BINDINGS))
        if c.get('late_binding'):mapping[0]=0x20
        mask=c.get('keymask',0xA55A);latch=0 if release or special else scan;buttons=c.get('buttons',0xBEEF)
        if special:
            bit=2 if scan==125 else 1
            buttons=(buttons&~bit) if release else (buttons|bit)
        match=next((i for i,v in enumerate(mapping) if v!=255 and v==lookup),None)
        if match is not None:
            if lookup_release:mask&=~(1<<match);latch=0
            else:mask|=1<<match
        check(get16(ref['memory'],ds,0x1FC7)==mask,'independent binding mask differs')
        check(get16(ref['memory'],ds,0x14)==buttons,'independent special buttons differ')
        check(ref['memory'][physical(ds,0x1FD0)]==latch,'independent scan latch differs')
        for i in range(83):
            value=(0 if release else 0x94) if i==scan else memory[physical(ds,0xF78+i)]
            check(ref['memory'][physical(ds,0xF78+i)]==value,'independent key-state array differs')
        saved=dict(r)
        if core:saved['ip']=0x17B3
        else:saved.update(ip=HARDWARE[0],cs=HARDWARE[1],flags=HARDWARE[2],sp=(r['sp']+6)&0xFFFF)
        for name in base.REG_NAMES:
            if core and name=='flags':continue
            check(out[name]==saved[name],'IRQ saved state differs: '+name)


def compare(native,c,core):
    memory,r,device=setup(c)
    ref=Machine(c,bytearray(memory),dict(r),copy.deepcopy(device),core).run()
    check((ref['status'],ref['child_status'],ref['service_status'])==(c.get('expected',0),c.get('child_status',0),c.get('service_status',0)),c['name']+': unexpected stop')
    independent(c,memory,r,ref,core)
    if c.get('spill'):spill_expected(c,ref)
    if native:base.compare_states(c['name'],native.run(c,memory,r,device,core),ref)
    return ref


def hashes():
    paths=set(poll.hashes())|{'tests/keyboard_input.py','c/keyboard_input.c','c/keyboard_input.h','src/entry_services.asm','src/image_tail.asm',
        'src/game_code_late_after_decimal.asm','src/input_menu_and_retry.asm','c/display_status.c','c/display_status.h'}
    paths|=FIXTURE_SOURCES
    paths|={'c/'+n+suffix for n in (*text.glyph.SOURCES,'text_stream','display_start','background_drawing','display_setup','drawing_layout','display_pages','vga_clear','palette_transition','palette_rows','palette_channels','palette_ports') for suffix in ('.c','.h')}
    paths|={'src/planar_drawing.asm'}
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def handoff(native,load):
    """Installation -> make/break IRQ -> input polling, preserving actual RAM.

    Hardware entry and the caller's near-call frames are explicit boundaries.
    """
    c=dict(name=f'handoff-{load:04x}',entry='install',load=load,seed=load,flags=0xD7,
           raw=0x10,suppression=0,controller=0,keymask=0,bindings=PINNED_BINDINGS,character_fixture=True)
    memory,r,device=setup(c);stages=[]
    ref=Machine(c,bytearray(memory),dict(r),copy.deepcopy(device),False).run()
    independent(c,memory,r,ref,False)
    actual=native.run(c,memory,r,device,False) if native else None
    if actual:base.compare_states(c['name'],actual,ref)
    stages.append((c['name']+'-install',ref))
    for raw,keymask,y,button in ((0x10,1,0x2F,0),(0x90,0,0x2F,0),(0x39,0x10,0x2F,1),(0xB9,0,0x2F,0)):
        c=dict(c,entry='irq',raw=raw)
        def enter(state):
            regs=dict(state['regs'])
            for value in (regs['flags'],regs['cs'],regs['ip']):
                regs['sp']=(regs['sp']-2)&0xFFFF
                put16(state['memory'],regs['ss'],regs['sp'],value,state['device'])
            regs.update(cs=get16(state['memory'],0,0x26),ip=get16(state['memory'],0,0x24),flags=regs['flags']&~0x300)
            return regs
        saved=dict(ref['regs']);r=enter(ref)
        check((r['cs'],r['ip'])==(load,0x16D4),'installed keyboard target differs')
        ref=Machine(c,ref['memory'],r,ref['device'],False).run()
        check(ref['status']==0 and ref['regs']==saved,'IRQ did not restore interrupted state')
        check(get16(ref['memory'],0x3000,0x1FC7)==keymask,'handoff IRQ mask differs')
        if actual:
            nr=enter(actual)
            actual=native.run(c,actual['memory'],nr,actual['device'],False,copy_state=False)
            base.compare_states(c['name']+f'-irq{raw:02x}',actual,ref)
        stages.append((c['name']+f'-irq{raw:02x}',ref))
        pc=dict(c,entry='input',mode=2)
        def call_frame(state,entry_ip=0x418C):
            regs=dict(state['regs']);regs['sp']=(regs['sp']-2)&0xFFFF
            put16(state['memory'],regs['ss'],regs['sp'],regs['ip'],state['device'])
            regs['ip']=entry_ip
            return regs
        r=call_frame(ref);before=bytearray(ref['memory'])
        ref=poll.Machine(pc,ref['memory'],r,ref['device'],False).run()
        poll.independent(pc,before,r,ref,False)
        if actual:
            nr=call_frame(actual)
            actual=native.poll.run(pc,actual['memory'],nr,actual['device'],BINDING,False)
            base.compare_states(c['name']+f'-poll{raw:02x}',actual,ref)
        check(get16(ref['memory'],0x3000,0x10)==0x60 and get16(ref['memory'],0x3000,0x12)==y and
              get16(ref['memory'],0x3000,0x14)==button,'produced input state did not reach pointer/buttons')
        stages.append((c['name']+f'-poll{raw:02x}',ref))
    # A new make reaches the character reader, then its produced repeat count
    # feeds the menu loop without any fixture rewriting of key/table bytes.
    c=dict(c,entry='irq',raw=2)
    r=enter(ref);saved=dict(ref['regs'])
    ref=Machine(c,ref['memory'],r,ref['device'],False).run()
    check(ref['regs']==saved,'character IRQ interrupted state differs')
    if actual:
        nr=enter(actual);actual=native.run(c,actual['memory'],nr,actual['device'],False,copy_state=False)
        base.compare_states(c['name']+'-character-irq',actual,ref)
    stages.append((c['name']+'-character-irq',ref))
    c=dict(c,entry='reader');r=call_frame(ref,0x4D1A)
    ref=Machine(c,ref['memory'],r,ref['device'],False).run()
    check(ref['regs']['ax']&255==0x31 and ref['memory'][physical(0x3000,0xF7A)]==0x93,'IRQ make did not reach character reader')
    if actual:
        nr=call_frame(actual,0x4D1A);actual=native.run(c,actual['memory'],nr,actual['device'],False,copy_state=False)
        base.compare_states(c['name']+'-character',actual,ref)
    stages.append((c['name']+'-character',ref))
    c=dict(c,entry='scale',selection_from_state=True);r=dict(ref['regs'],ip=0x4A9F)
    ref=Machine(c,ref['memory'],r,ref['device'],False).run()
    check(ref['status']==0 and ref['regs']['ip']==0x4401 and ref['regs']['sp']==r['sp'] and
          ref['memory'][physical(0x3000,0xF7A)]==0x86 and ref['memory'][physical(0x3000,0x2005)]==1 and
          ref['cursor']==76,'repeat state did not reach menu scale selection')
    if actual:
        nr=dict(actual['regs'],ip=0x4A9F);actual=native.run(c,actual['memory'],nr,actual['device'],False,copy_state=False)
        base.compare_states(c['name']+'-scale',actual,ref)
    stages.append((c['name']+'-scale',ref))
    # Continue with real controller choice/calibration and then consume the
    # resulting callback, baselines and selector through the native input path.
    c=dict(c,entry='controller',selection_from_state=False,selection_chars=(0x32,),
           choice_samples=(0xEF,),axis_samples=(3,1,1,0),latch=0)
    r=dict(ref['regs'],ip=0x4A4E)
    ref=Machine(c,ref['memory'],r,ref['device'],False).run()
    check(ref['status']==0 and ref['memory'][physical(0x3000,0x25A6)]==1 and
          get16(ref['memory'],0x3000,0x25A0)==0x4334 and
          (get16(ref['memory'],0x3000,0x25A2),get16(ref['memory'],0x3000,0x25A4))==(3,1) and
          ref['memory'][physical(0x3000,0x2005)]==2,'calibration did not produce live input configuration')
    if actual:
        nr=dict(actual['regs'],ip=0x4A4E);actual=native.run(c,actual['memory'],nr,actual['device'],False,copy_state=False)
        base.compare_states(c['name']+'-controller',actual,ref)
    stages.append((c['name']+'-controller',ref))
    pc=dict(c,entry='input',mode=1,callback=0x4334,port_kind='low',samples=(3,)*128+(0,),buttons=0xCF,
            dx=ref['regs']['dx'],base_x=0x60,base_y=0x2F,baseline_x=3,baseline_y=1,scale=2)
    r=call_frame(ref);before=bytearray(ref['memory'])
    ref=poll.Machine(pc,ref['memory'],r,ref['device'],False).run()
    poll.independent(pc,before,r,ref,False)
    if actual:
        nr=call_frame(actual)
        actual=native.poll.run(pc,actual['memory'],nr,actual['device'],BINDING,False)
        base.compare_states(c['name']+'-calibrated-input',actual,ref)
    check(ref['status']==0 and (get16(ref['memory'],0x3000,0x10),get16(ref['memory'],0x3000,0x12))==(0x63,0x36),
          'calibration output did not reach pointer movement')
    stages.append((c['name']+'-calibrated-input',ref))
    return stages


SPILL_READER_CALLS=112
def spill_keyboard(native):
    """Row-54 key bytes as record bytes, on the same RAM: the code-entry
    reader 4D1A polled repeatedly over the residual records 54..56 (creation
    state; bit-7 bytes F8/FF/F6 act as held keys), then IRQ make of scan 15
    (94 into record 55 +14) and further polls. Each stage compares original
    and C over the previous stage's RAM."""
    c=[row for row in cases() if row['name']=='reader-empty'][0]|dict(name='reader-row54',runtime_ds=SPILL_DS,spill=True,
        bindings=PINNED_BINDINGS,keymask=0,seed=0x4D1A54)
    memory,r,device=setup(c)
    ref=dict(memory=bytearray(memory),regs=dict(r),device=copy.deepcopy(device))
    actual=dict(memory=bytearray(memory),regs=dict(r),device=copy.deepcopy(device)) if native else None
    stages=[];emitted=[]
    def frame(state,ip):
        regs=dict(state['regs']);regs['sp']=(regs['sp']-2)&0xFFFF
        put16(state['memory'],regs['ss'],regs['sp'],0xD00D,state['device']);regs['ip']=ip;return regs
    def poll(index,first):
        nonlocal ref,actual
        regs=dict(r) if first else frame(ref,0x4D1A);before=bytearray(ref['memory'])
        out=Machine(c,ref['memory'],regs,ref['device'],False).run()
        check(out['status']==0,c['name']+': reader stopped');independent(c,before,regs,out,False)
        if actual is not None:
            nr=dict(r) if first else frame(actual,0x4D1A)
            actual=native.run(c,actual['memory'],nr,actual['device'],False,copy_state=False)
            base.compare_states(f'{c["name"]}-poll{index:03d}',actual,out)
        ref=out;stages.append((f'{c["name"]}-poll{index:03d}',out))
        if out['regs']['ax']&255!=255:emitted.append((index,83-out['regs']['cx'],out['regs']['ax']&255))
    for index in range(SPILL_READER_CALLS):poll(index,index==0)
    # Residual bytes count down from their own value: the first emission is
    # record 55 +02 (Y low F6 at scan 03, '2'; 76h..13h takes 99 polls), then
    # +06 (scan 07, '6'), then +00 (scan 01, F8) which the pinned table
    # translates to Esc; each poll stops at its first hit.
    check(emitted[:3]==[(98,3,0x32),(99,7,0x36),(100,1,0x1B)],c['name']+f': residual emissions {emitted[:4]}')
    residual=len(emitted)
    ic=dict(c,name='reader-row54-irq-scan-15',entry='irq',raw=0x15)
    def enter(state):
        regs=dict(state['regs'])
        for value in (regs['flags'],regs['cs'],regs['ip']):
            regs['sp']=(regs['sp']-2)&0xFFFF
            put16(state['memory'],regs['ss'],regs['sp'],value,state['device'])
        regs.update(cs=c['load'],ip=0x16D4,flags=regs['flags']&~0x300);return regs
    put16(ref['memory'],ic['load'],0x16D9,SPILL_DS)
    regs=enter(ref);saved=dict(ref['regs']);before=bytearray(ref['memory'])
    out=Machine(ic,ref['memory'],regs,ref['device'],False).run()
    check(out['status']==0 and out['regs']==saved,ic['name']+': IRQ did not restore interrupted state')
    spill_expected(ic,out)
    if actual is not None:
        nr=enter(actual);actual=native.run(ic,actual['memory'],nr,actual['device'],False,copy_state=False)
        base.compare_states(ic['name'],actual,out)
    ref=out;stages.append((ic['name'],out))
    c=dict(c,name='reader-row54-after-scan-15')
    for index in range(13):poll(index,False)
    # 94 counts 13h on its first decrement, but the poll stops at the earlier
    # residual hit (scan 06), so scan 15 ('Y') is emitted on the second poll.
    check(emitted[residual:residual+2]==[(0,6,0x35),(1,0x15,0x59)],
          c['name']+f': held scan 15 (record 55 +14) emissions {emitted[residual:residual+3]}')
    return stages


def screen_handoff(native,load):
    """Screen -> calibration -> input on actual returned RAM and device planes."""
    c=next(c for c in cases() if c['name']=='screen-controller')|dict(load=load,axis_samples=(3,1,1,0),selection_chars=(0x32,0x32))
    memory,r,device=setup(c);ds=r['ds'];before=bytearray(memory)
    ref=Machine(c,memory,dict(r),device,False).run()
    independent(c,before,r,ref,False)
    actual=native.run(c,before,r,copy.deepcopy(setup(c)[2]),False) if native else None
    if actual:base.compare_states(c['name']+'-prepared',actual,ref)
    stages=[(c['name']+f'-prepared-{load:04x}',ref)]
    check((get16(ref['memory'],ds,0x25A2),get16(ref['memory'],ds,0x25A4),ref['memory'][physical(ds,0x2005)])==(3,1,2),'screen calibration handoff differs')
    pc=dict(c,entry='input',mode=1,callback=0x4334,port_kind='low',samples=(3,)*128+(0,),buttons=0xCF,
            dx=ref['regs']['dx'],base_x=0x60,base_y=0x30,baseline_x=3,baseline_y=1,scale=2)
    def frame(out):
        r=dict(out['regs'],ip=0x418C,sp=(out['regs']['sp']-2)&0xFFFF)
        put16(out['memory'],r['ss'],r['sp'],0xD00D,out['device']);return r
    before=bytearray(ref['memory']);r=frame(ref)
    ref=poll.Machine(pc,ref['memory'],r,ref['device'],False).run()
    poll.independent(pc,before,r,ref,False)
    if actual:
        nr=frame(actual);actual=native.poll.run(pc,actual['memory'],nr,actual['device'],BINDING,False)
        base.compare_states(c['name']+'-screen-input',actual,ref)
    check((get16(ref['memory'],ds,0x10),get16(ref['memory'],ds,0x12))==(0x63,0x37),'prepared screen configuration did not reach input movement')
    stages.append((c['name']+f'-input-{load:04x}',ref))
    return stages


def worker(directory=None,snapshot=None):
    before=hashes()
    if snapshot:check(before==json.loads(Path(snapshot).read_text()),'keyboard snapshot changed')
    native=Native(directory) if directory else None
    rows=[];sites=set();edges=set()
    def record(name,core,ref):
        sites.update(ref['sites']);edges.update(ref['edges'])
        rows.append(dict(case=name,core=core,steps=ref['steps'],events=len(ref['events']),transport_events=ref['transport_events'],
            provider_events=sum(e.get('provider_events',0) for e in ref['services']),service_calls=len(ref['services']),
            far_return_events=ref.get('far_return_events',0)))
    for c in cases():
        for core in ((False,) if c['entry'] in ('scale','controller','mode','screen') else (True,False)):
            record(c['name'],core,compare(native,c,core))
        gc.collect()
        if (c['entry']=='irq' and c['raw']%32==0) or (c['name'].startswith(('reader-byte-','choice-byte-')) and int(c['name'][-2:],16)%32==0) or (not c['name'].startswith(('irq-scan','reader-byte','reader-index','choice-byte'))):print('CHECKED '+c['name'],flush=True)
    for name,ref in spill_keyboard(native):record(name,False,ref)
    gc.collect();print('CHECKED row-54 key-byte reader/IRQ chain',flush=True)
    for load in base.LOADS:
        for name,ref in handoff(native,load):record(name,False,ref)
        for name,ref in screen_handoff(native,load):record(name,False,ref)
        gc.collect();print(f'CHECKED same-RAM keyboard/input handoff{load:04x}',flush=True)
    check(set(OWN)<=sites,'keyboard sites missing: '+str(sorted(set(OWN)-sites)))
    check(EDGES<=edges,'keyboard outcomes missing: '+str(sorted(EDGES-edges)))
    mutations=[]
    if native:
        lookup={c['name']:c for c in cases()}
        for mutation,name in ((1,'wait-counter-exhausted'),(2,'command-clear'),(3,'irq-special-zero-lookup'),(4,'irq-scan-53-gate-00'),(5,'irq-relocated-ds'),(6,'irq-eoi-return-changed'),(7,'install-query-returned-ds'),(8,'reader-reload'),(9,'reader-index-00'),(10,'reader-live-second-read'),(11,'scale-upper-then-three'),(12,'controller-high'),(13,'controller-asymmetric-low'),(14,'mode-mouse-gate-fe'),(15,'mode-escape'),(16,'screen-mouse-fe'),(17,'screen-keyboard')):
            try:compare(Native(directory,mutation),lookup[name],True)
            except base.Mismatch as error:mutations.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
            else:raise base.OracleFailure(f'keyboard mutant{mutation} survived')
            gc.collect()
    check(before==hashes(),'keyboard inputs changed')
    write_json(REPORT if native else BUILD/'keyboard-input-original-differential.json',dict(
        image='main',image_sha256=sha(base.IMAGE),own_known_bytes=sum(i.size for i in OWN.values()),
        entry_code_ranges={name:list(span) for name,span in RANGES.items()},
        known_connected_bytes=sum(ins.size for at,ins in (INS|poll.INS).items() if at not in BOUNDARY),
        case_count=len(cases())+2*len(base.LOADS),single_case_count=len(cases()),handoff_count=2*len(base.LOADS),comparison_count=len(rows),executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(OWN)&sites),
        branch_edges=sorted(edges),own_branch_edges=sorted(EDGES),instruction_steps=sum(r['steps'] for r in rows),ordered_bus_events=sum(r['events'] for r in rows),
        declared_interrupt_transport_events=sum(r['transport_events'] for r in rows),declared_provider_events=sum(r['provider_events'] for r in rows),declared_service_calls=sum(r['service_calls'] for r in rows),
        declared_far_return_events=sum(r['far_return_events'] for r in rows),
        reference_limits=dict(retf_selector_ea_wrap_sp=[0xFFFE,0xFFFF]),
        mutation_count=len(mutations),mutations=mutations,input_hashes=before,rows=rows,
        limits=dict(timeout_seconds=SECONDS,process_commit_mib=MEMORY_MIB,instructions=MAX_STEPS,events=MAX_EVENTS,screen_instructions=2_000_000,screen_events=600_000),
        scope='Keyboard16D4, controller17B4/17BE, DOS installer1562, reader4D1A, choice43CE and complete input-selection screen4A01..4AC4 with native text/glyph/renderer, EOI/input/display children; same-RAM configuration-to-input handoffs. Row-54 spill: IRQ make/break of scans 15/16/42/43/27 over records 55/56 (canonical DS19B9, records 00..62 appended), and a same-RAM 4D1A poll chain over the residual record bytes plus a scan-15 make. Screen preparation4A01..4A2D composes tested native children; enclosing menu continuation4401 remains untranslated. Declared RETF observation rejects selector-EA wrap at SPFFFE/FFFF pending an independent oracle; no scheduling/platform-body proof.'))
    print(f'PASS keyboard: {len(rows)} comparisons,{len(set(OWN)&sites)} own sites,{len(EDGES)} own outcomes,{len(mutations)} mutants',flush=True)


def main():
    if sys.argv[1:]==['--original-worker']:worker();return
    if len(sys.argv)==4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3]);return
    if sys.argv[1:]==['--original-only']:
        run_bounded([sys.executable,__file__,'--original-worker'],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True);return
    if sys.argv[1:]:raise SystemExit('usage: keyboard_input.py [--original-only]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='keyboard-input-',parent=BUILD) as directory:
        snapshot=Path(directory)/'inputs.json';write_json(snapshot,hashes())
        run_bounded([sys.executable,__file__,'--worker',str(directory),str(snapshot)],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)


if __name__=='__main__':main()

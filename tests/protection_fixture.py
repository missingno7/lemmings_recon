"""Declared media outcomes built from bounded original063E executions.

The real encoded bytes, INT1/INT3 and identified disk routine execute on the
shared engine. No plaintext view is loaded. Synthetic sectors are independent
CRC constraints, not an asset or runtime dump. Fixture replay is an explicitly
opaque provider boundary; wrapper execution and its bus remain fully compared.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
import verification as v
from common import sha
from tools.protection import derive

def decoded(a,b):return {i.address:i for i in v.MD.disasm(v.IMAGE[a:b],a)}
_,_,HANDLER,STREAM,HANDLER_ROWS=derive()
VIEWS={r['address']:bytes.fromhex(r['bytes']) for r in STREAM['instructions']+HANDLER_ROWS}
PROBE_INS=decoded(0x63E,0x66D)|decoded(0xDB3,0xDFF)
PROBE_INS.update({a:next(v.MD.disasm(raw,a)) for a,raw in VIEWS.items()})

def crc(data):
    value=0xEDC
    for byte in data:
        value^=byte<<8
        for _ in range(8):value=((value<<1)^(0x1021 if value&0x8000 else 0))&65535
    return value

def constrain(data,start,length,at,target):
    """Solve16 independent input bits for a recorded original CRC target."""
    base=crc(data[start:start+length]);basis={}
    for bit in range(16):
        sample=bytearray(data);sample[at+bit//8]^=1<<(bit%8)
        value=crc(sample[start:start+length])^base;mask=1<<bit
        while value:
            pivot=value.bit_length()-1
            if pivot not in basis:basis[pivot]=(value,mask);break
            value^=basis[pivot][0];mask^=basis[pivot][1]
    value=target^base;mask=0
    while value:
        pivot=value.bit_length()-1;v.check(pivot in basis,'CRC fixture has no solution')
        value^=basis[pivot][0];mask^=basis[pivot][1]
    for bit in range(16):
        if mask>>bit&1:data[at+bit//8]^=1<<(bit%8)
    v.check(crc(data[start:start+length])==target,'CRC fixture constraint differs')

def sectors():
    c=bytearray(512);constrain(c,0,0x20,0,0xD597)
    b=bytearray(512);b[0x3C:0x3E]=b'\xbc\x33'
    constrain(b,0,0x46,0,0x6E62);constrain(b,0,0x4E,0x4C,0x581C)
    constrain(b,0x4E,0x39,0x4E,0xBF60)
    v.check(crc(b[:0x87])==0xA9F2,'admission CRC pair differs')
    return {1:bytes(512),12:bytes(c),11:bytes(b)}
SECTORS=sectors()

class Access(v.BusAccess):
    def __init__(self,c,m,r,d):super().__init__(c,m,r,d,max_events=8_000_000,packed_events=True);self.disks=[]

def run_probe(memory,registers,outcome):
    c=dict(load=registers['cs'],seed=0);m=bytearray(memory);r=dict(registers)
    d=v.new_device(0);a=Access(c,m,r,d)
    def interrupt(machine,number):
        if number in (1,3):
            machine.hardware_interrupt(number,returns={0xDFE,0xE39},software=True);return
        v.check(number==0x13,'probe escaped declared BIOS disk domain')
        def disk(access,q):
            fn=q['ax']>>8;failed=fn==2 and outcome!=0
            v.check(len(a.disks)<64,'disk fixture budget exhausted')
            a.disks.append(dict(ax=q['ax'],bx=q['bx'],cx=q['cx'],dx=q['dx'],es=q['es']))
            if fn==2 and outcome==0:
                sector=q['cx']&255;v.check(sector in SECTORS,'unexpected sector fixture')
                v.check(q['cx']>>8==0 and q['dx']>>8==0,'fixture cylinder/head differs')
                for n,value in enumerate(SECTORS[sector]):a.patch(q['es'],q['bx']+n,value,'disk-sector',word=False)
            else:v.check(fn in (0,2),'unexpected BIOS disk request')
            q['ax']=(q['ax']&255)|(0x8000 if failed else 0)
            saved=v.get16(a.memory,q['ss'],q['sp']+4)
            a.word_write(q['ss'],q['sp']+4,(saved&~1)|int(failed),q['flags'])
            return 0
        q=machine.state()
        binding=(v.get16(a.memory,0,0x4E),v.get16(a.memory,0,0x4C))
        machine.software_interrupt(0x13,q['ip'],binding,disk)
        v.check(not machine.stopped,'declared BIOS disk service stopped')
        machine.previous=None
    # The probe owns the real input near word. Stop before its outer RET.
    outer={0xE3C,0xE49,0xE57,0xE65,0xE64}
    rets={p for p,i in PROBE_INS.items() if i.mnemonic=='ret'}
    machine=v.OriginalMachine(c,m,r,d,True,instructions=PROBE_INS,access=a,
        outer_returns=outer,child_returns={p:set(PROBE_INS) for p in rets},
        max_steps=3_000_000,interrupt=interrupt,
        execution_views=VIEWS,trap_returns={0xE39},
        writable_code={v.physical(r['cs'],n) for n in (*range(0x66D,0x98C),*range(0xD9E,0xE3A))})
    out=machine.run()
    v.check((out['regs']['flags']&1)==outcome,'original probe outcome differs')
    v.check(out['regs']['sp']==r['sp'],'probe stack depth differs')
    for n in ('cs','ds','es','ss','cx','si','di','bp'):v.check(out['regs'][n]==r[n],'probe preserved '+n+' differs')
    segment=(r['cs']+0x98)&65535;off=0x21C if segment&0xFFF>0xFDF else 12
    selected={v.physical(segment,off+n) for n in range(512)}
    v.check(all(out['memory'][p]==0 for p in selected),'original buffer cleanup differs')
    v.check(out['memory'][:20]==memory[:20],'probe IVT restoration differs')
    table=v.physical(v.get16(memory,0,0x7A),v.get16(memory,0,0x78))
    v.check(out['memory'][table:table+11]==memory[table:table+11],'probe floppy table restoration differs')
    for lo,hi in ((0x66D,0x98C),(0xD9E,0xE66)):
        at=v.physical(r['cs'],lo)
        v.check(out['memory'][at:at+hi-lo]==memory[at:at+hi-lo],'probe code restoration differs')
    return out,a.disks,selected

class Fixture:
    """One exact original outcome for one declared caller packet and memory."""
    def __init__(self,m,r,outcome):
        self.entry=dict(r);self.out,self.disks,self.selected=run_probe(m,r,outcome)
        self.outcome=outcome
        self.changes=[(i,b) for i,b in enumerate(self.out['memory']) if b!=m[i] and i not in self.selected]
        # No persistent change outside stack and the selected sector buffer.
        stack={v.physical(r['ss'],r['sp']-n) for n in range(1,256)}
        v.check(all(p in stack for p,_ in self.changes),'unexpected probe persistent effect')
    def apply(self,a,r,*,clear):
        v.check(r==self.entry,'media fixture caller packet differs: '+str({n:(r[n],self.entry[n]) for n in r if r[n]!=self.entry[n]}))
        for p,b in self.changes:
            a.patch(p>>4,p&15,b,'media-outcome',word=False)
        r.update(self.out['regs'])
        if clear:
            # Externally projected final clear; opaque internal traffic is
            # separately retained in original-run evidence, not wrapper traces.
            for p in sorted(self.selected):
                a.access('write',p,r['flags'],value=0)
                if a.sync:a.sync(p,b'\0');a.sync(p+v.SIZE,b'\0')
        return self.outcome
    def evidence(self):
        return dict(outcome=('PASS','FAIL')[self.outcome],steps=self.out['steps'],
            events=len(self.out['events']),sites=sorted(self.out['sites']),disks=self.disks,
            output_sha256=sha(self.out['memory']),entry=self.entry,returned=self.out['regs'])

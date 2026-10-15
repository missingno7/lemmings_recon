"""Bounded original drawing callers with explicit known far-call frames.

Executes pinned instructions in Unicorn; no target opcode or return is patched.
Far RETF observation uses the same isolated read-hook workaround as the terrain
oracle. Callers provide their complete allowed instruction map and far CALL PCs.
"""
import hashlib
import struct
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
    UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INSN, UC_HOOK_INTR)
import terrain_drawing as piece
from unpack import relocated

oracle=piece.oracle
render=piece.render
aligned=piece.aligned
x=piece.x
common=piece.common
FAMILIES=piece.FAMILIES
check_device=piece.check_device


class DeviceTrace:
    """Stream device order; exact phase flags also live in the whole-bus trace."""
    def __init__(self):
        self.count=0
        self.digest=hashlib.sha256()

    def append(self,item):
        if self.count>=common.MAX_VGA_EVENTS:
            raise common.GuardExhaustion('drawing caller VGA event budget exhausted')
        kind,address,value,flags=item
        self.digest.update(struct.pack('<BIHH',
            {'read':0,'write':1,'out':2,'outb':3,'inb':4}[kind],
            address,value,flags&0x600))
        self.count+=1

    def __len__(self):return self.count

    def signature(self):return self.count,self.digest.hexdigest()


def original(case,device,regs,flags,*,instructions,far_calls,
             continuations=(),observe=None,stop_before=None,max_steps=2_000_000,
             interrupt=None,trace_instruction=None,phase_flags=None,
             defined_mask_after=None):
    INS=instructions
    BRANCHES={p for p,i in INS.items() if i.group(piece.capstone.CS_GRP_JUMP)
              or i.mnemonic.startswith('loop')}
    MAX_STEPS=max_steps
    loaded=relocated(piece.IMAGE,piece.ORACLE['relocations'],regs['cs'])
    code_values={(((regs['cs']<<4)+p+n)&0xfffff):loaded[p+n]
                 for p,i in INS.items() for n in range(i.size)}
    if any(device.memory[p]!=value for p,value in code_values.items()):
        raise common.VerificationFailure('Drawing caller entered with modified decoded code')
    u=Uc(UC_ARCH_X86,UC_MODE_16)
    u.mem_map(0,2<<20)
    u.mem_write(0,bytes(device.memory)*2)
    for n,reg in oracle.REG.items():u.reg_write(reg,regs[n])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags)
    seen,edges=set(),set()
    previous=None
    last=None
    mask=0xfd7
    event_flags=flags
    steps=0
    frames=[]
    pending_near=None
    pause=None
    boundary=None
    failure=[]
    child_entry=None
    body_entry=None
    body_memory=None
    body_planes=None
    body_address=None

    def fail(message):
        if not failure:failure.append(message)
        u.emu_stop()

    def code(uc,pc,_size,_):
        nonlocal previous,last,mask,event_flags,steps,pending_near,pause,boundary
        nonlocal child_entry,body_entry,body_memory,body_planes,body_address
        cs=uc.reg_read(oracle.REG['cs'])
        off=uc.reg_read(oracle.REG['ip'])
        if last is not None:
            mask=(defined_mask_after(previous,mask) if defined_mask_after is not None
                  else render._defined_mask(last,mask))
        if pending_near is not None:
            expected=pending_near;pending_near=None
            if expected is False:
                boundary=('outer-return',cs,off);uc.emu_stop();return
            frames.pop()
            if (cs,off)!=expected:
                boundary=('changed-child-near',cs,off);uc.emu_stop();return
        # The previous branch has executed even when this destination is a
        # stop-before-instruction continuation. Record its edge, not a site
        # execution for the destination.
        if previous in BRANCHES:edges.add((previous,off))
        if cs==regs['cs'] and off in continuations:
            boundary=('continuation',cs,off);uc.emu_stop();return
        if cs!=regs['cs'] or off not in INS:
            fail(f'{case["name"]}: original escaped at{cs:04x}:{off:04x};last={last},previous={previous},frames={frames}');return
        if stop_before is not None and off==stop_before:
            boundary=('ready-return',cs,off);uc.emu_stop();return
        ins=INS[off]
        event_flags=uc.reg_read(x.UC_X86_REG_EFLAGS)
        # Optional instruction-specific normalization must be independently
        # evidenced by the caller. Existing oracles retain their raw behavior.
        # In particular37B4/37B6..37B8 may need the pinned REP/POP AF probe.
        if phase_flags is not None:
            event_flags=phase_flags(off,uc,event_flags)
        if observe is not None:
            observe(off,uc,device)
        steps+=1
        if steps>MAX_STEPS:fail('original step budget exhausted');return
        seen.add(off)
        previous=off;last=ins.mnemonic
        if off==0x8822:
            child_entry={n:uc.reg_read(r) for n,r in oracle.REG.items()}
            child_entry['flags']=event_flags
        if off in FAMILIES and body_entry is None:
            body_address=off
            body_entry={n:uc.reg_read(r) for n,r in oracle.REG.items()}
            body_entry['flags']=event_flags
            body_memory=bytes(device.memory)
            body_planes=[bytearray(p) for p in device.vga.planes]
        if off in far_calls:
            frames.append((cs,off+ins.size))
        elif ins.mnemonic=='call':
            frames.append((cs,off+ins.size))
        elif ins.mnemonic=='retf':
            pause=(cs,off,event_flags);uc.emu_stop()
        elif ins.mnemonic=='ret':
            pending_near=frames[-1] if frames else False

    def read(uc,_access,address,size,_value,_):
        for n in range(size):
            raw=address+n;p=raw&0xfffff
            try:
                value=device.vga.read(device.memory,p,event_flags)
                if trace_instruction is None or trace_instruction(previous):
                    device.events.add('read',p,value,event_flags,mask)
                # Ordinary RAM is already synchronized by the write hook.
                # Device reads and the duplicate A20 mapping need injection.
                if 0xa0000<=p<0xb0000 or raw>=1<<20:
                    uc.mem_write(raw,bytes((value,)))
                check_device(device,'original read')
            except BaseException as error:fail(str(error));return

    def write(uc,_access,address,size,value,_):
        for n in range(size):
            raw=address+n;p=raw&0xfffff;byte=(value>>(8*n))&255
            if p in code_values and byte!=code_values[p]:
                fail(f'decoded instruction byte modified at physical{p:05x}')
                return
            try:
                device.vga.write(device.memory,p,byte,event_flags)
                if trace_instruction is None or trace_instruction(previous):
                    device.events.add('write',p,byte,event_flags,mask)
                if raw>=1<<20:uc.mem_write(p,bytes((byte,)))
                check_device(device,'original write')
            except BaseException as error:fail(str(error));return

    fixture=aligned.BytePortFixture()
    def out(uc,port,size,value,_):
        try:
            if size==2:
                device.vga.out(port,value,event_flags)
                device.events.add('out',port,value,event_flags,mask)
            elif size==1:
                fixture.out_byte(device.vga,port,value,event_flags)
                device.events.add('outb',port,value,event_flags,mask)
            else:raise common.VerificationFailure('unsupported output width')
            check_device(device,'original output')
        except BaseException as error:fail(str(error))

    def inp(uc,port,size,_):
        try:
            if size!=1:raise common.VerificationFailure('unsupported input width')
            value=fixture.in_byte(device.vga,port,event_flags,{})
            device.events.add('inb',port,value,event_flags,mask)
            check_device(device,'original input')
            return value
        except BaseException as error:fail(str(error));return 0

    code_hook=u.hook_add(UC_HOOK_CODE,code)
    read_hook=u.hook_add(UC_HOOK_MEM_READ,read)
    u.hook_add(UC_HOOK_MEM_WRITE,write)
    u.hook_add(UC_HOOK_INSN,out,None,1,0,x.UC_X86_INS_OUT)
    u.hook_add(UC_HOOK_INSN,inp,None,1,0,x.UC_X86_INS_IN)
    def intr(uc,num,_):
        nonlocal mask
        try:
            if interrupt is None:
                raise common.VerificationFailure(f'unexpected INT{num:02x}')
            interrupt(uc,num,device)
            # Declared DOS fixtures return every modeled status flag explicitly.
            mask=0xfd7
            if any(device.memory[p]!=value for p,value in code_values.items()):
                raise common.VerificationFailure('DOS provider modified decoded code')
        except BaseException as error:fail(str(error))
    u.hook_add(UC_HOOK_INTR,intr)
    while boundary is None and not failure:
        pc=(u.reg_read(oracle.REG['cs'])<<4)+u.reg_read(oracle.REG['ip'])
        u.emu_start(pc,0,count=MAX_STEPS-steps+1)
        if pause is None:
            if boundary is None and not failure:fail('original instruction budget exhausted')
            break
        cs,ip,ret_flags=pause;pause=None
        if not frames:fail('far return without a known caller frame');break
        expected=frames.pop()
        ss=u.reg_read(oracle.REG['ss']);sp=u.reg_read(oracle.REG['sp'])
        # Record original bus-visible words, then execute the original RETF
        # without its read hook. No opcode or target is patched. Word high bytes
        # use physical+1; SP wraps only between the two words.
        for word in range(2):
            offset=(sp+2*word)&65535
            for n in range(2):
                raw=(ss<<4)+offset+n;p=raw&0xfffff
                value=device.vga.read(device.memory,p,ret_flags)
                device.events.add('read',p,value,ret_flags,mask)
                u.mem_write(raw,bytes((value,)))
        check_device(device,'original far-return reads')
        u.hook_del(code_hook);u.hook_del(read_hook)
        u.ctl_remove_cache(0,2<<20)
        u.emu_start((cs<<4)+ip,0,count=1)
        actual=(u.reg_read(oracle.REG['cs']),u.reg_read(oracle.REG['ip']))
        code_hook=u.hook_add(UC_HOOK_CODE,code)
        read_hook=u.hook_add(UC_HOOK_MEM_READ,read)
        u.ctl_remove_cache(0,2<<20)
        if actual!=expected:boundary=('changed-child-far',*actual)
    if failure:raise common.VerificationFailure(f'{case["name"]}: {failure[0]}')
    device.check(case['name'])
    result={n:u.reg_read(r) for n,r in oracle.REG.items()}
    result['flags']=u.reg_read(x.UC_X86_REG_EFLAGS)
    return result,mask,seen,edges,boundary,child_entry,(body_address,body_entry,body_memory,body_planes)


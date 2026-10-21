"""Independent generated VGA bus traces and host platform known answers."""
import ctypes as ct
import gc
import random
import sys
import time
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools')]
from bounded_process import run_bounded,temporary_build_directory
from common import BUILD,write_json,sha
from host_support import Host,Event,ROOT,v,sources,loop as g
from minimap_vga import MinimapVga,fixture_vectors

def worker(directory):
    began=time.perf_counter()
    import game_loop as g
    paths={*sources(),*(ROOT/'c').glob('*.h'),ROOT/'host/platform_host.h',Path(__file__),ROOT/'tests/minimap_vga.py',ROOT/'tests/host_support.py',ROOT/'tools/hostbuild.py',ROOT/'assets/russell.dat'}
    before=g.input_hashes();before.update({p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in paths})
    h=Host(directory);rng=random.Random(0x564741)
    model=MinimapVga(0x510);memory=bytearray(rng.randbytes(v.SIZE))
    h.memory[:]=memory
    for p in range(4):h.vga.planes[p][:]=model.planes[p]
    for name in ('latches','seq','gc'):getattr(h.vga,name)[:]=getattr(model,name)
    h.vga.si=model.si;h.vga.gi=model.gi
    fixture_vectors()
    count=0
    for mode in range(4):
        for op in range(4):
            for rotation in range(8):
                for _ in range(24):
                    settings=((0x3c4,2,rng.randrange(16)),(0x3ce,0,rng.randrange(16)),
                        (0x3ce,1,rng.randrange(16)),(0x3ce,2,rng.randrange(16)),
                        (0x3ce,3,rotation|(op<<3)),(0x3ce,4,rng.randrange(4)),
                        (0x3ce,5,mode|rng.choice((0,8))),(0x3ce,7,rng.randrange(16)),
                        (0x3ce,8,rng.randrange(256)))
                    for port,index,value in settings:
                        # Word and equivalent byte writes must share one device.
                        if count&1:h.call('out',port,index,1);h.call('out',port+1,value,1)
                        else:h.call('out',port,index|(value<<8),2)
                        model.out(port,index|(value<<8),0)
                    p=0xa0000+rng.randrange(65536);got=h.call('read',p)
                    assert got==model.read(memory,p,0)
                    p=0xa0000+rng.randrange(65536);value=rng.randrange(256)
                    h.call('write',p,value);model.write(memory,p,value,0);count+=1
                for i in range(4):assert bytes(h.vga.planes[i])==model.planes[i],(mode,op,rotation,i)
    assert bytes(h.memory)==memory
    assert list(h.vga.latches)==model.latches
    assert list(h.vga.seq)==model.seq and list(h.vga.gc)==model.gc
    # Six-bit DAC component/index rollover, distinct read/write cursors.
    h.call('out',0x3c8,255,1)
    for value in (1,64,255,22,33,44):h.call('out',0x3c9,value,1)
    h.call('out',0x3c7,255,1)
    assert [h.call('in',0x3c9) for _ in range(6)]==[1,0,63,22,33,44]
    h.call('out',0x3d4,0x120c,2);h.call('out',0x3d4,0x340d,2)
    assert list(h.vga.crtc[12:14])==[0x12,0x34]
    assert [h.call('in',0x3da) for _ in range(8)]==[0,0,0,0,0,1,1,0]
    # Native entry, arena48 and MAIN.DAT producers; no constructor stores.
    counter=(ct.c_uint8*1)(9)
    assert h.call('file_overlay',b'russell.dat',counter,1)
    boot=h.call('boot',0x1010,b'/v /o /a',1);assert boot.status==0,h.call('error')
    assert h.call('file_overlay',b'russell.dat',None,0)
    regs=boot.registers;ds=regs.ds
    assert (regs.cs,regs.ip,regs.ss,regs.sp)==(0x1010,0x43F2,0x244E,0x4AF4)
    assert v.get16(h.memory,ds,0x1FE4)==0x3000 and v.get16(h.memory,ds,0x1FF4)==0x7971
    assert h.memory[v.physical(ds,0x25A7)]==h.memory[v.physical(ds,0x1F71)]==1
    assert v.get16(h.memory,0,32)==0x700 and v.get16(h.memory,0,34)==0xB000
    assert bytes(h.memory[v.physical(0x1010,0x98C):v.physical(0x1010,0xB8C)])==bytes(512)
    assert v.get16(h.memory,0x1010,0xD9C)==0x9090
    assert v.get16(h.memory,ds,0x1FF6)==0x1000
    for off,expected in ((0x201F,g.session.keyboard.PINNED_BINDINGS),(0x202E,g.session.keyboard.PINNED_CHARACTERS)):
        p=v.physical(ds,off);assert bytes(h.memory[p:p+len(expected)])==bytes(expected)
    # Independently recorded output of59BB on pinned MAIN.DAT section0.
    assert sha(bytes(h.memory[0x40000:0x594b8]))=='6bf0c6b5568796cf2d42daf057ca95078e79136a6ab97e7b8f829d40f464e6d6'
    for segment,bank in zip((0x5f7e,0x6e9f),g.menu.animation.resource_banks()):
        assert bytes(h.memory[segment*16:segment*16+len(bank)])==bank
    platform_vectors(h,regs)
    policy_profiles(directory,h.dll)
    h.check();h.close();del h;gc.collect()
    assert before=={p:sha((ROOT/p).read_bytes()) for p in before},'host VGA inputs changed during campaign'
    write_json(BUILD/'host-vga.json',dict(accepted=True,traces=count,seconds=time.perf_counter()-began,
        input_hashes=before))
    print(f'PASS host_vga: {count} generated traces; modes0..3/read0..1, DAC/CRTC/clock/startup',flush=True)

def policy_profiles(directory,library):
    for policy,status in ((0,4),(2,7)):
        h=Host(directory,library)
        try:
            counter=(ct.c_uint8*1)(9)
            assert h.call('file_overlay',b'russell.dat',counter,1)
            boot=h.call('boot',0x1010,b'/v /o /a',policy)
            assert boot.status==status,(policy,boot.status,h.call('error'))
            if policy==0:
                assert boot.child_status==3 and boot.service_status==2
                assert boot.registers.ip==0x63E
            else:
                assert boot.registers.ip==0xF08
                assert v.get16(h.memory,boot.registers.ds,0x252A)&255==9
                assert v.get16(h.memory,0,32)==0x700 and v.get16(h.memory,0,34)==0xB000
                assert bytes(h.memory[v.physical(0x1010,0x98C):v.physical(0x1010,0xB8C)])==bytes(512)
            h.check()
        finally:h.close()

def platform_vectors(h,regs):
    class InterruptResult(ct.Structure):_fields_=[('status',ct.c_uint16),('service_status',ct.c_uint16)]
    fn=h.dll.lmn_interrupt_service
    fn.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.c_uint16,ct.c_uint16,ct.POINTER(v.InterruptService),ct.POINTER(v.Bus)]
    fn.restype=InterruptResult
    s=h.call('services').contents;memory=h.call('memory');ds=regs.ds
    def interrupt(number,service,**values):
        r=v.Regs(ax=0,bx=0,cx=0,dx=0,si=0x5123,di=0x6123,bp=0x8123,sp=0x7000,cs=regs.cs,ds=ds,es=0x6400,ss=0x9000,ip=0x4401,flags=0x202)
        for n,value in values.items():setattr(r,n,value)
        out=fn(memory,ct.byref(r),number,0x4403,service,s.bus)
        assert out.status==0 and (r.ip,r.cs,r.sp)==(0x4403,regs.cs,0x7000),(out.status,h.call('error'))
        assert (r.si,r.di,r.bp)==(0x5123,0x6123,0x8123)
        return r
    for i,value in enumerate(b'main.dat\0'):h.memory[v.physical(ds,0x600+i)]=value
    out=interrupt(0x21,s.dos,ax=0x3d00,dx=0x600);assert not out.flags&1;handle=out.ax
    out=interrupt(0x21,s.dos,ax=0x3f00,bx=handle,cx=32,dx=0xfff8)
    assert out.ax==32 and not out.flags&1
    data=(ROOT/'assets/main.dat').read_bytes()[:32]
    assert bytes(h.memory[v.physical(ds,(0xfff8+i)&65535)] for i in range(32))==data
    out=interrupt(0x21,s.dos,ax=0x3e00,bx=handle);assert out.ax==0 and not out.flags&1
    out=interrupt(0x21,s.dos,ax=0x3509);assert (out.es,out.bx)==(regs.cs,0x16d4)
    # IVT writes are canonical; an unsupported handler must not be silently
    # redirected to the usual09 target. Test IF deferral first, then restore.
    out=interrupt(0x21,s.dos,ax=0x2509,dx=0x1234,ds=0x3456)
    assert v.get16(h.memory,0,36)==0x1234 and v.get16(h.memory,0,38)==0x3456
    interrupt(0x21,s.dos,ax=0x2509,dx=0x16d4,ds=regs.cs)
    # LIFO conventional-memory allocation, resize and release.
    out=interrupt(0x21,s.dos,ax=0x4800,bx=16);assert not out.flags&1;allocated=out.ax
    out=interrupt(0x21,s.dos,ax=0x4a00,bx=8,es=allocated);assert not out.flags&1
    out=interrupt(0x21,s.dos,ax=0x4900,es=allocated);assert not out.flags&1
    # Menu installs its timer after the43F2 handoff. Execute that native child
    # before the isolated hardware-delivery vectors below.
    install=h.dll.lmn_install_menu_timer_core
    install.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.POINTER(v.Bus)];install.restype=g.menu_timer.Result
    installed=install(memory,ct.byref(regs),s.bus);assert installed.status==0
    h.call('automatic_timer',0)
    r=v.Regs.from_buffer_copy(regs);r.ip=0x4453;r.flags&=~0x200
    e=Event(h.call('time'),2,0,0,0x3b);assert h.call('enqueue',ct.byref(e))
    assert s.poll.contents.poll(s.poll.contents.context,memory,ct.byref(r),r.ip)==0
    assert h.call('inputs')==0
    r.flags|=0x200
    assert s.poll.contents.poll(s.poll.contents.context,memory,ct.byref(r),r.ip)==0
    assert h.call('inputs')==1 and h.memory[v.physical(ds,0xf78+0x3b)]==0x94
    # Mode-FF PIT cadence is reload-based; masked requests stay pending.
    h.memory[v.physical(ds,0x200e)]=255;h.call('out',0x43,0x36,1)
    h.call('out',0x40,0,1);h.call('out',0x40,0x40,1);epoch=h.call('time')
    h.call('automatic_timer',1);h.call('out',0x21,1,1)
    h.call('set_time',epoch+16384)
    assert s.poll.contents.poll(s.poll.contents.context,memory,ct.byref(r),r.ip)==0
    assert h.call('irqs')==0
    h.call('out',0x21,0,1)
    assert s.poll.contents.poll(s.poll.contents.context,memory,ct.byref(r),r.ip)==0
    assert h.call('irqs')==1

def main():
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2]);return
    with temporary_build_directory(prefix='host-vga-',parent=BUILD) as directory:
        run_bounded([sys.executable,__file__,'--worker',directory],cwd=ROOT,timeout=180,memory_mib=512,check=True)
if __name__=='__main__':main()

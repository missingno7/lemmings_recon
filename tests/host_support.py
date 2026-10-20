"""ctypes declarations for the host; no instruction or bus implementation."""
import ctypes as ct
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
import verification as v
import game_loop as loop
from hostbuild import build_host,sources

class Vga(ct.Structure):
    _fields_=[('planes',(ct.c_uint8*65536)*4),('latches',ct.c_uint8*4),
        ('seq',ct.c_uint8*5),('gc',ct.c_uint8*9),('si',ct.c_uint8),('gi',ct.c_uint8),
        ('crtc',ct.c_uint8*32),('ci',ct.c_uint8),('attr',ct.c_uint8*32),
        ('ai',ct.c_uint8),('attr_data',ct.c_uint8),('dac',(ct.c_uint8*3)*256),
        ('dac_read',ct.c_uint8),('dac_write',ct.c_uint8),('dac_component',ct.c_uint8),
        ('dac_read_component',ct.c_uint8),('pel_mask',ct.c_uint8),('mode',ct.c_uint8),
        ('word_outputs',ct.c_uint32)]
class Event(ct.Structure):
    _fields_=[('time',ct.c_uint64)]+[(n,ct.c_uint16) for n in ('kind','x','y','value')]
POLL=ct.CFUNCTYPE(ct.c_uint16,ct.c_void_p,ct.c_void_p,ct.POINTER(v.Regs),ct.c_uint16)
OBSERVE=ct.CFUNCTYPE(None,ct.c_void_p,ct.c_void_p,ct.POINTER(v.Regs),ct.c_uint16)

class Host:
    def __init__(self,directory):
        self.dll=ct.CDLL(str(build_host(Path(directory)/'host.dll',dll=True)))
        self.bind('create',[ct.c_char_p],ct.c_void_p)
        self.bind('destroy',[],None)
        self.bind('memory',[],v.MEM)
        self.bind('vga',[],ct.POINTER(Vga))
        self.bind('services',[],ct.POINTER(loop.Services))
        self.bind('error',[],ct.c_char_p)
        for name in ('time','frames','irqs','sound_requests','inputs','hash'):self.bind(name,[],ct.c_uint64)
        self.bind('set_limits',[ct.c_uint64]*3,None)
        self.bind('set_hooks',[ct.c_void_p,POLL,OBSERVE],None)
        self.bind('automatic_timer',[ct.c_int],None)
        self.bind('enqueue',[ct.POINTER(Event)],ct.c_int)
        self.bind('file_overlay',[ct.c_char_p,v.MEM,ct.c_size_t],ct.c_int)
        self.bind('set_time',[ct.c_uint64],ct.c_int)
        self.bind('deliver',[ct.POINTER(v.Regs),ct.c_uint16,ct.c_uint8],ct.c_uint16)
        self.bind('post_startup',[ct.c_uint16,ct.POINTER(v.Regs)],ct.c_int)
        self.bind('prepare_resources',[ct.POINTER(v.Regs)],ct.c_int)
        self.bind('run',[ct.POINTER(v.Regs)],loop.Result)
        self.bind('read',[ct.c_uint32],ct.c_uint8)
        self.bind('write',[ct.c_uint32,ct.c_uint8],None)
        self.bind('out',[ct.c_uint16,ct.c_uint16,ct.c_uint],None)
        self.bind('in',[ct.c_uint16],ct.c_uint8)
        self.bind('ppm',[ct.c_char_p],ct.c_int)
        self.ptr=self.dll.lmn_host_create(str(ROOT/'assets').encode())
        assert self.ptr
        self.memory=(ct.c_uint8*v.SIZE).from_address(ct.addressof(self.call('memory').contents))
        self.vga=self.call('vga').contents
    def bind(self,name,args,result):
        fn=getattr(self.dll,'lmn_host_'+name)
        fn.argtypes=([ct.c_void_p] if name!='create' else [])+args
        fn.restype=result
    def call(self,name,*args):return getattr(self.dll,'lmn_host_'+name)(self.ptr,*args)
    def check(self):assert self.call('error')==b'',self.call('error').decode()
    def close(self):self.call('destroy');self.ptr=None

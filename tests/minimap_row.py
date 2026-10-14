"""Connected eight-mask row sampler and its original live stack frames."""
from minimap_connected import run_suite,field
def cases():
    out=[]
    def add(name,**kw):out.append(dict(name=name,seed=len(out),**kw))
    for population in range(17):
        for df in (False,True):add(f'population-{population}-df-{df}',words=[(1<<population)-1]*8,df=df,samples=8)
    for si in (0,1,0xfff0,0xfffe,0xffff):add(f'source-{si:04x}',si=si,samples=8)
    for sp in (0,1,0xffff):add(f'stack-{sp:04x}',sp=sp,samples=8)
    add('SS-physical-wrap',ss=0xffff,samples=8)
    add('ES-physical-wrap',es=0xffff,si=0x000f,samples=8)
    b=field('MinimapColumnBits')
    add('saved-si-alias',cs_ss=True,sp=b+4,words=[65535]*8,restored_si=0x10ff,samples=8)
    add('saved-cx-alias',cs_ss=True,sp=b+2,words=[65535]*8,restored_cx=0x12ff,samples=8)
    add('saved-leaf-counter-extends-loop',cs_ss=True,sp=b+8,counter_alias=True,samples=260)
    add('leaf-return-alias',cs_ss=True,sp=b+6,words=[65535]*8,return_ip=0x7aaf,samples=1)
    add('outer-return-alias',cs_ss=True,sp=b,words=[65535]*8,return_ip=0xffff,samples=8)
    return out
if __name__=='__main__':run_suite('minimap_row',cases(),[(1,'population-16-df-False'),(2,'saved-si-alias'),(3,'leaf-return-alias')])

"""Connected minimap column, mode1 source reads and nineteen mode0 writes."""
from minimap_connected import run_suite,field
def cases():
    out=[]
    def add(name,**kw):out.append(dict(name=name,seed=len(out),**kw))
    for column in tuple(range(0,208,16))+(200,207,208,0x7fef,0x7ff0,0x7fff,0x8000,0xffef,0xfff0,0xffff):
        for df in (False,True):add(f'column-{column:04x}-df-{df}',column=column,df=df,samples=160)
    for sp in (0x100,1,0,0xffff):add(f'stack-{sp:04x}',sp=sp,samples=160)
    add('SS-physical-wrap',ss=0xffff,samples=160)
    add('DS-physical-wrap',ds=0xffff,samples=160)
    add('DS-code-frame',ds_cs=True,samples=160)
    for df in (False,True):add(f'DS-scratch-clear-alias-df-{df}',ds_scratch_alias=True,df=df,samples=160)
    for df in (False,True):add(f'thirteen-column-cycle-df-{df}',iterations=13,df=df,samples=2080)
    add('saved-ds-mirror-alias',sp=10,saved_ds_mirror=True,samples=160)
    add('scratch-alias-saved-ds-and-outer-ret',cs_ss=True,sp=field('MinimapColumnBits')+2,all_ones=True,restored_ds=0xffff,return_ip=0xffff,samples=160)
    add('row-return-alias',cs_ss=True,sp=field('MinimapColumnBits')+4,all_ones=True,return_ip=0x79ff,samples=8)
    add('aperture-stack-return-mode1',ss=0xa000,sp=0xe000,all_ones=True,return_ip=0,samples=1)
    add('aperture-pop-ES-zero-set-reset',ss=0xa000,sp=0xe000,all_ones=True,aperture_pop_es=True,return_ip=0,samples=1)
    return out
if __name__=='__main__':run_suite('minimap_column',cases(),[(1,'column-7ff0-df-False'),(2,'column-0000-df-False'),(3,'saved-ds-mirror-alias')])

"""Reproducible evidence for known main-image indirect callback targets.

Direct accesses and local pointer definitions are evidence, not a whole-program
alias proof. Every target domain remains explicitly incomplete until its incoming
state, bulk writes, aliases and unknown-code obligations are closed.
"""
import argparse
import capstone
from capstone import x86 as x
from common import ROOT,BUILD,read_json,write_json,sha
from unpack import unpack,ASSET
from explore import analyze

def decoded(analysis):
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);md.detail=True
    result={}
    for row in analysis['instructions']:
        ins=next(md.disasm(bytes.fromhex(row['bytes']),row['address'],count=1))
        if ins.size!=row['size']:raise ValueError('Instruction extent changed')
        result[ins.address]=ins
    return md,result

def segment(md,mem):
    if mem.segment:return md.reg_name(mem.segment)
    return 'ss' if mem.base in (x.X86_REG_BP,x.X86_REG_SP) else 'ds'

def accesses(md,ins):
    result=[]
    for op in ins.operands:
        if op.type!=x.X86_OP_MEM:continue
        result.append(dict(address=ins.address,bytes=ins.bytes.hex(),instruction=ins.mnemonic+' '+ins.op_str,
                           segment=segment(md,op.mem),base=md.reg_name(op.mem.base),
                           index=md.reg_name(op.mem.index),displacement=op.mem.disp,size=op.size,
                           access='address' if ins.mnemonic=='lea' else
                           ('read_write' if op.access==3 else 'write' if op.access==2 else 'read' if op.access==1 else 'unknown')))
    return result

def local_ax_definition(pc,ins,barriers):
    before={i.address+i.size:i for i in ins.values()}
    origin=pc
    for _ in range(32):
        if origin in barriers:return None
        prev=before.get(origin)
        if prev is None:return None
        if prev.group(capstone.CS_GRP_CALL) or prev.mnemonic in ('int','int3','ret','retf','iret'):
            return None
        _,written=prev.regs_access()
        if any(r in written for r in (x.X86_REG_AX,x.X86_REG_AL,x.X86_REG_AH,x.X86_REG_EAX)):
            return prev
        origin=prev.address
    return None

def analyze_callbacks():
    image,oracle=unpack(ASSET.read_bytes());a=analyze();md,ins=decoded(a)
    refs=[r for i in ins.values() for r in accesses(md,i)]
    direct=[r for r in refs if r['segment']=='ds' and not r['base'] and not r['index']]
    fields=[]
    for name,lo,hi in (('display_probe_records',0x2013,0x201f),
                        ('input_poll_callback',0x25a0,0x25a2),
                        ('drawing_callback_slots',0x2e,0x40),
                        ('saved_timer_vector',0x1fbe,0x1fc2)):
        matching=[r for r in direct if r['displacement']<hi and r['displacement']+r['size']>lo]
        fields.append(dict(name=name,segment_frame=0x9a9,start=lo,end=hi,
                           initial_bytes=image[0x9a90+lo:0x9a90+hi].hex(),direct_accesses=matching,
                           closure='Direct-access census of recovered main code only; actual DS values and non-absolute aliases remain pending'))
    # Original drawing slot constructor: nine consecutive MOV word [absolute],imm.
    constructors=[];slots={}
    for pc in range(0xfc1,0xff7,6):
        i=ins[pc];dst,src=i.operands
        if not (i.mnemonic=='mov' and dst.type==x.X86_OP_MEM and dst.size==2
                and not dst.mem.base and not dst.mem.index and src.type==x.X86_OP_IMM):
            raise ValueError('Drawing callback constructor changed')
        slots[dst.mem.disp]=src.imm&0xffff
        constructors.append(dict(address=pc,bytes=i.bytes.hex(),slot=dst.mem.disp,target=src.imm&0xffff))
    barriers=set(a['routines'])|{e['target'] for e in a['edges'] if e['target'] is not None and e['kind']!='fallthrough'}
    stores=[]
    for i in ins.values():
        if i.mnemonic!='mov' or len(i.operands)!=2:continue
        dst,src=i.operands
        if not (dst.type==x.X86_OP_MEM and dst.mem.base==x.X86_REG_SI and dst.mem.disp==0x14 and dst.size==2):continue
        definition=local_ax_definition(i.address,ins,barriers)
        item=dict(address=i.address,bytes=i.bytes.hex(),instruction=i.mnemonic+' '+i.op_str,
                  owner_contract='SI points into the active 2D-byte object-record array; DS is the game data frame')
        if src.type==x.X86_OP_REG and src.reg==x.X86_REG_AX and definition is not None:
            item['definition']=dict(address=definition.address,bytes=definition.bytes.hex(),instruction=definition.mnemonic+' '+definition.op_str)
            if definition.mnemonic=='mov' and len(definition.operands)==2:
                origin=definition.operands[1]
                if (origin.type==x.X86_OP_MEM and not origin.mem.base and not origin.mem.index
                        and segment(md,origin.mem)=='ds' and origin.mem.disp in slots):
                    item.update(source_slot=origin.mem.disp,target=slots[origin.mem.disp])
        stores.append(item)
    hints=read_json(ROOT/'metadata/hints.json')['indirect_transfers']
    for h in hints:
        if image[h['address']:h['address']+len(bytes.fromhex(h['bytes']))].hex()!=h['bytes']:
            raise ValueError('Callback hint does not match canonical instruction')
        if any(p not in ins for p in h['targets']):raise ValueError('Known callback target not decoded')
    indexed_writes=[r for r in refs if (r['base'] or r['index']) and r['access'] in ('write','read_write','unknown')]
    result=dict(canonical_sha256=sha(image),fields=fields,drawing_constructors=constructors,
                object_callback_stores=stores,conditional_indirect_targets=hints,
                metrics=dict(direct_memory_accesses=len(direct),indexed_write_operands=len(indexed_writes),
                             object_callback_stores=len(stores),locally_traced_object_stores=sum('target' in s for s in stores),
                             conditional_edges=sum(len(h['targets']) for h in hints),
                             legitimately_closed_transfers=sum(bool(h.get('legitimate_closed')) for h in hints),
                             all_target_domains_complete=all(h.get('legitimate_closed') for h in hints)),
                # Closure is for the legitimate program; non-legitimate pointer values arise
                # only from characterized corruption recorded beside each transfer.
                open_obligations=[] if all(h.get('legitimate_closed') for h in hints) else
                    ['Legitimate writer domains of the open transfers in metadata/hints.json'])
    write_json(BUILD/'indexed-write-candidates.json',indexed_writes)
    return result

def verify(write=False):
    result=analyze_callbacks();path=ROOT/'metadata/indirect-evidence.json'
    if write:write_json(path,result)
    if read_json(path)!=result:raise ValueError('Indirect callback evidence stale; review changed inputs before refreshing')
    write_json(BUILD/'indirect-evidence.json',result)
    m=result['metrics']
    print(f'PASS callback evidence: {m["conditional_edges"]} known callback edges, {m["locally_traced_object_stores"]}/{m["object_callback_stores"]} local object-pointer definitions; '
          f'{m["legitimately_closed_transfers"]} transfers closed for the legitimate program')
    return m

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write-metadata',action='store_true')
    args=p.parse_args();verify(args.write_metadata)

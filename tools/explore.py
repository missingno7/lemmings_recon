"""Recursive discovery, explicit edges and unresolved frontier (not linear sweep)."""
import capstone
from capstone import x86 as x
from common import ROOT, BUILD, read_json, write_json
from unpack import unpack, ASSET

def discover(image, hints, legacy, relocations=()):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
    md.detail = True
    seeds = {r['offset'] for r in hints['entries']}
    seeds.update(r['offset'] for r in legacy['accepted'])
    work, instructions, edges, unresolved, routines = list(sorted(seeds, reverse=True)), {}, [], [], set(seeds)
    occupied = {}
    limit = hints['code_limit']
    relocation_sites = {r['linear'] for r in relocations}
    while work:
        off = work.pop()
        while off not in instructions:
            if not 0 <= off < limit:
                unresolved.append(dict(address=off, kind='target_outside_provisional_code', evidence='Requires segment/region investigation'))
                break
            if off in occupied:
                unresolved.append(dict(address=off, kind='overlapping_decode', owner=occupied[off]))
                break
            ins = next(md.disasm(image[off: min(off+15,limit)],off),None)
            if not ins:
                unresolved.append(dict(address=off, kind='decode_failure'))
                break
            if any(k in occupied for k in range(off, off+ins.size)):
                unresolved.append(dict(address=off, kind='overlapping_decode'))
                break
            for k in range(off, off+ins.size):
                occupied[k] = off
            m = ins.mnemonic
            row = dict(address=off, size=ins.size, bytes=ins.bytes.hex(), mnemonic=m, operands=ins.op_str,
                       data_references=[dict(segment=md.reg_name(op.mem.segment) or 'default', displacement=op.mem.disp,
                                             base=md.reg_name(op.mem.base), index=md.reg_name(op.mem.index), size=op.size)
                                        for op in ins.operands if op.type == x.X86_OP_MEM])
            instructions[off] = row
            nxt = off+ins.size
            transfer = ins.group(capstone.CS_GRP_JUMP) or ins.group(capstone.CS_GRP_CALL) or m.startswith('loop')
            terminal = m in ('ret','retf','iret','hlt','ljmp','jmp')
            if transfer:
                if len(ins.operands) == 1 and ins.operands[0].type == x.X86_OP_IMM:
                    target = ins.operands[0].imm & 0xffff
                    edges.append(dict(source=off,target=target,kind='call' if m=='call' else 'branch'))
                    work.append(target)
                    if m == 'call':
                        routines.add(target)
                elif (m in ('lcall','ljmp') and len(ins.operands)==2 and
                      all(op.type==x.X86_OP_IMM for op in ins.operands) and
                      ins.operands[0].imm==0 and off+3 in relocation_sites):
                    target=ins.operands[1].imm & 0xffff
                    edges.append(dict(source=off,target=target,kind='far_call' if m=='lcall' else 'far_branch'))
                    work.append(target)
                    routines.add(target)
                else:
                    unresolved.append(dict(address=off,kind='indirect_or_far_transfer',instruction=m+' '+ins.op_str))
            if m == 'int':
                edges.append(dict(source=off,target=None,kind='interrupt',vector=ins.operands[0].imm))
                # Known DOS terminate service is a non-returning platform edge.
                prev = [r for r in instructions.values() if r['address']+r['size']==off]
                if ins.operands[0].imm==0x21 and prev and prev[-1]['mnemonic']=='mov' and prev[-1]['operands'].startswith('ax, 0x4c'):
                    terminal = True
            if not terminal:
                edges.append(dict(source=off,target=nxt,kind='fallthrough'))
            else:
                break
            off = nxt
    for edge in edges:
        if edge['target'] is not None:
            edge['resolved'] = edge['target'] in instructions
    classes = ['unresolved'] * len(image)
    for k in occupied:
        classes[k] = 'instruction'
    for r in hints['regions']:
        if not r.get('overlay'):
            if any(classes[k] != 'unresolved' for k in range(r['start'],r['end'])):
                raise ValueError('Data hint conflicts with decoded instruction')
            classes[r['start']:r['end']] = [r['class']]*(r['end']-r['start'])
    regions = []
    start = 0
    for at in range(1, len(image)+1):
        if at==len(image) or classes[at]!=classes[start]:
            regions.append(dict(start=start,end=at,classification=classes[start]))
            start=at
    return dict(instructions=list(sorted(instructions.values(),key=lambda r:r['address'])),
                edges=edges, unresolved=sorted(unresolved,key=lambda r:r['address']),
                routines=sorted(routines), regions=regions, overlays=[r for r in hints['regions'] if r.get('overlay')],
                metrics=dict(image_bytes=len(image),classified_bytes=sum(c!='unresolved' for c in classes),
                             decoded_instruction_bytes=len(occupied),instructions=len(instructions),
                             identified_entry_candidates=len(routines),resolved_edges=sum(e.get('resolved',False) for e in edges),
                             unresolved_transfers=len(unresolved),unresolved_byte_runs=sum(r['classification']=='unresolved' for r in regions)))

def analyze():
    image, meta = unpack(ASSET.read_bytes())
    return discover(image,read_json(ROOT/'metadata/hints.json'),read_json(ROOT/'metadata/legacy-seeds.json'),meta['relocations'])

if __name__ == '__main__':
    result=analyze()
    write_json(BUILD/'analysis.json',result)
    print(result['metrics'])
    for r in result['unresolved']:
        print(r)

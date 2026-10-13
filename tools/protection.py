"""Static state-specific reconstruction of the original protection code.

The stream view concatenates each instruction's visible execution bytes. It is
a readable analysis view, never a loaded game image or a runtime memory snapshot.
Default verification does not regenerate maintained source, ledgers or pins.
"""
import argparse
import re
import subprocess
import capstone
from capstone import x86 as x
from common import ROOT,BUILD,read_json,write_json,sha
from unpack import unpack,ASSET
from reconstruct import spellings,relative
from build import tool

START,END=0x66d,0xe66
INT1_START,INT1_END=0xdff,0xe3a

def decode_word(image,pc):
    if not 2<=pc<len(image)-1:
        raise ValueError('Static protection word outside supported image window')
    prior=int.from_bytes(image[pc-2:pc],'little')^0xffff
    key=((prior<<1)|(prior>>15))&0xffff
    return int.from_bytes(image[pc:pc+2],'little')^key

def discover_stream(image):
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);md.detail=True
    todo=[(START,'tf_on')];rows={};owners={};edges=[];unresolved=[]
    entries={(START,'tf_on')}
    while todo:
        pc,state=todo.pop()
        if (pc,state) in rows:continue
        if not START<=pc<END:
            unresolved.append(dict(address=pc,state=state,kind='outside_protected_window'))
            continue
        if state=='tf_on':
            raw=decode_word(image,pc).to_bytes(2,'little')+image[pc+2:pc+15]
        else:raw=image[pc:pc+15]
        ins=next(md.disasm(raw,pc,count=1),None)
        if not ins:raise ValueError(f'Cannot decode protection {state}/{pc:04X}')
        for off in range(pc,pc+ins.size):
            if off in owners and owners[off]!=(pc,state):
                raise ValueError(f'Overlapping state views at {off:04X}')
            owners[off]=(pc,state)
        row=dict(address=pc,state=state,size=ins.size,bytes=ins.bytes.hex(),
                 stored_bytes=image[pc:pc+ins.size].hex(),mnemonic=ins.mnemonic,
                 operands=ins.op_str,data_references=[
                     dict(segment=md.reg_name(op.mem.segment) or 'default',
                          displacement=op.mem.disp,base=md.reg_name(op.mem.base),
                          index=md.reg_name(op.mem.index),size=op.size)
                     for op in ins.operands if op.type==x.X86_OP_MEM])
        rows[pc,state]=row
        def edge(target,kind,target_state=state):
            edges.append(dict(source=pc,state=state,target=target,
                              target_state=target_state,kind=kind))
            if target is not None:todo.append((target,target_state))
        nxt=pc+ins.size;m=ins.mnemonic
        if m=='int3':
            # DB3 toggles saved TF and negates INT1, then restores/decrypts.
            edge(nxt,'protection_toggle','tf_off' if state=='tf_on' else 'tf_on')
            continue
        if ins.group(capstone.CS_GRP_JUMP) or ins.group(capstone.CS_GRP_CALL) or m.startswith('loop'):
            if len(ins.operands)==1 and ins.operands[0].type==x.X86_OP_IMM:
                target=ins.operands[0].imm&0xffff
                edge(target,'call' if m=='call' else 'branch')
                if m=='call':entries.add((target,state))
            else:
                unresolved.append(dict(address=pc,state=state,kind='indirect_transfer',instruction=m+' '+ins.op_str))
        if m=='int':
            edge(None,'platform_interrupt')
            edges[-1]['vector']=ins.operands[0].imm
            edges[-1]['return_contract']='Original interrupt returns with TF clear; result registers/flags remain a platform contract'
        if m not in ('ret','retf','iret','hlt','jmp','ljmp'):edge(nxt,'fallthrough')
    for e in edges:
        if e['target'] is not None:e['resolved']=(e['target'],e['target_state']) in rows
    ordered=sorted(rows.values(),key=lambda r:r['address'])
    return dict(instructions=ordered,edges=edges,unresolved=unresolved,
                entries=[dict(address=p,state=s) for p,s in sorted(entries)],
                metrics=dict(instructions=len(rows),instruction_bytes=len(owners),
                             tf_on_instructions=sum(r['state']=='tf_on' for r in ordered),
                             tf_off_instructions=sum(r['state']=='tf_off' for r in ordered),
                             entry_candidates=len(entries),resolved_edges=sum(e.get('resolved',False) for e in edges),
                             unresolved_transfers=len(unresolved)))

def derive():
    image,oracle=unpack(ASSET.read_bytes())
    stream=discover_stream(image)
    view=bytearray(image)
    for r in stream['instructions']:
        view[r['address']:r['address']+r['size']]=bytes.fromhex(r['bytes'])
    # All 59 bytes become actual plaintext together when DB3 negates the handler.
    handler=bytes((-v)&255 for v in image[INT1_START:INT1_END])
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);md.detail=True
    rows=[dict(address=i.address,size=i.size,bytes=i.bytes.hex(),mnemonic=i.mnemonic,
               operands=i.op_str,state='int1_plaintext',data_references=[
                   dict(segment=md.reg_name(op.mem.segment) or 'default',displacement=op.mem.disp,
                        base=md.reg_name(op.mem.base),index=md.reg_name(op.mem.index),size=op.size)
                   for op in i.operands if op.type==x.X86_OP_MEM]) for i in md.disasm(handler,INT1_START)]
    if sum(r['size'] for r in rows)!=len(handler):raise ValueError('INT1 plaintext does not decode completely')
    return image,bytes(view),handler,stream,rows

def regions(rows,start,end):
    covered={k for r in rows for k in range(r['address'],r['address']+r['size'])}
    result=[];at=start
    while at<end:
        cls='instruction' if at in covered else 'unresolved'
        stop=at+1
        while stop<end and (stop in covered)==(at in covered):stop+=1
        result.append(dict(start=at,end=stop,classification=cls));at=stop
    return result

def ledger(stream,handler_rows):
    path=ROOT/'metadata/protection-symbols.json'
    existing={(s['address'],s['state']):s for s in read_json(path)} if path.exists() else {}
    result=[]
    for ent in stream['entries']:
        pc,state=ent['address'],ent['state']
        row=existing.get((pc,state),dict(address=pc,segment=0,state=state,kind='entry',size=None,
                    symbol_name='ProtectedDiskEntry' if pc==START else f'protected_sub_{pc:04X}',aliases=[],
                    confidence='PROVEN' if pc==START else 'STRONGLY_SUPPORTED',
                    evidence=['066C INT3 decrypts saved return 066D' if pc==START else 'Direct call in derived state-specific original stream'],
                    verification_status='UNTRANSLATED'))
        row['callers']=[e['source'] for e in stream['edges'] if e['kind']=='call' and e['target']==pc and e['target_state']==state]
        ins={(r['address'],r['state']):r for r in stream['instructions']}
        outgoing={}
        for e in stream['edges']:outgoing.setdefault((e['source'],e['state']),[]).append(e)
        todo,seen=[(pc,state)],set();callees=set();refs=[]
        while todo:
            node=todo.pop()
            if node in seen or node not in ins:continue
            seen.add(node)
            refs.extend(dict(instruction=node[0],state=node[1],**ref) for ref in ins[node]['data_references'])
            for e in outgoing.get(node,[]):
                if e['kind']=='call':callees.add(e['target'])
                elif e['target'] is not None:todo.append((e['target'],e['target_state']))
        row['callees']=sorted(callees);row['data_references']=refs
        row['reachable_instruction_bytes']=sum(ins[p]['size'] for p in seen)
        result.append(row)
    result.extend(existing.get((pc,'int1_plaintext'),dict(address=pc,segment=0,state='int1_plaintext',kind='entry',size=None,
                  symbol_name=name,aliases=[],callers=[],callees=[],data_references=[],confidence='PROVEN',
                  evidence=[evidence],verification_status='UNTRANSLATED')) for pc,name,evidence in (
                    (INT1_START,'ProtectionInt1Handler','0DB3 installs this address as INT1 after negating 59 bytes'),
                    (0xe1c,'ProtectionDecodeNextWord','Shared tail entered by INT3 with TF set and by active INT1')))
    for s in result:
        if s['state']=='int1_plaintext':
            owned=[r for r in handler_rows if r['address']>=s['address']]
            s['size']=INT1_END-s['address']
            s['data_references']=[dict(instruction=r['address'],**ref) for r in owned for ref in r['data_references']]
            s['reachable_instruction_bytes']=sum(r['size'] for r in owned)
    return result

def source(name,image,rows,edges,symbols,start,end):
    analysis=dict(regions=regions(rows,start,end))
    texts=spellings(analysis,image)
    probe=['bits 16','org 0']
    for n,r in enumerate(rows):
        probe.extend([relative(texts[r['address']],r),f'times {32*(n+1)}-($-$$) db 0xcc'])
    probe_path=BUILD/f'protection-{name}-probe.asm';probe_path.write_text('\n'.join(probe)+'\n')
    subprocess.run([tool('nasm'),'-f','bin','-O0','-o',str(probe_path.with_suffix('.bin')),str(probe_path)],check=True)
    encoded=probe_path.with_suffix('.bin').read_bytes()
    exceptions={r['address'] for n,r in enumerate(rows)
                if encoded[n*32:(n+1)*32]!=bytes.fromhex(r['bytes'])+b'\xcc'*(32-r['size'])}
    labels={s['address']:s['symbol_name'] for s in symbols}
    ins={r['address']:r for r in rows}
    canonical={p:r['classification'] for r in read_json(ROOT/'metadata/regions.json')['regions']
               for p in range(r['start'],r['end'])}
    for e in edges:
        if e['target'] in ins and e['kind']!='fallthrough':
            labels.setdefault(e['target'],f'protected_loc_{e["target"]:04X}')
    out=['; Derived execution view. Canonical load bytes are in src/program.asm.',
         '; Stream instructions show bytes visible while TF is on/off; first-word patches can overlap.',
         '; Bytes outside this view retain stored encoding and canonical region classifications.',
         'bits 16',f'org 0x{start:04x}']
    pc=start
    while pc<end:
        if pc in labels:out.append(labels[pc]+':')
        if pc in ins:
            r=ins[pc];text=texts[pc]
            m=re.match(r'^(\w+) (short |near )?(0x[0-9a-f]+)$',text)
            if m and (m[1].startswith('j') or m[1].startswith('loop') or m[1]=='call'):
                target=int(m[3],16)&0xffff
                text=(m[1]+' '+(m[2] or '')+labels[target] if target in labels else relative(text,r))
            if pc in exceptions:
                text='db '+','.join(f'0x{v:02x}' for v in bytes.fromhex(r['bytes']))+' ; ENCODED: '+text+' (NASM chooses a different encoding)'
            out.append(f'    {text} ; @{pc:05X} {r["state"]}')
            pc+=r['size']
        else:
            stop=pc+1
            while (stop<min(end,pc+16) and stop not in ins and stop not in labels
                   and canonical[stop]==canonical[pc]):stop+=1
            note=('; UNKNOWN: stored bytes outside the derived instruction graph' if canonical[pc]=='unresolved'
                  else '; STORED: outside this execution view; canonical '+canonical[pc])
            out.extend([note,
                        '    db '+','.join(f'0x{v:02x}' for v in image[pc:stop])+f' ; @{pc:05X}'])
            pc=stop
    path=ROOT/f'src/protection/{name}.asm';path.parent.mkdir(exist_ok=True)
    path.write_text('\n'.join(out)+'\n')
    return [dict(address=p,bytes=ins[p]['bytes'],instruction=texts[p],
                 reason='NASM selects different opcode/operand width') for p in sorted(exceptions)]

def verify(generate=False):
    BUILD.mkdir(exist_ok=True)
    image,view,handler,stream,handler_rows=derive()
    pins=dict(canonical_sha256=sha(image),stream_start=START,stream_end=END,
              stream_view_sha256=sha(view[START:END]),int1_start=INT1_START,int1_end=INT1_END,
              int1_plaintext_sha256=sha(handler),stream_metrics=stream['metrics'],
              int1_instruction_count=len(handler_rows))
    symbols=ledger(stream,handler_rows)
    if generate:
        write_json(ROOT/'metadata/protection-symbols.json',symbols)
        encodings=source('stream',view,stream['instructions'],stream['edges'],
                         [s for s in symbols if s['state']!='int1_plaintext'],START,END)
        hv=bytearray(image);hv[INT1_START:INT1_END]=handler
        handler_edges=[dict(target=int(i.op_str,16),kind='branch') for i in
            capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16).disasm(handler,INT1_START)
            if i.mnemonic.startswith('j')]
        encodings+=source('int1',hv,handler_rows,handler_edges,
                          [s for s in symbols if s['state']=='int1_plaintext'],INT1_START,INT1_END)
        write_json(ROOT/'metadata/protection-encodings.json',encodings)
        write_json(ROOT/'metadata/protection-cfg.json',stream)
        # Derivations are pinned explicitly only in the bootstrap, never by verify.
        write_json(ROOT/'metadata/protection-views.json',pins)
    if read_json(ROOT/'metadata/protection-views.json')!=pins:
        raise ValueError('Protection derivation differs from pinned views')
    if read_json(ROOT/'metadata/protection-cfg.json')!=stream:
        raise ValueError('Protection CFG differs from maintained inventory')
    if read_json(ROOT/'metadata/protection-symbols.json')!=symbols:
        raise ValueError('Protection symbol references are stale')
    for name,start,end,expected,state in (
            ('stream',START,END,view[START:END],False),
            ('int1',INT1_START,INT1_END,handler,True)):
        path=ROOT/f'src/protection/{name}.asm'
        if any(re.search(r'\bincbin\b|%include',ln.split(';',1)[0],re.I) for ln in path.read_text().splitlines()):
            raise ValueError('Forbidden include in protection source')
        checked=BUILD/f'protection-{name}-checked.asm'
        lines=[f'%include "{path.as_posix()}"']
        for s in symbols:
            if (s['state']=='int1_plaintext')==state:
                lines.append(f'times -(({s["symbol_name"]}-$$)!={s["address"]-start}) db 0')
        checked.write_text('\n'.join(lines)+'\n')
        out=checked.with_suffix('.bin')
        subprocess.run([tool('nasm'),'-f','bin','-O0','-o',str(out),str(checked)],check=True)
        if out.read_bytes()!=expected:raise ValueError('Protection ASM view mismatch: '+name)
    result=dict(pins,encoding_exceptions=len(read_json(ROOT/'metadata/protection-encodings.json')),
                scope='State-specific main-image views; not additional canonical image bytes or C coverage')
    write_json(BUILD/'protection-verification.json',result)
    print(f'PASS protection views: {stream["metrics"]["instructions"]} stream instructions, {len(handler_rows)} INT1 instructions, exact derived ASM')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--generate',action='store_true')
    args=p.parse_args();verify(args.generate)

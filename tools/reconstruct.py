"""Explicit bootstrap generation; verify.py NEVER regenerates maintained ASM.

Decode only recursive-descent instruction ranges. NASM spelling is independently
roundtripped per instruction. Alternative opcode encodings remain documented db
exceptions rather than silently changing original instruction bytes.
"""
import re
import subprocess
from common import ROOT, BUILD, read_json, write_json
from unpack import ASSET, unpack
from explore import analyze
from build import tool

def spellings(analysis,image):
    result={}
    tmp=BUILD/'decode.bin'
    for reg in analysis['regions']:
        if reg['classification']!='instruction':
            continue
        tmp.write_bytes(image[reg['start']:reg['end']])
        text=subprocess.check_output([tool('ndisasm'),'-b','16','-o',str(reg['start']),str(tmp)],text=True)
        for line in text.splitlines():
            m=re.match(r'^([0-9A-F]+)\s+([0-9A-F]+)\s+(.*)',line)
            if m:
                result[int(m[1],16)]=m[3]
    return result

def relative(text,row):
    m=re.match(r'^(\w+) (short |near )?(0x[0-9a-f]+)$',text)
    if m and (m[1].startswith('j') or m[1].startswith('loop') or m[1]=='call'):
        delta=(int(m[3],16)-row['address']) & 0xffff
        if delta>=0x8000:
            delta-=0x10000
        return m[1]+' '+(m[2] or '')+f'$+({delta})'
    return text

def generate():
    image,oracle=unpack(ASSET.read_bytes())
    a=analyze()
    BUILD.mkdir(exist_ok=True)
    texts=spellings(a,image)
    rows=a['instructions']
    probe=['bits 16','org 0']
    for n,row in enumerate(rows):
        text=relative(texts[row['address']],row)
        probe.extend([f'; instruction {row["address"]:04X}',text,f'times {32*(n+1)}-($-$$) db 0xcc'])
    (BUILD/'encoding-probe.asm').write_text('\n'.join(probe)+'\n')
    subprocess.run([tool('nasm'),'-f','bin','-O0','-o',str(BUILD/'encoding-probe.bin'),str(BUILD/'encoding-probe.asm')],check=True)
    encoded=(BUILD/'encoding-probe.bin').read_bytes()
    exceptions=set()
    for n,r in enumerate(rows):
        b=bytes.fromhex(r['bytes'])
        if encoded[n*32:(n+1)*32]!=b+bytes([0xcc])*(32-len(b)):
            exceptions.add(r['address'])
    ledger_path=ROOT/'metadata/symbols.json'
    ledger=read_json(ledger_path) if ledger_path.exists() else []
    known={r['address']:r for r in ledger}
    call_targets={e['target'] for e in a['edges'] if e['kind'] in ('call','far_call')}
    for off in a['routines']:
        if off not in known:
            known[off]=dict(address=off,segment=0,kind='entry',size=None,symbol_name=f'sub_{off:04X}',aliases=[],
                            callers=[],callees=[],data_references=[],confidence='STRONGLY_SUPPORTED' if off in call_targets else 'HYPOTHESIS',
                            evidence=['Static direct call target' if off in call_targets else 'Signature-matched legacy entry lead'],
                            verification_status='UNTRANSLATED')
    # Per-entry reachable graph intentionally preserves shared tails/overlap.
    ins={r['address']:r for r in rows}
    outgoing={}
    for e in a['edges']:
        outgoing.setdefault(e['source'],[]).append(e)
    for off,s in known.items():
        if s['kind']!='entry':
            continue
        todo,seen=[off],set()
        callees,refs=set(),[]
        while todo:
            pc=todo.pop()
            if pc in seen or pc not in ins:
                continue
            seen.add(pc)
            refs.extend(dict(instruction=pc,**r) for r in ins[pc]['data_references'])
            for e in outgoing.get(pc,[]):
                if e['kind'] in ('call','far_call'):
                    callees.add(e['target'])
                elif e['target'] is not None:
                    todo.append(e['target'])
        s['callers']=[e['source'] for e in a['edges'] if e['target']==off and e['kind'] in ('call','far_call')]
        s['callees']=sorted(callees)
        s['data_references']=refs
        s['reachable_instruction_bytes']=sum(ins[p]['size'] for p in seen)
    write_json(ledger_path,sorted(known.values(),key=lambda r:r['address']))
    names={off:s['symbol_name'] for off,s in known.items()}
    for e in a['edges']:
        if e['target'] in ins:
            names.setdefault(e['target'],f'loc_{e["target"]:04X}')
    # Only transfer targets need a label; sequential labels add visual noise.
    labels={off:s['symbol_name'] for off,s in known.items()}
    for e in a['edges']:
        if e['kind'] not in ('fallthrough','interrupt') and e['target'] in ins:
            labels.setdefault(e['target'],f'loc_{e["target"]:04X}')
    dest=ROOT/'src'
    dest.mkdir(exist_ok=True)
    code=['; Static code frame 0000; semantic module boundaries remain under investigation.']
    data=['; Image from DS frame 09A9 onward; UNKNOWN is not a claim of passive data.']
    mapping=[]
    emitted=set()
    pos=0
    classification={k:r['classification'] for r in a['regions'] for k in range(r['start'],r['end'])}
    code_limit=read_json(ROOT/'metadata/hints.json')['code_limit']
    while pos<len(image):
        lines=code if pos<code_limit else data
        file='src/code.asm' if pos<code_limit else 'src/image_tail.asm'
        if pos in labels:
            lines.append(labels[pos]+':')
            emitted.add(pos)
        if pos in ins:
            row=ins[pos]
            text=texts[pos]
            m=re.match(r'^(\w+) (short |near )?(0x[0-9a-f]+)$',text)
            if m and (m[1].startswith('j') or m[1].startswith('loop') or m[1]=='call'):
                target=int(m[3],16)&0xffff
                # Keep the probed relative expression for unresolved targets.
                # NASM -O0 can widen an absolute numeric Jcc to a near branch.
                text=(m[1]+' '+(m[2] or '')+labels[target]
                      if target in labels else relative(text,row))
            if pos in exceptions:
                text='db '+','.join(f'0x{b:02x}' for b in bytes.fromhex(row['bytes']))+' ; ENCODED: '+text+' (NASM chooses a different encoding)'
            lines.append('    '+text+f' ; @{pos:05X}')
            mapping.append(dict(start=pos,end=pos+row['size'],file=file,line=len(lines),kind='instruction',encoded=pos in exceptions))
            pos+=row['size']
        else:
            end=pos+1
            while (end<min(len(image),pos+16) and end not in labels and end not in ins and
                   end!=code_limit and classification[end]==classification[pos]):
                end+=1
            cls=classification[pos]
            lines.append('; UNKNOWN: unresolved bytes' if cls=='unresolved' else '; DATA: '+cls)
            lines.append('    db '+','.join(f'0x{b:02x}' for b in image[pos:end])+f' ; @{pos:05X}')
            mapping.append(dict(start=pos,end=end,file=file,line=len(lines),kind=cls))
            pos=end
    equates=''.join(f'{name} equ $$ + 0x{off:04X} ; overlay inside instruction\n' for off,name in labels.items() if off not in emitted)
    (dest/'program.asm').write_text('bits 16\norg 0\n'+equates+'%include "code.asm"\n%include "image_tail.asm"\n')
    (dest/'code.asm').write_text('\n'.join(code)+'\n')
    (dest/'image_tail.asm').write_text('\n'.join(data)+'\n')
    write_json(ROOT/'metadata/regions.json',dict(regions=a['regions'],overlays=a['overlays']))
    write_json(BUILD/'source-map.json',mapping)
    write_json(BUILD/'analysis.json',a)
    write_json(ROOT/'metadata/encoding-exceptions.json', [dict(address=p,bytes=ins[p]['bytes'],instruction=texts[p],reason='NASM 2.x default encoding differs; explicit bytes preserve original opcode/operand widths') for p in sorted(exceptions)])
    print(f'Generated {len(image)} ASM bytes; {len(rows)} instructions, {len(exceptions)} explicit encoding exceptions')

if __name__=='__main__':
    generate()

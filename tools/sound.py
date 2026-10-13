"""Static sound-driver discovery, explicit ASM bootstrap and exact verification.

Use --generate only to establish/refresh source after reviewing hints. Default
verification never rewrites source, symbols, regions, or accepted image hashes.
"""
import argparse
import re
import struct
import subprocess
from common import ROOT,BUILD,read_json,write_json,sha
from resources import sound_images
from explore import discover
from reconstruct import spellings,relative
from build import tool

def analyze_driver(name,image):
    h=read_json(ROOT/'metadata/sound-hints.json')[name]
    hints=dict(code_limit=len(image),entries=[dict(offset=0)],regions=h['regions'])
    if name=='adlib':
        for seed in read_json(ROOT/'metadata/legacy-seeds.json')['external']:
            if seed['segment']!=0x2911:
                continue
            off=seed['offset'];sig=bytes.fromhex(seed['signature'])
            if image[off:off+len(sig)]!=sig:
                raise ValueError(f'AdLib legacy signature mismatch at{off:04X}')
            hints['entries'].append(dict(offset=off))
    for table in h['dispatch_tables']:
        for off in range(table['start'],table['end'],2):
            hints['entries'].append(dict(offset=struct.unpack_from('<H',image,off)[0]))
    a=discover(image,hints,{'accepted':[]})
    a['dispatch_tables']=h['dispatch_tables']
    return a

def generate_driver(name,image,a):
    text=spellings(a,image)
    probe=['bits 16','org 0']
    for n,r in enumerate(a['instructions']):
        probe.extend([relative(text[r['address']],r),f'times {32*(n+1)}-($-$$) db 0xcc'])
    path=BUILD/f'{name}-probe.asm'
    path.write_text('\n'.join(probe)+'\n')
    subprocess.run([tool('nasm'),'-f','bin','-O0','-o',str(path.with_suffix('.bin')),str(path)],check=True)
    encoded=path.with_suffix('.bin').read_bytes()
    exceptions={r['address'] for n,r in enumerate(a['instructions'])
                if encoded[n*32:(n+1)*32]!=bytes.fromhex(r['bytes'])+b'\xcc'*(32-r['size'])}
    labels={p:f'{name}_sub_{p:04X}' for p in a['routines']}
    labels[0]=name+'_InterruptEntry'
    for edge in a['edges']:
        if edge['kind']!='fallthrough' and edge['target'] is not None:
            labels.setdefault(edge['target'],f'{name}_loc_{edge["target"]:04X}')
    rows=['; Canonical decompressed driver. No initialization/relocation patches.',
          '; Entry offset0000 is installed as INT61 by main CS:0576..057B.',
          '; UNKNOWN includes unclassified sound data; no no-code claim is implied.',
          'bits 16','org 0']
    ins={r['address']:r for r in a['instructions']}
    kind={p:r['classification'] for r in a['regions'] for p in range(r['start'],r['end'])}
    at=0
    while at<len(image):
        if at in labels:
            rows.append(labels[at]+':')
        if at in ins:
            r=ins[at];s=text[at]
            m=re.match(r'^(\w+) (short |near )?(0x[0-9a-f]+)$',s)
            if m and (m[1].startswith('j') or m[1].startswith('loop') or m[1]=='call'):
                target=int(m[3],16)&0xffff
                s=(m[1]+' '+(m[2] or '')+labels[target]
                   if target in labels else relative(s,r))
            if at in exceptions:
                s='db '+','.join(f'0x{x:02x}' for x in bytes.fromhex(r['bytes']))+' ; ENCODED: '+s+' (NASM selects different opcode/operand width)'
            rows.append('    '+s+f' ; @{at:05X}')
            at+=r['size']
        else:
            end=at+1
            while end<min(len(image),at+16) and end not in ins and end not in labels and kind[end]==kind[at]:
                end+=1
            rows.append('; UNKNOWN: unresolved bytes' if kind[at]=='unresolved' else '; DATA: '+kind[at])
            rows.append('    db '+','.join(f'0x{x:02x}' for x in image[at:end])+f' ; @{at:05X}')
            at=end
    source=ROOT/f'src/sound/{name}.asm'
    source.parent.mkdir(exist_ok=True)
    source.write_text('\n'.join(rows)+'\n')
    write_json(ROOT/f'metadata/{name}-regions.json',dict(regions=a['regions'],overlays=a['overlays']))
    symbols=[]
    outgoing={}
    for e in a['edges']:
        outgoing.setdefault(e['source'],[]).append(e)
    for addr in a['routines']:
        todo,seen,callees,refs=[addr],set(),set(),[]
        while todo:
            p=todo.pop()
            if p in seen or p not in ins:
                continue
            seen.add(p)
            refs.extend(dict(instruction=p,**r) for r in ins[p]['data_references'])
            for e in outgoing.get(p,[]):
                if e['kind']=='call':
                    callees.add(e['target'])
                elif e['target'] is not None:
                    todo.append(e['target'])
        symbols.append(dict(address=addr,segment='driver-relative',kind='entry',size=None,symbol_name=labels[addr],aliases=[],
                            callers=[e['source'] for e in a['edges'] if e['target']==addr and e['kind']=='call'],
                            callees=sorted(callees),data_references=refs,reachable_instruction_bytes=sum(ins[p]['size'] for p in seen),
                            confidence='PROVEN' if addr==0 else 'STRONGLY_SUPPORTED',
                            evidence=['Main0576..057B installs offset0 as INT61' if addr==0 else 'Static call/table target or signature-matched legacy lead'],
                            verification_status='UNTRANSLATED'))
    write_json(ROOT/f'metadata/{name}-symbols.json',symbols)
    write_json(ROOT/f'metadata/{name}-encodings.json',[
        dict(address=p,bytes=ins[p]['bytes'],instruction=text[p],reason='NASM chooses a different encoding') for p in sorted(exceptions)])

def verify_drivers(generate=False):
    BUILD.mkdir(exist_ok=True)
    images=sound_images()
    if generate:
        # This bootstrap does not update the acceptance hashes automatically.
        for name,(image,meta) in images.items():
            a=analyze_driver(name,image)
            generate_driver(name,image,a)
    pins=read_json(ROOT/'metadata/sound-oracle.json')
    result={}
    for name,(image,meta) in images.items():
        if meta!=pins[name]:
            raise ValueError('Sound oracle identity mismatch: '+name)
        a=analyze_driver(name,image)
        if dict(regions=a['regions'],overlays=a['overlays'])!=read_json(ROOT/f'metadata/{name}-regions.json'):
            raise ValueError('Sound region inventory stale: '+name)
        source=ROOT/f'src/sound/{name}.asm'
        if any(re.search(r'\bincbin\b|%include',line.split(';',1)[0],re.I) for line in source.read_text().splitlines()):
            raise ValueError('Forbidden binary or source include in sound source')
        out=BUILD/f'{name}-rebuilt.bin'
        checked=BUILD/f'{name}-checked.asm'
        lines=[f'%include "{source.as_posix()}"']
        for symbol in read_json(ROOT/f'metadata/{name}-symbols.json'):
            lines.append(f'times -(({symbol["symbol_name"]}-$$)!={symbol["address"]}) db 0')
        checked.write_text('\n'.join(lines)+'\n')
        subprocess.run([tool('nasm'),'-f','bin','-O0','-o',str(out),str(checked)],check=True)
        if out.read_bytes()!=image:
            raise ValueError('Rebuilt sound bytes differ: '+name)
        write_json(BUILD/f'{name}-analysis.json',a)
        result[name]=dict(a['metrics'],byte_exact_asm_bytes=len(image),image_sha256=sha(image),
                          encoding_exceptions=len(read_json(ROOT/f'metadata/{name}-encodings.json')),
                          c_routines=0,c_bytes=0,differential_c_instructions=0,
                          source_sha256=sha(source.read_bytes()))
        print(f'PASS {name}: {len(image)} ASM bytes exact; {a["metrics"]["decoded_instruction_bytes"]} decoded bytes; {a["metrics"]["unresolved_transfers"]} unresolved transfers')
    write_json(BUILD/'sound-verification.json',result)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--generate',action='store_true')
    a=p.parse_args()
    verify_drivers(a.generate)

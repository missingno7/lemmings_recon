"""Static installed-handler and external timer-chain evidence, without booting.

Opcode claims are explicit original-byte intervals. The registry describes the
known installations, not an exhaustive proof against further vector writes.
"""
from common import ROOT,BUILD,read_json,write_json,sha
from unpack import unpack,ASSET
from explore import analyze
from resources import sound_images,section_spans
import argparse

def registry():
    image,oracle=unpack(ASSET.read_bytes());a=analyze()
    ranges=[(0x40,0x45),(0x5d,0x84),(0x85,0x90),(0xf48,0xf64),
            (0x1562,0x1580),(0x1644,0x1660),(0x16b5,0x16c7),
            (0x1893,0x189d),(0x4c66,0x4c70),(0x5028,0x503b),
            (0x58d2,0x58e4),(0x58ec,0x58fd),(0x5902,0x5913),
            (0x5940,0x5951),(0x5951,0x5976)]
    entries={r['address'] for r in a['instructions']}
    for off in (0xf6f,0xf70,0x16d4,0x17c7,0x18f8,0x4c47):
        if off not in entries:raise ValueError(f'Installed handler missing from census at {off:04X}')
    fixups={r['linear'] for r in oracle['relocations']}
    if not {0x1653,0x5968}.issubset(fixups):raise ValueError('PC-speaker frame relocation missing')
    pc,meta=sound_images()['pcspeaker']
    if meta['load_frame']*16+len(pc)!=0x8716 or meta['load_frame']*16+meta['entry_offset']!=0x85a2:
        raise ValueError('PC-speaker overlay layout changed')
    if image[0x8420:0x8716]!=bytes(len(pc)):raise ValueError('Unexpected stored overlay bytes')
    if image[0x9a90+0x252b:0x9a90+0x2534]!=b'main.dat\0':raise ValueError('MAIN.DAT loader filename changed')
    symbols={s['address']:s for s in read_json(ROOT/'metadata/symbols.json') if s['segment']==0 and s['kind']=='entry'}
    todo=[0x59bb,0x5cc1,0x5ac1,0x57d1];seen=set()
    while todo:
        pc0=todo.pop()
        if pc0 in seen:continue
        seen.add(pc0)
        if pc0 not in symbols:raise ValueError('Graphics helper entry missing')
        todo.extend(symbols[pc0]['callees'])
    file_entries={0x1b79,0x1ba9,0x1baf,0x1d2e}
    if seen&file_entries:raise ValueError('Resource helper may consume additional packed sections')
    return dict(canonical_sha256=sha(image),opcode_claims=[dict(start=lo,end=hi,bytes=image[lo:hi].hex()) for lo,hi in ranges],
        installations=[
          dict(vector=9,target_image='main',offset=0x16d4,site=0x157c,kind='dos_set_vector'),
          dict(vector=8,target_image='main',offset=0x17c7,site=0x164e,kind='dos_set_vector'),
          dict(vector=8,target_image='main',offset=0x4c47,site=0x502e,kind='direct_ivt_write'),
          dict(vector=0x24,target_image='main',offset=0x18f8,site=0x8d,kind='dos_set_vector'),
          dict(vector_from=dict(frame=0x9a9,offset=0x1fc6),initial_value=0xc,target_image='main',offset=0xf70,
               site=0xf60,kind='dos_set_vector'),
          dict(api='INT33 AX000C',target_image='main',offset=0xf6f,site=0xf53,kind='far_mouse_callback',return_mechanism='retf'),
          dict(vector=0x60,target_image='pcspeaker',frame=0x842,offset=0x182,site=0x165d,
               kind='loaded_component',flat_runtime_offset=0x85a2),
          dict(vector=0x61,target_image='adlib_or_tandysnd',offset=0,site=0x57b,kind='allocated_component'),
          dict(vector=0x62,target_image='external_saved_private_irq',site=0x81,kind='dos_set_vector',
               source=dict(frame=0x9a9,offset=0x1fc2))],
        restorations=[dict(vector=9,site=0x158e,source=dict(frame=0x9a9,offset=0x1fba)),
                      dict(vector=8,site=0x16bd,source=dict(frame=0x9a9,offset=0x1fbe)),
                      dict(vector_from=dict(frame=0x9a9,offset=0x1fc6),site=0xfae,source=dict(frame=0x9a9,offset=0x1fc2))],
        pc_speaker_load=dict(source=meta['source'],section_index=5,section_offset=meta['section_offset'],
                             section_size=meta['packed_size'],decoded_size=len(pc),sha256=sha(pc),
                             decode_sites=[0x58e0,0x58f9,0x590f,0x594d,0x5960,0x5972],
                             graphics_helper_entries_without_file_reads=sorted(seen)),
        external_chains=read_json(ROOT/'metadata/hints.json')['external_transfers'],
        scope='Known installed vectors and opcode evidence; generic writes/aliases and additional installs remain open')

def verify(write=False):
    result=registry();path=ROOT/'metadata/interrupt-evidence.json'
    if write:write_json(path,result)
    if read_json(path)!=result:raise ValueError('Interrupt registry stale; review changed evidence before refreshing')
    write_json(BUILD/'interrupt-evidence.json',result)
    print('PASS interrupt evidence: installed handlers, PC-speaker load and two external IRET chains')
    return dict(known_installations=len(result['installations']),external_iret_chains=len(result['external_chains']),
                pc_speaker_overlay_bytes=result['pc_speaker_load']['decoded_size'])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write-metadata',action='store_true')
    args=p.parse_args();verify(args.write_metadata)

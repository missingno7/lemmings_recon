"""Reproducible, separate byte/translation/execution accounting."""
import argparse
from common import ROOT,BUILD,read_json,write_json,sha
from explore import analyze
from unpack import unpack,ASSET,relocated

def report():
    analysis=analyze()
    m=dict(analysis['metrics'])
    verified=read_json(BUILD/'verification.json')
    if not verified.get('bounded_extractor_checks'):
        raise ValueError('Full extractor checks required for coverage; run tools/verify.py without --skip-stub')
    for path,digest in verified['verification_inputs'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale static verification for '+path+'; run tools/verify.py')
    image,oracle=unpack(ASSET.read_bytes())
    built=(BUILD/'asm/program.bin').read_bytes()
    if built!=image or verified['canonical_sha256']!=sha(image):
        raise ValueError('Run tools/verify.py before reporting coverage')
    for field in ('reconstructed_asm_bytes','byte_exact_asm_bytes'):
        m[field]=verified[field]
    symbols=read_json(ROOT/'metadata/symbols.json')
    translated=[s for s in symbols if s.get('c_implementation')]
    m['translated_c_routines']=len(translated)
    code_bytes=set()
    for s in translated:
        code_bytes.update(range(s['address'],s['address']+s['size']))
    m['translated_c_code_bytes']=len(code_bytes)
    d=read_json(BUILD/'differential.json')
    paths={'checksum.c':'c/checksum.c','checksum.h':'c/checksum.h',
           'lemmings_sym.h':'c/lemmings_sym.h','symbols.json':'metadata/symbols.json',
           'checksum.py':'tests/checksum.py','difftest.py':'tools/difftest.py','cbuild.py':'tools/cbuild.py'}
    for name,path in paths.items():
        if d['input_hashes'][name]!=sha((ROOT/path).read_bytes()):
            raise ValueError('Stale differential report for '+path+'; run tools/difftest.py')
    if d['oracle']['relocated_image_sha256']!=sha(relocated(image,oracle['relocations'],int(d['oracle']['load_segment'],16))):
        raise ValueError('Differential oracle identity changed')
    executed={int(x,16) for r in d['routines'] for x in r['executed_instruction_addresses']}
    m['differential_cases']=d['case_count']
    m['mutations_detected']=d['mutation_count']
    m['original_instructions_executed']=len(executed)
    m['unresolved_main_code_candidate_bytes']=sum(r['end']-r['start'] for r in analysis['regions'] if r['classification']=='unresolved' and r['start']<0x9a90)
    m['unresolved_main_code_candidate_runs']=sum(r['classification']=='unresolved' and r['start']<0x9a90 for r in analysis['regions'])
    m['unresolved_image_bytes']=len(image)-m['classified_bytes']
    m['unresolved_direct_targets']=sum(e['target'] is not None and not e.get('resolved',False) for e in analysis['edges'])
    m['unresolved_indirect_transfers']=sum(r['kind']=='indirect_or_far_transfer' for r in analysis['unresolved'])
    m['runtime_control_frontiers']=sum(r['kind'].startswith('runtime_modified') for r in analysis['unresolved'])
    m['sound']=verified['sound']
    m['protection']=verified['protection']
    state_insns=m['protection']['stream_metrics']['instructions']+m['protection']['int1_instruction_count']
    m['state_specific_decoded_instructions']=state_insns
    combined_bytes=m['byte_exact_asm_bytes']+sum(s['byte_exact_asm_bytes'] for s in m['sound'].values())
    combined_insns=m['instructions']+state_insns+sum(s['instructions'] for s in m['sound'].values())
    m['all_images_byte_exact_asm_bytes']=combined_bytes
    m['all_images_decoded_instructions']=combined_insns
    write_json(BUILD/'coverage.json',m)
    text=f'''# Reconstruction completeness

Main-image identity is established. Full static, C and native completion are not.
Regenerate this report with tools/verify.py, tools/difftest.py, then tools/coverage.py
--write-doc. No dynamic gameplay coverage is used.

| Metric | Value |
|---|---:|
| Canonical image bytes | {m['image_bytes']:,} |
| Classified image bytes | {m['classified_bytes']:,} |
| Decoded instruction bytes | {m['decoded_instruction_bytes']:,} |
| Reconstructed ASM bytes | {m['reconstructed_asm_bytes']:,} |
| Byte-exact ASM bytes | {m['byte_exact_asm_bytes']:,} |
| Identified routine entry candidates | {m['identified_entry_candidates']} |
| Translated C routines | {m['translated_c_routines']} |
| Translated C code bytes | {m['translated_c_code_bytes']} |
| Differential cases | {m['differential_cases']} |
| Mutation checks detected | {m['mutations_detected']} |
| Original instruction coverage | {len(executed)} / {m['instructions']:,} decoded ({100*len(executed)/m['instructions']:.3f}%) |
| Unresolved image bytes / runs | {m['unresolved_image_bytes']:,} / {m['unresolved_byte_runs']} |
| Unresolved runs inside provisional code frame | {m['unresolved_main_code_candidate_runs']} ({m['unresolved_main_code_candidate_bytes']:,} bytes) |
| Resolved static CFG edges, including fallthrough | {m['resolved_edges']:,} |
| Unresolved direct targets / indirect transfers | {m['unresolved_direct_targets']} / {m['unresolved_indirect_transfers']} |
| Runtime-modified control-flow frontiers | {m['runtime_control_frontiers']} |
| Additional state-specific main instruction sites | {state_insns} |

The decoded instruction denominator is incomplete: unknown runs in the main and
sound-driver images may add executable bytes. Entry candidates include historical leads,
shared tails and manually investigated code; they are not proven disjoint functions.
The complete region partition labels uncertainty rather than claiming classification.
There are {verified['encoding_exceptions']:,} main-image decoded instructions expressed as explicit encoding exceptions.

Gate A passes for the main EXE: deterministic static unpack, full byte comparison,
63 independently checked relocations, entry/stack state and input identity. Gate B
has an exact buildable initial ASM image, but remains open for code/data, indirect
transfer, external-driver and semantic closure. Gates C/D have only the checksum
cluster: both routines are TESTED within docs/checksum.md's domain; all other main
entry candidates are UNTRANSLATED. CS:8363 reachability remains UNRESOLVED despite
its complete bounded instruction/branch coverage. Gate E is not started.

The checksum tests execute 44/44 cluster instruction addresses and all 10 static
branch edges. They compare registers, defined flags and the entire 1 MiB memory,
including push/pop residue, across poisoned fixtures. AF is excluded only on the
phase-wrap path, where the last XOR makes it architecturally undefined.

External driver images now reconstruct exactly, with separate static accounting:

| Image | Exact ASM bytes | Classified bytes | Decoded instructions | Entry candidates | Unresolved transfers | C routines |
|---|---:|---:|---:|---:|---:|---:|
'''
    for name,s in m['sound'].items():
        text+=f'| {name} | {s["byte_exact_asm_bytes"]:,} | {s["classified_bytes"]:,} | {s["instructions"]} | {s["identified_entry_candidates"]} | {s["unresolved_transfers"]} | 0 |\n'
    text+=f'''
Across all three images, {combined_bytes:,} ASM bytes are exact and {combined_insns:,}
instructions have been decoded. C differential coverage remains {len(executed)} / {combined_insns:,}
({100*len(executed)/combined_insns:.3f}%) of this still-incomplete decoded inventory. Four bounded
DAT extraction checks exercise 145 main-image instructions; these are extractor
verification, not C translation coverage and not driver execution tests.

All 16 legacy AdLib signatures at segment 2911 match the static extraction. The
seventeenth external lead is F000:FF53 firmware/environment code, not a driver entry.
Both sound dispatch tables lack sufficient bounds checks; their out-of-table paths
remain unresolved. Driver code/data closure and behavioral translation are open.
Main INT3 protection has independently checked state-specific views: 372 stream
instructions (325 TF-on, 47 TF-off) and 29 transformed INT1 instructions. The
original handlers pass 19 constructed-frame cases and checks at every one of the
325 derived TF-on instruction points, comparing full memory, registers and defined
flags. These checks execute only 61 handler instruction sites; the disk-check body
has not been executed. The two raw-image control frontiers remain represented in
the separate protection CFG. Platform contracts, memory aliases and skipped code
still need review; see protection.md. No protected routine has been translated to C.
No public executable or proprietary asset is tracked. See executable.md for local
provenance, control-frontier.json for addresses, and next-work.md for proof obligations.
'''
    return m,text

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--write-doc',action='store_true')
    a=p.parse_args()
    metrics,text=report()
    if a.write_doc:
        (ROOT/'docs/completeness.md').write_text(text,encoding='utf-8')
    print(text)

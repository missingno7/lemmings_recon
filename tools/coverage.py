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
           'lemmings_sym.h':'c/lemmings_sym.h','regs.h':'c/regs.h','symbols.json':'metadata/symbols.json',
           'checksum.py':'tests/checksum.py','difftest.py':'tools/difftest.py','cbuild.py':'tools/cbuild.py'}
    for name,path in paths.items():
        if d['input_hashes'][name]!=sha((ROOT/path).read_bytes()):
            raise ValueError('Stale differential report for '+path+'; run tools/difftest.py')
    if d['oracle']['relocated_image_sha256']!=sha(relocated(image,oracle['relocations'],int(d['oracle']['load_segment'],16))):
        raise ValueError('Differential oracle identity changed')
    executed={int(x,16) for r in d['routines'] for x in r['executed_instruction_addresses']}
    dat=read_json(BUILD/'dat-differential.json')
    for path,digest in dat['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale DAT differential report for '+path+'; run tools/difftest.py')
    if dat['image_sha256']!=sha(image):raise ValueError('DAT differential oracle changed')
    executed.update(dat['executed_instruction_addresses'])
    m['differential_cases']=d['case_count']+dat['case_count']
    m['mutations_detected']=d['mutation_count']+dat['mutation_count']
    m['original_instructions_executed']=len(executed)
    m['unresolved_main_code_candidate_bytes']=sum(r['end']-r['start'] for r in analysis['regions'] if r['classification']=='unresolved' and r['start']<0x9a90)
    m['unresolved_main_code_candidate_runs']=sum(r['classification']=='unresolved' and r['start']<0x9a90 for r in analysis['regions'])
    m['unresolved_image_bytes']=len(image)-m['classified_bytes']
    m['unresolved_direct_targets']=sum(e['target'] is not None and not e.get('resolved',False) for e in analysis['edges'])
    m['unresolved_indirect_transfers']=sum(r['kind']=='indirect_or_far_transfer' for r in analysis['unresolved'])
    m['runtime_control_frontiers']=sum(r['kind'].startswith('runtime_modified') for r in analysis['unresolved'])
    m['sound']=verified['sound']
    pc=read_json(BUILD/'pcspeaker-differential.json')
    for path,digest in pc['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale PC-speaker differential report for '+path+'; run tools/difftest.py')
    if pc['image_sha256']!=m['sound']['pcspeaker']['image_sha256']:
        raise ValueError('PC-speaker differential oracle changed')
    m['sound']['pcspeaker']['differential_c_instructions']=len(pc['executed_instruction_addresses'])
    m['all_images_translated_c_routines']=m['translated_c_routines']+m['sound']['pcspeaker']['c_routines']
    m['all_images_translated_c_bytes']=m['translated_c_code_bytes']+pc['translated_code_bytes']
    m['all_images_differential_cases']=m['differential_cases']+pc['case_count']
    m['all_images_mutations_detected']=m['mutations_detected']+pc['mutation_count']
    c_executed=len(executed)+len(pc['executed_instruction_addresses'])
    m['all_images_original_c_instructions_executed']=c_executed
    m['protection']=verified['protection']
    m['indirect']=verified['indirect']
    m['interrupts']=verified['interrupts']
    m['dat_io']=verified['dat_io']
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
| Known conditional indirect edges | {m['indirect']['conditional_edges']} |

The decoded instruction denominator is incomplete: unknown runs in the main and
sound-driver images may add executable bytes. Entry candidates include historical leads,
shared tails and manually investigated code; they are not proven disjoint functions.
The complete region partition labels uncertainty rather than claiming classification.
There are {verified['encoding_exceptions']:,} main-image decoded instructions expressed as explicit encoding exceptions.

Gate A passes for the main EXE: deterministic static unpack, full byte comparison,
63 independently checked relocations, entry/stack state and input identity. Gate B
has an exact buildable initial ASM image, but remains open for code/data, indirect
transfer, external-driver and semantic closure. Gates C/D have the checksum,
DAT leaf and PC-speaker helper clusters. The two checksum and three DAT main
routines are TESTED within docs/checksum.md and docs/dat.md's domains; remaining
main entry candidates are UNTRANSLATED. CS:8363 reachability remains UNRESOLVED despite
its complete bounded instruction/branch coverage. Gate E is not started.

The checksum tests execute 44/44 cluster instruction addresses and all 10 static
branch edges. They compare registers, defined flags and the entire 1 MiB memory,
including push/pop residue, across poisoned fixtures. AF is excluded only on the
phase-wrap path, where the last XOR makes it architecturally undefined.

The DAT leaf suite covers 33/33 instructions and all six local branch edges in
470 cases. It compares full memory, registers and defined flags, including zero
bit counts (256 iterations), zero incremented match counts (65,536 iterations),
live overlapping copies and overwritten saved registers. Three compiled mutants
are detected. The section decoder and file/cache provider remain UNTRANSLATED;
the strict static extractor's validation rules are not substituted for original
runtime behavior. See dat.md.

Loaded sound-component images reconstruct exactly, with separate static accounting:

| Image | Exact ASM bytes | Classified bytes | Decoded instructions | Entry candidates | Unresolved transfers | C routines |
|---|---:|---:|---:|---:|---:|---:|
'''
    for name,s in m['sound'].items():
        text+=f'| {name} | {s["byte_exact_asm_bytes"]:,} | {s["classified_bytes"]:,} | {s["instructions"]} | {s["identified_entry_candidates"]} | {s["unresolved_transfers"]} | {s["c_routines"]} |\n'
    text+=f'''
Across all four component images, {combined_bytes:,} ASM bytes are exact and {combined_insns:,}
instructions have been decoded. C differential coverage is {c_executed} / {combined_insns:,}
({100*c_executed/combined_insns:.3f}%) of this still-incomplete decoded inventory. There are
{m['all_images_translated_c_routines']} tested C routines occupying {m['all_images_translated_c_bytes']} original code bytes across images,
with {m['all_images_differential_cases']} differential cases and {m['all_images_mutations_detected']} compiled mutations detected. Six bounded
DAT extraction checks exercise 145 main-image instructions; these are extractor
verification, not C translation coverage and not driver execution tests.

All 16 legacy AdLib signatures at segment 2911 match the static extraction. The
seventeenth external lead is F000:FF53 firmware/environment code, not a driver entry.
All three sound dispatch tables lack sufficient bounds checks; their out-of-table paths
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

Callback evidence traces all 32 recovered object-record pointer stores to nine
drawing callback slots and identifies four display probes, three input callbacks
and the code-input BP callback. The 18 known indirect edges are present in the CFG,
while all five near-callback target domains remain explicitly incomplete. Thirty-two
bounded caller fixtures cover 214 original caller instruction sites with declared
callee boundaries. They check routing and save/restore behavior, including DF-set
traversal and unlisted live pointers; they are not C coverage or callee tests.
See indirect-callbacks.md for alias and incoming-state obligations.

The PC-speaker image is MAIN.DAT section 5: 758 separately reconstructed payload
bytes loaded over canonical zeros at main 08420..08715. Component byte totals count
both stored main bytes and the payload image; they are not unique runtime-memory
bytes. Original extraction is checked at the actual overlay destination at two loads.
The payload's trailing 161 bytes and single pre-entry byte remain UNKNOWN. Its three
closed helpers (effect selection, tick and stop) now have C11 cores and near-call
adapters. The PC-speaker suite compares full memory/registers, defined flags and
port traces in 335 cases, covers all 60 helper instruction sites and all 17 branches,
and detects three compiled mutations. The IRQ dispatcher remains UNTRANSLATED;
none of its unresolved target paths has been silently replaced. See pcspeaker.md.

Two saved INT08 chains now have explicit external IRET edges and original return
continuations. Nineteen bounded tail cases check complete memory and saved-register/
flag results across loads, stack wrap and external clobbers. Nineteen installed-
handler fixtures check 0F6F/0F70/18F8 and their declared service boundaries. These
are caller/handler checks, not full timer, BIOS, C or game execution coverage.
See interrupts.md for provider contracts and the menu wrapper's unsaved ES effect.

The complete DAT read wrapper at 1D2E..1E1B now has {m['dat_io']['case_count']}
bounded original-code cases, covering all {m['dat_io']['original_instruction_sites']} instructions and
{m['dat_io']['branch_edges']} branch edges under declared DOS fixtures. Full memory/register/flag
checks expose direct-read errors, short reads, cache creation and hits, saved-frame
aliases, ignored cache-fill errors and pointer/count wrap. This is provider-contract
evidence, not C translation or actual DOS execution coverage; see dat-io.md.
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

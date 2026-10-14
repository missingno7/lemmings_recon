"""Fail-closed canonical/ASM/relocation gate; never rewrites source or pins."""
import argparse
from pathlib import Path
from common import ROOT, BUILD, read_json, write_json, sha
from unpack import ASSET, unpack, relocated
from build import assemble
from explore import analyze
import symtab

def verify(check_stub=True):
    (BUILD/'verification.json').unlink(missing_ok=True)
    for row in read_json(ROOT/'metadata/inputs.json')['files']:
        data=(ROOT/row['path']).read_bytes()
        if len(data)!=row['size'] or sha(data)!=row['sha256']:
            raise ValueError('Input identity changed: '+row['path'])
    for row in read_json(ROOT/'metadata/toolchain-lock.json')['executables']:
        if sha(Path(row['path']).read_bytes())!=row['sha256']:
            raise ValueError('Tool identity changed: '+row['path'])
    import capstone,unicorn
    lock=read_json(ROOT/'metadata/toolchain-lock.json')['python_packages']
    if capstone.__version__!=lock['capstone'] or unicorn.__version__!=lock['unicorn']:
        raise ValueError('Python package version differs from lock')
    image,meta=unpack(ASSET.read_bytes())
    if meta!=read_json(ROOT/'metadata/oracle.json'):
        raise ValueError('Fresh static decoding differs from pinned oracle')
    for path in (ROOT/'src').glob('*.asm'):
        for line in path.read_text().splitlines():
            code=line.split(';',1)[0].lower()
            if 'incbin' in code or ('%include' in code and path.name!='program.asm'):
                raise ValueError('Forbidden external byte/include source: '+str(path))
    actual=assemble()
    if actual!=image:
        differences=[i for i,(a,b) in enumerate(zip(actual,image)) if a!=b]
        raise ValueError(f'ASM mismatch: size {len(actual)}/{len(image)}, first differing offsets {differences[:10]}')
    for load in (0x1010,0x1213,0x2345):
        if relocated(actual,meta['relocations'],load)!=relocated(image,meta['relocations'],load):
            raise ValueError('Relocated image differs')
    analysis=analyze()
    inventory=dict(regions=analysis['regions'],overlays=analysis['overlays'])
    if inventory!=read_json(ROOT/'metadata/regions.json'):
        raise ValueError('Region inventory stale; investigate source/hints before regenerating')
    if (ROOT/'c/lemmings_sym.h').read_text()!=symtab.header():
        raise ValueError('C symbol header stale; run tools/symtab.py')
    from pcspeaker_symtab import header as pcspeaker_header
    if (ROOT/'c/pcspeaker_sym.h').read_text()!=pcspeaker_header():
        raise ValueError('PC-speaker C symbol header stale')
    if check_stub:
        from check_unpack import check
        for load,poison in ((0x1010,0),(0x1213,0xa5),(0x2345,0x5a)):
            check(load,poison)
    from sound import verify_drivers
    sound_metrics=verify_drivers()
    from protection import verify as verify_protection
    protection_metrics=verify_protection()
    from indirect import verify as verify_indirect
    indirect_metrics=verify_indirect()
    from interrupts import verify as verify_interrupts
    interrupt_metrics=verify_interrupts()
    if check_stub:
        import importlib.util
        spec=importlib.util.spec_from_file_location('sound_unpack',ROOT/'tests/sound_unpack.py')
        suite=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(suite)
        results=[suite.check(n,s,p) for n in ('adlib','tandysnd') for s,p in ((0x3000,0xa5),(0x4000,0x5a))]
        results += [suite.check('pcspeaker',load+0x842,p,load) for load,p in ((0x1010,0xa5),(0x2345,0x5a))]
        write_json(BUILD/'sound-unpack-tests.json',results)
        spec=importlib.util.spec_from_file_location('protection_tests',ROOT/'tests/protection.py')
        suite=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(suite)
        checks=suite.check()
        protection_metrics['handler_test_cases']=checks['case_count']
        protection_metrics['handler_instruction_sites']=len(checks['instruction_addresses'])
        spec=importlib.util.spec_from_file_location('dispatch_tests',ROOT/'tests/dispatch.py')
        suite=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(suite)
        checks=suite.check()
        indirect_metrics['bounded_caller_cases']=checks['case_count']
        indirect_metrics['caller_instruction_sites']=len(checks['original_instruction_sites'])
        for module_name,filename,prefix in (('installed_interrupt_tests','interrupts','handler'),
                                           ('timer_chain_tests','timer_chain','chain')):
            spec=importlib.util.spec_from_file_location(module_name,ROOT/f'tests/{filename}.py')
            suite=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(suite)
            checks=suite.check()
            interrupt_metrics[prefix+'_test_cases']=checks['case_count']
            interrupt_metrics[prefix+'_instruction_sites']=len(checks['original_instruction_sites'])
        spec=importlib.util.spec_from_file_location('dat_io_tests',ROOT/'tests/dat_io.py')
        suite=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(suite)
        checks=suite.check()
        dat_io_metrics=dict(case_count=checks['case_count'],
                            original_instruction_sites=len(checks['original_instruction_sites']),
                            branch_edges=len(checks['branch_edges']))
        spec=importlib.util.spec_from_file_location('decimal_digits_tests',ROOT/'tests/decimal_digits.py')
        suite=importlib.util.module_from_spec(spec);spec.loader.exec_module(suite)
        decimal_metrics=suite.check()
    metrics=dict(analysis['metrics'],reconstructed_asm_bytes=len(actual),byte_exact_asm_bytes=len(actual),
                 encoding_exceptions=len(read_json(ROOT/'metadata/encoding-exceptions.json')),
                 canonical_sha256=sha(image))
    metrics['sound']=sound_metrics
    metrics['protection']=protection_metrics
    metrics['indirect']=indirect_metrics
    metrics['interrupts']=interrupt_metrics
    if check_stub:metrics['dat_io']=dat_io_metrics
    if check_stub:metrics['decimal_digits_contracts']=decimal_metrics
    metrics['bounded_extractor_checks']=bool(check_stub)
    inputs=list((ROOT/'src').rglob('*.asm'))+[ROOT/p for p in
        ('metadata/hints.json','metadata/oracle.json','metadata/symbols.json',
         'metadata/regions.json','metadata/encoding-exceptions.json',
         'metadata/legacy-seeds.json','tools/unpack.py','tools/explore.py',
         'tools/build.py','tools/check_unpack.py','tools/verify.py',
         'tools/resources.py','tools/sound.py','tests/sound_unpack.py',
         'metadata/sound-oracle.json','metadata/sound-hints.json',
         'tools/protection.py','tests/protection.py','metadata/protection-symbols.json',
         'metadata/protection-views.json','metadata/protection-cfg.json','metadata/protection-encodings.json',
         'tools/indirect.py','tests/dispatch.py','metadata/indirect-evidence.json',
         'tools/interrupts.py','tests/interrupts.py','tests/timer_chain.py','metadata/interrupt-evidence.json')]
    inputs.append(ROOT/'tools/pcspeaker_symtab.py')
    inputs.append(ROOT/'metadata/pcspeaker-producers.json')
    inputs.append(ROOT/'tests/dat_io.py')
    inputs.append(ROOT/'tests/decimal_digits.py')
    inputs += [ROOT/f'metadata/{n}-{kind}.json' for n in sound_metrics for kind in ('symbols','regions','encodings')]
    metrics['verification_inputs']={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in inputs}
    write_json(BUILD/'verification.json',metrics)
    write_json(BUILD/'analysis.json',analysis)
    print(f'PASS {len(actual)} ASM bytes exact; {len(meta["relocations"])} relocations; no masked differences')
    print(f'FRONTIER {metrics["unresolved_byte_runs"]} unresolved byte runs; {metrics["unresolved_transfers"]} unresolved transfers')
    return metrics

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--skip-stub',action='store_true',help='Fast edit loop only; release gate must include stub checks')
    a=p.parse_args()
    verify(not a.skip_stub)

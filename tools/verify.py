"""Fast exact-image gate; --contracts adds the bounded behavioral campaign."""
import argparse
import ast
import importlib
import sys
import time
from contextlib import contextmanager, ExitStack
from pathlib import Path
from unittest.mock import patch
from common import ROOT, BUILD, read_json, write_json, sha
from unpack import ASSET, unpack, relocated
from build import assemble
from explore import analyze
import symtab

def local_python_closure(paths):
    """Conservatively include local imports, including imports inside helpers.

    Both local search roots are checked: test workers also load tools via
    sys.path. Dynamic worker roots are supplied by their consumed manifests.
    This reads source only; it neither imports test workers nor runs discovery.
    """
    pending=list(paths);seen=set()
    while pending:
        path=pending.pop()
        if path in seen:continue
        seen.add(path)
        if path.suffix!='.py':continue
        tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            names=([a.name for a in node.names] if isinstance(node,ast.Import) else
                   [node.module] if isinstance(node,ast.ImportFrom) and node.module else [])
            for name in names:
                for folder in ('tools','tests'):
                    candidate=ROOT/folder/(name.replace('.','/')+'.py')
                    if candidate.is_file():pending.append(candidate)
    return seen

def verification_sources():
    """Declared non-worker inputs for both verification scopes."""
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
    inputs.append(ROOT/'tools/sound_latch_symtab.py')
    inputs.append(ROOT/'c/sound_latches_sym.h')
    inputs.append(ROOT/'metadata/pcspeaker-producers.json')
    inputs.append(ROOT/'tests/dat_io.py')
    inputs.append(ROOT/'tests/decimal_digits.py')
    inputs += [ROOT/f'metadata/{n}-{kind}.json' for n in read_json(ROOT/'metadata/sound-oracle.json')
               for kind in ('symbols','regions','encodings')]
    inputs.append(BUILD/'asm/checked.asm')
    inputs.extend(BUILD/f'{name}-checked.asm' for name in read_json(ROOT/'metadata/sound-oracle.json'))
    inputs.extend(BUILD/f'protection-{name}-checked.asm' for name in ('stream','int1'))
    return inputs

def provenance_inputs(paths):
    """Complete consumed local closure, plus identities checked by this gate."""
    paths=set(paths)|{ROOT/p for p in ('tools/common.py','tools/symtab.py',
        'metadata/inputs.json','metadata/toolchain-lock.json',
        'c/lemmings_sym.h','c/pcspeaker_sym.h','c/sound_latches_sym.h')}
    paths.update(ROOT/row['path'] for row in read_json(ROOT/'metadata/inputs.json')['files'])
    paths.update(Path(row['path']) for row in read_json(ROOT/'metadata/toolchain-lock.json')['executables'])
    return local_python_closure(paths)

def input_manifest(paths):
    def key(path):
        return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path.resolve())
    return {key(p):sha(p.read_bytes()) for p in sorted(provenance_inputs(paths))}

def runtime_identity():
    import capstone,unicorn
    return dict(python=dict(path=str(Path(sys.executable).resolve()),sha256=sha(Path(sys.executable).read_bytes()),
                            version=sys.version),
                packages={m.__name__:dict(version=m.__version__,path=str(Path(m.__file__).resolve()))
                          for m in (capstone,unicorn)})

@contextmanager
def resolved_tool_usage():
    """Bind every assembler/disassembler call to the executable we actually hash.

    Consumers import build.tool by value, so bind those aliases as well. No
    assembler is launched here. The lock is checked against the selected bytes,
    rather than assuming the lock's pathname was selected by PATH/the override.
    """
    import build
    resolve=build.tool;used={}
    def selected(name):
        path=Path(resolve(name)).resolve();digest=sha(path.read_bytes())
        lock=read_json(ROOT/'metadata/toolchain-lock.json')['executables']
        expected=[r['sha256'] for r in lock if Path(r['path']).stem.lower()==name.lower()]
        if digest not in expected:raise ValueError('Selected tool identity differs from lock: '+str(path))
        row=dict(path=str(path),sha256=digest)
        if name in used and used[name]!=row:raise ValueError('Selected tool changed during verification: '+name)
        used[name]=row
        return str(path)
    with ExitStack() as stack:
        for name in ('build','sound','protection','reconstruct'):
            stack.enter_context(patch.object(importlib.import_module(name),'tool',selected))
        yield used

def identity_provenance_errors(result):
    """Reject legacy/incomplete manifests as retained identity evidence."""
    errors=[];inputs=result.get('verification_inputs',{})
    if result.get('provenance_version')!=1:return ['missing full input/tool provenance']
    required=provenance_inputs(verification_sources())
    for path in required:
        key=path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path.resolve())
        if key not in inputs:errors.append('unrecorded input: '+key)
    if result.get('verification_runtime')!=runtime_identity():errors.append('runtime identity changed')
    tools=result.get('verification_tools',{})
    if 'nasm' not in tools:errors.append('missing resolved NASM identity')
    for name,row in tools.items():
        import build
        path=Path(row['path'])
        try:
            same=(path.is_file() and sha(path.read_bytes())==row['sha256'] and
                  Path(build.tool(name)).resolve()==path.resolve())
        except (OSError,RuntimeError):same=False
        if not same:errors.append('resolved tool changed: '+name)
    return errors

def verify(check_stub=True, *, contracts=False):
    with resolved_tool_usage() as used:
        return _verify(check_stub,contracts=contracts,resolved_tools=used)

def _verify(check_stub=True, *, contracts=False, resolved_tools):
    if contracts and not check_stub:
        raise ValueError('Contract verification requires unpacker checks')
    # An edit-loop run must neither replace nor delete the full contract report.
    # Each mode invalidates its own report before doing work, including on failure.
    report_path = BUILD/('verification.json' if contracts else 'static-verification.json')
    report_path.unlink(missing_ok=True)
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
    from sound_latch_symtab import header as sound_latch_header
    if (ROOT/'c/sound_latches_sym.h').read_text()!=sound_latch_header():
        raise ValueError('Sound latch C symbol header stale')
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
    if contracts:
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
        from bounded_process import run_bounded
        run_bounded([sys.executable,str(ROOT/'tests/cache_allocation_contract.py')],
                    cwd=ROOT,timeout=60,memory_mib=256)
        cache_report=read_json(BUILD/'cache-allocation-contract-original.json')
        cache_allocation_metrics=dict(case_count=cache_report['case_count'],
            original_instruction_sites=cache_report['routine']['decoded_sites'],
            branch_outcomes=len(cache_report['branch_outcomes']['edges']),
            c_coverage_claimed=False,reachability_proven=False)
        run_bounded([sys.executable,str(ROOT/'tests/video_restore.py'),'--original-only'],
                    cwd=ROOT,timeout=150,memory_mib=384)
        video_report=read_json(BUILD/'video-restore-contract-original.json')
        video_restore_metrics=dict(case_count=video_report['case_count'],
            original_instruction_sites=len(video_report['executed_instruction_addresses']),
            auxiliary_core_cases=video_report['auxiliary_core_cases'],c_coverage_claimed=False)
        run_bounded([sys.executable,str(ROOT/'tests/vector_restore.py'),'--original-only'],
                    cwd=ROOT,timeout=150,memory_mib=384)
        vector_report=read_json(BUILD/'vector-restore-contract-original.json')
        vector_restore_metrics=dict(case_count=vector_report['case_count'],
            original_instruction_sites=len(vector_report['executed_instruction_addresses']),
            auxiliary_core_cases=vector_report['auxiliary_core_cases'],c_coverage_claimed=False)
        run_bounded([sys.executable,str(ROOT/'tests/timer_restore.py'),'--original-only'],
                    cwd=ROOT,timeout=150,memory_mib=384)
        timer_report=read_json(BUILD/'timer-restore-contract-original.json')
        timer_restore_metrics=dict(case_count=timer_report['case_count'],
            original_instruction_sites=len(timer_report['executed_instruction_addresses']),
            auxiliary_core_cases=timer_report['auxiliary_core_cases'],c_coverage_claimed=False)
        run_bounded([sys.executable,str(ROOT/'tests/fatal_cleanup.py'),'--original-only'],
                    cwd=ROOT,timeout=150,memory_mib=384)
        cleanup_report=read_json(BUILD/'fatal-cleanup-contract-original.json')
        cleanup_metrics=dict(case_count=cleanup_report['case_count'],
            original_instruction_sites=len(cleanup_report['executed_instruction_addresses']),
            caller_instruction_sites=cleanup_report['caller_sites'],
            branch_edges=len(cleanup_report['branch_edges']),c_coverage_claimed=False)
        run_bounded([sys.executable,str(ROOT/'tests/file_error.py'),'--original-only'],
                    cwd=ROOT,timeout=150,memory_mib=384)
        file_error_report=read_json(BUILD/'file-error-contract-original.json')
        file_error_metrics=dict(case_count=file_error_report['case_count'],
            original_instruction_sites=len(file_error_report['executed_instruction_addresses']),
            caller_instruction_sites=file_error_report['caller_sites'],
            branch_edges=len(file_error_report['branch_edges']),c_coverage_claimed=False)
        run_bounded([sys.executable,str(ROOT/'tests/resource_raw_full.py'),'--original-only'],
                    cwd=ROOT,timeout=150,memory_mib=384)
        raw_full_report=read_json(BUILD/'resource-raw-full-contract-original.json')
        raw_full_metrics=dict(case_count=raw_full_report['case_count'],
            original_instruction_sites=len(raw_full_report['executed_instruction_addresses']),
            caller_instruction_sites=raw_full_report['caller_sites'],
            original_boundaries_per_case=raw_full_report['original_boundaries_per_case'],
            branch_edges=len(raw_full_report['branch_edges']),c_coverage_claimed=False)
        display_metrics={}
        for name in ('display_status','display_start','display_setup','text_glyph','text_stream','display_pages','background_drawing','palette_channels','palette_rows','palette_ports','palette_row_select','palette_transition','retry_input'):
            run_bounded([sys.executable,str(ROOT/'tests'/(name+'.py')),'--original-only'],
                        cwd=ROOT,timeout=180 if name=='retry_input' else 720 if name in ('palette_row_select','palette_transition') else 390 if name=='palette_ports' else 660 if name=='palette_rows' else 360 if name=='palette_channels' else 210 if name=='background_drawing' else 150,memory_mib=384)
            report=read_json(BUILD/(name.replace('_','-')+'-contract-original.json'))
            display_metrics[name]=dict(case_count=report['case_count'],
                original_instruction_sites=len(report['executed_instruction_addresses']),
                branch_edges=len(report['branch_edges']),c_coverage_claimed=False)
            if name=='retry_input':
                display_metrics[name].update(exhaustive_word_cases=report['exhaustive_word_cases'],
                    original_only_keyboard_prefix_cases=report['producer_contracts']['case_count'])
    metrics=dict(analysis['metrics'],reconstructed_asm_bytes=len(actual),byte_exact_asm_bytes=len(actual),
                 encoding_exceptions=len(read_json(ROOT/'metadata/encoding-exceptions.json')),
                 canonical_sha256=sha(image))
    metrics['sound']=sound_metrics
    metrics['protection']=protection_metrics
    metrics['indirect']=indirect_metrics
    metrics['interrupts']=interrupt_metrics
    if contracts:metrics['dat_io']=dat_io_metrics
    if contracts:metrics['decimal_digits_contracts']=decimal_metrics
    if contracts:metrics['cache_allocation_contracts']=cache_allocation_metrics
    if contracts:metrics['video_restore_contracts']=video_restore_metrics
    if contracts:metrics['vector_restore_contracts']=vector_restore_metrics
    if contracts:metrics['timer_restore_contracts']=timer_restore_metrics
    if contracts:metrics['fatal_cleanup_contracts']=cleanup_metrics
    if contracts:metrics['file_error_contracts']=file_error_metrics
    if contracts:metrics['resource_raw_full_contracts']=raw_full_metrics
    if contracts:metrics['display_contracts']=display_metrics
    metrics['verification_scope']='contracts' if contracts else 'static'
    metrics['bounded_unpacker_checks']=bool(check_stub)
    metrics['bounded_extractor_checks']=bool(contracts)
    inputs=verification_sources()
    if contracts:
        inputs.extend(ROOT/path for path in cache_report['input_sha256'])
        inputs.extend(ROOT/path for path in video_report['input_hashes'])
        inputs.extend(ROOT/path for path in vector_report['input_hashes'])
        inputs.extend(ROOT/path for path in timer_report['input_hashes'])
        inputs.extend(ROOT/path for path in cleanup_report['input_hashes'])
        inputs.extend(ROOT/path for path in file_error_report['input_hashes'])
        inputs.extend(ROOT/path for path in raw_full_report['input_hashes'])
        for name in ('display_status','display_start','display_setup','text_glyph','text_stream','display_pages','background_drawing','palette_channels','palette_rows','palette_ports','palette_row_select','palette_transition','retry_input'):
            report=read_json(BUILD/(name.replace('_','-')+'-contract-original.json'))
            inputs.extend(ROOT/path for path in report['input_hashes'])
    metrics['verification_inputs']=input_manifest(inputs)
    metrics['provenance_version']=1
    metrics['verification_tools']=dict(resolved_tools)
    metrics['verification_runtime']=runtime_identity()
    write_json(report_path,metrics)
    write_json(BUILD/'analysis.json',analysis)
    print(f'PASS {len(actual)} ASM bytes exact; {len(meta["relocations"])} relocations; no masked differences')
    print(f'FRONTIER {metrics["unresolved_byte_runs"]} unresolved byte runs; {metrics["unresolved_transfers"]} unresolved transfers')
    print(f'PASS {metrics["verification_scope"]} verification; report: {report_path.name}')
    return metrics

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    modes=p.add_mutually_exclusive_group()
    modes.add_argument('--contracts',action='store_true',
        help='Also run the complete original-only behavioral contracts; required before aggregate coverage')
    modes.add_argument('--skip-stub',action='store_true',
        help='Static edit-loop check without bounded unpacker execution; not a contract gate')
    a=p.parse_args(argv)
    started=time.perf_counter()
    result=verify(not a.skip_stub,contracts=a.contracts)
    print(f'Elapsed: {time.perf_counter()-started:.2f}s')
    return result

if __name__=='__main__':
    main()

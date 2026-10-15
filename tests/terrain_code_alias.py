"""Original-only evidence for the terrain loop's unresolved code-stack alias."""
import gc
import sys
from pathlib import Path

sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),
               str(Path(__file__).resolve().parent)]
import terrain_stream as stream
from bounded_process import run_bounded
from common import BUILD, sha, write_json


def worker():
    evidence=[]
    for redraw,after in ((0,0x3768),(1,0x3978)):
        case=dict(name=f'code-stack-alias-{redraw}',seed=0,redraw=redraw,
            load=0x1010,ss=0x1010,sp=after+3,width=8,height=1,
            commands=[stream.command(8191,5)])
        memory,regs,flags,_game_ds=stream.prepare(case)
        device=stream.common.TraceDevice(bytearray(memory),0x3752)
        actual,_mask,seen,_edges,boundary,_child,_body=stream.piece.original(
            case,device,regs,flags,continuations=(after,))
        if boundary!=('continuation',0x1010,after):
            raise RuntimeError(f'Alias did not reach original near continuation: {boundary}')
        base=(regs['cs']<<4)+after
        changed=bytes(device.memory[base:base+3])
        expected=bytes((0x10,after&255,after>>8))
        if changed!=expected or changed==stream.IMAGE[after:after+3]:
            raise RuntimeError('Expected saved-SI and near-CALL code stores differ')
        decoded=next(stream.piece.MD.disasm(changed,after))
        if decoded.mnemonic!='adc':raise RuntimeError('Modified opcode identity differs')
        evidence.append(dict(entry=stream.RANGES[redraw][0],stop=after,
            stack_segment=regs['ss'],stack_offset=regs['sp'],
            original_bytes=stream.IMAGE[after:after+3].hex(),changed_bytes=changed.hex(),
            changed_instruction=f'{decoded.mnemonic} {decoded.op_str}',
            stopped_before_modified_instruction=True,executed_sites=sorted(seen),
            returned_source_cursor=actual['si']))
        gc.collect()
    write_json(BUILD/'terrain-code-alias-contracts.json',dict(
        image_sha256=sha(stream.IMAGE),original_only=True,c_coverage=False,cases=evidence,
        domain='ConstructedSS=CS stack overlaps the caller loop. Original identified '
            'children execute,then stop before the modified instruction; no game boot '
            'and no modified target execution or native-C equivalence claim.'))
    print('PASS terrain code alias:2 original-only stops before modified ADC; no C coverage')


if __name__=='__main__':
    if sys.argv[1:]==['--worker']:worker()
    elif len(sys.argv)==1:
        run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker'],
                    cwd=stream.ROOT,timeout=15,memory_mib=256)
    else:raise SystemExit('Unexpected terrain_code_alias arguments')

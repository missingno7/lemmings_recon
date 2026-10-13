"""Generate PC-speaker C offsets from the component's canonical symbol ledger."""
from common import ROOT,read_json

def header():
    rows=read_json(ROOT/'metadata/pcspeaker-symbols.json')
    out=['/* Generated from metadata/pcspeaker-symbols.json. */',
         '#ifndef LEMMINGS_PCSPEAKER_SYM_H','#define LEMMINGS_PCSPEAKER_SYM_H']
    names=set()
    for r in rows:
        for name in (r['symbol_name'],*r['aliases']):
            name='PC_'+name.removeprefix('pcspeaker_')
            if name in names:raise ValueError('Duplicate PC-speaker symbol')
            names.add(name);out.append(f'#define {name} 0x{r["address"]:04X}u')
        if 'element_size_symbol' in r:
            name='PC_'+r['element_size_symbol'].removeprefix('pcspeaker_')
            out.append(f'#define {name} {r["element_size"]}u')
    return '\n'.join(out+['#endif',''])

def generate():
    (ROOT/'c/pcspeaker_sym.h').write_text(header())

if __name__=='__main__':generate()

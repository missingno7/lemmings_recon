"""Define an evidence-backed symbol and split an unresolved db row if needed."""
import argparse
from common import ROOT, read_json, write_json
from where import address, rows
import symtab

def define(off,name,kind,size,evidence,segment=0):
    symbols=read_json(ROOT/'metadata/symbols.json')
    if any(s['address']+s['segment']*16==off for s in symbols):
        raise ValueError('Address already defined; use rename.py')
    relative=off-segment*16
    if relative<0 or (segment and relative>0xffff):raise ValueError('Symbol outside selected segment frame')
    symbols.append(dict(address=relative,segment=segment,kind=kind,size=size,symbol_name=name,aliases=[],
                        callers=[],callees=[],data_references=[],confidence='PROVEN',evidence=[evidence],verification_status='UNRESOLVED'))
    symtab.validate(symbols)
    matches=[r for r in rows() if r[0]<=off]
    start,path,n,text=matches[-1]
    lines=path.read_text().splitlines()
    if off==start:
        lines.insert(n-1,name+':')
    else:
        if not text.strip().startswith('db ') or 'ENCODED' in text:
            raise ValueError('Cannot split an instruction; use an overlay symbol in ledger')
        values=text.strip()[3:].split(';')[0].strip().split(',')
        split=off-start
        if not 0<split<len(values):
            raise ValueError('Address outside db row')
        lines[n-1:n]=['    db '+','.join(values[:split])+f' ; @{start:05X}',name+':',
                       '    db '+','.join(values[split:])+f' ; @{off:05X}']
    path.write_text('\n'.join(lines)+'\n')
    write_json(ROOT/'metadata/symbols.json',sorted(symbols,key=lambda r:r['segment']*16+r['address']))
    symtab.generate()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('address');p.add_argument('name')
    p.add_argument('--kind',default='data');p.add_argument('--size',type=int)
    p.add_argument('--segment',type=lambda value:int(value,16),default=0)
    p.add_argument('--evidence',required=True)
    a=p.parse_args()
    define(address(a.address),a.name,a.kind,a.size,a.evidence,a.segment)

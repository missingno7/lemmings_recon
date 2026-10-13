"""Show callers, callees and references without executing the game."""
import sys
from common import ROOT, read_json
from where import address

if __name__=='__main__':
    off=address(sys.argv[1])
    symbols=read_json(ROOT/'metadata/symbols.json')
    row=next(r for r in symbols if r['address']==off and r['segment']==0)
    print(row['symbol_name'],row['confidence'],row['verification_status'])
    for field in ('callers','callees'):
        print(field+':',' '.join(f'{x:04X}' for x in row[field]))
    for ref in row['data_references']:
        print(ref)

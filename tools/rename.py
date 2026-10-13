"""Rename ledger symbol and maintained ASM references; regenerate C offsets."""
import re
import sys
from common import ROOT, read_json, write_json
import symtab

def rename(old,new):
    rows=read_json(ROOT/'metadata/symbols.json')
    matches=[r for r in rows if r['symbol_name']==old]
    if len(matches)!=1:
        raise ValueError('Expected exactly one existing symbol')
    row=matches[0]
    row['aliases']=list(dict.fromkeys([*row['aliases'],old]))
    row['symbol_name']=new
    symtab.validate(rows)
    changes={}
    for path in (ROOT/'src').glob('*.asm'):
        original=path.read_text()
        updated=re.sub(r'\b'+re.escape(old)+r'\b',new,original)
        if updated!=original:
            changes[path]=updated
    # C clients consume generated CS_/SEGxxxx_ names; tests may look up the
    # canonical name as a string. Update both forms without duplicating offsets.
    pattern=re.compile(r'\b((?:CS_|SEG[0-9A-F]{4}_)?)(?:'+re.escape(old)+r')\b')
    clients=list((ROOT/'c').glob('*.c'))+list((ROOT/'c').glob('*.h'))+list((ROOT/'tests').glob('*.py'))
    for path in clients:
        if path.name=='lemmings_sym.h':
            continue
        original=path.read_text()
        updated=pattern.sub(lambda m:m[1]+new,original)
        if updated!=original:
            changes[path]=updated
    write_json(ROOT/'metadata/symbols.json',rows)
    for path,text in changes.items():
        path.write_text(text)
    symtab.generate()

if __name__=='__main__':
    if len(sys.argv)!=3:
        raise SystemExit('usage: rename.py OLD NEW (then run verify.py)')
    rename(*sys.argv[1:])

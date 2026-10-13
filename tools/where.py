"""Address/symbol -> maintained source and original static disassembly."""
import argparse
import re
import capstone
from common import ROOT, read_json
from unpack import unpack, ASSET

def address(value):
    symbols=read_json(ROOT/'metadata/symbols.json')
    protected=ROOT/'metadata/protection-symbols.json'
    if protected.exists():symbols+=read_json(protected)
    for s in symbols:
        if value in [s['symbol_name'],*s['aliases']]:
            return s['segment']*16+s['address']
    if value.lower().startswith('ds:'):
        return 0x9a90+int(value[3:],16)
    return int(value.split(':')[-1],16)

def rows(state=None):
    result=[]
    paths=(ROOT/'src').glob('*.asm') if state is None else (ROOT/'src/protection').glob('*.asm')
    for path in sorted(paths):
        for line,text in enumerate(path.read_text().splitlines(),1):
            m=re.search(r'; @([0-9A-F]{5})(?: (tf_on|tf_off|int1_plaintext))?$',text)
            if m and m[2]==state:
                result.append((int(m[1],16),path,line,text))
    return sorted(result)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('address')
    p.add_argument('--disasm',type=int,default=0)
    p.add_argument('--state',choices=('tf_on','tf_off','int1_plaintext'))
    a=p.parse_args()
    off=address(a.address)
    matches=[r for r in rows(a.state) if r[0]<=off]
    if not matches:
        raise SystemExit('No source at address')
    start,path,line,text=matches[-1]
    print(f'{off:05X}: {path}:{line} (+{off-start}) {text.strip()}')
    if a.disasm:
        if a.state:
            from protection import derive
            _,_,_,stream,handler=derive()
            known=handler if a.state=='int1_plaintext' else stream['instructions']
            for ins in [r for r in known if r['address']>=off and r['state']==a.state][:a.disasm]:
                print(f'{ins["address"]:05X} {ins["bytes"]:24} {ins["mnemonic"]} {ins["operands"]}')
            raise SystemExit(0)
        image,_=unpack(ASSET.read_bytes())
        md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16)
        for ins in md.disasm(image[off:off+15*a.disasm],off,count=a.disasm):
            print(f'{ins.address:05X} {ins.bytes.hex():24} {ins.mnemonic} {ins.op_str}')

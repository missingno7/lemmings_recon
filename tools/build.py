"""Assemble maintained NASM source without access to original binary inputs."""
import os
import shutil
import subprocess
from common import ROOT, BUILD, read_json

def tool(name):
    path = os.environ.get('LEMMINGS_' + name.upper()) or shutil.which(name)
    if not path:
        raise RuntimeError(f'{name} not found; set LEMMINGS_{name.upper()}')
    return path

def assemble():
    out = BUILD/'asm'
    out.mkdir(parents=True,exist_ok=True)
    checks=['%include "program.asm"']
    for symbol in read_json(ROOT/'metadata/symbols.json'):
        linear=symbol['segment']*16+symbol['address']
        checks.append(f'times -(({symbol["symbol_name"]} - $$) != {linear}) db 0 ; assert {symbol["symbol_name"]}')
    checked=out/'checked.asm'
    checked.write_text('\n'.join(checks)+'\n')
    subprocess.run([tool('nasm'),'-f','bin','-O0','-I',str(ROOT/'src')+os.sep,
                    '-l',str(out/'program.lst'),'-o',str(out/'program.bin'),
                    str(checked)],check=True)
    return (out/'program.bin').read_bytes()

if __name__=='__main__':
    print(f'Assembled {len(assemble())} bytes')

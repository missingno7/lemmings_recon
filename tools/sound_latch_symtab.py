"""Generate driver-relative C offsets from the two maintained sound ledgers."""
from common import ROOT, read_json


def header():
    out = ['/* Generated from metadata/adlib-symbols.json and tandysnd-symbols.json. */',
           '#ifndef LEMMINGS_SOUND_LATCHES_SYM_H',
           '#define LEMMINGS_SOUND_LATCHES_SYM_H']
    names = set()
    for driver, prefix in (('adlib', 'ADLIB_'), ('tandysnd', 'TANDY_')):
        for row in read_json(ROOT / f'metadata/{driver}-symbols.json'):
            for symbol in (row['symbol_name'], *row['aliases']):
                name = prefix + symbol.removeprefix(driver + '_')
                if name in names:
                    raise ValueError('Duplicate sound symbol: ' + name)
                names.add(name)
                out.append(f'#define {name} 0x{row["address"]:04X}u')
    return '\n'.join(out + ['#endif', ''])


if __name__ == '__main__':
    (ROOT / 'c/sound_latches_sym.h').write_text(header())

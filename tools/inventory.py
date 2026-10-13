"""Explicit one-time inventory/import; never invoked by the verification gate."""
import re
import argparse
from common import ROOT, read_json, write_json, sha
from unpack import unpack, ASSET, relocated

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy', type=str, required=True)
    args = parser.parse_args()
    from pathlib import Path
    legacy = Path(args.legacy)
    image, oracle = unpack(ASSET.read_bytes())
    loaded = relocated(image, oracle['relocations'], 0x1010)
    audit = legacy/'generated/vmless_boot/manifest.json'
    expected = read_json(audit)['source_exe']
    assert expected['sha256'] == oracle['packed_sha256']
    rows = []
    for p in sorted((ROOT/'assets').iterdir()):
        if p.is_file():
            b = p.read_bytes()
            old = legacy/'assets'/p.name
            rows.append(dict(path=p.relative_to(ROOT).as_posix(), size=len(b), sha256=sha(b),
                             matching_legacy_path=str(old) if old.exists() and sha(old.read_bytes()) == sha(b) else None))
    write_json(ROOT/'metadata/inputs.json', dict(schema=1, provenance='Pre-existing local assets; historical source not independently established.',
               audited_exe_manifest=str(audit), audited_exe_manifest_sha256=sha(audit.read_bytes()), files=rows))
    write_json(ROOT/'metadata/oracle.json', oracle)
    seeds, rejected, external = [], [], []
    for p in sorted((legacy/'lemmings/lifted/functions').glob('lifted_*.py')):
        text = p.read_text(encoding='utf-8')
        m = re.search(r'ENTRY = \(0x([0-9a-f]+), 0x([0-9a-f]+)\)', text, re.I)
        sig = re.search(r"SIGNATURE = bytes.fromhex\('([0-9a-f]+)'\)", text)
        if not m or not sig:
            continue
        seg, off = (int(v, 16) for v in m.groups())
        row = dict(segment=seg, offset=off, source=str(p), source_sha256=sha(p.read_bytes()), signature=sig[1])
        if seg != 0x1010:
            external.append(row)
        elif loaded[off:off+len(bytes.fromhex(sig[1]))] == bytes.fromhex(sig[1]):
            row['comparison'] = 'Full signature equals independently verified image relocated to 1010h; no masks'
            seeds.append(row)
        else:
            rejected.append(row)
    write_json(ROOT/'metadata/legacy-seeds.json', dict(note='Signature-matched entry leads, not proof of complete routine boundaries.',
               accepted=seeds, rejected=rejected, external=external))
    print(f'Inventoried {len(rows)} assets; seeds: {len(seeds)} matched, {len(rejected)} rejected, {len(external)} external')

if __name__ == '__main__':
    main()

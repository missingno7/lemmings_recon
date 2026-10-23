"""Fetch the pinned SDL3 MinGW development release into build/third_party.

The archive is identified by metadata/sdl3.json (URL, size, SHA-256). Nothing
downloaded is committed; build/ is gitignored. Extraction is checked against
path traversal and only the pinned target's include/lib/bin trees are used.
"""
import hashlib
import urllib.request
import zipfile
from pathlib import PurePosixPath
from common import ROOT, BUILD, read_json

PIN = read_json(ROOT/'metadata/sdl3.json')
DEST = BUILD/'third_party'/f"SDL3-{PIN['version']}"


def sdl3_root():
    """Directory holding include/, lib/ and bin/ for the pinned target."""
    return DEST/f"SDL3-{PIN['version']}"/PIN['target']


def fetch():
    root = sdl3_root()
    if (root/'include/SDL3/SDL.h').is_file():
        return root
    archive = BUILD/'third_party'/PIN['url'].rsplit('/', 1)[1]
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.is_file() or archive.stat().st_size != PIN['size']:
        with urllib.request.urlopen(PIN['url'], timeout=120) as response:
            data = response.read(PIN['size'] + 1)
        archive.write_bytes(data)
    data = archive.read_bytes()
    if len(data) != PIN['size'] or hashlib.sha256(data).hexdigest() != PIN['sha256']:
        archive.unlink()
        raise ValueError('SDL3 archive does not match metadata/sdl3.json')
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe path in SDL3 archive: '+name)
        z.extractall(DEST)
    if not (root/'include/SDL3/SDL.h').is_file():
        raise ValueError('SDL3 archive layout differs from the pinned target')
    return root


if __name__ == '__main__':
    print(fetch())

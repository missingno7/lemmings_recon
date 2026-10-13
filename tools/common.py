"""Small shared file helpers; no runtime or game dependencies."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')

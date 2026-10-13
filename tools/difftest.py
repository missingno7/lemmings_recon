"""Run the bounded native C-versus-original instruction suites."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    subprocess.run([sys.executable, str(ROOT / "tests" / "checksum.py")],
                   cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "tests" / "pcspeaker.py")],
                   cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "tests" / "dat.py")],
                   cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "tests" / "dat_io_c.py")],
                   cwd=ROOT, check=True)

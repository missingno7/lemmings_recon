"""Run the bounded native C-versus-original instruction suites."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    subprocess.run([sys.executable, str(ROOT / "tests" / "decimal_digits_c.py")],
                   cwd=ROOT, check=True, timeout=120)
    subprocess.run([sys.executable, str(ROOT / "tests" / "checksum.py")],
                   cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "tests" / "pcspeaker.py")],
                   cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "tests" / "dat.py")],
                   cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "tests" / "dat_io_c.py")],
                   cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "tests" / "dat_section.py")],
                   cwd=ROOT, check=True, timeout=120)
    subprocess.run([sys.executable, str(ROOT / "tests" / "dat_cache.py")],
                   cwd=ROOT, check=True, timeout=120)
    subprocess.run([sys.executable, str(ROOT / "tests" / "dat_files.py")],
                   cwd=ROOT, check=True, timeout=120)
    subprocess.run([sys.executable, str(ROOT / "tests" / "dat_load.py")],
                   cwd=ROOT, check=True, timeout=120)
    subprocess.run([sys.executable, str(ROOT / "tests" / "resource_raw.py")],
                   cwd=ROOT, check=True, timeout=120)
    subprocess.run([sys.executable, str(ROOT / "tests" / "resource_rle.py")],
                   cwd=ROOT, check=True, timeout=120)
    subprocess.run([sys.executable, str(ROOT / "tests" / "special_blit.py")],
                   cwd=ROOT, check=True, timeout=120)
    subprocess.run([sys.executable, str(ROOT / "tests" / "special_setup.py")],
                   cwd=ROOT, check=True, timeout=120)
    subprocess.run([sys.executable, str(ROOT / "tests" / "resource_select.py")],
                   cwd=ROOT, check=True, timeout=120)
    subprocess.run([sys.executable, str(ROOT / "tests" / "object_graphics.py")],
                   cwd=ROOT, check=True, timeout=120)
    subprocess.run([sys.executable, str(ROOT / "tests" / "object_coordinates.py")],
                   cwd=ROOT, check=True, timeout=120)
    subprocess.run([sys.executable, str(ROOT / "tests" / "object_cells.py")],
                   cwd=ROOT, check=True, timeout=120)
    subprocess.run([sys.executable, str(ROOT / "tests" / "steel_cells.py")],
                   cwd=ROOT, check=True, timeout=120)
    subprocess.run([sys.executable, str(ROOT / "tests" / "object_state.py")],
                   cwd=ROOT, check=True, timeout=120)
    for suite in ('vga_clear','drawing_layout','level_drawing'):
        subprocess.run([sys.executable,str(ROOT/'tests'/(suite+'.py'))],cwd=ROOT,check=True,timeout=120)

"""Run the agent's ants.py with parts switched off, to see what draws the line.

    python3 check_variants.py        # from this folder; about a minute

Variants (3 seeds each): the agent's version, ants that ignore pheromone
(they still lay it), and carrying ants with no pull toward the nest.
"""
import re
import subprocess
import sys
from pathlib import Path

here = Path(__file__).parent
src = (here / "ants.py").read_text()

VARIANTS = {
    "agent's version": lambda s: s,
    "ants ignore smell": lambda s: s.replace("    p = field[cx, cy]\n", "    p = field[cx, cy] * 0\n"),
    "no compass": lambda s: s.replace("GUIDE = 1.5", "GUIDE = 0.0"),
}

for name, change in VARIANTS.items():
    for seed in (1, 2, 3):
        code = change(src).replace("default_rng(1)", f"default_rng({seed})")
        code = code.replace('plt.savefig("ants.png"', 'plt.savefig("/dev/null", format="png"')
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout
        last = [l for l in out.splitlines() if l.startswith("step")][-1]
        total = re.search(r"total\s+(\d+)", last).group(1)
        carrying = re.search(r"carrying\s+(\d+)", last).group(1)
        corridor = re.search(r"corridor \(final\): ([\d.]+)%", out).group(1)
        print(f"{name:18s} seed {seed}: delivered {total:>5}, "
              f"green trail in corridor {corridor:>5}%, stuck carrying {carrying:>3}")

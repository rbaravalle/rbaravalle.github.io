"""Run Opus's ants.py with parts switched off, 3 seeds each.

    python3 check_variants.py      # from this folder; a few minutes
"""
import multiprocessing as mp, re, subprocess, sys
from pathlib import Path
src = (Path(__file__).parent / "ants.py").read_text()
SENSE = "v = np.where(carry, sample(home_ph, sp), sample(food_ph, sp))"
VARIANTS = {
    "Opus's version":                lambda s: s,
    "carriers ignore home trail":    lambda s: s.replace(SENSE, "v = np.where(carry, 0.0, sample(food_ph, sp))"),
    "searchers ignore food trail":   lambda s: s.replace(SENSE, "v = np.where(carry, sample(home_ph, sp), 0.0)"),
    "deposits don't fade":           lambda s: s.replace("EVAP, TAU = 0.985, 150.0", "EVAP, TAU = 0.985, 1e12"),
    "no minimum smell":              lambda s: s.replace("R) > 0.05", "R) > -1.0"),
}
def job(a):
    name, seed = a
    code = VARIANTS[name](src)
    assert code != src or name == "Opus's version", name
    code = code.replace("default_rng(1)", f"default_rng({seed})").replace('plt.savefig("ants.png", dpi=90)', "pass")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout
    total = int(re.search(r"delivered (\d+) of", out).group(1))
    left = re.findall(r"food left (\[[^\]]*\])", out)[-1]
    return name, seed, total, left
if __name__ == "__main__":
    jobs = [(n, s) for n in VARIANTS for s in (1, 2, 3)]
    with mp.Pool() as pool:
        for n, s, total, left in pool.imap(job, jobs):
            print(f"{n:28s} seed {s}: delivered {total:5d} of 9000, food left at the end {left}", flush=True)

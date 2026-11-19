"""Run the agent's ants.py with parts switched off, 4 seeds each (8 for the agent's version).

    python3 check_variants.py      # from this folder; several minutes
"""
import multiprocessing as mp, types
from pathlib import Path
src = (Path(__file__).parent / "ants.py").read_text()
VARIANTS = {   # name: (code change, extra params)
    "agent's version":             (lambda s: s, {}),
    "no fading deposits (TAU=0)":  (lambda s: s, {"TAU": 0.0}),
    "laden ants ignore home trail":(lambda s: s, {"IGNORE_HOME": 1}),
    "empty ants ignore food trail":(lambda s: s.replace("                field = A\n", "                field = None\n"), {}),
}
SEEDS = {"agent's version": range(1, 9)}
def job(a):
    name, seed = a
    change, extra = VARIANTS[name]
    m = types.ModuleType("v"); exec(change(src).replace('if __name__ == "__main__":', "if False:"), m.__dict__)
    r = m.run(dict(extra, SEED=seed))
    return name, seed, r["total"], r["late"], r["mean_trip"]
if __name__ == "__main__":
    jobs = [(n, s) for n in VARIANTS for s in SEEDS.get(n, range(1, 5))]
    with mp.Pool() as pool:
        for n, s, tot, late, trip in pool.imap(job, jobs):
            print(f"{n:30s} seed {s}: delivered {tot:6d}, last 3000 {late:5d}, mean trip {trip:7.1f}", flush=True)

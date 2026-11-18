"""Run the agent's ants.py with parts switched off (2 seeds each).

    python3 check_variants.py      # from this folder; a few minutes
"""
import multiprocessing as mp, types
from pathlib import Path
src = (Path(__file__).parent / "ants.py").read_text()
ANCHOR = "    B[nest_mask] = 1.0\n"
VARIANTS = {
    "agent's version": lambda s: s,
    "empty ants ignore food trail": lambda s: s.replace(ANCHOR, ANCHOR + "    Z = np.zeros((H, W))\n")
        .replace("field = A if not laden[i] else B", "field = Z if not laden[i] else B"),
    "nest smell only at the nest": lambda s: s.replace(ANCHOR, ANCHOR + "    B = np.where(nest_mask, 1.0, 0.0)\n"),
}
def job(a):
    name, seed = a
    m = types.ModuleType("v"); exec(VARIANTS[name](src).replace('if __name__ == "__main__":', "if False:"), m.__dict__)
    r = m.run(dict(SEED=seed))
    return name, seed, r["total"], r["late"], r["strong"], float(r["laden"].mean())
if __name__ == "__main__":
    jobs = [(n, s) for n in VARIANTS for s in (1, 2)]
    with mp.Pool(4) as pool:
        for n, s, tot, late, strong, laden in pool.imap(job, jobs):
            print(f"{n:30s} seed {s}: delivered {tot:5d}, last 3000 {late:5d}, "
                  f"strong trail cells {strong:4d}, carrying {laden:.2f}", flush=True)

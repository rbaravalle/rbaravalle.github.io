"""Control experiment: do laden ants get home because of the home trail?

Condition 'trail':  laden ants follow the home trail laid by other ants (normal).
Condition 'ignore': laden ants ignore the home trail (random walk); everything else identical.
"""
import multiprocessing as mp
import os
import ants

SEEDS = [1, 2, 3, 4]


def job(args):
    cond, seed = args
    params = dict(SEED=seed, IGNORE_HOME=1 if cond == "ignore" else 0)
    r = ants.run(params)
    return cond, seed, r["total"], r["late"], r["mean_trip"], r["strong"]


if __name__ == "__main__":
    jobs = [(c, s) for c in ("trail", "ignore") for s in SEEDS]
    with mp.Pool(min(len(jobs), os.cpu_count())) as pool:
        rows = pool.map(job, jobs)

    print(f"{'condition':9s} {'seed':>4s} {'delivered':>9s} {'last3000':>9s} {'mean trip':>10s}")
    for cond, seed, tot, late, trip, strong in rows:
        print(f"{cond:9s} {seed:4d} {tot:9d} {late:9d} {trip:10.1f}")

    def mean(cond, idx):
        vals = [r[idx] for r in rows if r[0] == cond]
        return sum(vals) / len(vals)

    t_tot, i_tot = mean("trail", 2), mean("ignore", 2)
    print(f"\nmean delivered: trail {t_tot:.0f}  ignore {i_tot:.0f}")
    print(f"mean trip steps: trail {mean('trail', 4):.1f}  ignore {mean('ignore', 4):.1f}")
    ok = mean("ignore", 4) > 3 * mean("trail", 4)
    print("PASS: the home trail is what brings ants home" if ok
          else "FAIL: removing the home trail did not reduce deliveries clearly")

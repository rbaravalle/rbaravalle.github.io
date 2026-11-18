"""Ant foraging with pheromone trails (stigmergy).

Ants do NOT know where the nest or food is. They only:
  - sense pheromone in the 3 cells ahead of them,
  - deposit pheromone on the cell they step on,
  - pick up / drop food when they stand on a food / nest patch
    (environment rule, not something the ants read).

Two pheromone channels:
  A ("food trail"): laid by ants carrying food. Empty ants follow it to food.
  B ("nest trail"): laid by empty ants; the nest also emits it. Laden ants follow it home.
"""
import sys
import numpy as np

W, H = 80, 60
NEST = (8, 30)        # (x, y) – hidden from ants
FOOD = (71, 30)       # (x, y) – hidden from ants
R = 2                 # radius of nest / food patches
DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]

DEFAULTS = dict(
    N_ANTS=250,
    STEPS=12000,
    EVAP=0.995,       # per-step evaporation (closer to 1 = longer memory)
    DIFF=0.0,         # per-step diffusion fraction (0 keeps trails narrow)
    DEPOSIT=1.0,
    SHARP=12.0,       # how strongly ants prefer stronger smell (higher = narrower trail)
    FLOOR=0.001,      # base attraction when no pheromone (exploration)
    NEST_SCENT_LEN=8.0,  # length scale of the nest's fixed smell gradient
    SEED=1,
)


def run(params, verbose=False):
    p = {**DEFAULTS, **params}
    rng = np.random.default_rng(p["SEED"])
    A = np.zeros((H, W))  # food trail
    yy, xx = np.mgrid[0:H, 0:W]
    nest_mask = (xx - NEST[0]) ** 2 + (yy - NEST[1]) ** 2 <= R * R
    food_mask = (xx - FOOD[0]) ** 2 + (yy - FOOD[1]) ** 2 <= R * R
    # nest smell: a fixed pheromone gradient emitted by the nest (not laid by ants)
    dist = np.sqrt((xx - NEST[0]) ** 2 + (yy - NEST[1]) ** 2)
    B = np.exp(-dist / p["NEST_SCENT_LEN"])
    B[nest_mask] = 1.0
    # ant state arrays
    n = p["N_ANTS"]
    X = np.full(n, NEST[0]); Y = np.full(n, NEST[1])
    Hd = rng.integers(8, size=n)
    laden = np.zeros(n, dtype=bool)

    def diffuse(F):
        q = np.pad(F, 1, mode="edge")
        nb = (q[:-2, 1:-1] + q[2:, 1:-1] + q[1:-1, :-2] + q[1:-1, 2:]) / 4
        return (1 - p["DIFF"]) * F + p["DIFF"] * nb

    food_delivered = 0
    pickups = 0
    window = 0
    log = []
    for step in range(1, p["STEPS"] + 1):
        for i in range(n):
            field = A if not laden[i] else B
            cands, wts = [], []
            for k in (-1, 0, 1):
                d = (Hd[i] + k) % 8
                nx, ny = X[i] + DIRS[d][0], Y[i] + DIRS[d][1]
                if 0 <= nx < W and 0 <= ny < H:
                    cands.append((d, nx, ny))
                    wts.append((field[ny, nx] + p["FLOOR"]) ** p["SHARP"])
            if not cands:
                Hd[i] = (Hd[i] + 4) % 8
                continue
            w = np.array(wts)
            d, nx, ny = cands[rng.choice(len(cands), p=w / w.sum())]
            Hd[i], X[i], Y[i] = d, nx, ny
            if laden[i]:
                A[ny, nx] += p["DEPOSIT"]   # food trail, laid only when carrying food
            if not laden[i] and food_mask[ny, nx]:
                laden[i] = True
                pickups += 1
                Hd[i] = (Hd[i] + 4) % 8
            elif laden[i] and nest_mask[ny, nx]:
                laden[i] = False
                Hd[i] = (Hd[i] + 4) % 8
                food_delivered += 1
                window += 1
        A = diffuse(A) * p["EVAP"]

        if step % 1000 == 0:
            flat = np.sort(A.ravel())[::-1]
            top = flat[: flat.size // 10].sum() / max(flat.sum(), 1e-9)
            strong = int((A > 0.2 * A.max()).sum()) if A.max() > 0 else 0
            if verbose:
                print(f"step {step:6d} | delivered total {food_delivered:5d} "
                      f"| last 1000 {window:4d} | laden {laden.mean():4.2f} "
                      f"| strong trail cells {strong:4d} | top10% share {top:4.2f}")
            log.append(window)
            window = 0

    late = sum(log[-3:])          # deliveries in last 3000 steps
    log_early = sum(log[:3])      # deliveries in first 3000 steps
    return dict(pickups=pickups, total=food_delivered, late=late, log_early=log_early, strong=strong, top=top,
                A=A, B=B, nest_mask=nest_mask, food_mask=food_mask,
                X=X, Y=Y, laden=laden, p=p)


def save_png(res, path="ants.png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    A, B, R_ = res["A"], res["B"], R
    fig, ax = plt.subplots(figsize=(10, 7.5))
    F = A  # show the food trail only (nest smell is a gradient, not a trail)
    cmap = plt.get_cmap("magma").copy(); cmap.set_bad("black")
    ax.imshow(np.ma.masked_less_equal(F, 0), cmap=cmap, origin="lower", extent=(0, W, 0, H),
              norm=matplotlib.colors.LogNorm(vmin=0.05, vmax=max(F.max(), 0.1)))
    e = ~res["laden"]
    ax.scatter(res["X"][e] + 0.5, res["Y"][e] + 0.5, s=8, c="cyan", label="ant (empty)")
    ax.scatter(res["X"][~e] + 0.5, res["Y"][~e] + 0.5, s=10, c="lime", label="ant (carrying food)")
    ax.add_patch(plt.Circle((NEST[0] + 0.5, NEST[1] + 0.5), R_, color="white", fill=False, lw=2))
    ax.add_patch(plt.Circle((FOOD[0] + 0.5, FOOD[1] + 0.5), R_, color="orange", fill=False, lw=2))
    ax.text(NEST[0], NEST[1] + R_ + 2, "nest", color="white", ha="center")
    ax.text(FOOD[0], FOOD[1] + R_ + 2, "food", color="orange", ha="center")
    ax.set_title(f"Ants after {res['p']['STEPS']} steps — food delivered: {res['total']}")
    ax.legend(loc="upper right", fontsize=8)
    plt.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "sweep":
        configs = [
            dict(),
            dict(SHARP=4.0),
            dict(SHARP=4.0, FLOOR=0.005),
            dict(SHARP=4.0, FLOOR=0.005, EVAP=0.99),
            dict(SHARP=6.0, FLOOR=0.005, EVAP=0.99),
            dict(SHARP=4.0, FLOOR=0.005, EVAP=0.99, DIFF=0.0),
        ]
        for c in configs:
            r = run(c)
            print(f"{str(c):70s} total {r['total']:4d} late3000 {r['late']:4d} "
                  f"strong cells {r['strong']:4d} top10% {r['top']:.2f}")
    else:
        extra = {}
        for arg in sys.argv[1:]:
            k, v = arg.split("=")
            extra[k] = float(v) if "." in v or "e" in v.lower() else int(v)
        r = run(extra, verbose=True)
        print(f"\nDeliveries in last 3000 steps: {r['late']}  total: {r['total']}")
        print(f"strong trail cells: {r['strong']}  top10% share: {r['top']:.2f}")
        early = r["log_early"]
        ok = r["late"] > 0 and r["late"] >= early and r["strong"] < 300
        print("PASS: deliveries continue and trail is narrow (strong cells < 300)" if ok
              else "FAIL: trail not established or too wide")
        save_png(r)
        print("saved ants.png")

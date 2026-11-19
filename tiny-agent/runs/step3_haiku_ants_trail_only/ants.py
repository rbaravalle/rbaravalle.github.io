"""Ant foraging with pheromone trails (stigmergy).

Information rules (the only information ants have):
  - Nest and food emit NO smell.
  - Ants sense only the two pheromone channels, in the 3 cells ahead.
  - Ants lay pheromone only on the cell they step on:
      * empty ants lay the HOME trail  (B)  -> laid on the way out from the nest
      * laden ants lay the FOOD trail  (A)  -> laid on the way back from the food
  - Empty ants follow the FOOD trail (A) to find food.
  - Laden ants follow the HOME trail (B) to get home.
  - Picking up / dropping food happens when an ant stands on a food / nest patch
    (environment rule; the ant itself does not read the patch coordinates).

Control: IGNORE_HOME=True makes laden ants ignore the HOME trail (random walk),
while still laying the same pheromone. This shows whether the trail is what
brings them home.
"""
import sys
import numpy as np

W, H = 80, 60
NEST = (8, 30)        # (x, y) – hidden from ants (only the environment uses it)
FOOD = (71, 30)       # (x, y) – hidden from ants (only the environment uses it)
R = 2                 # radius of nest / food patches
DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]

DEFAULTS = dict(
    N_ANTS=250,
    STEPS=12000,
    EVAP=0.99,        # per-step evaporation (closer to 1 = longer memory)
    DEPOSIT=1.0,
    SHARP=4.0,        # how strongly ants prefer stronger smell
    FLOOR=0.001,      # base attraction when no pheromone (exploration)
    IGNORE_HOME=0,    # 1 = laden ants ignore the home trail (control)
    TAU=150.0,        # deposit fades with time since leaving nest/food (0 = no fade)
    SEED=1,
)


def run(params, verbose=False):
    p = {**DEFAULTS, **params}
    rng = np.random.default_rng(p["SEED"])
    A = np.zeros((H, W))  # food trail (laid by laden ants)
    B = np.zeros((H, W))  # home trail (laid by empty ants)
    yy, xx = np.mgrid[0:H, 0:W]
    nest_mask = (xx - NEST[0]) ** 2 + (yy - NEST[1]) ** 2 <= R * R
    food_mask = (xx - FOOD[0]) ** 2 + (yy - FOOD[1]) ** 2 <= R * R

    n = p["N_ANTS"]
    X = np.full(n, NEST[0]); Y = np.full(n, NEST[1])
    Hd = rng.integers(8, size=n)
    laden = np.zeros(n, dtype=bool)
    trip_start = np.zeros(n, dtype=int)

    food_delivered = 0
    trip_times = []
    pickups = 0
    window = 0
    log = []
    for step in range(1, p["STEPS"] + 1):
        for i in range(n):
            # what the ant smells: food trail if empty, home trail if laden
            if laden[i]:
                field = None if p["IGNORE_HOME"] else B
            else:
                field = A
            cands, wts = [], []
            for k in (-1, 0, 1):
                d = (Hd[i] + k) % 8
                nx, ny = X[i] + DIRS[d][0], Y[i] + DIRS[d][1]
                if 0 <= nx < W and 0 <= ny < H:
                    cands.append((d, nx, ny))
                    s = 0.0 if field is None else field[ny, nx]
                    wts.append((s + p["FLOOR"]) ** p["SHARP"])
            if not cands:
                Hd[i] = (Hd[i] + 4) % 8
                continue
            w = np.array(wts)
            d, nx, ny = cands[rng.choice(len(cands), p=w / w.sum())]
            Hd[i], X[i], Y[i] = d, nx, ny

            # lay pheromone on the cell just entered
            age = step - trip_start[i]
            fade = np.exp(-age / p["TAU"]) if p["TAU"] > 0 else 1.0
            if laden[i]:
                A[ny, nx] += p["DEPOSIT"] * fade   # food trail: laid by laden ants
            else:
                B[ny, nx] += p["DEPOSIT"] * fade   # home trail: laid by empty ants

            # environment rules: pick up food / drop food
            if not laden[i] and food_mask[ny, nx]:
                laden[i] = True
                pickups += 1
                trip_start[i] = step
                Hd[i] = (Hd[i] + 4) % 8
            elif laden[i] and nest_mask[ny, nx]:
                laden[i] = False
                Hd[i] = (Hd[i] + 4) % 8
                food_delivered += 1
                window += 1
                trip_times.append(step - trip_start[i])
                trip_start[i] = step
        A *= p["EVAP"]
        B *= p["EVAP"]

        if step % 1000 == 0:
            strong = int((A > 0.2 * A.max()).sum()) if A.max() > 0 else 0
            if verbose:
                print(f"step {step:6d} | delivered total {food_delivered:5d} "
                      f"| last 1000 {window:4d} | laden {laden.mean():4.2f} "
                      f"| strong food-trail cells {strong:4d}")
            log.append(window)
            window = 0

    late = sum(log[-3:])
    early = sum(log[:3])
    strong = int((A > 0.2 * A.max()).sum()) if A.max() > 0 else 0
    return dict(total=food_delivered, pickups=pickups, late=late, early=early,
                strong=strong,
                mean_trip=float(np.mean(trip_times)) if trip_times else float("nan"),
                A=A, B=B, nest_mask=nest_mask, food_mask=food_mask,
                X=X, Y=Y, laden=laden, p=p)


def save_png(res, path="ants.png", title_extra=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    F = res["A"]
    fig, ax = plt.subplots(figsize=(10, 7.5))
    cmap = plt.get_cmap("magma").copy(); cmap.set_bad("black")
    ax.imshow(np.ma.masked_less_equal(F, 0), cmap=cmap, origin="lower",
              extent=(0, W, 0, H),
              norm=matplotlib.colors.LogNorm(vmin=0.05, vmax=max(F.max(), 0.1)))
    e = ~res["laden"]
    ax.scatter(res["X"][e] + 0.5, res["Y"][e] + 0.5, s=8, c="cyan", label="ant (empty)")
    ax.scatter(res["X"][~e] + 0.5, res["Y"][~e] + 0.5, s=10, c="lime", label="ant (carrying food)")
    ax.add_patch(plt.Circle((NEST[0] + 0.5, NEST[1] + 0.5), R, color="white", fill=False, lw=2))
    ax.add_patch(plt.Circle((FOOD[0] + 0.5, FOOD[1] + 0.5), R, color="orange", fill=False, lw=2))
    ax.text(NEST[0], NEST[1] + R + 2, "nest", color="white", ha="center")
    ax.text(FOOD[0], FOOD[1] + R + 2, "food", color="orange", ha="center")
    ax.set_title(f"Food trail after {res['p']['STEPS']} steps — delivered: {res['total']}{title_extra}")
    ax.legend(loc="upper right", fontsize=8)
    plt.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    extra = {}
    for arg in sys.argv[1:]:
        k, v = arg.split("=")
        extra[k] = float(v) if "." in v or "e" in v.lower() else int(v)
    r = run(extra, verbose=True)
    print(f"\nDeliveries in last 3000 steps: {r['late']}  total: {r['total']}  "
          f"mean trip (steps): {r['mean_trip']:.1f}")
    print(f"strong food-trail cells: {r['strong']}")
    save_png(r)
    print("saved ants.png")

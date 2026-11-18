"""Ant foraging with pheromone trails: food source -> nest.

Ants search for food (following a 'food' pheromone laid by ants returning
home), pick it up, and carry it back to the nest (following a 'home'
pheromone laid by ants that left the nest). A wall with one gap forces
trails to bend around it. A baseline run with pheromones disabled
(search + homing bias still on, no pheromone) is used to check that trails help.
"""
import random
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

N = 60                      # grid is N x N, indexed [x, y]
NEST = (8, 8)
FOOD = (50, 50)
R = 3                        # radius of nest / food source
N_ANTS = 150
STEPS = 10000
DEP = 1.0                    # pheromone deposited per step
DECAY = 0.998                # per-step evaporation factor
ALPHA = 4.0                  # how strongly ants follow pheromone
INERTIA = 1.5                # bonus for continuing in same direction
HOME_W = 0.5                 # carriers get a mild bonus for steps toward the nest
DIRS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def make_wall():
    wall = np.zeros((N, N), dtype=bool)
    wall[30, :] = True
    wall[30, 38:45] = False  # single gap, off the straight line nest-food
    return wall


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def run(use_pheromone, seed=1, log=True):
    random.seed(seed)
    np.random.seed(seed)
    wall = make_wall()
    home_ph = np.zeros((N, N))
    food_ph = np.zeros((N, N))
    ants = []
    for _ in range(N_ANTS):
        d = random.choice(DIRS)
        ants.append({"x": NEST[0], "y": NEST[1], "carry": False, "d": d})
    deliveries = 0
    hist = []          # (step, cumulative deliveries)

    for t in range(1, STEPS + 1):
        for a in ants:
            x, y = a["x"], a["y"]
            field = None
            if use_pheromone:
                field = home_ph if a["carry"] else food_ph
            cells, weights = [], []
            for dx, dy in DIRS:
                nx, ny = x + dx, y + dy
                if 0 <= nx < N and 0 <= ny < N and not wall[nx, ny]:
                    w = 1.0
                    if field is not None:
                        f = field[nx, ny]
                        w += ALPHA * f / (1.0 + f)  # saturating: keeps randomness
                    if (dx, dy) == a["d"]:
                        w *= INERTIA
                    if a["carry"] and cheb((nx, ny), NEST) < cheb((x, y), NEST):
                        w += HOME_W
                    cells.append((nx, ny, (dx, dy)))
                    weights.append(w)
            nx, ny, d = random.choices(cells, weights=weights)[0]
            a["x"], a["y"], a["d"] = nx, ny, d

            if use_pheromone:
                if a["carry"]:
                    food_ph[nx, ny] += DEP   # carriers mark the food->nest trail
                else:
                    home_ph[nx, ny] += DEP   # searchers mark the nest->food trail

            if not a["carry"] and cheb((nx, ny), FOOD) <= R:
                a["carry"] = True
                a["d"] = (-d[0], -d[1])      # turn around toward nest
            elif a["carry"] and cheb((nx, ny), NEST) <= R:
                a["carry"] = False
                a["d"] = (-d[0], -d[1])
                deliveries += 1

        home_ph *= DECAY
        food_ph *= DECAY
        if t % 100 == 0:
            hist.append((t, deliveries))
            if log:
                carrying = sum(a["carry"] for a in ants)
                on_trail = sum(1 for a in ants if food_ph[a["x"], a["y"]] > 0.5
                               or home_ph[a["x"], a["y"]] > 0.5)
                print(f"  step {t:5d}  delivered_total={deliveries:4d}  "
                      f"carrying={carrying:3d}  ants_on_trail={on_trail:3d}  "
                      f"food_ph_total={food_ph.sum():8.1f}")
    return {"hist": hist, "deliveries": deliveries, "ants": ants,
            "home_ph": home_ph, "food_ph": food_ph, "wall": wall}


def concentration(field, top_frac=0.05):
    """Fraction of total pheromone held by the top 5% of cells (1 = one line)."""
    v = np.sort(field.ravel())[::-1]
    k = max(1, int(top_frac * v.size))
    total = v.sum()
    return float(v[:k].sum() / total) if total > 0 else 0.0


def ascii_map(A, step=2):
    """Coarse text picture of the food->nest trail (N = nest, F = food, # = wall)."""
    f = A["food_ph"]
    chars = " .:-=+*#%@"
    mx = f.max() if f.max() > 0 else 1.0
    print("\nASCII trail map (x across, y up; each char = %dx%d cells):" % (step, step))
    for y in range(N - 1, -1, -step):
        row = ""
        for x in range(0, N, step):
            cx, cy = x, y
            if cheb((cx, cy), NEST) <= R:
                row += "N"
            elif cheb((cx, cy), FOOD) <= R:
                row += "F"
            elif A["wall"][cx, cy]:
                row += "#"
            else:
                v = f[x:x + step, y - step + 1:y + 1].max() / mx
                row += chars[min(len(chars) - 1, int(v * (len(chars) - 1)))]
        print("  " + row)


def main():
    print("Run A: with pheromone trails")
    A = run(True, seed=1)
    print("Run B: baseline, pheromones off (random walk)")
    B = run(False, seed=1, log=False)

    print(f"\nTotal deliveries  pheromone={A['deliveries']}  baseline={B['deliveries']}")
    print("Cumulative deliveries over time (step: pheromone / baseline):")
    for (t, a), (_, b) in zip(A["hist"], B["hist"]):
        if t % 2000 == 0:
            print(f"  {t:5d}: {a:4d} / {b:4d}")
    conc = concentration(A["food_ph"])
    print(f"\nFood-trail concentration (mass in top 5% cells): {conc:.3f}")

    # Last-window rate vs. first-window rate for pheromone run
    h = A["hist"]
    first = h[9][1]
    last = h[-1][1] - h[-11][1]
    print(f"Deliveries first 1000 steps={first}, last 1000 steps={last}")

    ok1 = A["deliveries"] > 2 * max(B["deliveries"], 1)
    ok2 = conc > 0.15
    ok3 = last > first
    print(f"CHECK pheromone > 2x baseline deliveries: {'PASS' if ok1 else 'FAIL'}")
    print(f"CHECK trail concentrated (>0.15):         {'PASS' if ok2 else 'FAIL'}")
    print(f"CHECK throughput rising over time:        {'PASS' if ok3 else 'FAIL'}")

    # Figure
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5))
    ax = axes[0]
    combo = A["home_ph"] + A["food_ph"]
    im = ax.imshow(np.log1p(combo).T, origin="lower", cmap="magma")
    wall = A["wall"]
    ax.imshow(np.ma.masked_where(~wall.T, wall.T), origin="lower",
              cmap="gray", alpha=1.0)
    xs = [a["x"] for a in A["ants"]]
    ys = [a["y"] for a in A["ants"]]
    ax.scatter(xs, ys, s=6, c="cyan", label="ants")
    ax.scatter([NEST[0]], [NEST[1]], s=300, marker="s", c="lime", label="nest")
    ax.scatter([FOOD[0]], [FOOD[1]], s=300, marker="*", c="yellow", label="food")
    ax.set_title(f"Final state (step {STEPS}), log pheromone")
    ax.legend(loc="upper left", fontsize=8)
    fig.colorbar(im, ax=ax, fraction=0.046)

    ax = axes[1]
    ax.imshow(np.log1p(A["food_ph"]).T, origin="lower", cmap="Reds")
    ax.set_title("Food->nest trail (carrier pheromone)")
    ax = axes[2]
    ax.imshow(np.log1p(A["home_ph"]).T, origin="lower", cmap="Blues")
    ax.set_title("Nest->food trail (searcher pheromone)")

    fig2_ax = fig.add_axes([0.0, 0.0, 0.0, 0.0])  # placeholder (unused)
    fig2_ax.remove()
    fig.suptitle(f"Deliveries: pheromone={A['deliveries']}  baseline={B['deliveries']}")
    fig.tight_layout()
    fig.savefig("ants.png", dpi=110)
    ascii_map(A)
    print("\nSaved ants.png")


if __name__ == "__main__":
    main()

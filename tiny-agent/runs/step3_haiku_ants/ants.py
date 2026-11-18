"""Ant foraging with pheromone trails: food source -> nest.

Two pheromone fields:
  trail_food : laid by ants carrying food (marks the way back to the nest from the food)
  trail_home : laid by ants searching for food (marks the way to the food)
Carrying ants follow trail_home toward the nest; searching ants follow trail_food.
Prints numbers over time; saves final state to ants.png.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

rng = np.random.default_rng(1)

W = H = 80
N_ANTS = 400
STEPS = 30000
REPORT = 2000
NEST = np.array([10, 10])
FOOD = np.array([68, 68])
NEST_R = 3
FOOD_R = 3
DEPOSIT = 1.0
DECAY = 0.998
ALPHA = 1.5          # pheromone sensitivity
INERTIA = 1.6        # bonus for continuing in the same direction
EPS = 0.05
REVERSE = 0.1       # weight multiplier for turning straight back
GUIDE = 1.5          # carrying ants: bias toward the nest direction

DIRS = np.array([(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)])

pos = np.tile(NEST, (N_ANTS, 1)).astype(int)
carry = np.zeros(N_ANTS, dtype=bool)
last_dir = rng.integers(0, 8, N_ANTS)
trail_food = np.zeros((W, H))
trail_home = np.zeros((W, H))

xs, ys = np.meshgrid(np.arange(W), np.arange(H), indexing="ij")
_seg = FOOD - NEST
_t = np.clip(((xs - NEST[0]) * _seg[0] + (ys - NEST[1]) * _seg[1]) / (_seg @ _seg), 0, 1)
seg_dist = np.hypot(xs - (NEST[0] + _t * _seg[0]), ys - (NEST[1] + _t * _seg[1]))
CORRIDOR = 6.0


def on_path_share(field):
    """Share of pheromone mass lying within CORRIDOR cells of the straight nest-food line."""
    tot = field.sum()
    return field[seg_dist <= CORRIDOR].sum() / tot if tot > 0 else 0.0


delivered = 0
window_delivered = 0
history = []


def choose_moves(field, pos, last_dir, guide_to=None):
    """Pick a neighbour per ant with probability ~ (pheromone+eps)^ALPHA * inertia.
    guide_to: optional (N,2) target; multiplies weights by exp(GUIDE*cos(angle)) so
    loaded ants can still find the nest before a trail exists."""
    nxt = pos[:, None, :] + DIRS[None, :, :]               # (N,8,2)
    inside = (nxt[..., 0] >= 0) & (nxt[..., 0] < W) & (nxt[..., 1] >= 0) & (nxt[..., 1] < H)
    cx = np.clip(nxt[..., 0], 0, W - 1)
    cy = np.clip(nxt[..., 1], 0, H - 1)
    p = field[cx, cy]
    w = (np.log1p(p) + EPS) ** ALPHA          # log: stops one huge peak from trapping ants
    w = np.where(np.arange(8)[None, :] == last_dir[:, None], w * INERTIA, w)
    # discourage immediate reversal (opposite of last direction is index 7-i)
    w = np.where(np.arange(8)[None, :] == (7 - last_dir)[:, None], w * REVERSE, w)
    if guide_to is not None:
        to = guide_to - pos                                  # (N,2)
        norm = np.linalg.norm(to, axis=1, keepdims=True) + 1e-9
        dn = np.linalg.norm(DIRS, axis=1)[None, :]
        cosang = (DIRS[None, :, :] * (to / norm)[:, None, :]).sum(axis=2) / dn
        w = w * np.exp(GUIDE * cosang)
    w = np.where(inside, w, 0.0)
    cum = np.cumsum(w, axis=1)
    r = rng.random(len(pos)) * cum[:, -1]
    k = (cum < r[:, None]).sum(axis=1)
    k = np.minimum(k, 7)
    return k


for step in range(1, STEPS + 1):
    # ---- move every ant one step ----
    k = np.where(carry,
                 choose_moves(trail_home, pos, last_dir, guide_to=np.tile(NEST, (N_ANTS, 1))),
                 choose_moves(trail_food, pos, last_dir))
    pos = pos + DIRS[k]
    pos[:, 0] = np.clip(pos[:, 0], 0, W - 1)
    pos[:, 1] = np.clip(pos[:, 1], 0, H - 1)
    last_dir = k

    # ---- deposit pheromone where each ant stands ----
    cx, cy = pos[:, 0], pos[:, 1]
    np.add.at(trail_food, (cx[carry], cy[carry]), DEPOSIT)
    np.add.at(trail_home, (cx[~carry], cy[~carry]), DEPOSIT)

    # ---- pick up food at source ----
    at_food = (~carry) & (np.abs(pos - FOOD).max(axis=1) <= FOOD_R)
    carry[at_food] = True
    # ---- drop food at nest ----
    at_nest = carry & (np.abs(pos - NEST).max(axis=1) <= NEST_R)
    n_drop = at_nest.sum()
    delivered += n_drop
    window_delivered += n_drop
    carry[at_nest] = False

    # ---- evaporate ----
    trail_food *= DECAY
    trail_home *= DECAY

    if step % REPORT == 0:
        # path measure: share of strong food-trail mass lying in cells with high pheromone
        strong = trail_food > 0.5 * trail_food.max()
        frac_cells = strong.sum() / (W * H)
        history.append((step, window_delivered, delivered))
        print(f"step {step:6d} | delivered in window {window_delivered:4d} | "
              f"total {delivered:5d} | carrying {carry.sum():3d} | "
              f"strong-trail cells {strong.sum():5d} ({100*frac_cells:4.1f}% of grid) | "
              f"food-trail on nest-food corridor {100*on_path_share(trail_food):5.1f}%")
        window_delivered = 0

# ---- summary checks ----
corridor = on_path_share(trail_food)
rates = [h[1] for h in history]
print()
print(f"deliveries per window, last 5: {rates[-5:]}")
print(f"food-trail mass on nest-food corridor (final): {100*corridor:.1f}%")
ok_path = corridor > 0.8
ok_flow = min(rates[-5:]) >= 50
print(f"PATH FORMED (corridor share > 80%): {'PASS' if ok_path else 'FAIL'}")
print(f"FLOW SUSTAINED (>=50 deliveries per window, last 5): {'PASS' if ok_flow else 'FAIL'}")

# ---- image ----
fig, ax = plt.subplots(1, 2, figsize=(12, 6))
ax[0].imshow(trail_food.T, origin="lower", cmap="Greens")
ax[0].set_title("food trail pheromone (food -> nest)")
ax[1].imshow(trail_home.T, origin="lower", cmap="Blues")
ax[1].set_title("home trail pheromone (nest -> food)")
for a in ax:
    a.scatter(*NEST, c="red", s=200, marker="s", label="nest")
    a.scatter(*FOOD, c="orange", s=200, marker="*", label="food")
    a.legend(loc="lower right")
fig.suptitle(f"Ants after {STEPS} steps, total delivered = {delivered}")
plt.tight_layout()
plt.savefig("ants.png", dpi=110)
print("saved ants.png")

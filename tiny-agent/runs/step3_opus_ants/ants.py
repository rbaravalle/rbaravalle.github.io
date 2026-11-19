"""Ant foraging: emergent trails from pheromone only.
Ants never know where nest/food are. They only:
  - smell two pheromone fields with 3 short-range sensors (left/front/right)
  - notice nest/food when they physically step onto it
Searching ants lay 'home' pheromone (stronger the more recently they left a nest)
and follow 'food' pheromone. Carrying ants lay 'food' pheromone and follow 'home'.
"""
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def uniform_filter(a, _=3):
    p = np.pad(a, 1, mode="edge")
    return sum(p[1+dy:1+dy+a.shape[0], 1+dx:1+dx+a.shape[1]] for dy in (-1,0,1) for dx in (-1,0,1)) / 9.0

rng = np.random.default_rng(1)
W = H = 200
N_ANTS, STEPS = 600, 10000
NESTS = [(40, 40), (160, 150)]
FOODS = [(165, 35), (35, 165), (120, 80)]
FOOD_AMOUNT = 3000
R_NEST, R_FOOD = 6, 5
SPEED, SENS_D, SENS_A, TURN = 1.0, 4.0, 0.6, 0.45
EVAP, TAU = 0.985, 150.0

yy, xx = np.mgrid[0:H, 0:W]
def disk_mask(centers, r):
    m = np.zeros((H, W), bool)
    for cx, cy in centers: m |= (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
    return m
nest_mask, food_mask = disk_mask(NESTS, R_NEST), disk_mask(FOODS, R_FOOD)

home_ph = np.zeros((H, W)); food_ph = np.zeros((H, W))
start = rng.integers(len(NESTS), size=N_ANTS)
pos = np.array(NESTS, float)[start] + rng.normal(0, 2, (N_ANTS, 2))
ang = rng.uniform(0, 2 * np.pi, N_ANTS)
carry = np.zeros(N_ANTS, bool)
picked_at = [[] for _ in FOODS]
food_left = np.full(len(FOODS), FOOD_AMOUNT)
food_id = np.full((H, W), -1)
for i, (cx, cy) in enumerate(FOODS): food_id[(xx - cx) ** 2 + (yy - cy) ** 2 <= R_FOOD ** 2] = i
scout = rng.random(N_ANTS) < 0.15       # explorers: weak pheromone attraction, more wandering
noise = np.where(scout, 0.35, 0.12)
t_since = np.zeros(N_ANTS)          # steps since last touching nest/food
delivered_log, total = [], 0
SNAPS = [800, 2000, 4500, 7000, 9000]; snaps = {}

def sample(field, p):
    x = np.clip(p[:, 0].astype(int), 0, W - 1); y = np.clip(p[:, 1].astype(int), 0, H - 1)
    return field[y, x]

def render():
    img = np.zeros((H, W, 3))
    img[..., 1] = np.sqrt(food_ph / (np.percentile(food_ph, 99.5) + 1e-9)).clip(0, 1)
    img[..., 2] = np.sqrt(home_ph / (np.percentile(home_ph, 99.5) + 1e-9)).clip(0, 1) * 0.7
    img[food_id >= 0] = (0.4, 0.4, 0.1); img[food_mask] = (1, 1, 0.2); img[nest_mask] = (1, 0.3, 0.1)
    for x, y in pos[carry].astype(int): img[y, x] = (1, 0, 1)
    for x, y in pos[~carry].astype(int): img[y, x] = np.maximum(img[y, x], 0.6)
    return img, food_left.tolist()

for step in range(STEPS):
    # --- sense: carriers follow home pheromone, searchers follow food pheromone
    s = []
    for da in (-SENS_A, 0, SENS_A):
        sp = pos + SENS_D * np.c_[np.cos(ang + da), np.sin(ang + da)]
        v = np.where(carry, sample(home_ph, sp), sample(food_ph, sp))
        s.append(v)
    L, F, R = s
    smell = np.maximum(np.maximum(L, F), R) > 0.05   # below this the ant smells nothing
    turn = smell * np.where(scout & ~carry & (rng.random(N_ANTS) < 0.5), 0.0, 1.0) * np.where((L > F) & (L > R), -TURN, np.where((R > F) & (R > L), TURN, 0.0))
    ang += turn + rng.normal(0, 1, N_ANTS) * noise
    # --- move, bounce off walls
    pos += SPEED * np.c_[np.cos(ang), np.sin(ang)]
    out_x = (pos[:, 0] < 0) | (pos[:, 0] >= W - 1); out_y = (pos[:, 1] < 0) | (pos[:, 1] >= H - 1)
    ang[out_x] = np.pi - ang[out_x]; ang[out_y] = -ang[out_y]
    pos = np.clip(pos, 0, W - 1.001)
    t_since += 1
    # --- contact events (local only)
    on_food = sample(food_mask, pos) & ~carry
    fid = sample(food_id, pos)
    for i in range(len(FOODS)):
        hit = np.flatnonzero(on_food & (fid == i))
        if len(hit) > food_left[i]: on_food[hit[food_left[i]:]] = False; hit = hit[:food_left[i]]
        food_left[i] -= len(hit); picked_at[i].append((step, len(hit)))
        if food_left[i] == 0: food_mask[food_id == i] = False
    on_nest = sample(nest_mask, pos) & carry
    carry[on_food] = True; ang[on_food] += np.pi; t_since[on_food] = 0
    carry[on_nest] = False; ang[on_nest] += np.pi; t_since[on_nest] = 0
    total += on_nest.sum()
    t_since[sample(nest_mask, pos) & ~carry] = 0   # passing through nest refreshes
    # --- deposit: strength decays with time since leaving source -> gradient
    amt = np.exp(-t_since / TAU)
    ix = pos[:, 0].astype(int); iy = pos[:, 1].astype(int)
    np.add.at(food_ph, (iy[carry], ix[carry]), amt[carry])
    np.add.at(home_ph, (iy[~carry], ix[~carry]), amt[~carry])
    # --- evaporate + slight diffusion
    food_ph = EVAP * (0.8 * food_ph + 0.2 * uniform_filter(food_ph, 3))
    home_ph = EVAP * (0.8 * home_ph + 0.2 * uniform_filter(home_ph, 3))
    if step + 1 in SNAPS: snaps[step + 1] = render()
    if (step + 1) % 500 == 0:
        delivered_log.append(total)
        fp = np.sort(food_ph.ravel())[::-1]; c = np.cumsum(fp) / fp.sum()
        area = (np.searchsorted(c, 0.8) + 1) / fp.size * 100
        prev = delivered_log[-2] if len(delivered_log) > 1 else 0
        print(f"step {step+1:5d}  delivered total {total:6d}  last 500 steps {total-prev:5d}  "
              f"food left {food_left.tolist()}  carrying {carry.sum():3d}  80% of food-pheromone in {area:5.2f}% of area")

# --- trail check: sample food pheromone along straight lines nest->food vs. random background
def line_mean(a, b, n=100):
    t = np.linspace(0.15, 0.85, n)
    return food_ph[(a[1] + t * (b[1] - a[1])).astype(int), (a[0] + t * (b[0] - a[0])).astype(int)].mean()
for i, f in enumerate(FOODS):
    ev = [st for st, k in picked_at[i] for _ in range(k)]
    if ev: print(f"food {f}: picked {len(ev)} units, from step {ev[0]} to {ev[-1]}")
    else: print(f"food {f}: never found")
print("PASS: every food source supplied >=1000 units" if all(FOOD_AMOUNT - food_left >= 1000) else "FAIL: some food source barely used")
bg = food_ph.mean()
print(f"background mean food pheromone {bg:.4f}")
for f in []:
    n = min(NESTS, key=lambda q: np.hypot(q[0]-f[0], q[1]-f[1]))
    print(f"food {f} -> nearest nest {n}: pheromone on line / background = {line_mean(n, f)/bg:6.1f}x")
first, last = delivered_log[0], delivered_log[-1] - delivered_log[-2]
print(f"delivered {total} of {FOOD_AMOUNT*len(FOODS)} total food; first 500 steps {first}, peak 500 steps {max(np.diff([0]+delivered_log))}")

# --- image
fig, ax = plt.subplots(2, 3, figsize=(15, 10.5)); ax = ax.ravel()
for a, (st, (im, left)) in zip(ax, snaps.items()):
    a.imshow(im, origin="lower"); a.set_title(f"step {st}  food left {left}", fontsize=10); a.axis("off")
x = np.arange(500, STEPS + 1, 500)
ax[5].bar(x, np.diff([0] + delivered_log), width=400)
ax[5].set_xlabel("step"); ax[5].set_title("food delivered per 500 steps")
fig.suptitle("green = food trail, blue = home trail, red = nests, yellow = food (dim = eaten), "
             "magenta = ant carrying, grey = searching")
plt.tight_layout(); plt.savefig("ants.png", dpi=90)
print("saved ants.png")

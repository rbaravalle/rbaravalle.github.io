"""
A tiny 2D top-down world for a Create 3-sized robot.

  - make_house(seed): a random floor plan of a few rooms inside 5 x 6 m,
    with one door in every interior wall and one exit in the outer wall.
    Every interior wall starts and ends on the outer wall or on an earlier
    interior wall, so all walls are connected to the outer wall.
  - SimRobot: a round robot (radius 0.17 m) with move(meters) and
    turn(degrees). Each action returns a fresh lidar scan. A move stops on a
    bump. There is no odometry: the robot never learns its own position.
  - The lidar reports 8 sectors of minimum distance, with a little noise.
    Anything farther than 8 m reads as None (">8 m" for the model). Inside
    the house every reading is below 8 m, so ">8 m" only happens when a ray
    escapes through the exit.

Pure Python, no dependencies. Seeds: the floor plan comes from the house seed;
the lidar noise comes from a separate noise seed, so repeated runs of one house
differ only in what the agent does.
"""
import math
import random
from dataclasses import dataclass, field

ROBOT_RADIUS = 0.17       # m, roughly a Create 3
LIDAR_RANGE = 8.0         # m; farther than this reads as None
LIDAR_NOISE = 0.02        # m, standard deviation
SECTORS = ["front", "front-left", "left", "back-left",
           "back", "back-right", "right", "front-right"]   # counterclockwise
RAYS_PER_SECTOR = 9       # rays at -20, -15, ..., +20 degrees around each sector centre
MAX_MOVE = 2.0            # m per move command, forwards
MAX_BACK = 1.0            # m per move command, backwards
MOVE_STEP = 0.01          # m, collision check resolution
WALL_HALF = 0.04          # m, half the wall thickness (walls are 8 cm thick)


@dataclass
class House:
    seed: int
    width: float                      # x extent of the outer wall
    height: float                     # y extent
    walls: list                       # [(x1, y1, x2, y2)], doors and the exit are gaps
    rooms: list                       # [(x0, y0, x1, y1)] rectangles
    exit: tuple                       # (x1, y1, x2, y2): the gap in the outer wall
    start: tuple                      # (x, y, heading_deg)
    doors: list = field(default_factory=list)   # [(x1, y1, x2, y2)] gaps in interior walls

    def outer_polygon(self):
        w, h = self.width, self.height
        return [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]

    def is_outside(self, x, y):
        """The simulator's success test: the robot's centre left the outer wall polygon."""
        return x < 0.0 or y < 0.0 or x > self.width or y > self.height

    def to_json(self):
        return {"seed": self.seed, "width": self.width, "height": self.height,
                "walls": [list(w) for w in self.walls], "rooms": [list(r) for r in self.rooms],
                "doors": [list(d) for d in self.doors], "exit": list(self.exit),
                "start": list(self.start)}


# ---------------------------------------------------------------- floor plans

def _split_line(a, b, gaps):
    """Cut the segment a..b (scalars along one axis) by gap intervals. Returns pieces."""
    pieces, cur = [], a
    for g0, g1 in sorted(gaps):
        if g0 > cur:
            pieces.append((cur, g0))
        cur = max(cur, g1)
    if cur < b:
        pieces.append((cur, b))
    return pieces


def _door_seg(wall):
    o, c, a, b, d0, d1 = wall
    return (c, d0, c, d1) if o == "v" else (d0, c, d1, c)


def make_house(seed, n_splits=None):
    """A random floor plan. Same seed, same house."""
    rng = random.Random(f"house-{seed}")
    W = round(rng.uniform(4.0, 5.0), 2)
    H = round(rng.uniform(5.0, 6.0), 2)
    n_splits = n_splits if n_splits is not None else rng.choice([2, 3, 3])
    MIN_ROOM = 1.5

    rooms = [(0.0, 0.0, W, H)]
    interior = []          # (orientation, fixed coord, lo, hi, door_lo, door_hi)
    junctions = {"bottom": [], "top": [], "left": [], "right": []}   # where walls meet the outer wall
    for _ in range(n_splits):
        rng.shuffle(rooms)
        rooms.sort(key=lambda r: -(r[2] - r[0]) * (r[3] - r[1]))   # split a big room
        for i, (x0, y0, x1, y1) in enumerate(rooms):
            rw, rh = x1 - x0, y1 - y0
            vertical = rw > rh if abs(rw - rh) > 0.3 else rng.random() < 0.5
            span = rw if vertical else rh
            if span < 2 * MIN_ROOM:
                vertical = not vertical
                span = rw if vertical else rh
                if span < 2 * MIN_ROOM:
                    continue
            lo = (x0 if vertical else y0) + MIN_ROOM
            hi = (x1 if vertical else y1) - MIN_ROOM
            a, b = (y0, y1) if vertical else (x0, x1)    # the wall runs from a to b
            # Both ends must land on solid wall, away from existing doors.
            # Otherwise a wall piece floats free and the house has an island.
            for _ in range(100):
                c = round(rng.uniform(lo, hi), 2)
                ends = [(c, a), (c, b)] if vertical else [(a, c), (b, c)]
                if all(_dist_point_segment(px, py, *_door_seg(d)) > 0.45
                       for px, py in ends for d in interior):
                    break
            else:
                continue
            door_w = round(rng.uniform(0.75, 0.9), 2)
            d0 = round(rng.uniform(a + 0.3, b - 0.3 - door_w), 2)
            interior.append(("v" if vertical else "h", c, a, b, d0, d0 + door_w))
            if vertical:
                rooms[i:i + 1] = [(x0, y0, c, y1), (c, y0, x1, y1)]
                if y0 == 0.0: junctions["bottom"].append(c)
                if y1 == H: junctions["top"].append(c)
            else:
                rooms[i:i + 1] = [(x0, y0, x1, c), (x0, c, x1, y1)]
                if x0 == 0.0: junctions["left"].append(c)
                if x1 == W: junctions["right"].append(c)
            break

    # The exit: a gap in the outer wall, away from corners and wall junctions.
    exit_w = round(rng.uniform(0.8, 0.9), 2)
    for _ in range(1000):
        side = rng.choice(["bottom", "top", "left", "right"])
        length = W if side in ("bottom", "top") else H
        e0 = round(rng.uniform(0.35, length - 0.35 - exit_w), 2)
        if all(j < e0 - 0.3 or j > e0 + exit_w + 0.3 for j in junctions[side]):
            break
    e1 = e0 + exit_w

    walls = []
    for s, length in (("bottom", W), ("top", W), ("left", H), ("right", H)):
        gaps = [(e0, e1)] if s == side else []
        for p0, p1 in _split_line(0.0, length, gaps):
            if s == "bottom": walls.append((p0, 0.0, p1, 0.0))
            if s == "top":    walls.append((p0, H, p1, H))
            if s == "left":   walls.append((0.0, p0, 0.0, p1))
            if s == "right":  walls.append((W, p0, W, p1))
    exit_seg = {"bottom": (e0, 0.0, e1, 0.0), "top": (e0, H, e1, H),
                "left": (0.0, e0, 0.0, e1), "right": (W, e0, W, e1)}[side]

    doors = []
    for o, c, a, b, d0, d1 in interior:
        for p0, p1 in _split_line(a, b, [(d0, d1)]):
            walls.append((c, p0, c, p1) if o == "v" else (p0, c, p1, c))
        doors.append((c, d0, c, d1) if o == "v" else (d0, c, d1, c))

    walls = [tuple(round(v, 3) for v in w) for w in walls]

    # Start: a random free spot in a random room other than the exit's room,
    # random heading. So every run has to find at least one door before the
    # exit: starting next to the exit would test nothing about memory.
    house = House(seed, W, H, walls, rooms, tuple(round(v, 3) for v in exit_seg), (0, 0, 0), doors)
    mx, my = (exit_seg[0] + exit_seg[2]) / 2, (exit_seg[1] + exit_seg[3]) / 2
    start_rooms = [r for r in rooms
                   if not (r[0] - 1e-6 <= mx <= r[2] + 1e-6 and r[1] - 1e-6 <= my <= r[3] + 1e-6)]
    for _ in range(1000):
        x0, y0, x1, y1 = rng.choice(start_rooms)
        x, y = rng.uniform(x0 + 0.45, x1 - 0.45), rng.uniform(y0 + 0.45, y1 - 0.45)
        if _clearance(walls, x, y) > 0.45 and _dist_point_segment(x, y, *exit_seg) > 1.0:
            break
    house.start = (round(x, 3), round(y, 3), round(rng.uniform(-180, 180), 1))
    return house


# ---------------------------------------------------------------- geometry

def _dist_point_segment(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _clearance(walls, x, y):
    """Distance from a point to the nearest wall surface (walls are WALL_HALF thick each side)."""
    return min(_dist_point_segment(x, y, *w) for w in walls) - WALL_HALF


def _ray_hit(ox, oy, ang, walls):
    """Distance along a ray to the nearest wall surface, or math.inf.

    Each wall is a capsule: its centre line widened by WALL_HALF on both sides,
    with round ends. Zero-thickness walls would be invisible end-on, between
    two lidar rays, and still block the robot.
    """
    dx, dy = math.cos(ang), math.sin(ang)
    best = math.inf
    t = WALL_HALF
    for x1, y1, x2, y2 in walls:
        ex, ey = x2 - x1, y2 - y1
        L = math.hypot(ex, ey)
        nx, ny = -ey / L, ex / L
        # the two long sides
        for s in (t, -t):
            ax, ay = x1 + nx * s, y1 + ny * s
            den = dx * ey - dy * ex
            if abs(den) < 1e-12:
                continue
            k = ((ax - ox) * ey - (ay - oy) * ex) / den
            u = ((ax - ox) * dy - (ay - oy) * dx) / den
            if k > 1e-9 and 0 <= u <= 1 and k < best:
                best = k
        # the two round ends
        for cx, cy in ((x1, y1), (x2, y2)):
            fx, fy = ox - cx, oy - cy
            b = fx * dx + fy * dy
            c = fx * fx + fy * fy - t * t
            disc = b * b - c
            if disc >= 0:
                k = -b - math.sqrt(disc)
                if 1e-9 < k < best:
                    best = k
    return best


def check_house(house):
    """The two properties the experiment relies on. Returns a list of problems.

    1. Every wall piece is connected to the outer wall (no islands), which is
       what guarantees that the wall follower gets out.
    2. The robot's body fits through, from the start to outside (grid search).
    """
    problems = []

    def touches(a, b):
        return any(_dist_point_segment(px, py, *b) < 1e-6 for px, py in ((a[0], a[1]), (a[2], a[3]))) \
            or any(_dist_point_segment(px, py, *a) < 1e-6 for px, py in ((b[0], b[1]), (b[2], b[3])))

    walls = house.walls
    seen, todo = {0}, [0]          # walls[0] is a piece of the outer wall
    while todo:
        i = todo.pop()
        for j in range(len(walls)):
            if j not in seen and touches(walls[i], walls[j]):
                seen.add(j)
                todo.append(j)
    if len(seen) != len(walls):
        problems.append(f"{len(walls) - len(seen)} wall pieces not connected to the outer wall")

    g = 0.05
    nx, ny = int(house.width / g) + 21, int(house.height / g) + 21

    def free(i, j):
        return _clearance(walls, i * g - 0.5, j * g - 0.5) >= ROBOT_RADIUS

    sx, sy = round((house.start[0] + 0.5) / g), round((house.start[1] + 0.5) / g)
    seen, todo, out = {(sx, sy)}, [(sx, sy)], False
    while todo and not out:
        i, j = todo.pop()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            p = (i + di, j + dj)
            if p in seen or not (0 <= p[0] < nx and 0 <= p[1] < ny) or not free(*p):
                continue
            if house.is_outside(p[0] * g - 0.5, p[1] * g - 0.5):
                out = True
                break
            seen.add(p)
            todo.append(p)
    if not out:
        problems.append("no path for the robot from the start to outside")
    return problems


# ---------------------------------------------------------------- robots

class Robot:
    """The interface the agent and the wall follower drive.

    A Create3Robot (ROS 2 on the Raspberry Pi) can implement the same three
    methods later. Each action returns a dict:
        {"action": ..., "requested": ..., "done": <how much was done>,
         "bump": bool, "scan": [8 distances in m or None]}
    """

    def move(self, meters):
        raise NotImplementedError

    def turn(self, degrees):
        raise NotImplementedError

    def scan(self):
        raise NotImplementedError


class SimRobot(Robot):
    def __init__(self, house, noise_seed):
        self.house = house
        self.x, self.y, self.heading = house.start     # heading in degrees, CCW from +x
        self.rng = random.Random(f"noise-{noise_seed}")
        self.bumps = 0

    @property
    def outside(self):
        return self.house.is_outside(self.x, self.y)

    def pose(self):
        """Ground truth, for the simulator and the replay only. The agent never sees this."""
        return (round(self.x, 3), round(self.y, 3), round(self.heading, 1))

    def scan(self):
        out = []
        h = math.radians(self.heading)
        for i in range(len(SECTORS)):
            centre = h + math.radians(45 * i)
            d = min(_ray_hit(self.x, self.y, centre + math.radians(o), self.house.walls)
                    for o in range(-20, 21, 40 // (RAYS_PER_SECTOR - 1)))
            if d > LIDAR_RANGE:
                out.append(None)
            else:
                out.append(round(max(0.0, d + self.rng.gauss(0, LIDAR_NOISE)), 2))
        return out

    def move(self, meters):
        req = float(meters)
        m = max(-MAX_BACK, min(MAX_MOVE, req))
        sign = 1 if m >= 0 else -1
        h = math.radians(self.heading)
        dx, dy = math.cos(h) * sign, math.sin(h) * sign
        moved, bump = 0.0, False
        while moved < abs(m) - 1e-9:
            step = min(MOVE_STEP, abs(m) - moved)
            nx, ny = self.x + dx * step, self.y + dy * step
            if _clearance(self.house.walls, nx, ny) < ROBOT_RADIUS:
                bump = True
                break
            self.x, self.y, moved = nx, ny, moved + step
        if bump:
            self.bumps += 1
        return {"action": "move", "requested": req, "done": round(sign * moved, 2),
                "clamped": m != req, "bump": bump, "scan": self.scan()}

    def turn(self, degrees):
        req = float(degrees)
        d = max(-180.0, min(180.0, req))
        self.heading = (self.heading + d + 180.0) % 360.0 - 180.0
        return {"action": "turn", "requested": req, "done": round(d, 1),
                "clamped": d != req, "bump": False, "scan": self.scan()}


def format_scan(scan):
    """The lidar as the model reads it."""
    return ", ".join(f"{name} {'>8 m' if d is None else f'{d:.2f} m'}"
                     for name, d in zip(SECTORS, scan))


if __name__ == "__main__":
    h = make_house(1)
    r = SimRobot(h, 1)
    print(h.width, h.height, len(h.rooms), "rooms", h.exit, h.start)
    print(format_scan(r.scan()))

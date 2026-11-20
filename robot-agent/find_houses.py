"""
Find houses that actually test memory.

    python3 find_houses.py --from 0 --to 2000

A house qualifies when:
  1. the exit is (nearly) hidden: it can't be seen from the start room or from
     any dead end, and from at most 10% of the floor of any other room
     (usually a strip in front of the exit room's door). A house where it is
     hidden from everywhere outside its room is very rare (1 in 400): with
     doors this wide, doorways nearly always let some line of sight through;
  2. there is a dead end off the route, branching from a room the robot has to
     go through, so it can waste time there and must remember it did;
  3. the wall follower gets out (it always does eventually) - its step count
     is printed for reference.
"""
import argparse
import math
from multiprocessing import Pool

import sim
import wall_follower


def rooms_at(h, x, y, eps=1e-6):
    return [i for i, r in enumerate(h.rooms)
            if r[0] - eps <= x <= r[2] + eps and r[1] - eps <= y <= r[3] + eps]


def room_graph(h):
    adj = {i: set() for i in range(len(h.rooms))}
    for d in h.doors:
        rs = rooms_at(h, (d[0] + d[2]) / 2, (d[1] + d[3]) / 2)
        for a in rs:
            for b in rs:
                if a != b:
                    adj[a].add(b)
    return adj


def route(adj, start, goals):
    prev, front = {start: None}, [start]
    while front:
        nxt = []
        for r in front:
            for n in adj[r]:
                if n not in prev:
                    prev[n] = r
                    nxt.append(n)
        front = nxt
    g = next(g for g in goals if g in prev)
    path = [g]
    while prev[path[-1]] is not None:
        path.append(prev[path[-1]])
    return path[::-1]


def _seg_dist(p1, p2, q1, q2):
    """Distance between two segments (0 if they cross)."""
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    d1, d2 = cross(q1, q2, p1), cross(q1, q2, p2)
    d3, d4 = cross(p1, p2, q1), cross(p1, p2, q2)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return 0.0
    return min(sim._dist_point_segment(*p1, *q1, *q2), sim._dist_point_segment(*p2, *q1, *q2),
               sim._dist_point_segment(*q1, *p1, *p2), sim._dist_point_segment(*q2, *p1, *p2))


def exit_visible_from(h, x, y, targets):
    """Can a straight line from (x, y) reach some point of the exit gap
    without touching a wall? (Lines that pass the gap continue to open space.)"""
    for q in targets:
        if all(_seg_dist((x, y), q, (w[0], w[1]), (w[2], w[3])) > sim.WALL_HALF + 1e-6
               for w in h.walls):
            return True
    return False


def exit_visibility(h, exit_room, step=0.15):
    """For each room other than the exit's, the fraction of the free floor from
    which the exit can be seen. Returns {room: fraction}."""
    x1, y1, x2, y2 = h.exit
    # points across the gap, a little inside the jambs
    targets = [(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t) for t in (0.1, 0.3, 0.5, 0.7, 0.9)]
    out = {}
    for i, (rx0, ry0, rx1, ry1) in enumerate(h.rooms):
        if i == exit_room:
            continue
        seen = total = 0
        nx, ny = int((rx1 - rx0) / step), int((ry1 - ry0) / step)
        for a in range(1, nx):
            for b in range(1, ny):
                x, y = rx0 + a * step, ry0 + b * step
                if sim._clearance(h.walls, x, y) < sim.ROBOT_RADIUS:
                    continue
                total += 1
                seen += exit_visible_from(h, x, y, targets)
        out[i] = seen / total if total else 0.0
    return out


def exit_hidden(h, exit_room, step=0.15):
    return all(v == 0 for v in exit_visibility(h, exit_room, step).values())


def check(seed):
    h = sim.make_house(seed)
    adj = room_graph(h)
    start = rooms_at(h, *h.start[:2])[0]
    ex = h.exit
    goals = rooms_at(h, (ex[0] + ex[2]) / 2, (ex[1] + ex[3]) / 2)
    path = route(adj, start, goals)
    dead_ends = [n for m in path[:-1] for n in adj[m] if n not in path]
    if len(path) < 3 or not dead_ends:
        return None
    vis = exit_visibility(h, goals[0])
    # The exit must be invisible from the start room and from every dead end,
    # and visible from at most MAX_SEEN of the floor anywhere else.
    if vis[start] > 0 or any(vis[d] > 0 for d in dead_ends) or max(vis.values()) > MAX_SEEN:
        return None
    r = sim.SimRobot(h, seed)
    n = wall_follower.run(r, 3000)
    return seed, len(path) - 1, len(dead_ends), max(vis.values()), n if r.outside else None


MAX_SEEN = 0.10


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="lo", type=int, default=0)
    ap.add_argument("--to", dest="hi", type=int, default=1000)
    a = ap.parse_args()
    with Pool() as pool:
        for res in pool.imap(check, range(a.lo, a.hi), chunksize=8):
            if res:
                s, doors, dead, seen, n = res
                print(f"house {s}: {doors} doors to the exit, {dead} dead end(s) off the route, "
                      f"exit seen from at most {seen:.1%} of any other room, wall follower {n} steps",
                      flush=True)

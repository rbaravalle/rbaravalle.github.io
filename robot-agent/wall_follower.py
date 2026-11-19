"""
The baseline without a model: keep the wall on your right.

It sees exactly what the agent sees (the 8-sector scan returned by the last
action) and uses the same two actions. It keeps no memory at all, not even a
step counter: each action depends only on the latest scan.

Because every interior wall is connected to the outer wall, following any wall
with your right hand eventually takes you along the outer wall and out of the
exit. So it is guaranteed to get out, as long as the step limit allows.
"""
from sim import SECTORS

FRONT, FL, LEFT, BL, BACK, BR, RIGHT, FR = range(8)

WALL = 0.27        # m, the distance it keeps from the wall (centre to wall surface);
                   # small enough to fit through a door with the jamb on the right
GAIN = 90.0        # degrees of steering per metre of distance error
FIND = 1.2         # m: if nothing is closer than this, drive straight to find a wall
STEP = 0.3         # m, longest step while following a wall
TOL = 30.0         # degrees: smaller heading errors are not worth a turn
FAR = 9.0          # what a ">8 m" reading counts as


def _d(scan, i):
    return FAR if scan[i] is None else scan[i]


def _wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def decide(scan, last):
    """Next action from the latest scan. Returns ("move", m) or ("turn", deg).

    The rule: find the closest thing around me, and drive along it with it on
    my right, at distance WALL. Going around corners, door jambs and the edge of
    the exit falls out of this rule by itself: as I pass a jamb, the closest
    point swings behind me and I turn around it.

    `last` is the previous action and whether it bumped, or None. It is used
    for two things only: after a bump, turn left; after a turn, take a step
    (turning alone changes nothing).
    """
    d = [_d(scan, i) for i in range(8)]
    # The closest thing on my right-hand side (front, front-right, right,
    # back-right); only if there is none, the closest thing anywhere.
    i = min((FRONT, FR, RIGHT, BR), key=lambda k: d[k])
    if d[i] > FIND:
        i = min(range(8), key=lambda k: d[k])
    if d[i] > FIND:
        # Open space: drive straight until something is close.
        return ("move", max(0.05, min(1.0, d[FRONT] - WALL - 0.1)))
    # Direction of the closest point: refine the sector centre with its two
    # neighbours (a parabola through the three readings).
    a, b, c = d[(i - 1) % 8], d[i], d[(i + 1) % 8]
    den = a - 2 * b + c
    off = 0.0 if den <= 1e-9 else max(-0.5, min(0.5, 0.5 * (a - c) / den))
    phi = 45.0 * (i + off)
    # Heading that keeps that point on my right, plus a correction for distance:
    # too far, steer towards it; too close, steer away.
    target = _wrap(phi + 90.0 - max(-45.0, min(45.0, GAIN * (b - WALL))))
    if last is not None and len(last) > 2 and last[2]:
        return ("turn", 45)         # the bumper fired: turn left, away from it
    if last is not None and last[0] == "turn":
        free = min(d[FRONT] - WALL, d[FL] - 0.3, d[FR] - 0.3)
        if free > 0.05:
            return ("move", round(min(STEP, free), 2))
    if abs(target) > TOL or d[FRONT] < WALL + 0.1:
        if abs(target) <= TOL:
            target = 45.0           # blocked ahead with no better idea: turn left
        return ("turn", round(target))
    return ("move", round(max(0.05, min(STEP, d[FRONT] - WALL - 0.1)), 2))


def run(robot, max_steps, on_step=None, scan=None):
    """Drive a Robot until it leaves the house or hits the step limit.
    `scan` is the starting scan, if the caller already took it."""
    scan = robot.scan() if scan is None else scan
    last = None
    for step in range(max_steps):
        kind, amount = decide(scan, last)
        result = robot.move(amount) if kind == "move" else robot.turn(amount)
        scan, last = result["scan"], (kind, amount, result["bump"])
        if on_step:
            on_step(step, kind, amount, result)
        if robot.outside:
            return step + 1
    return max_steps


if __name__ == "__main__":
    import statistics
    from sim import make_house, SimRobot
    steps, ok, bumps = [], 0, []
    N = 200
    for seed in range(N):
        r = SimRobot(make_house(seed), seed)
        n = run(r, 1000)
        if r.outside:
            ok += 1
            steps.append(n)
        bumps.append(r.bumps)
    print(f"wall follower: {ok}/{N} out; steps median {statistics.median(steps)}, "
          f"p90 {sorted(steps)[int(0.9 * len(steps))]}, max {max(steps)}; "
          f"bumps mean {statistics.mean(bumps):.2f}")

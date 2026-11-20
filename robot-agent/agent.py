"""
A robot agent with a small memory. Post 2's loop (tiny-agent/step3_vision.py),
with the shell tools swapped for a robot.

Same loop as before: ask the model, run the tool it asks for, send the result
back, repeat. What changes is what the model gets to see on each call, its
memory. There are four settings:

  goldfish  the latest scan and the last action only
  window    the last 10 actions and their results
  notebook  the window, plus a 500-character notebook it writes itself
  full      everything since the start
  odometry  everything since the start, plus wheel odometry (where the
            robot is relative to its start) after every action

There is no map, no SLAM and no planner: only the lidar scan that each action
returns (and, in the odometry setting only, where the wheels say it is).

Prompt caching is on. The stable parts come first (tools, system prompt, then
the notebook), so they can be read from the cache. Full history only ever
appends, so it caches well; a sliding window changes every call, so it can't.

You normally don't run this file directly: batch.py runs it many times and
logs everything. For one run by hand:

    python3 agent.py --setting notebook --house 3 --fake          # free
    python3 agent.py --setting notebook --house 3                 # paid, Haiku
"""
import argparse
import hashlib
import json
import random
import re
import time
from types import SimpleNamespace

import sim
import wall_follower

# Prices in USD per million tokens (input, output), as in post 2.
# Check https://platform.claude.com/docs/en/about-claude/pricing for current values.
MODELS = {
    "haiku": ("claude-haiku-5-5", 0.10, 0.50),   # prompts over 100K tokens: 0.50 / 2.50
    "opus":  ("claude-opus-5-5", 4.00, 20.00),
}
CACHE_WRITE = 1.25     # x the input price, 5-minute cache
CACHE_READ = 0.10      # x the input price (Haiku 5.5)

SETTINGS = ["goldfish", "window", "notebook", "full", "odometry"]
WINDOW = 10            # actions kept by "window" and "notebook"
NOTE_LIMIT = 500       # characters in the notebook

SYSTEM = """You are the brain of a small round robot (radius 0.17 m, the size of an \
iRobot Create 3). You are somewhere inside a house. Your job: get out of the house.

What you have:
{lidar}- move(meters): drive straight ahead (negative drives backwards, at most 1 m). \
At most 2 m per command. If you bump into something you stop there, and the \
result says so.
- turn(degrees): turn in place. Positive turns left (counterclockwise), negative \
turns right. From -180 to 180.
{position}

{memory}

The run ends by itself the moment your centre is outside the house. You have at \
most {max_steps} actions (moves and turns). If you are sure you cannot get out, \
call done(); calling done() while still inside counts as a failure.

On every turn, write one short sentence about what you see and what you will \
do, then call exactly one tool."""

LIDAR_TEXT = {
    "sectors": """- A 2D lidar. Every action returns a fresh scan of 8 directions around you \
(front, front-left, left, back-left, back, back-right, right, front-right). \
Each direction covers a 45-degree slice and reports two numbers, both measured \
from your body: "clear" is the free space before the nearest thing in that \
slice (you can drive forward about the front "clear" before you touch \
something; keep a margin, your sides can still catch a corner), and \
"farthest" is the longest distance seen in that slice. When "farthest" is much \
larger than "clear", part of the slice sees through a gap, such as a doorway. \
Readings are a little noisy.
- The house is small: from anywhere inside it, every distance is under 8 m. A \
"farthest" of ">8 m" means part of that slice sees open space beyond the \
house, through the exit. That is the only sign of the exit.
""",
    "rays": """- A 2D lidar. Every action returns a fresh scan of 72 rays, one every 5 \
degrees, as "angle:distance" pairs. Angles are counterclockwise from straight \
ahead: 0 is in front of you, 90 to your left, 180 behind, 270 to your right. \
Each distance is the free space between your body and the nearest thing along \
that ray. Readings are a little noisy.
- Your body is 0.34 m wide, so a single ray does not tell you how far you can \
drive: something just beside the ray at 0 can still hit your side. Before \
driving forward, look at every ray from 330 through 0 to 30: the smallest of \
them is about how far you can drive straight ahead (keep a margin).
- A doorway or other gap shows up as several neighbouring rays that are much \
longer than the rays on either side of them. To go through it, turn to face \
the middle of that group of long rays, and check that it is wide enough for \
you: at a distance of 1 m, 5 degrees is about 9 cm.
- The house is small: from anywhere inside it, every distance is under 8 m. A \
ray reading ">8" sees open space beyond the house, through the exit. That is \
the only sign of the exit.
""",
}

MEMORY_TEXT = {
    "goldfish": "Your memory: you see only your latest scan and your last action. "
                "Nothing earlier is kept.",
    "window": f"Your memory: you see only your last {WINDOW} actions and their results. "
              "Anything older is forgotten.",
    "notebook": f"Your memory: you see only your last {WINDOW} actions and their results. "
                "Anything older is forgotten, except your notebook: at most "
                f"{NOTE_LIMIT} characters that stay with you for the whole run. "
                "write_note(text) replaces the whole notebook with text; "
                "read_notes() shows it. The current notebook is also shown at the "
                "start of every request.",
    "full": "Your memory: you see everything that happened since the start.",
    "odometry": "Your memory: you see everything that happened since the start.",
}

POSITION_TEXT = {
    "odometry": "- No map and no GPS. But your wheels count how far they turned: after "
                "every action you get your odometry, your position relative to where "
                "you started (x metres forward and y metres to the left of your start "
                "pose, and your heading in degrees; at the start all three are 0). It "
                "drifts a little with every action.",
}
NO_POSITION = ("- No map, no GPS, no odometry: you never learn your position. You only "
               "know what the scans tell you.")
SCAN_FORMAT = "sectors"   # or "rays": all 72 readings (batch.py --scan rays)
SCAN_CLEARANCE = True   # report free space from the body (the pilot runs used centre distances)
# Each sector reports "clear" (its minimum) and "farthest" (its maximum). The
# house-47 runs before this had only the minimum, which hides doorways and the
# exit: from inside the exit's room, the exit read ">8 m" from only 7% of poses.

TASK = "Get out of the house."

ROBOT_TOOLS = [
    {
        "name": "move",
        "description": "Drive straight ahead by this many meters (at most 2; negative "
                       "drives backwards, at most 1). Stops on a bump. Returns a fresh scan.",
        "input_schema": {
            "type": "object",
            "properties": {"meters": {"type": "number"}},
            "required": ["meters"],
        },
    },
    {
        "name": "turn",
        "description": "Turn in place by this many degrees. Positive = left "
                       "(counterclockwise), negative = right. -180 to 180. Returns a fresh scan.",
        "input_schema": {
            "type": "object",
            "properties": {"degrees": {"type": "number"}},
            "required": ["degrees"],
        },
    },
    {
        "name": "done",
        "description": "End the run. Only if you are sure you cannot get out: "
                       "calling it while inside the house counts as a failure.",
        "input_schema": {"type": "object", "properties": {}},
    },
]
NOTE_TOOLS = [
    {
        "name": "write_note",
        "description": f"Replace your whole notebook with this text (at most {NOTE_LIMIT} "
                       "characters). It is the only thing you keep beyond the last "
                       f"{WINDOW} actions. Not an action: it uses no step.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "read_notes",
        "description": "Show your notebook. Not an action: it uses no step.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def tools_for(setting):
    return ROBOT_TOOLS + (NOTE_TOOLS if setting == "notebook" else [])


def system_for(setting, max_steps):
    return SYSTEM.format(memory=MEMORY_TEXT[setting], max_steps=max_steps,
                         lidar=LIDAR_TEXT[SCAN_FORMAT],
                         position=POSITION_TEXT.get(setting, NO_POSITION))


# ---------------------------------------------------------------- helpers

def to_jsonable(x):
    """SDK objects -> plain dicts, for the logs."""
    if hasattr(x, "model_dump"):
        return x.model_dump(exclude_none=True)
    if isinstance(x, SimpleNamespace):
        return {k: to_jsonable(v) for k, v in vars(x).items()}
    if isinstance(x, dict):
        return {k: to_jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [to_jsonable(v) for v in x]
    return x


def scan_text(mins, maxes, rays):
    """The scan in the format this run uses."""
    if SCAN_FORMAT == "rays":
        return sim.format_rays(rays, SCAN_CLEARANCE)
    return sim.format_scan(mins, SCAN_CLEARANCE, maxes)


def describe(result, steps_used, max_steps, odometry=None):
    """A robot action's result, as the model reads it."""
    if result["action"] == "move":
        req, done = result["requested"], result["done"]
        if result["bump"]:
            text = f"BUMP: stopped after {abs(done):.2f} m of {abs(req):.2f} m."
        else:
            text = f"Moved {done:.2f} m."
    else:
        d = result["done"]
        text = f"Turned {abs(d):.0f} degrees {'left' if d >= 0 else 'right'}."
    if result.get("clamped"):
        text += " (The command was outside the allowed range and was clamped.)"
    out = (f"{text} Actions used: {steps_used} of {max_steps}.\n"
           f"Scan: {scan_text(result['scan'], result.get('scan_max'), result.get('rays_noisy'))}")
    if odometry is not None:
        x, y, h = odometry
        out += f"\nOdometry: x {x:.2f} m, y {y:.2f} m, heading {h:.0f} degrees."
    return out


def price(model, u):
    """Cost of one call from its usage, including cache reads and writes."""
    _, p_in, p_out = MODELS[model]
    prompt = u["input_tokens"] + u["cache_creation_input_tokens"] + u["cache_read_input_tokens"]
    if model == "haiku" and prompt > 100_000:
        p_in, p_out = 0.50, 2.50   # Haiku's long-prompt price
    return (u["input_tokens"] * p_in
            + u["cache_creation_input_tokens"] * p_in * CACHE_WRITE
            + u["cache_read_input_tokens"] * p_in * CACHE_READ
            + u["output_tokens"] * p_out) / 1_000_000


def usage_dict(u):
    return {"input_tokens": getattr(u, "input_tokens", 0) or 0,
            "output_tokens": getattr(u, "output_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
            "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0}


# ---------------------------------------------------------------- memory
#
# Every call is a fresh, one-message conversation, built from what the robot
# remembers. The run so far is a list of entries, one per model reply:
# "Step 12. You said: ... You called move(0.5). Result: ... Scan: ...".
# The four settings differ only in which entries go into the message:
#
#   goldfish  entries since the last robot action (so: the last action and its scan)
#   window    entries back to the WINDOW-th most recent robot action
#   notebook  the same window, plus the notebook at the top
#   full      every entry since the start
#
# Each entry is its own text block, and the message only ever grows at the end
# in "full", so the cache can read everything but the newest entry back.
# The model's own thinking from earlier calls is never sent back, in any
# setting: what it remembers of its reasoning is what it said out loud.

def kept_entries(setting, entries):
    """Which entries of the run this setting remembers."""
    if setting in ("full", "odometry"):
        return entries
    window = 1 if setting == "goldfish" else WINDOW
    cut, actions = len(entries), 0
    while cut > 0 and actions < window:
        cut -= 1
        actions += entries[cut]["robot_action"]
    return entries[cut:]


def build_messages(setting, entries, notes):
    """What the model sees on this call: one user message."""
    kept = kept_entries(setting, entries)
    head = TASK
    if len(kept) < len(entries):
        head += ("\n\n(Older steps are forgotten.)" if setting != "goldfish"
                 else "\n\n(You remember only your last action.)")
    if setting == "notebook":
        head += (f"\n\nYour notebook ({len(notes)}/{NOTE_LIMIT} characters):\n"
                 + (notes if notes else "(empty)"))
    head += "\n\nWhat you remember:" if setting != "goldfish" else ""
    blocks = [{"type": "text", "text": head}] + [{"type": "text", "text": e["text"]} for e in kept]
    return [{"role": "user", "content": blocks}]


def add_cache_marks(setting, messages):
    """Cache breakpoints, after the parts that stay the same between calls.
    (The system prompt, which comes after the tools, carries its own mark.)"""
    msg = messages[0]
    blocks = [dict(b) for b in msg["content"]]
    # full: everything so far, since the next call only appends.
    # the others: the task (and notebook); the entries after it change every call.
    i = len(blocks) - 1 if setting in ("full", "odometry") else 0
    blocks[i] = dict(blocks[i], cache_control={"type": "ephemeral"})
    return [{"role": "user", "content": blocks}]


# ---------------------------------------------------------------- fake model

class FakeClient:
    """A scripted stand-in for the model, so everything can be tested for free.

    It reads the latest scan out of the prompt (so the prompt really has to
    contain it), drives with the wall follower's rule, writes notes in the
    notebook setting, and now and then replies without a tool to exercise the
    nudge path. Token counts are estimates (characters / 4), and the prompt
    cache is simulated from the cache breakpoints, so the cost logging and
    the caching layout can be checked without spending anything.
    """

    MIN_CACHE = 512   # tokens; shorter prefixes are not cached

    def __init__(self, seed=0):
        self.rng = random.Random(f"fake-{seed}")
        self.cache = set()
        self.last = None
        self.calls = 0
        self.messages = self

    @staticmethod
    def _tok(obj):
        return max(1, len(json.dumps(to_jsonable(obj))) // 4)

    def _usage(self, tools, system, messages):
        blocks = [("tool", t) for t in tools] + [("system", b) for b in system]
        for m in messages:
            for b in m["content"]:
                blocks.append((m["role"], b))
        marks = [i for i, (_, b) in enumerate(blocks)
                 if isinstance(b, dict) and "cache_control" in b]
        h, hashes, toks, cum = hashlib.sha256(), [], [], 0
        for _, b in blocks:
            clean = {k: v for k, v in to_jsonable(b).items() if k != "cache_control"} \
                if isinstance(to_jsonable(b), dict) else to_jsonable(b)
            h.update(json.dumps(clean, sort_keys=True).encode())
            hashes.append(h.hexdigest())
            cum += self._tok(clean)
            toks.append(cum)
        total = toks[-1]
        last_mark = marks[-1] if marks else -1
        read = 0
        for i in range(last_mark, -1, -1):
            if hashes[i] in self.cache:
                read = toks[i]
                break
        write = 0
        if last_mark >= 0 and toks[last_mark] >= self.MIN_CACHE:
            write = toks[last_mark] - read
            for i in marks:
                if toks[i] >= self.MIN_CACHE:
                    self.cache.add(hashes[i])
        return SimpleNamespace(input_tokens=total - read - write, output_tokens=0,
                               cache_creation_input_tokens=write, cache_read_input_tokens=read)

    def create(self, model, max_tokens, system, tools, messages, **kw):
        self.calls += 1
        usage = self._usage(tools, system, messages)
        # The newest entry that holds a scan (after a note tool, it is an earlier one).
        text = ""
        for b in reversed(messages[-1]["content"]):
            text = b["text"] if isinstance(b, dict) else b.text
            if "Scan: " in text:
                break
        scans = re.findall(r"Scan: (.*)", text)
        names = {t["name"] for t in tools}
        thinking = SimpleNamespace(type="thinking", thinking="", signature="fake-signature")

        def reply(blocks, stop):
            out = 40 + 10 * len(blocks)
            usage.output_tokens = out
            return SimpleNamespace(content=[thinking] + blocks, stop_reason=stop, usage=usage,
                                   model="fake")

        if self.rng.random() < 0.02:
            return reply([SimpleNamespace(type="text", text="Let me think about where I am.")],
                         "end_turn")
        if "write_note" in names and self.calls % 15 == 1:
            note = f"call {self.calls}: following the wall on my right. " * 3
            return reply([SimpleNamespace(type="text", text="I will update my notebook."),
                          SimpleNamespace(type="tool_use", id=f"toolu_fake{self.calls}",
                                          name="write_note", input={"text": note[:300]})],
                         "tool_use")
        if "read_notes" in names and self.calls == 3:
            return reply([SimpleNamespace(type="tool_use", id=f"toolu_fake{self.calls}",
                                          name="read_notes", input={})], "tool_use")
        if not scans:
            raise ValueError("fake model: no scan found in the prompt")
        pairs = re.findall(r"(\d+):(>8|[0-9.]+)", scans[-1])
        if len(pairs) == 72:   # all rays: back to 8 sector minimums for the rule
            ray = {int(a): None if d == ">8" else float(d) for a, d in pairs}
            scan = []
            for i in range(8):
                ds = [ray[(45 * i + o) % 360] for o in range(-20, 21, 5)]
                scan.append(None if all(d is None for d in ds) else min(d for d in ds if d is not None))
        else:
            scan = [None if v == ">8 m" else float(v.split()[0])
                    for v in re.findall(r"(?:^|; )[a-z-]+ clear (>8 m|[0-9.]+ m)" if "clear" in scans[-1]
                                        else r"(?:^|, )[a-z-]+ (>8 m|[0-9.]+ m)", scans[-1])]
        assert len(scan) == 8, scans[-1]
        if SCAN_CLEARANCE:   # the rule works in distances from the centre
            scan = [None if d is None else d + sim.ROBOT_RADIUS for d in scan]
        last = self.last + ("BUMP:" in text,) if self.last else None
        kind, amount = wall_follower.decide(scan, last)
        self.last = (kind, amount)
        arg = {"meters": round(amount, 2)} if kind == "move" else {"degrees": amount}
        return reply([SimpleNamespace(type="text", text=f"Keeping the wall on my right: {kind}."),
                      SimpleNamespace(type="tool_use", id=f"toolu_fake{self.calls}",
                                      name=kind, input=arg)],
                     "tool_use")


# ---------------------------------------------------------------- one run

def run_agent(client, setting, house, noise_seed, max_steps, model="haiku",
              effort="medium", log=None, say=print, fake=False):
    """One run. Returns (result row, replay dict). `log(record)` gets every
    transcript record (header, each call, each tool, the end)."""
    log = log or (lambda rec: None)
    model_id = "fake" if fake else MODELS[model][0]
    robot = sim.SimRobot(house, noise_seed)
    tools = tools_for(setting)
    system_text = system_for(setting, max_steps)
    system = [{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}]
    log({"type": "header", "setting": setting, "model": model_id, "effort": effort,
         "house_seed": house.seed, "noise_seed": noise_seed, "max_steps": max_steps,
         "scan_format": SCAN_FORMAT, "scan_clearance": SCAN_CLEARANCE, "system": system_text, "tools": tools, "house": house.to_json(),
         "date": time.strftime("%Y-%m-%d %H:%M:%S %z"), "fake": fake})

    start_scan = robot.scan()
    start_rays = robot.last_rays
    # The run so far, as the model will read it (see "memory" above).
    start_text = f"Start. Scan: {scan_text(start_scan, robot.last_max, robot.last_rays_noisy)}"
    if setting == "odometry":
        start_text += "\nOdometry: x 0.00 m, y 0.00 m, heading 0 degrees."
    entries = [{"text": start_text, "robot_action": 0}]
    notes = ""
    steps, calls, nudges, note_writes, note_reads = 0, 0, 0, 0, 0
    in_a_row = 0          # replies without a tool call, in a row
    totals = {"input_tokens": 0, "output_tokens": 0,
              "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    cost = 0.0
    outcome, error = None, None
    replay_steps = []
    prev_sent = []
    t0 = time.time()
    max_calls = 3 * max_steps

    try:
        while outcome is None:
            if calls >= max_calls:
                outcome = "call_limit"
                break
            messages = add_cache_marks(setting, build_messages(setting, entries, notes))
            # Log only what changed since the last call (the logs stay small, and
            # nothing is lost: the unchanged blocks are in earlier call records).
            sent = to_jsonable(messages[0]["content"])
            keep = 0
            while keep < min(len(sent), len(prev_sent)) and sent[keep] == prev_sent[keep]:
                keep += 1
            t_call = time.time()
            response = client.messages.create(
                model=model_id,
                max_tokens=8000,
                system=system,
                tools=tools,
                tool_choice={"type": "auto", "disable_parallel_tool_use": True},
                messages=messages,
                **({} if fake else {"output_config": {"effort": effort}}),
            )
            calls += 1
            u = usage_dict(response.usage)
            c = price(model, u)
            cost += c
            for k in totals:
                totals[k] += u[k]
            log({"type": "call", "call": calls, "steps_before": steps,
                 "request": {"kept_blocks": keep, "new_blocks": sent[keep:]},
                 "response": {"content": to_jsonable(response.content),
                              "stop_reason": response.stop_reason},
                 "usage": u, "cost": c, "seconds": round(time.time() - t_call, 2)})
            prev_sent = sent

            texts = [b.text.strip() for b in response.content if b.type == "text" and b.text.strip()]
            say_text = " ".join(texts)
            said = f'You said: "{say_text}" ' if say_text else ""
            tool_uses = [b for b in response.content if b.type == "tool_use"]

            if response.stop_reason == "refusal":
                outcome = "refusal"
                break
            if not tool_uses:
                nudges += 1
                in_a_row += 1
                if in_a_row > 3:
                    outcome = "no_action"
                    break
                entries.append({"robot_action": 0, "text":
                                f"{said}You called no tool. The run only goes on through the "
                                "tools: call move, turn or done."})
                log({"type": "nudge", "text": entries[-1]["text"]})
                continue

            in_a_row = 0
            block = tool_uses[0]          # at most one: parallel tool use is off
            name, args = block.name, dict(block.input or {})
            bump, robot_action, call_text = False, 0, f"{name}()"
            try:
                if name in ("move", "turn"):
                    key = "meters" if name == "move" else "degrees"
                    value = float(args[key])
                    call_text = f"{name}({value:g})"
                    r = robot.move(value) if name == "move" else robot.turn(value)
                    steps += 1
                    robot_action = 1
                    bump = r["bump"]
                    output = describe(r, steps, max_steps,
                                      robot.odometry() if setting == "odometry" else None)
                    replay_steps.append({"i": steps, "action": name, "requested": value,
                                         "done": r["done"], "bump": bump,
                                         "pose": robot.pose(), "scan": r["scan"],
                                         "scan_max": r["scan_max"], "rays": r["rays"],
                                         "say": say_text, "notes": notes})
                elif name == "done":
                    outcome = "success" if robot.outside else "done_inside"
                    output = "Run ended."
                elif name == "write_note" and setting == "notebook":
                    text = str(args.get("text", ""))
                    call_text = f"write_note({len(text)} characters)"
                    if len(text) > NOTE_LIMIT:
                        output = (f"Error: the note is {len(text)} characters; the limit "
                                  f"is {NOTE_LIMIT}. The notebook was not changed.")
                    else:
                        notes = text
                        note_writes += 1
                        output = f"Notebook saved ({len(notes)}/{NOTE_LIMIT} characters)."
                        log({"type": "notes", "steps": steps, "text": notes})
                elif name == "read_notes" and setting == "notebook":
                    note_reads += 1
                    output = f"Your notebook ({len(notes)}/{NOTE_LIMIT}):\n" + (notes or "(empty)")
                else:
                    output = f"Error: unknown tool {name}."
            except (KeyError, TypeError, ValueError) as e:
                output = f"Error: bad input {json.dumps(args)} ({e})."
            log({"type": "tool", "name": name, "input": args, "output": output,
                 "pose": robot.pose(), "bump": bump, "steps": steps})
            label = f"Step {steps}." if robot_action else "(Not an action.)"
            entries.append({"robot_action": robot_action,
                            "text": f"{label} {said}You called {call_text}. Result: {output}"})

            if outcome is None and robot.outside:
                outcome = "success"
            elif outcome is None and steps >= max_steps:
                outcome = "step_limit"
    except Exception as e:  # noqa: BLE001 - a failed run is logged, the batch goes on
        outcome = "error"
        error = f"{type(e).__name__}: {e}"
        say(f"  error: {error}")

    row = {"setting": setting, "house_seed": house.seed, "noise_seed": noise_seed,
           "model": model_id, "effort": effort, "outcome": outcome,
           "success": outcome == "success", "steps": steps, "bumps": robot.bumps,
           "calls": calls, "nudges": nudges, "note_writes": note_writes,
           "note_reads": note_reads, "final_notes": notes, **totals,
           "cost": round(cost, 8), "seconds": round(time.time() - t0, 1), "error": error}
    log({"type": "end", **row})
    replay = {"setting": setting, "model": model_id, "outcome": outcome,
              "house": house.to_json(), "start": list(house.start),
              "start_scan": start_scan, "start_rays": start_rays, "steps": replay_steps,
              "final_notes": notes, "max_steps": max_steps}
    return row, replay


def run_wall_follower(house, noise_seed, max_steps, log=None):
    """The baseline, logged in the same format."""
    log = log or (lambda rec: None)
    robot = sim.SimRobot(house, noise_seed)
    log({"type": "header", "setting": "wall", "model": "none (wall follower)",
         "house_seed": house.seed, "noise_seed": noise_seed, "max_steps": max_steps,
         "house": house.to_json(), "date": time.strftime("%Y-%m-%d %H:%M:%S %z")})
    start_scan = robot.scan()
    robot_start_rays = robot.last_rays
    steps_log = []

    def on_step(i, kind, amount, r):
        steps_log.append({"i": i + 1, "action": kind, "requested": amount, "done": r["done"],
                          "bump": r["bump"], "pose": robot.pose(), "scan": r["scan"],
                          "scan_max": r["scan_max"], "rays": r["rays"],
                          "say": "", "notes": ""})
        log({"type": "tool", "name": kind, "input": amount, "pose": robot.pose(),
             "bump": r["bump"], "steps": i + 1})

    t0 = time.time()
    steps = wall_follower.run(robot, max_steps, on_step, scan=start_scan)
    outcome = "success" if robot.outside else "step_limit"
    row = {"setting": "wall", "house_seed": house.seed, "noise_seed": noise_seed,
           "model": "none", "effort": "", "outcome": outcome, "success": robot.outside,
           "steps": steps, "bumps": robot.bumps, "calls": 0, "nudges": 0,
           "note_writes": 0, "note_reads": 0, "final_notes": "",
           "input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0,
           "cache_read_input_tokens": 0, "cost": 0.0,
           "seconds": round(time.time() - t0, 1), "error": None}
    log({"type": "end", **row})
    replay = {"setting": "wall", "model": "none", "outcome": outcome, "house": house.to_json(),
              "start": list(house.start), "start_scan": start_scan,
              "start_rays": robot_start_rays, "steps": steps_log,
              "final_notes": "", "max_steps": max_steps}
    return row, replay


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--setting", choices=SETTINGS + ["wall"], default="notebook")
    ap.add_argument("--house", type=int, default=0)
    ap.add_argument("--steps", type=int, default=150)
    ap.add_argument("--model", choices=MODELS, default="haiku")
    ap.add_argument("--fake", action="store_true", help="scripted model, costs nothing")
    a = ap.parse_args()
    h = sim.make_house(a.house)
    if a.setting == "wall":
        row, _ = run_wall_follower(h, a.house, a.steps)
    else:
        if a.fake:
            client = FakeClient(a.house)
        else:
            import anthropic
            client = anthropic.Anthropic(max_retries=6)
        row, _ = run_agent(client, a.setting, h, a.house, a.steps, a.model, fake=a.fake)
    print(json.dumps(row, indent=1))

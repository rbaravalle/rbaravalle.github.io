"""Draw the system diagram for the robot agent post.

    python3 make_diagram.py      # writes assets/robot-agent/img/system.svg

Same palette and card style as tiny-agent/diagrams/make_diagrams.py.
"""
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "assets" / "robot-agent" / "img"

BLUE, GREEN, YELLOW, ORANGE, PINK = "#7fb4ff", "#c3e88d", "#ffcb6b", "#f78c6c", "#f4a6c0"
TEXT, SUB, LABEL, CARD, BORDER, BG = "#d6dae4", "#8a93a6", "#aeb6c8", "#232838", "#343b4d", "#1b1f2a"
CACHED_FILL, NEW_FILL = "#2f3d5c", "#5a4a1f"

W, H = 760, 790

parts = []


def add(s):
    parts.append(s)


def text(x, y, s, cls="t", anchor="start"):
    add(f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{s}</text>')


def lines(x, y, rows, cls="t", dy=17):
    for i, r in enumerate(rows):
        text(x, y + i * dy, r, cls)


def card(x, y, w, h, stroke=BORDER, dashed=False):
    dash = ' stroke-dasharray="6 5"' if dashed else ""
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{CARD}" stroke="{stroke}" stroke-width="1.5"{dash}/>')


def arrow(x1, y1, x2, y2, color, dashed=False):
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    name = {BLUE: "blue", GREEN: "green", YELLOW: "yellow", LABEL: "grey"}[color]
    add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2"{dash} '
        f'marker-end="url(#a-{name})"/>')


def block(x, y, w, h, cached, label=""):
    fill, stroke = (CACHED_FILL, BLUE) if cached else (NEW_FILL, YELLOW)
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
    if label:
        text(x + w / 2, y + h / 2 + 4, label, "blk", "middle")


# ---------------------------------------------------------------- regions
add(f'<rect x="12" y="12" width="402" height="482" rx="16" fill="none" stroke="{BORDER}" stroke-width="1.5" stroke-dasharray="7 6"/>')
text(28, 36, "ON YOUR COMPUTER", "region")
text(28, 52, "(on the real robot: its Raspberry Pi)", "small")
add(f'<rect x="434" y="12" width="314" height="482" rx="16" fill="none" stroke="{BORDER}" stroke-width="1.5" stroke-dasharray="7 6"/>')
text(450, 36, "IN THE CLOUD", "region")
text(450, 52, "(Anthropic API)", "small")

# ---------------------------------------------------------------- simulator
card(28, 66, 370, 170, GREEN)
text(44, 90, "Simulator  (sim.py)", "h")
text(382, 90, "on the real robot: the Create 3", "small", "end")
# mini house 47: 3.9 x 4.6 m scaled
hx, hy, s = 46, 104, 22.0
walls = [(0, 0, 4.84, 0), (4.84, 0, 4.84, 5.7), (0, 5.7, 3.19, 5.7), (4.08, 5.7, 4.84, 5.7), (0, 0, 0, 5.7),
         (0, 2.17, 0.46, 2.17), (1.32, 2.17, 4.84, 2.17), (2.61, 2.17, 2.61, 4.42), (2.61, 5.18, 2.61, 5.7),
         (2.94, 0, 2.94, 0.99), (2.94, 1.77, 2.94, 2.17)]
for x1, y1, x2, y2 in walls:
    add(f'<line x1="{hx + x1 * s:.1f}" y1="{hy + (5.7 - y1) * s:.1f}" x2="{hx + x2 * s:.1f}" '
        f'y2="{hy + (5.7 - y2) * s:.1f}" stroke="{LABEL}" stroke-width="2.4" stroke-linecap="round"/>')
add(f'<line x1="{hx + 3.19 * s:.1f}" y1="{hy:.1f}" x2="{hx + 4.08 * s:.1f}" y2="{hy:.1f}" stroke="{GREEN}" stroke-width="3" stroke-dasharray="3 3"/>')
rx, ry = hx + 1.14 * s, hy + (5.7 - 1.56) * s
for k in range(0, 360, 20):
    import math
    add(f'<line x1="{rx}" y1="{ry}" x2="{rx + 16 * math.cos(math.radians(k)):.1f}" '
        f'y2="{ry + 16 * math.sin(math.radians(k)):.1f}" stroke="{YELLOW}" stroke-opacity="0.35" stroke-width="1"/>')
add(f'<circle cx="{rx}" cy="{ry}" r="4.5" fill="{YELLOW}"/>')
lines(166, 116, ["The house: walls, doors, one exit.",
                 "Physics: a move advances 1 cm at",
                 "a time; if the body would touch a",
                 "wall, it stops there: BUMP.",
                 "Lidar: 72 rays, one every 5°.",
                 "Judges success: centre outside."], "t")

# ---------------------------------------------------------------- robot interface
arrow(80, 296, 80, 244, YELLOW)
text(90, 274, "move(1.0) or turn(45)", "lab")
arrow(360, 244, 360, 296, GREEN)
text(350, 274, "result + scan", "lab", "end")

# ---------------------------------------------------------------- agent loop
card(28, 304, 370, 178, BLUE)
text(44, 328, "Agent loop  (agent.py)", "h")
lines(44, 352, ["1. Turns the result into a log entry:"], "t")
lines(60, 369, ["“Step 12 ... BUMP ... Scan: front clear",
                "0.34 m, farthest >8 m; ...”"], "small", 16)
lines(44, 406, ["2. Memory: keeps the last entry (goldfish),"], "t")
lines(60, 423, ["10 (window), all (full), plus a notebook."], "small")
lines(44, 446, ["3. Builds a request, sends it, gets a reply.",
                "4. Runs the tool the reply asks for."], "t")

# ---------------------------------------------------------------- the cloud
card(450, 66, 284, 170, PINK)
text(466, 90, "Prompt cache", "h")
lines(466, 114, ["Remembers the beginning of recent",
                 "requests for 5 minutes.",
                 "If the next request starts with the",
                 "same text, that part is read back at",
                 "1/10 of the price, and faster.",
                 "Any change ends the match there."], "t")

card(450, 304, 284, 178, PINK)
add(f'<g transform="translate(486,356) scale(0.9)">'
    f'<path d="M-2,-22 C-12,-28 -27,-21 -26,-10 C-34,-6 -33,8 -25,12 C-25,22 -12,26 -2,21 Z" fill="{PINK}"/>'
    f'<path d="M2,-22 C12,-28 27,-21 26,-10 C34,-6 33,8 25,12 C25,22 12,26 2,21 Z" fill="{PINK}"/></g>')
text(526, 342, "Claude Haiku 5.5", "h")
text(526, 360, "the model", "small")
lines(466, 396, ["Reads the whole request, thinks",
                 "(hidden, billed as output), and",
                 "answers with one sentence and",
                 "one tool call. It keeps nothing",
                 "between calls."], "t")

arrow(592, 296, 592, 244, LABEL, dashed=True)
text(602, 268, "same start as before?", "lab")

# request / reply between agent and model
arrow(398, 400, 446, 400, YELLOW)
arrow(446, 440, 402, 440, GREEN)
text(422, 392, "request", "lab", "middle")
text(422, 458, "reply", "lab", "middle")

# ---------------------------------------------------------------- what is sent
text(28, 528, "What is sent to the cloud on every step (full history)", "h")
rows = [("call 1", 0), ("call 2", 1), ("call 3", 2), ("call 18", 17)]
y0 = 546
for r, (name, n) in enumerate(rows):
    y = y0 + r * 30
    text(28, y + 15, name, "t")
    x = 92
    block(x, y, 132, 20, cached=(n > 0), label="tools + system prompt")
    x += 136
    block(x, y, 70, 20, cached=(n > 0), label="task, start")
    x += 74
    shown = min(n, 12)
    for k in range(shown):
        last = k == shown - 1
        block(x, y, 20, 20, cached=not last, label="")
        x += 23
    if n > 12:
        text(x + 4, y + 15, "… 17 entries", "small")
    if n == 0:
        text(x + 4, y + 15, "(first call: everything is new)", "small")
y = y0 + 4 * 30 + 6
text(28, y + 15, "window", "t")
block(92, y, 132, 20, True, "tools + system prompt")
block(228, y, 70, 20, True, "task")
for k in range(10):
    block(302 + k * 23, y, 20, 20, False)
text(536, y + 15, "slides: never the same", "small")
ly = y + 40
block(28, ly, 18, 14, True)
text(52, ly + 12, "read from the cache: 1/10 of the price", "small")
block(330, ly, 18, 14, False)
text(354, ly + 12, "new text: full price", "small")
text(28, ly + 36, "Every reply also costs its output: one sentence, one tool call, and the hidden thinking (300-400 tokens).", "small")

svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif">
  <title id="t">The robot agent system</title>
  <desc id="d">On your computer: the simulator (house, physics, lidar) and the agent loop, connected by move/turn and result+scan. In the cloud: the model and the prompt cache. Every step the agent sends a request with the tools, system prompt, task and memory log, and gets back one sentence and one tool call. With full history each request repeats the previous one plus one new entry, so all but the newest entry is read from the cache.</desc>
  <defs>
    <marker id="a-blue" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{BLUE}"/></marker>
    <marker id="a-green" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{GREEN}"/></marker>
    <marker id="a-yellow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{YELLOW}"/></marker>
    <marker id="a-grey" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{LABEL}"/></marker>
    <style>
      .region {{ fill: {SUB}; font-size: 12px; font-weight: 700; letter-spacing: 1px; }}
      .h {{ fill: {TEXT}; font-size: 15px; font-weight: 600; }}
      .t {{ fill: {TEXT}; font-size: 12.5px; }}
      .small {{ fill: {SUB}; font-size: 11.5px; }}
      .lab {{ fill: {LABEL}; font-size: 12px; font-style: italic; }}
      .blk {{ fill: {TEXT}; font-size: 10.5px; }}
    </style>
  </defs>
  <rect width="{W}" height="{H}" fill="{BG}"/>
  {chr(10).join('  ' + p for p in parts)}
</svg>
"""
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "system.svg").write_text(svg)
print(f"wrote {OUT / 'system.svg'}")

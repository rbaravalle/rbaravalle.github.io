"""Draw the agent-loop diagrams for the tiny-agent post.

    python3 make_diagrams.py      # writes assets/tiny-agent/img/*.svg

One layout, five variants: the general loop and one per step. Elements a
step adds are outlined in yellow with a NEW badge; the human is orange.
"""
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "assets" / "tiny-agent" / "img"

BLUE, GREEN, YELLOW, ORANGE = "#7fb4ff", "#c3e88d", "#ffcb6b", "#f78c6c"
TEXT, SUB, LABEL, CARD, BORDER = "#d6dae4", "#8a93a6", "#aeb6c8", "#232838", "#343b4d"

HEAD = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 480" role="img" aria-labelledby="t d" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif">
  <title id="t">{{title}}</title>
  <desc id="d">{{desc}}</desc>
  <defs>
    <marker id="a-blue" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{BLUE}"/></marker>
    <marker id="a-green" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{GREEN}"/></marker>
    <marker id="a-yellow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{YELLOW}"/></marker>
    <marker id="a-orange" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{ORANGE}"/></marker>
    <style>
      .title {{ fill: {TEXT}; font-size: 18px; font-weight: 600; text-anchor: middle; }}
      .sub   {{ fill: {SUB}; font-size: 14px; text-anchor: middle; }}
      .label {{ fill: {LABEL}; font-size: 14px; font-style: italic; }}
      .line  {{ fill: none; stroke: #1b1f2a; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }}
    </style>
  </defs>
"""

# ---------- icons (drawn around 0,0) ----------
def person(color=LABEL):
    return (f'<circle cy="-6" r="8" fill="{color}"/>'
            f'<path d="M-14,16 Q-14,4 0,4 Q14,4 14,16 Z" fill="{color}"/>')

BRAIN = ('<path d="M-2,-22 C-12,-28 -27,-21 -26,-10 C-34,-6 -33,8 -25,12 C-25,22 -12,26 -2,21 Z" fill="#f4a6c0"/>'
         '<path d="M2,-22 C12,-28 27,-21 26,-10 C34,-6 33,8 25,12 C25,22 12,26 2,21 Z" fill="#f4a6c0"/>'
         '<path class="line" d="M-17,-12 Q-10,-9 -9,-1 M-22,4 Q-15,2 -10,7 M-8,13 Q-6,6 -1,5"/>'
         '<path class="line" d="M17,-12 Q10,-9 9,-1 M22,4 Q15,2 10,7 M8,13 Q6,6 1,5"/>')

HAND = (f'<g fill="{YELLOW}"><rect x="-12" y="-4" width="24" height="22" rx="7"/>'
        '<rect x="-12" y="-19" width="6" height="20" rx="3"/><rect x="-5.5" y="-25" width="6" height="26" rx="3"/>'
        '<rect x="1" y="-26" width="6" height="27" rx="3"/><rect x="7.5" y="-21" width="6" height="22" rx="3"/>'
        '<rect x="-21" y="-2" width="6" height="17" rx="3" transform="rotate(-38 -18 6)"/></g>')

EYE = ('<path d="M-30,0 Q0,-24 30,0 Q0,24 -30,0 Z" fill="#e8ecf4"/><circle r="11" fill="#82aaff"/>'
       '<circle r="5" fill="#1b1f2a"/><circle cx="3.5" cy="-3.5" r="2" fill="#ffffff"/>')

def eye_and_picture():
    pic = ('<g transform="translate(34,-6)"><rect x="-13" y="-11" width="26" height="22" rx="3" fill="#e8ecf4"/>'
           '<path d="M-10,8 L-3,-1 L3,5 L6,2 L10,8 Z" fill="#82aaff"/><circle cx="5" cy="-5" r="2.6" fill="#ffcb6b"/></g>')
    return f'<g transform="translate(-14,0)">{EYE}</g>{pic}'

# ---------- building blocks ----------
def card(x, y, w, h, icon, title, sub, icon_y, border=BORDER, new=False, dashed=False):
    stroke = YELLOW if new else border
    dash = ' stroke-dasharray="6 5"' if dashed else ""
    s = (f'<g transform="translate({x},{y})"><rect width="{w}" height="{h}" rx="14" fill="{CARD}" '
         f'stroke="{stroke}" stroke-width="{2.5 if new else 1.5}"{dash}/>'
         f'<g transform="translate({w/2},{icon_y})">{icon}</g>'
         f'<text class="title" x="{w/2}" y="{h-32}">{title}</text>')
    if sub:
        s += f'<text class="sub" x="{w/2}" y="{h-12}">{sub}</text>'
    if new:
        s += badge(w - 22, 0)
    return s + "</g>"

def badge(cx, cy):
    return (f'<g transform="translate({cx},{cy})"><rect x="-24" y="-12" width="48" height="24" rx="12" fill="{YELLOW}"/>'
            f'<text y="5" fill="#1b1f2a" font-size="13" font-weight="700" text-anchor="middle">NEW</text></g>')

def arrow(d, color=BLUE, dashed=False, width=2.5):
    name = {BLUE: "blue", GREEN: "green", YELLOW: "yellow", ORANGE: "orange"}[color]
    dash = ' stroke-dasharray="7 6"' if dashed else ""
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"{dash} marker-end="url(#a-{name})"/>'

def label(x, y, lines, anchor="start", color=None, size=14):
    fill = f' style="fill:{color}"' if color else ""
    return "".join(f'<text class="label" x="{x}" y="{y + 18*i}" text-anchor="{anchor}" font-size="{size}"{fill}>{t}</text>'
                   for i, t in enumerate(lines))

def repeat():
    return (f'<g transform="translate(380,265)"><path d="M-26,-10 A28,28 0 1 1 -10,26" fill="none" '
            f'stroke="#5b6478" stroke-width="2.5" marker-end="url(#a-blue)"/>'
            f'<text y="6" fill="{SUB}" font-size="15" text-anchor="middle">repeat</text></g>')

def done():
    return (f'<g transform="translate(598,38)"><rect width="132" height="48" rx="24" fill="#24311f" stroke="{GREEN}" stroke-width="1.5"/>'
            f'<path d="M30,24 L38,32 L52,16" fill="none" stroke="{GREEN}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<text x="64" y="30" fill="{GREEN}" font-size="17" font-weight="600">done</text></g>')

def task(note=None, you_color=LABEL, border=BORDER):
    s = (f'<g transform="translate(20,20)"><rect width="130" height="84" rx="12" fill="{CARD}" stroke="{border}" stroke-width="1.5"/>'
         f'<g transform="translate(65,30)">{person(you_color)}</g><text class="title" x="65" y="72">your task</text></g>')
    return s

# ---------- the diagrams ----------
def diagram(step):
    parts = []
    # arrows first, under the cards
    if step == 0:
        parts.append(arrow("M468,120 C560,120 640,140 640,196"))
        parts.append(label(560, 112, ["“type this", "code”"]))
        parts.append(arrow("M640,316 C640,400 560,410 470,410", ORANGE))
        parts.append(label(580, 432, ["output, errors"], "middle"))
        parts.append(arrow("M290,410 C150,410 120,300 120,250 C120,170 200,120 290,120", ORANGE))
        parts.append(label(140, 292, ["you paste", "it back"]))
    else:
        parts.append(arrow("M468,120 C560,120 640,140 640,196"))
        parts.append(label(560, 112, ["“please run", "tool X with Y”"]))
        parts.append(arrow("M640,316 C640,400 560,410 470,410"))
        parts.append(label(580, 432, ["what happened"], "middle"))
        parts.append(arrow("M290,410 C150,410 120,300 120,250 C120,170 200,120 290,120"))
        parts.append(label(140, 292, ["sent back to", "the model"]))
    if step is not None and step >= 2:   # results printed for the human too
        c = YELLOW if step == 2 else BLUE
        parts.append(arrow("M290,440 L64,440 L64,112", c, dashed=True, width=2.5 if step == 2 else 2))
        parts.append(label(84, 462, ["printed for me too"], color=c))
    if step == 1:   # the human only gets the final paragraph
        parts.append(arrow("M330,150 C330,180 100,170 85,112", ORANGE, dashed=True, width=2))
        parts.append(label(36, 196, ["all I see: a", "friendly paragraph"], color=ORANGE))
    parts.append(repeat())
    parts.append(arrow("M150,62 L290,62"))
    parts.append(arrow("M468,62 L590,62", GREEN))
    parts.append(label(536, 86, ["“here is my answer”"], "middle", size=13))

    # cards
    parts.append(task())
    # The model (the brain) is the same in every step; only hands and eyes change.
    parts.append(card(290, 20, 178, 130, BRAIN, "the model", "reads, decides, asks", 42))
    parts.append(done())
    if step == 0:
        parts.append(card(551, 196, 178, 120, person(ORANGE), "you run it", "copy · paste · run", 34, border=ORANGE))
        parts.append(card(290, 345, 178, 120, person(ORANGE), "you read it", "and report back", 34, border=ORANGE))
    else:
        parts.append(card(551, 196, 178, 120, HAND, "the tools", "read · write · run", 40, new=step == 1))
        if step == 3:
            parts.append(card(290, 345, 178, 120, eye_and_picture(), "the results", "whole output · images", 38, new=True))
        else:
            sub = "output · errors" if step in (1, 2) else "output · errors · images"
            parts.append(card(290, 345, 178, 120, EYE, "the results", sub, 38, new=step == 2))
    return "\n  ".join(parts)

META = {
    "agent-loop": ("The agent loop",
                   "Your task goes to the model (a brain). It either answers and is done, or asks for a tool. "
                   "The tools (a hand) read, write and run. The results (an eye) are sent back, and the loop repeats.", None),
    "step0-chatbot": ("Step 0: a chatbot",
                      "The model can only talk. It tells you what code to type; you run it, read the output and "
                      "errors, and paste them back. You are the hands and the eyes: you are the loop.", 0),
    "step1-hands": ("Step 1: hands",
                    "New: tools. The model asks to read, write and run, my code does it and sends the results back. "
                    "But I only see the model's final paragraph, not what the program printed.", 1),
    "step2-eyes": ("Step 2: eyes",
                   "New: every result is printed for me too, and the model is told to measure: back every claim "
                   "with output it saw.", 2),
    "step3-real-eyes": ("Step 3: real eyes",
                        "New: the model gets the whole output (start and end, with a note on what was cut) and can "
                        "look at images it saved, and it is told to look.", 3),
}

for name, (title, desc, step) in META.items():
    svg = HEAD.replace("{title}", title).replace("{desc}", desc) + "  " + diagram(step) + "\n</svg>\n"
    (OUT / f"{name}.svg").write_text(svg)
    print("wrote", OUT / f"{name}.svg")

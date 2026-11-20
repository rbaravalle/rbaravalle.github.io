---
title: "How much does a robot need to remember? An agent with no map"
# Fixed address for the local preview. Remove when publishing (move to _posts/).
permalink: /drafts/robot-agent-memory/
---

<!--
DRAFT, second version. All numbers are from the runs of 2026-11-20, with
Claude Haiku 5.5 at medium effort:
  pilot:    5 houses, 1 run per setting, $0.69
  round 1:  house 47, 5 runs per setting, $1.24
  round 2:  house 47, 1 run per setting (clearance, odometry), $0.38
  round 3:  house 47, 1 run per setting (clear + farthest), $0.07
-->

In the [last post]({% post_url 2026-11-18-a-tiny-agent %}) I opened the box:
a coding agent is a loop around a model, and what makes it work is the
feedback. This time I wanted to apply an agent to a robotics task, something I undertand well.

Here is the question behind the next few posts. Classical robot navigation
(SLAM, path planners, hand-written behaviours) is intelligence we wrote by
hand, because machines had none of their own. Now they have some. **Can an
agent replace that hand-written stack?** I don't expect one blog post to
answer that. I just want to understand these systems in a simulated example that I can later extend.

The agent gets **no map, no SLAM and no planner**. Only a sensor (simulating a Lidar), two actions,
and a limited memory. Its job: get out of a house.

## I was concerned about costs and context size

When a robot builds a map, it is answering a question: *what do I need to
remember about this space?* SLAM's answer is written by hand: a metric map,
plus an estimate of where I am on it. An agent with no map has to come up
with its own answer, for example by writing notes to itself. Do those notes
turn into a kind of map in words?

Memory costs real money in these exercises. Everything the agent remembers is sent to
the model again on every call: more memory means more tokens, more latency,
more context. So the question for this post was:

**Without a map, how much memory does a robot agent need, what does it choose
to remember, and what does that memory cost?**

The answer I got is mostly about something else. What
the robot could *see* mattered more than what it could remember, and what it
could see was my decision, not the model's.

## The setup

Everything here is simulated. I'd like to run it on my Create 3 (a Raspberry
Pi with a 2D lidar) one day, so the simulated robot looks like that one, but
this post is pure software. All the code is in
[the repository](https://github.com/rbaravalle/rbaravalle.github.io/tree/main/robot-agent).

* **The house.** A random floor plan of a few rooms, inside 5 × 6 m, with one
  exit to the outside. Every interior wall is connected to the outer wall (that
  matters later). The robot never starts in the exit's room.
* **The robot.** Round, 0.17 m of radius, about the size of a Create 3. Two
  actions: `move(meters)` and `turn(degrees)`. A move stops if it bumps into
  something, and says so (more on the physics below).
* **The lidar.** It casts 72 rays, one every 5 degrees. The model doesn't get
  72 numbers: after every action it gets a summary, as text, of 8 directions
  (front, front-left, left, ... front-right), 45 degrees each, with a little
  noise. *What* that summary contains turned out to be the most important
  decision in this post, and I got it wrong twice. The house is small, so
  from inside it nothing is farther than 8 m. A reading of `>8 m` means open
  space beyond the house: that is the only hint of where the exit is.
* **No odometry.** The real Create 3 counts its wheel turns, so it always
  roughly knows where it is relative to where it started. That is a kind of
  memory you get for free, and I left it out on purpose, to keep the memory
  question clean. (It comes back in round 2.)
* **Success** is judged by the simulator, not the model: the robot's centre has
  to leave the house. The agent can call `done` to give up; calling it while
  still inside counts as a failure.

The agent loop is the one from post 2, with the shell tools swapped for
`move` and `turn`. Same model: Claude Haiku 5.5, the small cheap one, at its
default ("medium") effort. Here is the whole system in one picture:

<figure style="margin: 1.5em 0;">
  <img src="{{ '/assets/robot-agent/img/system.svg' | relative_url }}"
       style="width: 100%;"
       alt="The robot agent system. On my computer: the simulator (the house, the physics, a 72-ray lidar) and the agent loop. The agent loop sends move or turn to the simulator and gets back the result and a scan. It turns that into a log entry, keeps as much of the log as its memory setting allows, and sends a request to the cloud. In the cloud, Claude Haiku 5.5 reads the request and answers with one sentence and one tool call; a prompt cache remembers the start of recent requests and charges a tenth for repeating it. Below: with full history, every request repeats the previous one plus one new entry, so all but the newest entry is read from the cache; with a window, the entries change every call.">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    Everything on the left runs on my laptop. On the real Create 3, the
    simulator box becomes the robot itself (the same <code>move</code>,
    <code>turn</code> and scan, through ROS 2 on its Raspberry Pi), and the
    agent loop would run on the Pi. The model always runs in the cloud: every
    step is one request over the internet, and the model keeps nothing between
    requests. All its memory is what the loop decides to send.
  </figcaption>
</figure>

### How the simulator moves the robot

There is no real physics engine: no mass, no momentum, no wheel slip. The
simulator is *kinematic*: a move is a straight line, a turn is a turn in place.
To move 1 m, it advances the robot 1 cm at a time, and before each centimetre
it checks whether the robot's body (a circle of 17 cm radius) would touch a
wall. If it would, the robot stops where it is, and the result says `BUMP:
stopped after 0.43 m of 1.00 m`. That is roughly what the Create 3 does with
its front bumper: drive, feel the contact, stop. Turning in place can never
hit anything, because the robot is round. Walls are 8 cm thick; with
zero-thickness walls, a wall seen exactly end-on could slip between two lidar
rays: invisible, but solid.

## Four memory settings to compare

The robot sees its past as a short log, one entry per action:

```
Step 12. You said: "The front is the most open direction, so I'll drive
forward 1 m." You called move(1). Result: Moved 1.00 m.
Scan: front 1.82 m, front-left 1.40 m, left 0.62 m, ...
```

What changes between the settings is how much of that log it gets:

1. **Goldfish**: only the last action and its scan.
2. **Window**: the last 10 actions.
3. **Notebook**: the last 10 actions, plus a 500-character notebook that the
   robot writes itself (a `write_note` tool) and that is always shown to it.
4. **Full history**: everything since the start.

On every call the model gets one fresh message built from that memory. Its
own thinking from earlier calls is never sent back: what it remembers of its
reasoning is what it said out loud.

I expected less memory to be cheaper, but that isn't obvious, because of
*prompt caching*. The model keeps nothing between calls, so every request
carries everything again: the tool descriptions, the instructions, and the
memory. That is a lot of repeated text. With caching on, the API remembers
the beginning of each request for a few minutes. When the next request starts
with exactly the same text, that part is read back from the cache at a tenth
of the price (writing it the first time costs a quarter more than normal).
The match is from the very first character: as soon as one character differs,
everything after it is paid in full.

That favours full history in a way I hadn't expected. It only ever grows at
the end, so each request is the previous one plus one new entry, and all but
that entry comes from the cache (the bottom of the picture above). A sliding
window drops its oldest entry on every call, so from that point on nothing
matches. In the runs below, over 90% of the full-history input came from the
cache, against a third to 40% for the window.

## The baseline: keep the wall on your right

To compare against, the oldest trick for mazes: keep one hand on the wall and
walk. No model, no memory, about 30 lines of Python reading the same scan.

Because every wall in these houses is connected to the outer wall, following
the wall on your right is *guaranteed* to take you out, eventually. It is also slow: it gets out of all of 200 test houses, but needs a median of 170 actions, because it works in small
steps.

An "intelligent" agent should be able to beat it: it can drive 2 metres at a time, and it
can, in principle, think.

## The pilot: my first mistake

I started with a pilot: 5 houses, one run of each setting, to see what a run
costs. Total: $0.69. The first lesson was about my experiment, not the agent.
In one house every setting got out **in 2 steps**: the robot started in the
exit's room, with the exit in plain view. Three of the five houses started in
the exit's room. Those runs measure nothing about memory, and if I had
averaged them in, they would have looked like a success. That is when I added
the rule that the robot never starts in the exit's room.

Then I picked one house that needs some memory, house 47, and stayed with it.

<div data-robot-replay="{{ '/assets/robot-agent/runs/v3-wall-h047-r0.json' | relative_url }}"
     data-labels="Wall follower"></div>
<script src="{{ '/assets/robot-agent/replay.js' | relative_url }}"></script>

The robot starts bottom left. The way out goes up through the top-left room,
whose door to the exit room is high on its right wall. The bottom-right room
is a dead end. The wall follower takes 131 actions. The thin lines are the
lidar's 72 rays at each step; dashed rays see nothing within 8 m.

## Round 1: lost, with all the memory it needs

Five runs of each setting:

| | runs | got out | bumps per run | cost per run |
|---|---|---|---|---|
| wall follower | 1 | 1 (131 actions) | 1 | $0 |
| goldfish | 5 | 1 | 1.0 | $0.032 |
| window | 5 | 0 | 4.8 | $0.068 |
| notebook | 5 | 0 | 4.6 | $0.070 |
| full history | 5 | 0 | 2.6 | $0.077 |

One success out of twenty, and it went to the setting with the *least*
memory. That goldfish was lucky: after 98 actions of wandering it happened to
turn toward the open door, saw `>8 m`, and drove at it. Five runs can't rank
anything, and I'm not going to pretend they do. What they show clearly is
*how* the agent fails, and it failed the same way with every memory.

<div data-robot-replay="{{ '/assets/robot-agent/runs/v1-full-h047-r3.json' | relative_url }},{{ '/assets/robot-agent/runs/v1-notebook-h047-r2.json' | relative_url }}"
     data-labels="Full history (round 1),Notebook (round 1)"></div>

**It forgot its own body.** Of the 65 bumps, 51 came from the same mistake:
the scan says the front is clear for 1.63 m, the model asks for `move(1.5)`,
and the bumper stops it at 1.45 m. The distance was measured from the centre
of the robot, and the front of the robot is 17 cm ahead of its centre. The
prompt said so, once. The model read the number as "how far I can drive".

**It went around in circles.** With full history, the robot drove into the
dead-end room **six times**. Every time, it had in front of it the whole log
of the previous visits, and every time it reasoned as if it were somewhere
new:

> The front is open at 2.73 m, the most room in this scan, so I'll drive
> forward 2 m.

Its strategy in every setting was the same: drive toward the most open
direction. In a doorway, the most open direction is into the next room. In
that room, the most open direction is back through the doorway. It took
until action 146 for it to say "the corridor ends I've been cycling through".

The memory was there. What seemed to be missing was the ability to say *"I
have been here before"*. Two scans from the same doorway are never quite the
same: a few centimetres of position, a few degrees of heading, a little
noise, and eight numbers all change. Matching what you see now to what you
saw before, without knowing where you are, is called *place recognition* (or
*loop closure*). It is one of the hard parts of SLAM.

**The notebook held strategy, not a map.** Given 500 characters it chooses
itself, the robot wrote two to four notes per run, and they were lessons and
plans:

> Step 76: loop detected. Forward 2m from spot with front~2.4 always leads
> to front 0.4 wall (room ~3m deep). Spots cycle. Next: try back-right
> diagonal (turn -135) and explore new headings; avoid front-back shuttle.

It notices the loop and describes it well. It still can't say *where* the
loop is, so it can't avoid it. The closest it came to a map was one run that
started naming places:

> Step 100: Oscillating between A (front wall 0.15, back open 3.3) and B (2m
> behind A, front 2.15). Stop moving forward into A.

A and B, defined by what the lidar sees there and by the distance between
them: two nodes and an edge, a map in words. And in the pilot, one notebook
did something I liked a lot. At action 72, after going back and forth for
most of the run, it wrote:

> New plan (step 73+): systematic wall-follow instead of oscillating. Rule:
> if front <1.0 m, turn -90 (right). Else move 1 m forward.

It got out two actions later. Left alone with a notebook, the agent
reinvented the baseline.

## Round 2: give it back its body and its position

Two changes, and from here on one run per setting: one run is enough to see
the behaviour, and I'm not measuring success rates anyway.

1. **Clearance.** Every reading became the free space in front of the body,
   not the distance from the centre: the number a driver needs, not the
   number a sensor gives.
2. **Odometry**, as a fifth setting: full history, plus the wheel odometry
   after every action (`Odometry: x 1.23 m, y -0.40 m, heading 90 degrees`,
   relative to the start, drifting a little). If not knowing *where* it had
   been was the problem, this should fix it.

Clearance worked at once: 4 bumps in the five runs, against 1 to 5 per run
before. One run got out (the notebook, in 78 actions).

Odometry did something more interesting, and still failed. The robot started
to reason with a map in its head:

> I'm at about (0.6, 1.4) with 103 actions left and no exit seen yet. The
> unexplored pocket seems to be northwest, between x -1 and 0 and y 2 to 3.5,
> so I'll face west and probe.

> The southeast corner near (1.2, -0.3) is the last lead I haven't checked.

That is a map in words, with coordinates. It reached the exit's room at action
33 and searched it, methodically, for 38 actions. At action 39 it was 60 cm
from the exit, right below it, facing it. The front read **0.34 m**.

<div data-robot-replay="{{ '/assets/robot-agent/runs/v2-odometry-h047-r0.json' | relative_url }}"
     data-labels="Odometry (round 2)"></div>

## My Mistake: the sensor hid the exit

Each of the 8 directions reported the *minimum* of its slice: the closest
thing in 45 degrees. That is what you want for not hitting things, and it is
what my plan said. But a gap only shows up in a minimum if the *whole* slice
fits through it. At action 39, some rays went out through the exit. The door
jamb, in the same slice, set the reading.

From random poses inside the exit's room of house 47, the
exit read `>8 m` in **7%** of the scans, and in 16% within 1.5 m of it. If each
direction had also reported its farthest ray, it would have been 100%.
Doorways hide in the same way. The prompt told the robot that `>8 m` was the
only sign of the exit, and my sensor almost never showed it.

That changes how to read everything above. Some of the "going around in
circles" was a robot that couldn't see the doors. The replay viewer didn't
help me either: it drew the 8 summary readings as 8 lines, so it looked like
a lidar with 8 rays, and looked fine. A nice picture isn't a measurement, and
this time the picture I was trusting was my own.

### Why 8 numbers, and not all 72?

A fair question, once you see the replays: the lidar casts 72 rays, so why
not send all of them and let the model work out what they mean?

It wasn't cost. Sending all 72, labelled by angle (`0:1.36 5:1.34 10:1.37
...`), is about 180 tokens per scan, against about 90 for 8 directions with
two numbers each, and 36 for the 8 minimums I started with. With full
history most of that comes from the cache; even with the window, where
nothing does, the 72 rays would add about 2 cents to a run of 200 actions.

The real reason is that it was my plan, and the plan was a guess: a small
model would reason better over 8 named directions ("front-left is open")
than over a wall of 72 numbers, and the log would stay readable, for the
model and for me. I never tested that guess, and the 8 minimums are exactly
what hid the exit. Letting the model see everything, and find its own way to
read it, is closer to the spirit of the question this series asks. So the
code can now do both (`--scan rays`).

## Round 3: success, let it see the gaps

One change: every direction reports two numbers.

```
Scan: front clear 1.05 m, farthest 3.76 m; front-left clear 0.75 m,
farthest 2.80 m; ...
```

"Clear" for driving, "farthest" for seeing gaps. And the prompt says so: when
farthest is much larger than clear, part of the slice sees through a gap.

| | got out | actions | bumps | cost |
|---|---|---|---|---|
| wall follower | yes | 131 | 1 | $0 |
| goldfish | yes | 40 | 0 | $0.008 |
| window | yes | 68 | 5 | $0.029 |
| notebook | yes | 62 | 6 | $0.026 |
| full history | yes | 18 | 0 | $0.004 |
| odometry | yes | 18 | 0 | $0.004 |

Everything got out. The full-history robot went start room, top-left room,
exit room, out, in 18 actions, and it read the new numbers exactly as
intended:

> The front is blocked at about 0.7 m, but the front-left slice shows a gap
> (clear 0.75 m, farthest 2.8 m). I'll turn 45° left toward it and rescan.

> The front slice shows open space beyond 8 m with 1.58 m clear, so the exit
> is straight ahead.

<div data-robot-replay="{{ '/assets/robot-agent/runs/v3-full-h047-r0.json' | relative_url }},{{ '/assets/robot-agent/runs/v3-goldfish-h047-r0.json' | relative_url }},{{ '/assets/robot-agent/runs/v3-window-h047-r0.json' | relative_url }}"
     data-labels="Full history (round 3),Goldfish (round 3),Window (round 3)"></div>

The goldfish, the window and the notebook still went into the dead end four or
five times each before they found the right door, so memory may still matter.
One run each can't say how much. The window's bumps were new: the front was
clear for 3.7 m, it asked for 2 m, and its side caught a door jamb, five times
in seven actions at the same doorway. And the notebook's one note was place
recognition, done by hand:

> Steps 1-10 loop: current scan matches step-1 scan (front 1.6/3.6, left
> 0.4/4.0).

## Round 4: a harder house

With the sensor fixed, I wanted a harder house: house 260, three doors from
the start to the exit, where house 47 had two. The exit's room is right above
the start room, but there is no door between them: the way out is a U,
through the bottom-left room and the top-left room. The exit isn't visible
from the start, and the robot has to drive *away* from it first. The wall
follower takes 148 actions.

| | got out | actions | cost |
|---|---|---|---|
| wall follower | yes | 148 | $0 |
| goldfish | yes | 27 | $0.005 |
| window | yes | 21 | $0.007 |
| notebook | yes | 22 | $0.008 |
| full history | yes | 20 | $0.004 |
| odometry | yes | 15 | $0.003 |

<div data-robot-replay="{{ '/assets/robot-agent/runs/v4-full-h260-r0.json' | relative_url }},{{ '/assets/robot-agent/runs/v4-goldfish-h260-r0.json' | relative_url }},{{ '/assets/robot-agent/runs/v4-wall-h260-r0.json' | relative_url }}"
     data-labels="Full history (round 4),Goldfish (round 4),Wall follower (round 4)"></div>

Every setting got out, every one took the same U, and none of them went back
into a room it had left. The whole batch cost under 3 cents. The strategy is
visible in what the full-history robot said: it follows the biggest
"farthest" reading, from opening to opening.

> The back-right slice reports 5.48 m of farthest range, the only sign of an
> opening, so I'll turn to face it.

> The right side shows a view past 8 m, so the exit is likely that way. I'll
> turn right 90 degrees to face it.

In every run the exit first showed up from the top-left room, through the
doorway into the exit's room.

"Harder" was the wrong word, though. House 260 has more doors, but no dead
end: its rooms form a chain, so every opening the robot follows leads either
forward or back the way it came. Following openings can't go wrong for long
in a house like that. House 47 does have a dead end, and in round 3 the
goldfish, window and notebook all went into it four or five times. A house
with dead ends and loops is where memory should matter, and that is the test
I haven't run yet.

## What it costs

Failing is what costs money. A run that fails uses all 200 actions: about 3
cents for the goldfish, 7 to 8 cents for the others in round 1, and 18 cents
for the odometry run in round 2, which thought three times as much as the
others. Most of the cost is not the memory: it is the model *thinking* before
each move, 300 to 400 output tokens per action, almost all of it hidden
reasoning. A run that gets out in 18 actions costs less than half a cent.

Full history sends the most text, but almost all of it comes from the cache,
so it never cost much more than the window. Less memory was cheaper per
action, but the real cost driver is the number of actions, and an agent that
goes in circles takes a lot of them.

Everything in this post, 55 agent runs in five batches, cost **$2.41**.

## Limitations

* This is a learning experiment, not a claim that language models navigate
  well or badly in general. One small model, one prompt, one house for most of
  it.
* Very few runs: five per setting in round 1, one per setting after that.
  Enough to see *how* it behaves, not to rank the settings. In particular, I
  can't say from one run each that full history beats the goldfish in round 3.
* House 47 may be easy once the robot can see gaps: in round 3, a few rays
  reached the exit from the start room itself, through two doorways in a
  row, at action 7. House 260 has no dead end at all. Neither is the house
  that would test memory hardest.
* I didn't run the version that sends all 72 rays (`--scan rays`), so "would
  the model do better reading everything?" is still open.
* The simulator is only shaped like a Create 3: perfect actions, no wheel
  slip, walls as thin boxes, and a lidar summarised into 8 directions. Even
  with clear and farthest, the model doesn't know *where* in a 45-degree slice
  a gap is.
* No odometry, except in the one setting that adds it.
* Model: Claude Haiku 5.5 (`claude-haiku-5-5`), medium effort. All runs on 20
  November 2026.
* The code, seeds, transcripts and notes are all published in the repository.

## What I take away


I wanted to try an AI agent on a simple robotic task for the first time, as a first step.
I set out to ask how much a robot agent needs to remember, and I spent most
of the post learning what it needs to *see*. The model wasn't the weak link I
expected. Twice, the weak link was the interface I wrote for it: a distance
measured from the wrong place, and a summary that kept the closest thing and
threw away the gaps. Fixing those two took an agent that got out once in
twenty runs to one that got out in 18 actions, for less than half a cent,
and then out of a house with three doors in 15 to 27 actions, whatever its
memory. Memory, in these houses, mattered much less than I thought.

It is the same lesson as post 2, from the other side. There, the agent
followed the letter of my request and found loopholes in my check. Here, I
wrote the sensor to the letter of my plan ("8 sectors of minimum distance")
and it quietly hid the one thing the robot was looking for. An agent is only
as good as the feedback it gets, and writing that feedback is still a
hand-written, very human job.

So, can an agent replace the hand-written stack? Not from this. But the
places where it struggled are the places where the stack does its work:
recognising a place you have seen before, which the notebook tried to do by
hand, and turning raw sensor data into something you can reason with, which
I did badly, twice. The comparison I really want, the agent against a real
SLAM and planner, is for a later post.

Also this time, Claude built the simulator and drafted the post, and I
iterated.

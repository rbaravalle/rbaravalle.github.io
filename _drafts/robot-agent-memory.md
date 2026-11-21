---
title: "How much does a robotic agent need to remember?"
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

**There is no risk that your life gets boring if you have Conrad around.
"I am going to have a body!" - exclaims Conrad. People from Robotics SA is going to put me in the most advanced robot yet.**

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
remember about this space, in order to perform tasks on it?* SLAM's answer is written by hand: a metric map,
plus an estimate of where I am on it. An agent with no map has to come up
with its own answer, for example by writing notes to itself. Do those notes
turn into a kind of map in words?

Memory costs real money in these exercises (I don't have a powerful machine to run one locally). Everything the agent remembers is sent to
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
* **No odometry, initially.** The real Create 3 counts its wheel turns, so it always
  roughly knows where it is relative to where it started. That is a kind of
  memory you get for free, and I left it out on purpose, to keep the memory
  question clean. (It comes back in round 2.)
* **Success** is judged by the simulator, not the model: the robot's centre has
  to leave the house. The agent can call `done` to give up; calling it while
  still inside counts as a failure.

The agent loop is the one from post 2, with the shell tools swapped for
`move` and `turn`. Same model: Claude Haiku 5.5, the small cheap one, at its
default ("medium") effort.

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

### When is the model called?

Once per action, and only between actions. The model asks for one action,
say `move(1.5)`. The simulator then carries out the whole move on its own,
centimetre by centimetre, checking for contact, without asking the model
anything. Only when the move is finished, or stopped by a bump, does the loop
send the next request, with the result and a fresh scan. A 2 m move and a 10
cm move each cost exactly one call, and the model never sees what happens in
between.

In the runs in this post that was exactly one call per action (the notebook
added one now and then, to write a note). A call took about 2 seconds (median
1.8 s; one in ten took more than 3 s), and all that time the robot stands
still. On the real Create 3 it would be the same: drive, stop, think for two
seconds, drive again. That is slow for a robot, and it is one reason a real
system would keep fast reflexes, like stopping on the bumper, on the robot
itself, and ask the model only for the bigger decisions.

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

To compare against a trivial strategy, the oldest trick for mazes: keep one hand on the wall and
walk. Just 30 lines of Python reading the same scan.

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

<details markdown="1">
<summary style="cursor: pointer; margin: 1.2em 0 0.6em;"><b>Round 2: give it back its body and its position.</b> Clearance fixed the bumps. Odometry made it reason with coordinates, a map in words, but it searched the exit's room for 38 actions, once 60 cm from the exit, without seeing it. <i>(click to expand)</i></summary>

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

</details>

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

<details markdown="1">
<summary style="cursor: pointer; margin: 1.2em 0 0.6em;"><b>Round 4: a house with three doors.</b> Every setting got out in 15 to 27 actions, but the house has no dead end, so it tested less than I thought. <i>(click to expand)</i></summary>

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
with dead ends is where memory should matter.

</details>

<details markdown="1">
<summary style="cursor: pointer; margin: 1.2em 0 0.6em;"><b>Round 5: a house with a trap.</b> The trap caught only the wall follower: every agent saw the exit from the start room and drove straight to it. <i>(click to expand)</i></summary>

So I looked for a trap. In house 287 the robot starts in a long room at the
bottom, whose only door leads to a small hub room with two more doors. One
goes up to the exit's room. The other goes to the biggest room in the house,
and that room is a dead end. A robot that drives toward the most open space
should try the big room first, and then needs to remember that it already did.
(My floor plans can have dead ends, but never loops: each new wall adds
exactly one door, so the rooms always form a tree.)

| | got out | actions | cost |
|---|---|---|---|
| wall follower | no (needs 322) | 200 | $0 |
| goldfish | yes | 21 | $0.004 |
| window | yes | 15 | $0.004 |
| notebook | yes | 13 | $0.004 |
| full history | yes | 27 | $0.007 |
| odometry | yes | 16 | $0.003 |

<div data-robot-replay="{{ '/assets/robot-agent/runs/v5-wall-h287-r0.json' | relative_url }},{{ '/assets/robot-agent/runs/v5-full-h287-r0.json' | relative_url }}"
     data-labels="Wall follower (round 5),Full history (round 5)"></div>

The trap caught exactly one robot: the wall follower. Keeping its hand on the
wall, it went into the dead end, searched all of it, and ran out of actions
on its way back; it needs 322 to get out. No agent went into the dead end at
all. Every one of them saw the exit *from the start room*, between action 4
and action 9, through two doorways in a row, and then followed that `>8 m`
reading out.

So the trap didn't test memory either. When I picked the house I checked that
the exit wasn't visible from the starting spot, but not from the rest of the
start room. In houses this small, doorways often line up, and the exit can be
seen from far away. Once you can see where you're going, you don't need to
remember where you've been. A real memory test needs an exit that stays out
of sight until the very last room, and I haven't built that yet.

</details>

<details markdown="1">
<summary style="cursor: pointer; margin: 1.2em 0 0.6em;"><b>Round 6: all 72 rays.</b> Much worse: one success, about fifty bumps per run, three times the thinking. My hint told it to trust the ray straight ahead. <i>(click to expand)</i></summary>

The last question: what if the model reads the whole scan, 72 rays labelled
by angle, instead of my 8-direction summary? Same house as rounds 1 to 3,
house 47, one run per setting.

| | got out | actions | bumps | cost |
|---|---|---|---|---|
| goldfish | no | 200 | 53 | $0.077 |
| window | yes | 49 | 10 | $0.043 |
| notebook | no | 200 | 48 | $0.193 |
| full history | no | 200 | 47 | $0.348 |
| odometry | no | 200 | 55 | $0.418 |

Much worse: one success, about fifty bumps per run, and three times as much
thinking per action as in round 3 (about 1,000 output tokens against 300).
This one batch cost more than everything else in the post together.

<div data-robot-replay="{{ '/assets/robot-agent/runs/v6-rays-full-h047-r0.json' | relative_url }},{{ '/assets/robot-agent/runs/v6-rays-window-h047-r0.json' | relative_url }}"
     data-labels="Full history, 72 rays (round 6),Window, 72 rays (round 6)"></div>

The bumps have one cause, and it's mine again. The model reads the single ray
straight ahead and drives:

> The scan shows about 4 m of clear space straight ahead and to the
> front-right, with walls close on the left. I'll drive forward 2 m and
> rescan.

In that scan, the ray at 0° read 3.96 m, but rays 10 to 30 degrees to the
side read about 0.4 m: a door jamb, right next to its body. One ray says
nothing about a robot 34 cm wide. And my prompt for this format told it
exactly that: "you can drive forward about the distance at 0 before you touch
something". In the 8-direction format, "clear" was the minimum over a 40°
slice, so the width of the body was already built into the number. With raw
rays, the model would have to do that geometry itself, and with my hint it
didn't.

So this round doesn't show that raw data is worse. It shows that my summary
was doing real work: it turned 72 numbers into the two things that matter
for driving (can I fit, is there a gap) before the model ever saw them. That
is exactly the kind of hand-written processing a robotics stack is full of.

</details>

<details markdown="1">
<summary style="cursor: pointer; margin: 1.2em 0 0.6em;"><b>Round 7: all 72 rays, read properly.</b> Four of five got out, doing the geometry in words, but slower and at twelve times the price of the summary. <i>(click to expand)</i></summary>

Round 6 didn't solve anything; it only showed my hint was wrong. So I fixed
the hint and ran it again, on the same house with the same data. The prompt no
longer says to trust the ray straight ahead. It now says that the body is
0.34 m wide, that the smallest reading between 330 and 30 degrees is about
how far it can drive, and that a doorway is a group of neighbouring rays much
longer than the ones beside them (at 1 m, 5 degrees is about 9 cm).

| | got out | actions | bumps | cost |
|---|---|---|---|---|
| goldfish | yes | 149 | 8 | $0.120 |
| window | yes | 65 | 0 | $0.072 |
| notebook | yes | 42 | 0 | $0.054 |
| full history | yes | 95 | 6 | $0.111 |
| odometry | no | 200 | 28 | $0.489 |

<div data-robot-replay="{{ '/assets/robot-agent/runs/v7-rays-notebook-h047-r0.json' | relative_url }},{{ '/assets/robot-agent/runs/v7-rays-odometry-h047-r0.json' | relative_url }}"
     data-labels="Notebook, 72 rays read properly (round 7),Odometry, 72 rays read properly (round 7)"></div>

Four out of five got out, against one in round 6, and the bumps mostly went
away. The model now does the geometry itself, in words:

> The exit rays (355° to 10°) are open. The nearest obstacles are about 0.56 m
> at 20° on the left and about 0.17 m at 310° on the right, which leaves
> roughly 8 cm of clearance on each side. I'll drive a short 0.4 m and
> re-scan.

> The exit is straight ahead, but the wall corner at about 345-350° sits too
> close to the right for a direct drive. The clear lane is about 0.1 m to my
> left, so I'll turn left 90°, sidestep, and turn back.

So the raw data does work, once someone explains what the numbers mean. But
compare it with round 3, the same house with my 8-direction summary: there,
every setting got out in 18 to 68 actions, for 7 cents in total. Here it took
42 to 149 actions, and the batch cost 85 cents. The model thought about 1,500
output tokens per action, five times as much as in round 3, working out from
72 numbers what the summary used to hand it directly.

The odometry run failed, and it wasn't from misreading. Before its bumps it
reported the right numbers ("the nearest reading in the wider arc is 1.5 m at
30°") and drove less than that. The wall it kept hitting was beside it, just
outside the 30-degree arc my hint told it to check. My corrected hint is
better, but still not the whole geometry. It also went back into the dead end
four times, with its position in front of it every time.

The fix that worked was an explanation, and the explanation is hand-written
processing, moved from the code into the prompt. Either I turn 72 numbers into
"clear" and "farthest" before the model sees them, or I tell the model how to
do that itself, and it does it every step, slowly, at a price.

</details>

## Round 8: a house that hides its exit

So far, no memory setting has won, and the reason is the same every time: the
robot could see the exit from far away, through doorways in a row, and once
you can see where you're going you don't need to remember where you've been.
To actually ask the memory question, the exit has to stay out of sight.

That is harder to find than I thought. I wrote a search that checks, for every
point of the floor outside the exit's room, whether a straight line reaches
the exit gap without touching a wall. With doors this wide, almost every house
leaks: only 1 in 400 hides its exit from everywhere outside its room. So the
rule is slightly looser: the exit can't be seen from the start room or from
any dead end, and from almost nowhere else.

House 886 is the best of the first 2,000. The robot starts in a middle-left
room with two doors: one leads down to a small dead end, the other to a tall
room on the right. From there a door leads up to the top room, and the exit is
at its far left end. The exit can be seen from 0.4% of the right room's floor
and from nowhere else outside the top room. The wall follower explores the dead
end and the right room on the way, and needs 465 actions.

This time one run per setting wasn't enough: the question is about
differences between settings, and one run is mostly luck. I ran one first, to
see what it cost (21 cents), then two more, for three runs per setting, with
the 8-direction scan (clear + farthest).

| | got out | actions, each run | times into the right room |
|---|---|---|---|
| wall follower | 0 of 1 | 200 (needs 465) | 0 (lost in the dead end) |
| goldfish | 2 of 3 | 84, 78, 200 | 4, 4, 7 |
| window | 3 of 3 | 144, 199, 23 | 7, 11, 1 |
| notebook | 3 of 3 | 58, 168, 64 | 5, 6, 3 |
| full history | 3 of 3 | 16, 89, 87 | 1, 4, 2 |
| odometry | 2 of 3 | 200, 50, 59 | 9, 2, 2 |

<div data-robot-replay="{{ '/assets/robot-agent/runs/v8-full-h886-r0.json' | relative_url }},{{ '/assets/robot-agent/runs/v8-window-h886-r1.json' | relative_url }},{{ '/assets/robot-agent/runs/v8-odometry-h886-r0.json' | relative_url }},{{ '/assets/robot-agent/runs/v8-wall-h886-r0.json' | relative_url }}"
     data-labels="Full history, 16 actions (round 8),Window, 199 actions (round 8),Odometry, ran out (round 8),Wall follower (round 8)"></div>

The trap turned out to be the right-hand room, not the dead end. Its door up
to the top room is easy to miss, and run after run the robot went into the
right room, didn't find that door, came back to the start room, and tried
again. The last column counts those trips.

Here, finally, the agents beat the wall follower: 13 of the 15 runs got out,
while the wall follower spent 97 actions in the dead end and ran out of
steps. But between the memory settings there is still no clear winner. The
spread *within* a setting is bigger than the differences *between* them: the
window got out in 23 actions once and in 199 another time. There is a hint,
no more: the two settings that see everything (full history and odometry)
usually needed two trips into the right room, the others four to seven. One
odometry run still made nine.

And the transcripts show why more memory didn't help more. The agents do
notice the loop, and say so:

> Step 133: loops between spots A/B (front-back 1m). Front/back views ~3-4m
> but walls appear after 1m. [...] Avoid repeating back-and-forth; if stuck,
> try a new direction with long farthest.

That notebook run then kept doing what it did on every step, driving toward
the most open direction, and took 168 actions. The odometry run that failed
had its position after every action and made nine trips, and it used that
position once, at action 140 ("the back direction, which heads toward the area
near (0, -3)"), after saying that the scans "keep leading back into the same
cramped pocket". Memory lets the robot see that it's going in circles.
It doesn't give it a way to stop.

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

The most expensive batches of all were the two that read all 72 rays: $1.08
for five runs in round 6 and $0.85 in round 7, because each action thought
three to five times as much as with the summary.

Everything in this post, 85 agent runs in nine batches, cost **$4.90**.

## Limitations

* This is a learning experiment, not a claim that language models navigate
  well or badly in general. One small model, one prompt, one house for most of
  it.
* Very few runs: five per setting in round 1, three in round 8, one in the
  others. Enough to see *how* it behaves, not to rank the settings. Three
  runs can't confirm the hint in round 8.
* Only one house (886) really tested memory. In houses 47 and 287 the exit
  was visible from the start room, through doorways in a row; house 260 has no
  dead end. And even house 886 lets the exit be seen from a sliver of one
  room: with doors this wide, an exit hidden from everywhere is rare (1 house
  in 400).
* Rounds 6 and 7 depend on how I explained the 72 rays. A better explanation,
  or a stronger model, might read them faster and more cheaply than Haiku
  did with mine.
* The simulator is only shaped like a Create 3: perfect actions, no wheel
  slip, walls as thin boxes, and a lidar summarised into 8 directions. Even
  with clear and farthest, the model doesn't know *where* in a 45-degree slice
  a gap is.
* No odometry, except in the one setting that adds it.
* Model: Claude Haiku 5.5 (`claude-haiku-5-5`), medium effort. All runs on 20
  and 21 November 2026.
* The code, seeds, transcripts and notes are all published in the repository.

## What I take away

In short:

1. **Seeing mattered more than remembering.** The two fixes that turned
   failure into success were both about what the robot could see: distances
   from its body, and a scan that shows gaps. Neither was about memory.
2. **More data didn't help by itself.** All 72 rays only worked once I
   explained how to read them, and then cost twelve times as much as my
   8-direction summary, for a worse result. Data shaped for driving beat raw
   data.
3. **Memory didn't decide much, even when it should have.** Where the exit
   was visible from far away, memory didn't matter at all. Where it was
   hidden (round 8), there was still no clear winner: the variation from run
   to run was bigger than the differences between settings, with only a hint
   that seeing everything helps. The agents noticed their loops, but their
   strategy ("drive toward the most open direction") had no use for that.
   Remembering where you've been only helps if you have a plan that uses it,
   and that plan, systematic exploration, is one more thing a robotics stack
   writes by hand.


I wanted to try an AI agent on a simple robotic task for the first time, as a first step.
I set out to ask how much a robot agent needs to remember, and I spent most
of the post learning what it needs to *see*. The model wasn't the weak link I
expected. Twice, the weak link was the interface I wrote for it: a distance
measured from the wrong place, and a summary that kept the closest thing and
threw away the gaps. Fixing those two took an agent that got out once in
twenty runs to one that got out in 18 actions, for less than half a cent,
and then out of a house with three doors in 15 to 27 actions, whatever its
memory. Memory, in these houses, mattered much less than I thought, mostly
because the robot could see the exit from far away. Once you can see where
you're going, you don't need to remember where you've been.

And when I gave it everything, all 72 rays, it did worse. With a bad hint it
bumped into everything; with a good one it got out, but slower and at twelve
times the price, working out on every step what my 8-direction summary had
handed it directly. More data didn't help on its own: what helped was data
shaped into what matters for driving, whether I wrote that shaping in code or
explained it in the prompt. That shaping is most of what a hand-written
robotics stack does.

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

One more thing, about working with the agent that built all this. I needed to
steer it more than it looks like. It looks really capable, and it is, but you
are still valuable for decisions and common sense. If you are distracted, it
will try the most expensive experiments possible. (Its first plan was 100
runs per memory setting, about $25; the whole post ended up costing under
$5.) If you think a bit, you can help it: make it first try something that
shows the heart of the experiment, and only expand if needed. It is the same
as working with people.

Also this time, Claude built the simulator and drafted the post, and I
iterated.

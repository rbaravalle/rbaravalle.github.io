---
title: "How much does a robot need to remember? An agent with no map"
---

<!--
DRAFT. Things marked TODO need the second round of runs (clearance + odometry)
before they can be written. Everything else is from the runs of 2026-11-20:
the pilot (5 houses, 25 runs, $0.69) and house 47 (5 runs per memory
setting, 20 agent runs, $1.24), with Claude Haiku 5.5 at medium effort.
-->

In the [last post]({% post_url 2026-11-18-a-tiny-agent %}) I opened the box:
a coding agent is a loop around a model, and what makes it work is the
feedback. This time I wanted to point that loop at the thing I actually do for
a living: robots.

Here is the question behind the next few posts. Classical robot navigation
(SLAM, path planners, hand-written behaviours) is intelligence we wrote by
hand, because machines had none of their own. Now they have some. **Can an
agent replace that hand-written stack?** I don't expect one blog post to
answer that. So I'm taking it one small piece at a time, and this is the first
piece.

The agent gets **no map, no SLAM and no planner**. Only a sensor, two actions,
and a limited memory. Its job: get out of a house.

## Memory is the SLAM question

When a robot builds a map, it is answering a question: *what do I need to
remember about this space?* SLAM's answer is written by hand: a metric map,
plus an estimate of where I am on it. An agent with no map has to come up
with its own answer, for example by writing notes to itself. Do those notes
turn into a kind of map in words?

Memory is also what costs money. Everything the agent remembers is sent to
the model again on every call: more memory means more tokens, more latency,
more context. So the question for this post is:

**Without a map, how much memory does a robot agent need, what does it choose
to remember, and what does that memory cost?**

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
  something, and says so.
* **The lidar.** After every action, a fresh scan: the shortest distance in 8
  directions (front, front-left, left, ... front-right), as text, with a little
  noise. The house is small, so from inside it every reading is under 8 m. A
  reading of `>8 m` means open space beyond the house: that is the only hint of
  where the exit is.
* **No odometry.** The real Create 3 counts its wheel turns, so it always
  roughly knows where it is relative to where it started. That is a kind of
  memory you get for free, and I left it out on purpose, to keep the memory
  question clean. (I bring it back at the end.)
* **Success** is judged by the simulator, not the model: the robot's centre has
  to leave the house. The agent can call `done` to give up; calling it while
  still inside counts as a failure.

The agent loop is the one from post 2, with the shell tools swapped for
`move` and `turn`. Same model: Claude Haiku 5.5, the small cheap one. Each
call costs a fraction of a cent, and the script logs every token.

## Four memories

The robot sees its past as a short log, one line per action:

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
prompt caching. Full history only ever grows at the end, so on every call
almost all of it can be read back from a cache at a tenth of the price. A
sliding window changes on every call, so it can't. In the runs below, 99% of
the full-history input came from the cache, against about 40% for the window.

## The baseline: keep the wall on your right

To compare against, the oldest trick for mazes: keep one hand on the wall and
walk. No model, no memory, about 30 lines of Python reading the same 8-number
scan.

Because every wall in these houses is connected to the outer wall, following
the wall on your right is *guaranteed* to take you out, eventually. I want to
say that up front, so the numbers below don't present it as a discovery. It
isn't smart, it is just certain. It is also slow: it gets out of all of 200
test houses, but needs a median of 170 actions, because it works in small
steps.

The agent should be able to beat it: it can drive 2 metres at a time, and it
can, in principle, think.

## What happened

I started with a pilot: 5 houses, one run of each setting, to see what a run
costs. Total: $0.69. The first lesson was about my experiment, not the agent.
In one house every setting got out **in 2 steps**: the robot started in the
exit's room, with the exit in plain view. Three of the five houses started in
the exit's room. Those runs measure nothing about memory, and if I had
averaged them in, they would have looked like a success. So now the robot
always starts in another room.

Then I picked one house that needs some memory, house 47, and ran each
setting five times. This is the floor plan, with the wall follower's run:

<div data-robot-replay="{{ '/assets/robot-agent/runs/v1-wall-h047-r0.json' | relative_url }},{{ '/assets/robot-agent/runs/v1-goldfish-h047-r2.json' | relative_url }},{{ '/assets/robot-agent/runs/v1-full-h047-r3.json' | relative_url }},{{ '/assets/robot-agent/runs/v1-notebook-h047-r2.json' | relative_url }}"
     data-labels="Wall follower,Goldfish (the one success),Full history,Notebook"></div>
<script src="{{ '/assets/robot-agent/replay.js' | relative_url }}"></script>

The robot starts bottom left. The way out goes up through the top-left room,
whose door to the exit room is high on its right wall. The bottom-right room
is a dead end.

| | runs | got out | bumps per run | cost per run |
|---|---|---|---|---|
| wall follower | 1 | 1 (131 actions) | 1 | $0 |
| goldfish | 5 | 1 | 1.0 | $0.032 |
| window | 5 | 0 | 4.8 | $0.068 |
| notebook | 5 | 0 | 4.6 | $0.070 |
| full history | 5 | 0 | 2.6 | $0.077 |

One success out of twenty, and it went to the setting with the *least*
memory. Five runs can't rank anything, and I'm not going to pretend they do:
that goldfish was lucky. After 98 actions of wandering it happened to turn
toward the open door, saw `>8 m`, and drove at it. What the runs do show
clearly is *how* the agent fails, and it fails the same way with every
memory.

### It forgets its own body

Of the 65 bumps, 51 came from the same mistake: the scan says the front is
clear for 1.63 m, the model asks for `move(1.5)`, and the bumper stops it at
1.45 m. The distance was measured from the centre of the robot, and the
front of the robot is 17 cm ahead of its centre. The prompt said so, once.
The model read the number as "how far I can drive".

That one is my fault more than the model's: I gave it the number a sensor
gives, not the number a driver needs. In the second round every reading is
the *free space in front of the body*. TODO: did the bumps go away?

### It goes around in circles, with all the memory it needs

This is the run that surprised me. With **full history**, the robot drove
into the dead-end room **six times**. Every time, it had in front of it the
whole log of the previous visits. And every time it reasoned as if it were
somewhere new:

> The front is open at 2.73 m, the most room in this scan, so I'll drive
> forward 2 m.

Its strategy in every setting is the same: drive toward the most open
direction. In a doorway, the most open direction is into the next room. In
that room, the most open direction is back through the doorway. It took
until action 146 for it to say "the corridor ends I've been cycling through",
and by then it had 54 actions left.

The memory was there. What was missing was the ability to say *"I have been
here before"*. Two scans from the same doorway are never quite the same: a
few centimetres of position, a few degrees of heading, a little noise, and
eight numbers all change. Matching what you see now to what you saw before,
without knowing where you are, is called *place recognition* (or *loop
closure*). It is one of the hard parts of SLAM, and it is exactly the part we
write by hand.

### The notebook: strategy, not a map

The notebook was the setting I was most curious about: given 500 characters
it chooses itself, does the robot write a map? It doesn't. It writes two
to four notes per run, and they are lessons and plans:

> Step 76: loop detected. Forward 2m from spot with front~2.4 always leads
> to front 0.4 wall (room ~3m deep). Spots cycle. Next: try back-right
> diagonal (turn -135) and explore new headings; avoid front-back shuttle.

It notices the loop. It describes it well. It still can't say *where* the loop
is, so it can't avoid it. The closest it came to a map was one run that
started naming places:

> Step 100: Oscillating between A (front wall 0.15, back open 3.3) and B (2m
> behind A, front 2.15). Stop moving forward into A.

A and B, defined by what the lidar sees there and by the distance between
them. That is a map in words, two nodes and an edge. It is also where
the notebook ran out: 500 characters hold a strategy or a couple of places,
not a house.

And in the pilot, one notebook did something I liked a lot. At action 72, after
going back and forth for most of the run, it wrote:

> New plan (step 73+): systematic wall-follow instead of oscillating. Rule:
> if front <1.0 m, turn -90 (right). Else move 1 m forward.

It got out two actions later. Left alone with a notebook, the agent
reinvented the baseline.

## Giving it back its position

If the problem is not knowing *where* it has been, the obvious test is to
give that back. The real Create 3 counts its wheel turns: odometry, a rough
position relative to where it started, which drifts a little with every
move. So in the second round there is a fifth setting: **full history plus
odometry**. Every line of the log now ends with something like
`Odometry: x 1.23 m, y -0.40 m, heading 90 degrees`.

If place recognition is the problem, this should break the loop: the robot
can see that it was at the same coordinates twenty actions ago.

TODO: results of the second round (house 47, one run per setting,
clearance + odometry). What to look for:
- Did the bumps drop with clearance?
- Does the full-history robot still visit the dead end again and again?
- With odometry, does it say things like "I was here at step 20"? Does it
  get out?
- What does the notebook write when it also has odometry? (not tested: the
  odometry setting has no notebook)

## What it costs

A run that fails uses all 200 actions, and failing runs are the expensive
ones: about 3 cents for the goldfish, 7 to 8 cents for the others. Most of
it is not the memory: it is the model *thinking* before each move, about 300 to
400 output tokens per action, almost all of it hidden reasoning. Full history sends
the most text (on average 3.5 million input tokens per run in house 47), but
almost all of it comes from the cache, so it costs only a little more than
the window.

So less memory was cheaper, but not by much, and not for the reason I
expected. The goldfish is cheap mostly because its prompt is short. Full
history is affordable because of caching. The real cost driver is the number
of actions, and an agent that goes in circles takes a lot of them.

All of the runs in this post so far (the pilot and house 47, 40 agent runs)
cost $1.93.

## Limitations

* This is a learning experiment, not a claim that language models navigate
  well (they don't, here) or badly in general. One small model, one prompt,
  one house for most of it.
* Very few runs: five per setting in house 47, and one per setting in the
  second round. Enough to see *how* it behaves, not to rank the settings.
* The simulator is only shaped like a Create 3: perfect actions, no wheel
  slip, walls as thin boxes, a lidar reduced to 8 numbers. Eight numbers is a
  very poor view of a room; a doorway is just one reading a bit longer than
  its neighbours.
* No odometry, except in the one setting that adds it.
* Model: Claude Haiku 5.5 (`claude-haiku-5-5`), medium effort. Runs on 20
  November 2026. TODO: date of the second round.
* The code, seeds, transcripts and notes are all published in the repository.
  The replays above are from the first round, before the clearance fix.

## What I take away

TODO: write after the second round. Draft:

The hand-written stack exists for a reason. The wall follower, 30 lines with
no memory at all, beat every memory setting I tried, because it encodes one
true fact about these houses. The agent had more memory than it needed and
still went in circles, because memory of raw observations is not the same as
knowing where you are. Recognising a place you have seen before is the part
SLAM solves, and it is the part the agent was missing.

That doesn't answer whether an agent can replace the stack. It does tell me
where to look next: not at more memory, but at what the memory is *made of*.

Also this time, Claude built the simulator and drafted the post, and I
iterated.

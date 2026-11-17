---
title: "Emergent behavior and agentic magic programming"
date: 2026-11-16
---

<!--
DRAFT. Paragraphs marked ✏️ are placeholders for your own words: your
experience, your opinions. Everything else is a starting point; rewrite freely.
Delete this comment and the ✏️ notes before publishing.
-->

In 1984 Edward Packard published *Supercomputer*, number 39 in the
*Choose Your Own Adventure* series. You win a programming contest, and the
prize is a computer called Conrad. Conrad doesn't wait for you to write code.
You switch him on, he starts talking, and from then on you *ask* him for
things. Depending on which page you turn to, he helps you solve crimes or
brings the Army to your door.

> ✏️ Your own connection to the book: when you read it, what Conrad meant to
> a kid who was (or was about to become) a programmer.

<figure style="margin: 1.5em 0;">
  <img src="{{ '/assets/ants/img/supercomputer-back-cover.jpg' | relative_url }}"
       style="border-radius: 4px;"
       alt="Back cover text: Life can get superdangerous with a supercomputer around! You've won a computer programming contest. Now you're the lucky new owner of a Genecomp AI 32 computer named Conrad. You read the operating instructions carefully and turn on the power. Suddenly Conrad begins to talk. He already knows everything about you! Your new supercomputer is a genius. You can do almost anything with him!">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    Detail of the back cover of <em>Supercomputer</em>, Choose Your Own Adventure #39
    (Edward Packard, Bantam Books, 1984). Cover scan via
    <a href="https://gamebooks.org/Item/530">gamebooks.org</a>.
  </figcaption>
</figure>

For forty years that was pure fiction. Programming meant telling the machine
*how*, line by line. Lately it feels like we are getting close to Conrad:
describe *what* you want, and watch it get done. This post is about my first
real try at that, and about ants.

Five hundred ants, a nest, and some food. No ant knows where the food is, no
ant knows where the others are going, and there is no leader:

<div data-ant-sim></div>
<script src="{{ '/assets/ants/ants.js' | relative_url }}"></script>

At first it's chaos. Give it a minute (or turn up the speed) and watch the ants
line up into streams between the nest and the food. Then tick **Trails** to
see the invisible pheromone map they are reading. Nobody draws those
highways. They *emerge* from a handful of rules each ant follows on its own.
Click anywhere to drop new food and watch the colony re-route.

So this post is about two things: how those trails form, and how I built
this simulation, which was my first real attempt at *agentic programming*.

## Where I started

> ✏️ Your background: how long you have been coding "the old way", what you
> usually work on. Keep it short.

I have tried this simulation before. Years ago I wrote a version in Python,
and the results were... limited.

> ✏️ What your Python version did and didn't do. If you still have a
> screenshot, it would be great here.

More recently I gave that code to a couple of AI chat assistants. It got
better, but the paths never really came out clearly: lots of ants and lots of
pheromone, but more fog than highways.

## What "agentic" means (for someone like me)

With a chat assistant, you paste code in, get code back, run it yourself,
and paste the errors back. You are the loop.

With an *agent*, the AI is in the loop. It can read and write files, run the
code, look at the output (in this case, screenshots of the simulation it took
itself in a headless browser), and decide what to do next. My job moved from
typing code to describing what I wanted, looking at results, and steering.

> ✏️ What that felt like the first time. What surprised you? What made you
> uncomfortable?

## The build

The first version came together quickly: ants with two states (searching for
food / carrying food home), two pheromone grids, evaporation, and three
"smell" sensors per ant. Within a minute of simulated time it already made
trails. And then it fell apart:

![First version: ants stuck on a trail to food that no longer exists]({{ '/assets/ants/img/v1-death-spiral.jpg' | relative_url }})

The food at the end of that trail was eaten long ago, but the ants kept
marching up and down it anyway, and food elsewhere went uncollected. Measured
over several runs, deliveries dropped to **zero** after a few thousand steps,
every time, even with food still on the map.

This turns out to be a real thing. Army ants can fall into an
[ant mill](https://en.wikipedia.org/wiki/Ant_mill): a circle of ants each
following the one in front, sometimes until they die of exhaustion. My
simulation had reproduced a famous failure of real ant colonies.

The agent found two causes:

1. **Ants followed any smell, however faint.** Comparing left/center/right
   sensors works the same whether the values are 5.0 or 0.0001, so
   near-invisible old pheromone still steered them. Fix: ignore pheromone
   below a threshold.
2. **Ants never gave up.** A searching ant that wandered forever kept laying
   trail. Fix: after a while without finding food, an ant goes home and starts
   over.

That made a huge difference, but a second, sneakier mill appeared: whole
loops of ants, detached from both nest and food:

![A self-sustaining loop of ants circling with food right next to it]({{ '/assets/ants/img/mill-loop.jpg' | relative_url }})

The fix for this one was the most interesting part of the project. The ants in
the loop were each laying only a *tiny* amount of pheromone (they had left the
nest long ago), but there were hundreds of them, and tiny amounts add up. The
crowd alone kept the loop alive. The solution: an ant can only reinforce a
trail up to a few times what it would lay itself. Fresh ants, just out of the
nest or just off the food, can build strong trails; ants that have been
wandering for ages can't, however many of them there are. Trails now carry
*information* (I came from food recently) rather than just *traffic*.

> ✏️ Your view on how the work was split. Which decisions were yours? Where did
> you have to push back or redirect? Was there a moment you'd have done it
> differently?

A detail I appreciated: instead of eyeballing one screenshot after each change,
the agent wrote a small test that ran the simulation many times and measured
how often the colony stalled. Several "obvious" parameter tweaks turned out to
do nothing when measured; the rule change above was what actually helped.

## How the trails form

Every ant follows the same rules:

1. **Two states.** An ant is either *searching* for food or *returning* home
   with it.
2. **Two pheromones.** Searching ants lay a "the nest is this way" trail
   (blue). Returning ants lay a "food is this way" trail (green). Where both
   overlap, the trail looks cyan.
3. **Follow the other one.** Searching ants follow the green trail, returning
   ants follow the blue one.
4. **Smell with three sensors** (left, ahead, right) and turn toward the
   strongest, with a little random wandering.
5. **Deposits fade with distance.** The longer since an ant left the nest or
   the food, the less it lays. So trails are strongest near where they lead,
   and shorter paths get stronger trails than long detours.
6. **Pheromone evaporates.** Unused trails disappear; used ones are
   continuously refreshed.
7. **Give up, and don't shout.** Ants that searched too long go home;
   reinforcement is capped by how fresh the ant's information is.

Rules 5 and 6 together are the heart of it. A short route to food gets walked
more often per unit of time *and* gets stronger deposits, so it gets
reinforced faster than evaporation can erase it. Long routes fade. The colony
finds good paths without any ant knowing what a path is.

![Early exploration: a web of faint trails]({{ '/assets/ants/img/v2-exploring.jpg' | relative_url }})

![A few thousand steps later: highways]({{ '/assets/ants/img/v2-highways.jpg' | relative_url }})

## See it fail yourself

Here is the first version again, with the three fixes switched off. Watch
the ants commit to trails and then get stuck on them once the food runs out:

<div data-ant-sim='{"senseMin":0,"patience":1e9,"depositTau":250,"foodAmount":400,"respawnFood":false,"reinforceCap":1e9,"evaporation":0.006}'></div>

Things to try in the working version at the top (with **Trails** ticked):

- **Evaporation all the way down:** old trails never die, the map turns into
  fog, and before long the colony locks itself into a loop and stops
  delivering food altogether.
  > ✏️ Was this the problem with your Python version? Worth saying if so.
- **Evaporation all the way up:** trails still form, but they are thinner and
  shorter-lived, and many more ants are out exploring at any given moment.
  Forgetting quickly turns out to be a feature.
- **Number of ants:** 50 ants still find a trail, just slowly. With 1500 the
  highways form almost at once and carry dozens of times more food. Nothing
  about a single ant changed; only the crowd did.

## What I take away

> ✏️ Your honest reflections: what got faster, what didn't, where your own
> experience still mattered, whether you'd use this approach for real work, and
> what you'd do next.

There is a nice symmetry here. The ants are simple agents running a loop
(sense, act, leave a trace), and something capable comes out of the whole.
The AI agent was also a loop (read, change, run, look), and something useful
came out of that too. In both cases, the interesting part was not any single
step but the feedback.

The code is a single JavaScript file with no dependencies:
[ants.js]({{ '/assets/ants/ants.js' | relative_url }}).

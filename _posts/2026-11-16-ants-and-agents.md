---
title: "Emergent behavior and agentic magic programming"
date: 2026-11-16
---

In 1984 Edward Packard published *Supercomputer*, number 39 in the
*Choose Your Own Adventure* series. You win a programming contest, and the
prize is a computer called Conrad. Conrad doesn't wait for you to write code.
You switch him on, he starts talking, and from then on you *ask* him for
things. Depending on which page you turn to, he helps you solve crimes or
brings the Army to your door.

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

As a kid, this book caught my full attention. I still share that wonder: I
have always liked computers for their magic capabilities. These days, that
magic is very tangible. With AI you can literally ask for whatever you want,
and it gets built. I feel we could even win a million dollars, like in the
book, if we know how to use it properly.

Programming used to mean telling the machine *how*, line by line. More and
more, we can just tell it *what*. This post is about my first real try at
that, and about ants.

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

I have coded for more than 20 years, and AI assisted coding is a recent novelty I am starting to grasp.

I have tried this ant simulation before. Years ago I wrote a version in Python,
and the results were... limited.

I put up a simple python script that updated on every turn, trying to simulate the emergent behavior observed on ants for fun - I did not reach out to papers or any study. After some time I forgot about it as the results were not as expected. This took me some time - maybe a couple of days.

<figure style="margin: 1.5em 0; text-align: center;">
  <img src="{{ '/assets/ants/img/python-original.gif' | relative_url }}"
       width="320" height="320" style="border-radius: 4px; display: block; margin: 0 auto;"
       alt="My old Python simulation: a white field of food with black specks where ants have eaten, and a grey band of queens across the middle. No paths form.">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    My first Python version, running again today. White is food, black is where
    ants have eaten, the grey band is the queens.
    (<a href="{{ '/assets/ants/python/ants_original_py2.py' | relative_url }}">original code</a>,
    <a href="{{ '/assets/ants/python/ants.py' | relative_url }}">Python 3 port</a>)
  </figcaption>
</figure>

Looking at it again now, the reason is clear: in this first version my ants
never left anything behind for each other. Each one wandered on its own, and
nothing told the next ant where food had been found or where home was. Without
a shared trail, there was nothing for a path to form from.

In 2016 I came back to it with a second attempt, `antsCamino` (*camino* is
Spanish for path). This time the ants did leave a mark: every step added to a
shared "paths" map, the map slowly faded, and each ant steered toward the
most-walked cell next to it. And paths did form!

<figure style="margin: 1.5em 0; text-align: center;">
  <img src="{{ '/assets/ants/img/python-2016-camino.gif' | relative_url }}"
       width="320" height="320" style="border-radius: 4px; display: block; margin: 0 auto;"
       alt="My 2016 Python simulation: bright straight lines form on a black background, but they do not connect the grey food square at the bottom left with the white queen squares at the top right.">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    The 2016 version. Bright lines are the most-walked cells, the grey square
    (bottom left) is the food, the white squares (top right) are the queens.
    (<a href="{{ '/assets/ants/python/ants_camino_2016_py2.py' | relative_url }}">original code</a>,
    <a href="{{ '/assets/ants/python/ants_camino.py' | relative_url }}">Python 3 port</a>)
  </figcaption>
</figure>

But look at where they go: nowhere in particular. The lines connect neither
the food nor the queens. Running it again today, in two runs of 1,000 frames,
about 85% of the ants were locked onto those lines by frame 300, eating
stopped, and not a single piece of food reached a queen. Every step counted
the same, so a busy cell got busier whether or not it led anywhere. The map
recorded *traffic*, not *information*. Keep that in mind: the AI agent ran
into the very same trap later in this story.

More recently I gave that code to a couple of AI chat assistants (ChatGPT
first, then Gemini), and
iterated: run it, look at it, paste back what was wrong, ask for changes. I
did this a couple of times. Looking back, *I* was the agent. It got better,
but the result was not as clean. Faster results, but still not as expected.

Running the versions I kept shows how it went. I gave my first script to
ChatGPT, and in what came back, the ants
leave the nest (blue square) and huddle in a clump right next to it, far from
the food (green). In 2,000 steps they brought home between 1 and 3 pieces of
food.

<figure style="margin: 1.5em 0; text-align: center;">
  <img src="{{ '/assets/ants/img/chatbot-early.gif' | relative_url }}"
       width="280" height="280" style="border-radius: 4px; display: block; margin: 0 auto; image-rendering: pixelated;"
       alt="ChatGPT's version of my first script: white ants clumped in a magenta haze next to the blue nest, while the green food square sits untouched.">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    ChatGPT's version of my first script: the clump.
    (<a href="{{ '/assets/ants/python/chatbot_ants_ai.py' | relative_url }}">code</a>)
  </figcaption>
</figure>

The last one, from Gemini, says "ANTI-CLUMPING" in its own comments, so the
clump was clearly what I kept complaining about. Its ants do spread out and
bring food home (yellow ants are carrying food). But look for the paths:
there are almost none.

<figure style="margin: 1.5em 0; text-align: center;">
  <img src="{{ '/assets/ants/img/chatbot-gemini.gif' | relative_url }}"
       width="280" height="280" style="border-radius: 4px; display: block; margin: 0 auto; image-rendering: pixelated;"
       alt="The final Gemini version: ants scattered all over the map between the blue nest and two green food squares, with only faint red traces and no visible trails.">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    The final version, from Gemini: ants everywhere, trails nowhere.
    (<a href="{{ '/assets/ants/python/chatbot_gemini_final.py' | relative_url }}">code</a>)
  </figcaption>
</figure>

The chatbot was very sure of itself. Its explanation of the fix ended like this:

> **Higher Decay (`0.05`):** Trails disappear much faster. If ants get stuck
> in a loop, they stop reinforcing the correct path. The loop's pheromone
> decays rapidly, the trail breaks, and the ants are forced to wander randomly
> again, breaking the circle.
>
> **Static Compass (`dist_score`):** Ants carrying food now have a permanent
> "magnetic pull" towards the center. [...] the compass gently nudges them
> toward the nest every step.

So I tested it. With the pheromones switched off completely, the colony
delivers the same amount of food as with them on: about 90 pieces in 3,000
steps, averaged over three runs. The trails are decoration. The ants find
food by wandering, and a built-in compass that points to the nest from
anywhere on the map helps them get back (without it, deliveries drop by
about a quarter). The colony works, but nothing *emerges*. (A small extra:
the progress counter says "out of 500", but the map actually holds 50,000
units of food.)

Read the explanation again with that in mind. Every sentence sounds reasonable,
and the clump really was gone. But it was gone because the trails now vanish
before anyone can follow them: the fix worked by switching off the very
mechanism the paths were supposed to come from. The "gentle nudge" turned out
to be doing most of the work. Nobody measured any of it. The chatbot could
not run the code, and I, the human in the loop, only looked at the animation
and moved on.

## What "agentic" means (for someone like me)

With a chat assistant, you paste code in, get code back, run it yourself,
and paste the errors back. You are the loop.

With an *agent*, the AI is in the loop. It can read and write files, run the
code, *look at the output* (in this case, screenshots of the simulation it took
itself in a headless browser), and decide what to do next. This is the magic I am talking about.
My job moved from typing code to describing what I wanted, looking at results, and steering - I feel I am in the book asking Conrad things and complaining when I get "too rich".

## The build

Conrad/Claude did almost everything from one short request. I am not claiming I used every concept on agentic programming (MCP, RAG, etc. this is being used anyway but for this project I do not need to get into this...). I just paid for a monthly subscription and asked for something!

I saw the system working autonomously for approx. 30 minutes. The process Claude did was actually very similar to mine, but the agent kept going and succeeded in the end.

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
*information* (I came from food recently) rather than just *traffic*: exactly
what my 2016 version was missing.

A detail I appreciated: instead of eyeballing one screenshot after each change,
the agent wrote a small test that ran the simulation many times and measured
how often the colony stalled. Several "obvious" parameter tweaks turned out to
do nothing when measured; the rule change above was what actually helped.
That is the real difference from my chatbot round. There, a confident
explanation was the end of the story. Here, every explanation was a claim to be
measured, and the agent did the measuring itself.

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
- **Evaporation all the way up:** trails still form, but they are thinner and
  shorter-lived, and many more ants are out exploring at any given moment.
  Forgetting quickly turns out to be a feature.
- **Number of ants:** 50 ants still find a trail, just slowly. With 1500 the
  highways form almost at once and carry dozens of times more food. Nothing
  about a single ant changed; only the crowd did.

## What I take away

I love this. This is exactly what a computer should be about and what I think was the original idea when people start building these machines.

The agent (Claude) decided almost everything from one short request and succeeded in 30 minutes. It took me a couple of days just to fail and several (shy) attempts through the years. This changes everything. We have much more power to experiment with ideas. I would never have had enough time to do this myself.
I wonder how far can this go. I may be limited by my own imagination here.

There is a nice symmetry/irony here. The ants are simple agents running a loop
(sense, act, leave a trace), and something capable comes out of the whole.
The AI agent was also a loop (read, change, run, look), and something useful
came out of that too. In both cases, the interesting part was not any single
step but the feedback.

The code is a single JavaScript file with no dependencies:
[ants.js]({{ '/assets/ants/ants.js' | relative_url }}).
This code could be improved but that is not the main topic of this post.

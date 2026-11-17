---
title: "Emergent behavior and agentic magic programming"
date: 2026-11-16
---

In 1984 Edward Packard published *Supercomputer*, number 39 in the
*Choose Your Own Adventure* series. You win a programming contest, and the
prize is a computer called Conrad. Conrad doesn't wait for you to write code.
You switch it on, it starts talking, and from then on you *ask* for
things. Depending on which page you turn to, Conrad helps you solve crimes or
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
magic is very tangible. With recent AI (I now realize the computer was a Genecomp *AI* 32) you can literally ask for whatever you want,
and it gets built. I feel we could even win a million dollars, as in the
book, if we know how to use it properly.

Programming used to mean telling the machine *how*, line by line. Any deviation from expectations and the unforgiving rigidity of the process sent you to failure. More and
more, we can just tell it *what*. This post is about my first real try at
that, and about ant behavior. Why? Ants also have magic properties.

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

## Initial attempts

I have coded for more than 20 years, and AI-assisted coding is a recent novelty I am starting to grasp.
I have tried this ant simulation before. Years ago I wrote a version in Python,
and the results were... limited.

I did not want to spend tons of hours just setting everything up. I only wanted to see the magic, the behavior emerge. So I put up a simple Python script that updated on every turn, trying to simulate the emergent behavior observed on ants for fun - I did not reach out to papers or any study either. After some time I forgot about it as the results were not as expected. This took me some time - maybe a couple of days.

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

Looking at it again now, the reason for failure seems clear: in this first version my ants
never left anything behind for each other. Each one wandered on its own, and
nothing told the next ant where food had been found or where home was. Without
a shared trail, there was nothing for a path to form from.

In 2016 I came back to it with a second attempt. Add a trail.
This time the ants did leave a mark: every step added to a
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

But they go nowhere in particular. The lines connect neither
the food nor the queens. Running it again today, in two runs of 1,000 frames,
about 85% of the ants were locked onto those lines by frame 300, eating
stopped, and not a single piece of food reached a queen. Every step counted
the same, so a busy cell got busier whether or not it led anywhere. The map
recorded *traffic*, not *information*. Keep that in mind: the AI agent ran
into the very same trap later in this story.

### AI to the rescue

Last year, I started to be increasingly aware that AI got much better at coding, so I thought it could help me and maybe my "dream" would come true.
I gave my code to a couple of AI chat assistants (ChatGPT
first, then Gemini), and
iterated: run it, look at it, paste back what was wrong, ask for changes. I
did this a couple of times. Looking back, *I* was an agent. Results got better,
but the emergence was not there. 

Running the versions I kept shows how it went. I gave my first script to
ChatGPT, and in what came back, the ants
leave the nest (blue square) and huddle in a clump right next to it, far from
the food (green). In 2,000 steps they brought home between 1 and 3 pieces of
food. How frustrating!!

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
and moved on. I got increasingly frustrated and I dropped it for another year. Not even the AI could help me!

## Agentic AI

With a chat assistant, you paste code in, get code back, run it yourself,
and paste the errors back. You are the loop.

With an *agent*, the AI is in the loop. It can read and write files, run the
code, *look at the output* (in this case, screenshots of the simulation it took
itself in a headless browser), and decide what to do next. This is the magic I am talking about.
My job moved from having to learn boilerplate technologies to visualize something to describing what I wanted, looking at results, and steering - I feel I am in the book asking Conrad things and complaining when I get "too rich". I moved the main frustration to the agent (sorry!).

## It worked

My approximate prompt, I did not give Claude (Opus 5.5 medium) the earlier versions so it started from scratch!

> **I want to do a visualization of emergent behavior for "ants" - maybe we discussed this already - as they take "food" from a source through a "nest". I did this in python in the past - with limited results. I also tried giving my code to gemini and maybe you and it was working better, however the paths were not so clear. I want in the end to see paths forming between the foods and nests.**

In the next prompt I just confirmed a javascript/html version was ok as I wanted to put this as part of the blog.

Conrad/Claude did almost everything from this short request. I am not claiming I used every concept on agentic programming (MCP and friends: Claude uses some of this under the hood, but for this project I did not need to get into it myself). I just paid for a monthly subscription and asked for something!

I saw the system working autonomously for approx. 30 minutes. The process Claude did was actually very similar to mine, but the agent kept going and succeeded in the end.

Claude also explained everything and how it tried several things.

### Claude Details

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
following the one in front, sometimes until they die of exhaustion. The
simulation had reproduced a famous failure of real ant colonies.

Claude found two causes: ants followed any smell, however faint, and they
never gave up searching. The fixes were to ignore very weak pheromone and to
send ants home after a while without finding food. That made a huge
difference, but a second, sneakier mill appeared: whole loops of ants,
detached from both nest and food:

![A self-sustaining loop of ants circling with food right next to it]({{ '/assets/ants/img/mill-loop.jpg' | relative_url }})

The fix for this one was the most interesting part of the project, Claude comments. The ants in
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

Finally, after a decade (!), the trails emerge. The ideas behind them are not
new: two pheromones and "smell sensors" are well known from research on ant
colony algorithms going back to the early 1990s (I never looked at the
literature, remember?). What the agent did was make them actually work here.

How much searching did that take? Less than I expected: about 20
configurations in around 150 simulation runs, and three rule changes that
made the difference (ignore very faint smells, give up after a while, and cap
how much a single ant can reinforce a trail).

The heart of it is two simple rules. Ants lay less pheromone the longer it has
been since they left the nest or the food, and pheromone evaporates. A short
route to food gets walked more often per unit of time *and* gets stronger
deposits, so it gets reinforced faster than evaporation can erase it. Long
routes fade. The colony finds good paths without any ant knowing what a path
is. (The full list of rules is at the end of the post.)

![Early exploration: a web of faint trails]({{ '/assets/ants/img/v2-exploring.jpg' | relative_url }})

![A few thousand steps later: highways]({{ '/assets/ants/img/v2-highways.jpg' | relative_url }})

## What I take away

I love this. This is exactly what a computer should be about and what I think was the original idea when people started building these machines.
You can argue I did not succeed in getting the right rules myself and that I missed all that fun. I argue I had a lot of fun seeing the magic of the agent discovering everything, unblocking my previous issues and frustrations, and also enjoying the result of seeing the ant trails emergence I craved.

The agent (Claude) decided almost everything from one short request and succeeded in 30 minutes. It took me a couple of days just to fail and several (shy) attempts through the years. This changes everything. We have much more power to experiment with ideas and have fun with that, even if we are not the executors of endless trials and errors. I would never have had enough time to do this myself, and now I can move on and think about my next "crazy" idea: in the past I would have thought it was going to be so complex that it was not worth the time, now I know I can see agents experimenting with them. Magic here, there, everywhere.

There is a nice symmetry/irony here. The ants are also simple agents running a loop
(sense, act, leave a trace), and something capable comes out of the whole.
The AI agent was also a loop (read, change, run, look), and something useful
came out of that too. In both cases, the interesting part was not any single
step but the feedback.

The code is a single JavaScript file with no dependencies:
[ants.js]({{ '/assets/ants/ants.js' | relative_url }}).
This code could be improved but that is not the main topic of this post (I could ask Claude to improve it).

Also, finally, Claude did the first draft of the post and I just iterated. Fantastic.

Next: how does an agent like this actually work inside? I'm going to try
building a tiny one.

"Claude, please, I want a million dollars now".

## Appendix: the rules, and things to try

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

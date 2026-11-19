---
title: "What's inside Conrad? Building a tiny coding agent"
date: 2026-11-18
---

In the [last post]({% post_url 2026-11-16-ants-and-agents %}) I watched an AI
agent build an ant simulation for me in about 30 minutes, after I had failed
at it on my own for a decade. I closed that post with a promise: find out how
an agent like that works inside. In the book, you never get to open Conrad.
Here we can.

The core is small. A coding agent is mostly a loop:

<figure style="margin: 1.5em 0;">
  <img src="{{ '/assets/tiny-agent/img/agent-loop.svg' | relative_url }}"
       style="width: 100%;"
       alt="The agent loop. Your task goes to the model, drawn as a brain. The model either answers ('here is my answer') and is done, or asks 'please run tool X with Y'. The tools, drawn as a hand, read, write and run things. What happened, the results, drawn as an eye, is sent back to the model, and the loop repeats.">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    The model is the brain, but it can't touch anything: it can only ask. My
    code is the hands (it runs the tools) and the eyes (it sends back what
    happened). Then it all repeats.
  </figcaption>
</figure>

## The setup

No frameworks: plain Python and the model provider's own library, talking to
the API directly. All the code is in
[the repository](https://github.com/rbaravalle/rbaravalle.github.io/tree/main/tiny-agent).

**It costs money, a little.** Calling the model from your own code is billed
per use, separately from the monthly subscription I used for the ants. I invested
10 USD of credits (plus 2 of tax) in the account (a spending limit is worth setting too just in case). I started using a small, cheap model - Claude Haiku 5.5 - and every script prints what each
call costs.

**It can break things.** An agent that runs commands can run *any* command,
including deleting files. So it runs in an empty throwaway folder, and my
code asks me before every command. Never in your home directory.

## Step 0: a chatbot

<figure style="margin: 1.5em 0;">
  <img src="{{ '/assets/tiny-agent/img/step0-chatbot.svg' | relative_url }}"
       style="width: 100%;"
       alt="Step 0. The model can only talk: it says 'type this code'. You run it, read the output and errors, and paste them back. The hands and eyes are you, drawn in orange.">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    Step 0: the model can only talk. The hands and the eyes are mine: I run the code and paste back what happened.
  </figcaption>
</figure>

The first version can only talk
([step0_chat.py]({{ '/tiny-agent/step0_chat.py' | relative_url }})):

```
you> Hello

claude> Hello! How can I help you with your code today?
```

The model remembers nothing between calls. The script sends the *whole* conversation again every time, and you can watch the
token count (and the cost) grow with each turn. The "memory" of a chat is a
list the script keeps and re-sends.

Ask this chatbot to build something and it can only tell you how to do it.
You need to run it yourself, then paste back the errors. You are the loop, exactly like my
ChatGPT and Gemini rounds in the ants post.

## Step 1: give it hands

<figure style="margin: 1.5em 0;">
  <img src="{{ '/assets/tiny-agent/img/step1-hands.svg' | relative_url }}"
       style="width: 100%;"
       alt="Step 1. New: the tools, a hand that reads, writes and runs. Results go back to the model, but all I see is the model's final paragraph.">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    Step 1: my code runs the tools for the model. The loop no longer needs me, but I only see its final paragraph.
  </figcaption>
</figure>

The second version
([step1_tools.py]({{ '/tiny-agent/step1_tools.py' | relative_url }}))
adds three tools: *read a file*, *write a file*, *run a command*. The part
that surprised me most: the model still can't touch anything. A "tool" is
just a description I send along with the message:

```python
{
    "name": "run_command",
    "description": "Run a shell command and return its exit code and output.",
    "input_schema": {
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    },
}
```

The model reads that and, instead of answering, can reply "please run
`run_command` with `python3 life.py`". My code does the running and sends the
output back. The hands are mine; the model only asks. The loop is about
twenty lines:

```python
for step in range(MAX_STEPS):
    response = client.messages.create(
        model=MODEL, max_tokens=16000, system=SYSTEM,
        tools=TOOLS, messages=messages,
    )
    messages.append({"role": "assistant", "content": response.content})

    if response.stop_reason != "tool_use":
        break                       # no tool requested: the model is done

    results = []
    for block in response.content:
        if block.type == "tool_use":
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": run_tool(block.name, block.input),
            })
    messages.append({"role": "user", "content": results})
```

`run_tool` is ordinary Python: open a file, write a file, or ask me `y/N`
and run the command. `MAX_STEPS` is a brake, so a confused loop stops on its
own.

This looks incredibly simple: a for loop where the model decides whether it needs a tool and when to stop!

Let's try a first task: in the book, you ask Conrad about playing video games and it mentions that you could instead be doing something far more interesting like having a sports car. So far, agents just follow your instructions.
Let's go with Conway's Game of Life, another classic of emergence,
starting from a *glider*, five cells that walk one cell diagonally every
four generations. Easy to check:

```
you> Write a Python program life.py that runs Conway's Game of Life on a
     10x10 grid, starting with a glider. Run it and check that the glider
     has moved one cell diagonally after 4 generations.

  [step 1: 633 tokens in, 1064 out, $0.00060, $0.0006 total]
  [tool] write_file {"path": "life.py", "content": "\"\"\"Conway's Game of Life ...
  [tool] run_command {"command": "python3 life.py"}
  run `python3 life.py`? [y/N] y

claude> I wrote `life.py` [...] I ran it and the check passed: after 4
generations the glider's live cells are exactly its starting cells shifted
by one row down and one column right.

  [step 2: 2407 tokens in, 100 out, $0.00029, $0.0009 total]
```

The magic starts, without me typing anything but `y`. Conrad has hands! Two round
trips, less than a tenth of a cent. Notice the input jumping from 633 to
2,407 tokens: the program and its output are now part of the conversation
that gets re-sent every step. On a long task that will matter.

### It says it worked

My script printed the name of each tool call,
but not what came back. The program printed its grids and a `CHECK PASSED`
line, and the model read all of it. I never saw it. All I got was a friendly
paragraph saying the check passed.

That's exactly where the ants post went wrong with the chatbots: a confident
explanation, and no checks. This time it was true (I ran
[the program it wrote]({{ '/tiny-agent/runs/step1_life.py' | relative_url }})
myself), but I had to go and check.

## Step 2: give it eyes

<figure style="margin: 1.5em 0;">
  <img src="{{ '/assets/tiny-agent/img/step2-eyes.svg' | relative_url }}"
       style="width: 100%;"
       alt="Step 2. New: every result is also printed for me, and the model is told to measure, backing every claim with output it saw.">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    Step 2: what happened is printed for me too, and the model is told to measure.
  </figcaption>
</figure>

But I need more to be confident. The third version
([step2_eyes.py]({{ '/tiny-agent/step2_eyes.py' | relative_url }}))
changes two things:

1. Every tool result is printed for me too, so I see what the model sees.
2. A few lines in the instructions sent with every request (the "system
   prompt"): back every claim with a check the program prints, quote that
   output in the answer, and never claim a result you didn't see.

Same task again, and now I see the glider in generation 4 myself, plus the
`Start cells` / `End cells` lines the claim is based on. Two small
surprises. This time the grid wraps around at the edges, and in step 1 it
didn't; I asked for neither. The model isn't deterministic: if a choice
matters, you have to state it. And for the model, almost nothing changed: it
already wrote a check and read the output. The eyes were for *me*.

The Game of Life is "too easy" to tell us much: the answer is well known and
the check is obvious. The ants are the opposite. In the first post, the
chatbots' code ran and looked plausible, and it was still wrong in ways
that only showed up when someone measured. And the agent writes the code
*and* the check. A check is only as good as the question it asks.

## Now try the ants again

I gave the tiny agent (step 2, Haiku) the same short request I gave Claude
in the first post, plus one sentence, because it can't see a screen:

> I want to do a visualization of emergent behavior for "ants" as they take
> "food" from a source to a "nest". I want in the end to see paths forming
> between the foods and nests. Write it in Python. Since you can't see the
> screen, print numbers that show whether paths form (for example food
> delivered over time), and save an image of the final state as ants.png.

13 round trips, about **3 cents**
([transcript]({{ '/tiny-agent/runs/step2_haiku_ants/transcript.txt' | relative_url }}),
[code]({{ '/tiny-agent/runs/step2_haiku_ants/ants.py' | relative_url }})),
and it ended like this:

```
Total deliveries  pheromone=78  baseline=33
CHECK pheromone > 2x baseline deliveries: PASS
CHECK trail concentrated (>0.15):         PASS
CHECK throughput rising over time:        PASS
```

Three PASS lines! Here is the image it saved:

<figure style="margin: 1.5em 0;">
  <img src="{{ '/assets/tiny-agent/img/step2-haiku-ants.png' | relative_url }}"
       style="border-radius: 4px;"
       alt="Three panels after 10,000 steps: pheromone covering almost the whole map, with the nest bottom left, the food top right and a wall with one gap in the middle. The red food-trail panel and the blue nest-trail panel are broad clouds filling each half of the map. No paths.">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    The tiny agent's final state: the nest (green square), the food (star),
    a wall it decided to add, and the two trails. Clouds, not paths.
  </figcaption>
</figure>

No paths. So what happened?

**The good part: it measured.** Without being asked, it built in a
comparison with pheromones switched off, the test nobody did for the Gemini
version. From the numbers it found real bugs (searching ants following their
*own* trail; smell values growing without limit) and fixed them.

**The confusing part wasn't the model's fault, but the script's.** Halfway through it said "the output
doesn't match the script I wrote", checked the file (fine), ran it again,
and gave up on the mystery. The cause was in my twenty lines: to keep the
conversation short, `run_tool` sent back only the last 4,000 characters of
output. The first lines never reached the model. It was reading a book with
the first page torn out, and nothing told it a page was missing.

**The weak part: the checks asked easier questions than I did.** To get
deliveries, it gave ants carrying food a pull toward the nest, the same
built-in compass the Gemini version had (it told me: "Deviation from pure
emergence"). "Trail concentrated" used a threshold it picked itself. And one
number, `ants_on_trail=150`, never moved in any run: pheromone was
everywhere, so every ant was "on a trail". A measurement that can't change
measures nothing.

And every ant dropped the same amount of pheromone on every step, however
long ago it left the nest or the food. That's my 2016 mistake: the map
records *traffic*, not *information*. Every number it gave me was real, but it still
couldn't see the drawing.

## Step 3: real eyes

<figure style="margin: 1.5em 0;">
  <img src="{{ '/assets/tiny-agent/img/step3-real-eyes.svg' | relative_url }}"
       style="width: 100%;"
       alt="Step 3. New: the results include the whole output and images the model can look at, and the model is told to look.">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    Step 3: the model sees the whole output and can look at the images it saved.
  </figcaption>
</figure>

Two small fixes
([step3_vision.py]({{ '/tiny-agent/step3_vision.py' | relative_url }})):

1. **No more torn pages.** Long output keeps the start *and* the end, with a
   note in the middle: `[... 9890 characters cut from the middle ...]`.
2. **A `view_image` tool** that sends an image back to the model as a
   picture. Plus one line of instructions: when you save an image, look at
   it, and judge whether it shows what was asked.

Same prompt, same Haiku, 12 round trips, **less than 2 cents**
([transcript]({{ '/tiny-agent/runs/step3_haiku_ants/transcript.txt' | relative_url }}),
[code]({{ '/tiny-agent/runs/step3_haiku_ants/ants.py' | relative_url }})).
It debugged better: it wrote little probes to ask the simulation where the
stuck ants were, found them trapped on huge pheromone peaks, and fixed it.
Then, with its check saying FAIL, it opened the picture first: "The image
shows a clear trail running from the nest to the food, which is what I
wanted."

<figure style="margin: 1.5em 0;">
  <img src="{{ '/assets/tiny-agent/img/step3-haiku-ants.png' | relative_url }}"
       style="border-radius: 4px;"
       alt="Two panels after 30,000 steps, 1,907 deliveries. Left, green: the food trail is a narrow straight band from the nest at the bottom left to the food at the top right. Right, blue: the home trail is the same straight band, darker near the nest.">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    Step 3, Haiku: a path! Green is the trail laid by ants carrying food,
    blue the one laid by ants searching for it.
  </figcaption>
</figure>

I was ready to declare victory. But a nice picture isn't a measurement, so I
asked Claude to do what nobody did for the Gemini version: switch things off
and see what changes. That needs no model, just running the simulation
([script]({{ '/tiny-agent/runs/step3_haiku_ants/check_variants.py' | relative_url }})),
three seeds each:

| | delivered | ants stuck with food |
|---|---|---|
| the agent's version | 1,907 / 1,733 / 1,782 | 0–7 |
| ants ignore the smell | 1,187 / 1,197 / 1,154 | 3–6 |
| no compass | 4 / 1 / 2 | 210–309 |

The compass was back. The agent called it "mild"; in fact a step toward the
nest is about twenty times more likely than a step away. And with the smell
switched off, the green line is still there:

<figure style="margin: 1.5em 0;">
  <img src="{{ '/assets/tiny-agent/img/step3-haiku-ants-no-smell.png' | relative_url }}"
       style="border-radius: 4px;"
       alt="The same simulation with ants ignoring pheromone. Left, green: still a straight band from nest to food. Right, blue: a cloud covering the whole map, no path.">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    Same code, ants ignore the smell. The green line is the compass, drawing
    the shortest way home. The blue trail is a cloud.
  </figcaption>
</figure>

So the green line isn't emergent: ants told where home is walk straight
home. The blue half is real: searching ants follow the carriers' trail out
to the food, and 50% more food gets home because of it. Half a path, for two
cents. The harder half, finding the way home by a trail other ants lay, it
skipped.

### No compass allowed

The compass felt like cheating, so I added one sentence to the prompt:

> Ants must not know where the nest or the food is; they can only smell
> pheromone.

This was the most careful run so far
([transcript]({{ '/tiny-agent/runs/step3_haiku_ants_no_compass/transcript.txt' | relative_url }}),
[code]({{ '/tiny-agent/runs/step3_haiku_ants_no_compass/ants.py' | relative_url }})).
It ran small parameter sweeps, and when one setting looked great, it tried
other random seeds without being asked: "Seed 1 looks good, but seeds 2 and
3 are much weaker (189 and 0 deliveries). I'll [...] check robustness before
claiming anything." The lesson of the first post, from a two-cent model. It
counted food pickups and diagnosed the problem:

> The cause is the nest-trail channel: empty random-walking ants lay it
> everywhere, so it no longer points toward the nest.

Traffic, not information, again! Claude's version in the first post got out
of this trap by making deposits fade the longer an ant had been away. The
tiny agent got out differently: it deleted the trail the ants lay and
replaced it with a fixed smell coming from the nest, stronger the closer
you are, across the whole map. Result: a wide corridor from nest to food,
5,000 deliveries, consistent across six seeds. Its caveat: "the nest
gradient is a built-in field, not something the ants lay down. That is
still a smell, but it is a design choice you should know about."

It is a smell, technically. But a smell that covers the whole map and gets
stronger toward the nest is a map of where the nest is. In this version,
one step closer to the nest makes a move about 4.5 times more likely,
almost exactly the strength of the compass in the previous run. Switch the
gradient off and the trail smears over the map. The agent followed my
sentence to the letter and rebuilt the compass, with a new name.

### Closing the loophole

So I told it what was wrong, in the same window, so it still had the whole
conversation:

> The nest gradient is a compass in disguise: a smell covering the whole map
> that points to the nest from everywhere. Remove it. The nest and the food
> must not emit any smell; the only information ants have is pheromone that
> ants themselves lay down. Ants carrying food must find their way home
> using a trail other ants left. Show me, with a comparison where ants
> ignore that trail, that the trail is what brings them home.

I named the problem, not the fix, and asked for the measurement I had been
doing by hand. Its first attempt froze after 16 deliveries. And then:

> Empty ants lay the home trail even after wandering far from the nest,
> which is what creates loops. I'll make deposit strength fall off with
> time since the ant last left the nest or food, so each trail is strongest
> near its source.

That's the rule. The one from the first post, the one my 2016 version was
missing, the one it had walked around three times. Nobody told it. Once the
easy ways out were closed, it found it. Its comparison ended with
`PASS: the home trail is what brings ants home`, and the picture:

<figure style="margin: 1.5em 0;">
  <img src="{{ '/assets/tiny-agent/img/step3-haiku-trail-only-seed1.png' | relative_url }}"
       style="border-radius: 4px;"
       alt="Food trail after 12,000 steps, 12,157 deliveries: a single thin trail winding from the nest on the left to the food on the right, with a small loop near each end, and ants lined up along it.">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    No compass, no smell from the nest or the food: a single winding trail,
    with the ants lined up on it.
  </figcaption>
</figure>

Thin, winding, not the straight line a compass draws: it looks like
something ants made. About **14 cents** for the whole session, 39 round
trips. My own check
([script]({{ '/tiny-agent/runs/step3_haiku_ants_trail_only/check_variants.py' | relative_url }})):

| | delivered | trip home (steps) |
|---|---|---|
| the agent's version, 8 seeds | 2,557 to 12,157 (average 5,696) | 113 to 396 |
| deposits don't fade | 0, 19, 970, 5,132 | 132 to 207 |
| ants with food ignore the home trail | about 1,245 | about 1,510 |
| empty ants ignore the food trail | about 1,230 | about 555 |

Ignore either trail and the colony drops to what ants get by wandering.
Remove the fading and most runs stop delivering. This one is emergent. But
that picture was the best of eight seeds. In another, ants ended up
circling next to the food:

<figure style="margin: 1.5em 0;">
  <img src="{{ '/assets/tiny-agent/img/step3-haiku-trail-only-seed3.png' | relative_url }}"
       style="border-radius: 4px;"
       alt="Seed 3, 4,618 deliveries: a winding trail from the nest that ends near the food, with closed loops of ants circling beside the food patch and another loop higher up.">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    Another seed: closed loops of ants circling right next to the food.
    Deliveries dropped to a trickle.
  </figcaption>
</figure>

An [ant mill](https://en.wikipedia.org/wiki/Ant_mill) again, the same
failure Claude ran into in the first post. Claude needed three more rule
changes to get out of it; the tiny agent stopped at the fading rule (and
said so: "Results vary a lot by seed").

So, does the tiny agent pass the exam? Partly, with a lot of help. Twenty
lines of loop, a cheap model and 14 cents got the real mechanism. But *I*
noticed the compass, named the loophole and asked for the comparison that
mattered. Claude, in the first post, did both the searching and the
judging, from one short prompt. That comparison is unfair twice over,
though: a different model (Haiku against Opus) *and* a different harness
(my twenty lines against Claude Code). So, one last run.

### The fair comparison: same twenty lines, bigger model

Same `step3_vision.py`, the no-compass prompt, no hints. Only
`--model opus`
([transcript]({{ '/tiny-agent/runs/step3_opus_ants/transcript.txt' | relative_url }}),
[code]({{ '/tiny-agent/runs/step3_opus_ants/ants.py' | relative_url }})).

Nine round trips, **54 cents**, and it never asked me anything. Opus costs
about forty times more per token than Haiku, but it needed a quarter of the
steps and none of my help. Its first draft already had the fading rule. It
gave each ant three short "smell" sensors (left, front, right), like
Claude's version, and made the world harder on its own: two nests, three
food piles that run out.

Its first check passed, and then it looked at the picture:

> In the first version, every ant joined a single trail and two of the food
> piles were never used, even though the "rate increased" test passed. I
> only noticed this by looking at the image.

The eyes doing exactly their job. Then, once a pile was empty, ants kept
following its dead trail forever. Its fix was a minimum smell: below it, an
ant ignores the pheromone and wanders. That's one of Claude's three rule
changes from the first post.

<figure style="margin: 1.5em 0;">
  <img src="{{ '/assets/tiny-agent/img/step3-opus-ants.png' | relative_url }}"
       style="border-radius: 4px;"
       alt="Five snapshots and a bar chart. Each snapshot shows one bright, narrow, curved trail with ants on it between a red nest and a yellow food pile; as each pile runs out, the trail fades and a new one forms to another pile. The bar chart of deliveries per 500 steps rises and falls in waves.">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    Opus with my twenty lines. Red: nests, yellow: food (dim when eaten),
    green and blue: the two trails. Each pile gets its own trail; when it
    runs out, the colony moves on. Bottom right: deliveries over time.
  </figcaption>
</figure>

It didn't switch the trails off to check (I hadn't asked this time), so I
did, three seeds each
([script]({{ '/tiny-agent/runs/step3_opus_ants/check_variants.py' | relative_url }})):

| | food delivered (of 9,000) |
|---|---|
| Opus's version | 8,997 / 8,996 / 9,000: every pile emptied, every seed |
| ants carrying food ignore the home trail | about 2,430 |
| searching ants ignore the food trail | about 3,020 |
| deposits don't fade | 9 / 22 / 1,375 |
| no minimum smell | about 3,100: first pile emptied, then stuck |

Every rule does real work, nothing points the way home, and it holds on
every seed. So, model or harness? With the same twenty lines, Opus did on
its own what Haiku needed me for. The harness had to be good enough:
without the image, the one-trail problem would have passed. But the
judgment, knowing what counts as success, came from the model.

### Summary

All the ant runs side by side, plus Claude Code from the first post. A
"round trip" is one call to the model; `y` is me approving a command.

| run | model | round trips | time (approx.) | what I had to do | cost | result |
|---|---|---|---|---|---|---|
| step 2 | Haiku 5.5 | 13 | 5 min | 1 prompt, 11 × `y` | $0.03 | clouds, no paths |
| step 3 | Haiku 5.5 | 12 | 10 min | 1 prompt, 8 × `y` | $0.02 | a straight path, drawn by a compass |
| step 3, no compass | Haiku 5.5 | 25 | 20 min | 2 prompts ("go on"), 17 × `y` | $0.06 | a corridor, drawn by a hidden compass |
| … plus closing the loophole | Haiku 5.5 | +14 | +25 min | +1 prompt naming the problem, +10 × `y` | +$0.08 | real trails, but only on some seeds |
| step 3, no compass | Opus 5.5 | 9 | 5 min | 1 prompt, 6 × `y` | $0.54 | real trails, on every seed |
| first post: Claude Code | Opus 5.5 | not counted (it ran about 150 simulations) | 30 min | 2 short prompts | monthly subscription | the ants at the top of the first post |

Haiku is about forty times cheaper per token, and it got there for 14
cents, but only after about 45 minutes of my time, three prompts and me spotting
what was wrong. Opus cost four times more in total and needed nothing but
the first prompt. My time was the expensive part. And Claude Code did the
whole job, including the judgment, from one short request.

## How are production agents different from my script

I listed the problems as the tiny agent hit them, and each one is something
a product like Claude Code has an answer
for.

- **Cut output.** Mine cut long output silently, and the agent spent three
  steps investigating a program that was fine. Real agents trim too, but
  say what they cut.
- **Clumsy edits.** Mine can only overwrite whole files, so the agent edited
  with long `sed` one-liners and broke the file twice. Real agents have an
  edit tool: replace exactly this text with that, or fail loudly.
- **A growing conversation.** Everything is re-sent: one Haiku session grew
  to 55,000 tokens per step. Real agents use caching, and summarize or clear
  old parts of the conversation.
- **Permissions.** I typed `y` more than fifty times, and after twenty I
  wasn't really reading. Real agents let you allow kinds of commands (run
  the tests, yes; delete things, ask me).
- **A folder is not a sandbox.** The agent simply left mine: it wrote to
  `/tmp` and tried `cd /root`. An agent that runs commands belongs in a
  container or a cloud session, not on your own machine.
- **Time.** A parameter sweep hit my five-minute limit and was killed. The
  agent cleverly restarted it in the background (`nohup`) and polled it with
  `sleep 240`, leaving a process my loop knew nothing about. Real agents
  have background jobs they can start, watch and stop.
- **Knowing when to stop.** Haiku stopped early and needed a nudge; a real
  agent's system prompt is long, and much of it is about when to keep
  going, when to check, and when to ask.

## What I take away

I wanted to open Conrad, and inside there is a loop. My final version is
about 200 lines, most of them tool descriptions and printing; the loop
itself is twenty. The first time it wrote a file and ran it without me, it
felt like magic again, and now I know how small the trick is.

But the loop alone didn't make the ants work. *Hands* let it act, and I was
trusting a friendly paragraph. *Eyes* let me check, and everything it said
was true while the picture still had no paths. *Real eyes* let it check
itself: it looked at its own image and changed its mind.

Every shortcut was honest, even flagged in
its caveats, and every one followed the letter of my request. Writing the
request, and the check, turned out to be the hard part. When I named the
loophole and asked for the right comparison, even the smallest model found
the real rule. The bigger model didn't need me to.

And the symmetry from the first post holds. A single ant follows a few
rules in a loop; the trails come from the feedback, the pheromone that
tells the next ant what happened. A single call to the model just writes
text; the agent comes from the feedback, the tool results that tell the
next call what happened. In both cases a bad signal (traffic instead of
information, a check that measures the wrong thing) leads the whole loop
astray. When the signal is right, something capable comes out.

Main conclusions:

* I learned what an agent is

* All of it, five ant runs on two models, cost less than a dollar of the 10
USD. I still don't have the million dollars, but I know better what I would
be asking, and what I would have to check.

* I do not know exactly which model configuration was best, as Haiku was not 100% successful, but in future experiments I would likely start with better prompts and small models.

Also this time, Claude did the first draft of the post and I iterated. This
time I knew what was inside the box while it did.

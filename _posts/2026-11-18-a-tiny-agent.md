---
title: "What's inside Conrad? Building a tiny coding agent"
date: 2026-11-18
published: false   # DRAFT: remove this line to publish
---

In the [last post]({% post_url 2026-11-16-ants-and-agents %}) I watched an AI
agent build an ant simulation for me in about 30 minutes, after I had failed
at it on my own for a decade. I asked, it worked, and I enjoyed the magic. But
I closed that post with a promise: find out how an agent like that actually
works inside. In the book, you never get to open Conrad. Here we can.

The surprise, at least for me, is how small the core is. A coding agent is
mostly a loop:

```
          ┌─────────────────────────────────────────────┐
          │                                             │
  task ──►│  1. send the model: the task + a list of    │
          │     tools it may ask for                    │
          │                                             │
          │  2. the model answers either                │
          │       "here is my answer"   ──────────────► done
          │     or                                      │
          │       "please run tool X with inputs Y"     │
          │                                             │
          │  3. my code runs the tool and sends back    │
          │     the result ─────────────────┐           │
          │                                 │           │
          └─────────────── repeat ◄─────────┘───────────┘
```

That's it. The rest of this post builds it in small steps, the same way the
ants post went: first something that doesn't work, then something that does,
and then I'll try to find where it breaks.

## The setup

I wanted to see the moving parts, so no frameworks: plain Python and the
model provider's own library, talking to the API directly. Frameworks exist
to hide exactly the part I want to look at. All the code is in
[the repository](https://github.com/rbaravalle/rbaravalle.github.io/tree/main/tiny-agent).

Two practical notes before starting.

**It costs money, a little.** Calling the model from your own code is billed
per use, separately from the monthly subscription I used for the ants. I put
10 USD of credits in the account. A spending limit in the provider's console
is worth setting too, because a loop that goes wrong can keep calling the
model on its own. I used the smallest,
cheapest model (Claude Haiku 5.5) and made every script print what each call
costs. Spoiler: so far I have barely made a dent in the 10 USD.

**It can break things.** Once the agent can run commands, it can run *any*
command, including deleting files. So I run it inside an empty throwaway
folder, and my code asks me before every command. Never in your home
directory.

## Step 0: a chatbot

The first version can only talk
([step0_chat.py]({{ '/tiny-agent/step0_chat.py' | relative_url }})).
You type, it sends your message to the model, prints the answer, repeat:

```
you> Hello

claude> Hello! How can I help you with your code today?
```

Not impressive, but there is already one thing I didn't know. The model
remembers nothing between calls. Every time, my script sends the *whole*
conversation again from the start, and you can watch the token count (and
the cost) grow with each turn. The "memory" of a chat is just a list my
script keeps and re-sends.

If you ask this chatbot to build something, it can only tell you what to
type. You run it, you paste back the errors. You are the loop, exactly like
my ChatGPT and Gemini rounds in the ants post.

## Step 1: give it hands

The second version
([step1_tools.py]({{ '/tiny-agent/step1_tools.py' | relative_url }}))
adds three tools: *read a file*, *write a file*, *run a command*. And here is
the part that surprised me most: the model still can't touch anything. A
"tool" is just a description I send along with the message, a name and the
inputs it takes:

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
`run_command` with `python3 life.py`". My code does the actual running and
sends the output back. The hands are mine; the model only asks. The loop
itself is about twenty lines:

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
and run the command. `MAX_STEPS` (25) is a brake, so a confused loop stops on
its own.

Before going to the ants, I gave it a small task. Conway's Game of Life is
another classic of emergence (simple rules on a grid, and patterns that
seem alive come out), and the *glider* is its most famous pattern: five cells
that, every four generations, end up shifted one cell diagonally. They walk.
That makes it easy to check:

```
you> Write a Python program life.py that runs Conway's Game of Life on a
     10x10 grid, starting with a glider. Run it and check that the glider
     has moved one cell diagonally after 4 generations.

  [step 1: 633 tokens in, 1064 out, $0.00060, $0.0006 total]

  [tool] write_file {"path": "life.py", "content": "\"\"\"Conway's Game of Life ...

  [tool] run_command {"command": "python3 life.py"}

  run `python3 life.py`? [y/N] y

claude> I wrote `life.py`, which runs Conway's Game of Life on a 10x10 grid
(non-wrapping) starting from a glider in the top-left corner.

I ran it and the check passed: after 4 generations the glider's live cells
are exactly its starting cells shifted by one row down and one column right.

  [step 2: 2407 tokens in, 100 out, $0.00029, $0.0009 total]
```

The first time it ran a program it had just written, without me typing
anything but `y`, was a small "aha" moment. Conrad has hands!

A few things I noticed reading that transcript again:

- **Two round trips, less than a tenth of a cent.** In its first reply the
  model asked for *two* tools at once: write the file, then run it. It was
  confident enough that the file would be written fine not to wait.
- **The input jumps from 633 to 2,407 tokens.** That's the whole program it
  wrote plus the program's output, now part of the conversation that gets
  re-sent every step. Remember step 0: nothing is remembered, everything is
  re-sent. On a long task this is going to matter.
- **It made a decision I didn't ask for.** "Non-wrapping": cells at the edge
  don't wrap around to the other side. A reasonable choice, and the glider
  doesn't reach the edge in four generations, but it chose silently.
- **It wrote its own check.** The program
  ([here is what it wrote]({{ '/tiny-agent/runs/step1_life.py' | relative_url }}))
  shifts the starting cells by one row and one column and compares them with
  what is alive after four generations. In fairness, I asked it to check.

### Who was watching?

And then I realized something. My script prints the name of each tool
call, but not what came back. The program printed five grids and a
`CHECK PASSED` line, and the model read all of it. I never saw it. All I got
was the model telling me, in a friendly paragraph, that the check passed.

That's exactly where the ants post started to go wrong with the chatbots: a
confident explanation, and nobody measuring. This time it was true (I ran
`life.py` myself, and it does print `CHECK PASSED`), but I had to go and
check. So the next step is about eyes: making sure the agent, *and I*, see
what the program actually did.

## Step 2: give it eyes

The third version
([step2_eyes.py]({{ '/tiny-agent/step2_eyes.py' | relative_url }}))
has the same three tools and the same loop. Two things changed, and neither
is clever:

1. Every tool result is printed for me too, so I see what the model sees.
2. A few lines in the instructions I send with every request (the "system
   prompt"): back every claim with a check the program prints itself, quote
   that output in the final answer, and never claim a result you didn't see.

Same task, run again:

```
you> Write life.py: Conway's Game of Life on a 10x10 grid starting with a
     glider. Run it and check that the glider moved one cell diagonally
     after 4 generations.

  [step 1: 742 tokens in, 1058 out, $0.00060, $0.0006 total]

  [tool] write_file {"path": "life.py", "content": "\"\"\"Conway's Game of Life ...
  | Wrote 1680 characters to life.py

  [tool] run_command {"command": "python3 life.py"}

  run `python3 life.py`? [y/N] y
  | ... (37 lines hidden)
  |
  | Generation 4:
  | ..........
  | ..#.......
  | ...#......
  | .###......
  | ..........
  | (five more empty rows)
  |
  | Start cells: [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)]
  | End cells:   [(1, 2), (2, 3), (3, 1), (3, 2), (3, 3)]
  | PASS - glider moved one cell diagonally after 4 generations

claude> I wrote `life.py` and ran it. It simulates Conway's Game of Life on
a 10x10 grid with wrap-around edges, starting from a glider.

The check passed. The program's output includes:

    Start cells: [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)]
    End cells:   [(1, 2), (2, 3), (3, 1), (3, 2), (3, 3)]
    PASS - glider moved one cell diagonally after 4 generations

The end cells are the start cells shifted by (+1, +1), so the glider moved
one cell down and one cell right.

  [step 2: 2194 tokens in, 206 out, $0.00032, $0.0009 total]
```

Now I don't have to trust the paragraph. I can look at generation 4 myself,
find the glider one row down and one column right, and read the numbers
the claim is based on. Same cost as before, less than a tenth of a cent.

Two things I didn't expect:

- **Same question, different program.** This time the grid wraps around at
  the edges; in step 1 it didn't. I didn't ask for either. The model isn't
  deterministic, so you can't assume it will make the same choices twice,
  and if a choice matters, you have to say it.
- **For the model, almost nothing changed.** It already wrote a check in
  step 1, and it already read the output. The eyes I added were mostly for
  *me*. On a task this easy, the first try works and there is nothing to
  correct.

That second point is the honest one. The Game of Life is a task where the
answer is well known and the check is obvious: five cells, shifted by one.
The ants are the opposite. In the first post, the chatbots' code *ran*, and
the animation *looked* plausible, and it was still wrong in ways that only
showed up when someone measured: food delivered, with and without trails.
What made Claude succeed there wasn't writing the code, it was measuring,
over and over, and believing the numbers over the explanation. And one more
thing: the agent here writes the code *and* the check. A check is only as
good as the question it asks. Something to watch in the next test.

## The test: the ants again

Time for the real exam. I gave the tiny agent (step 2, still the cheap
Haiku model) the same short request I gave Claude in the first post, plus
one sentence, because this agent can't see a screen:

> I want to do a visualization of emergent behavior for "ants" as they take
> "food" from a source to a "nest". I want in the end to see paths forming
> between the foods and nests. Write it in Python. Since you can't see the
> screen, print numbers that show whether paths form (for example food
> delivered over time), and save an image of the final state as ants.png.

I raised the step limit to 60 and pressed `y` a lot. It needed 13 round
trips and about **3 cents**
([full transcript]({{ '/tiny-agent/runs/step2_haiku_ants/transcript.txt' | relative_url }}),
[the code it wrote]({{ '/tiny-agent/runs/step2_haiku_ants/ants.py' | relative_url }})).
And it ended like this:

```
Total deliveries  pheromone=78  baseline=33
CHECK pheromone > 2x baseline deliveries: PASS
CHECK trail concentrated (>0.15):         PASS
CHECK throughput rising over time:        PASS
```

Three PASS lines. Success? Here is the image it saved:

<figure style="margin: 1.5em 0;">
  <img src="{{ '/assets/tiny-agent/img/step2-haiku-ants.png' | relative_url }}"
       style="border-radius: 4px;"
       alt="Three panels after 10,000 steps: the left one shows pheromone covering almost the whole map, with the nest bottom left, the food top right and a wall with one gap in the middle. The red food-trail panel and the blue nest-trail panel are broad clouds filling each half of the map. No paths.">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    The tiny agent's final state. Left: all pheromone, with the nest (green
    square), the food (star) and a wall it decided to add. Middle and right:
    the two trails. Clouds, not paths.
  </figcaption>
</figure>

No paths. Pheromone everywhere. So what happened in those 13 steps?

**The good part: it measured, and it fixed real bugs.** Without being asked,
it built in a comparison: the same simulation with pheromones switched off.
That's exactly the test nobody did for the Gemini version in the first post.
Its first version delivered zero food, and from the numbers (no food
pheromone at all) it found the bug: searching ants were following their *own*
trail instead of the one left by ants carrying food. One-line fix. Then the
pheromone values grew without limit and every ant got stuck on the strongest
cell; it capped how much a smell can attract. Measure, find, fix, measure
again. That's the loop working.

**The confusing part was my fault.** Halfway through, it said:

> The output doesn't match the script I wrote (no "Run A:" header, and
> different log lines). I'll check what is actually on disk before trusting
> anything.

It checked the file. The file was fine. It ran again, saved the output to a
log, printed the log: still "doesn't match". It gave up on the mystery and
carried on. The cause was in *my* twenty lines: to keep the conversation
short, `run_tool` only sends back the last 4,000 characters of the output.
The program printed about 4,300, so the first lines, including the `Run A:`
header, never reached the model. It was seeing a page torn out of the
middle of a book and, very reasonably, concluding that the book was wrong.
Nothing told it a page was missing, so it never found out.

**The weak part: the checks asked easier questions than I did.** Look at
the three PASS lines again with the picture next to them:

- *"pheromone > 2x baseline"*: true, 78 against 33. But to get there it gave
  ants carrying food a pull toward the nest, the same built-in compass the
  Gemini version had. To its credit, it told me ("Deviation from pure
  emergence"), and it kept the compass in the comparison run too, so the
  comparison is fair. It still isn't paths.
- *"trail concentrated (>0.15)"*: the busiest 5% of the cells hold 24.7% of
  the pheromone. A threshold it picked itself, and far from a path.
- *"throughput rising"*: true, and even at the end 44 of the 150 ants are
  still wandering around with food they can't bring home.
- And one number never moved: `ants_on_trail=150`, in every line of every
  run. Pheromone is everywhere, so every ant is "on a trail". A measurement
  that can't change measures nothing, and nobody noticed.

And then the part I found most interesting. Every ant drops the same amount
of pheromone on every step, however long ago it left the nest or the food.
That's exactly my mistake from 2016: the map records *traffic*, not
*information*. The tiny agent walked straight into the trap I fell into, and
the one Claude's version had to get out of with its "fresh ants only" rule.

In fairness, its final message said "the trail is only partly formed" and
"I couldn't view `ants.png`". Every number it gave me was real. It didn't
lie; it graded its own homework with questions it wrote itself, and it
couldn't look at the drawing. So, measuring is necessary, but it's not
enough: you also have to measure the *right thing*, and the real goal here
("I want to *see* paths") is visual.

Claude, in the first post, ran about 150 simulations over 30 minutes and
took screenshots of its own result. The tiny agent ran 7, in 13 steps, for 3
cents, blind.

## Step 3: real eyes

The ant test gave me two fixes, both small
([step3_vision.py]({{ '/tiny-agent/step3_vision.py' | relative_url }})):

1. **No more torn pages.** Long output now keeps the start *and* the end,
   with a note in the middle: `[... 9890 characters cut from the middle ...]`.
   The agent can't avoid cut output, but now it knows when something is
   missing.
2. **A `view_image` tool.** It reads an image file and sends it back to the
   model as a picture instead of text. The model can look at `ants.png`.
   And one more line in the instructions: when you save an image, look at
   it, and judge whether it shows what was asked, not only whether the
   numbers pass.

Same prompt, same cheap Haiku model, fresh folder. 12 round trips, **less
than 2 cents**
([transcript]({{ '/tiny-agent/runs/step3_haiku_ants/transcript.txt' | relative_url }}),
[code]({{ '/tiny-agent/runs/step3_haiku_ants/ants.py' | relative_url }})).

The start looked like a replay: zero deliveries, run after run. But it
debugged better this time. Instead of guessing, it wrote little probes to
ask the simulation questions: how far are the ants from the nest? Where
exactly are the ones stuck carrying food? The answer was precise: they were
trapped on peaks of the trail (one cell had piled up to 57,848), bouncing
back and forth around them. It compressed the smell (so one huge
peak can't dominate) and stopped ants from turning straight back.
Deliveries jumped from 11 to almost 2,000.

Then the moment step 3 was built for. Its check said FAIL (it compared early
and late deliveries, a poor test, and it said so), and before touching the
check, it opened the picture:

> The image shows a clear trail running from the nest to the food, which is
> what I wanted.

<figure style="margin: 1.5em 0;">
  <img src="{{ '/assets/tiny-agent/img/step3-haiku-ants.png' | relative_url }}"
       style="border-radius: 4px;"
       alt="Two panels after 30,000 steps, 1,907 deliveries. Left, green: the food trail is a narrow straight band from the nest at the bottom left to the food at the top right. Right, blue: the home trail is the same straight band, darker near the nest.">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    Step 3, Haiku: a path! Green is the trail laid by ants carrying food,
    blue the one laid by ants searching for it.
  </figcaption>
</figure>

A path! And for less than two cents. I was ready to declare victory. But
the whole point of this post is that a nice picture isn't a measurement, so
I asked Claude to do what neither the agent nor I did for the Gemini
version: switch things off and see what changes (it's free, no model
involved, just running the simulation:
[the script]({{ '/tiny-agent/runs/step3_haiku_ants/check_variants.py' | relative_url }})).
Three seeds each:

| | delivered | green trail in the corridor | ants stuck with food |
|---|---|---|---|
| the agent's version | 1,907 / 1,733 / 1,782 | 100% | 0–7 |
| ants ignore the smell | 1,187 / 1,197 / 1,154 | 80–92% | 3–6 |
| no compass | 4 / 1 / 2 | 16–33% | 210–309 |

Remember the compass? To get the first deliveries, the agent again gave
ants carrying food a pull toward the nest. It called it "mild". It isn't:
the step pointing at the nest is about twenty times more likely than the one
pointing away. Take it out and nothing works: 300 ants wander around with
food forever. And with the compass on and the smell switched off, the green
line is still there:

<figure style="margin: 1.5em 0;">
  <img src="{{ '/assets/tiny-agent/img/step3-haiku-ants-no-smell.png' | relative_url }}"
       style="border-radius: 4px;"
       alt="The same simulation with ants ignoring pheromone. Left, green: still a straight band from nest to food, a bit wider and noisier. Right, blue: a cloud covering the whole map, darker around the nest, no path.">
  <figcaption style="font-size: 0.85em; color: #8a93a6; margin-top: 0.4em;">
    Same code, ants ignore the smell. The green line is still there: it's
    the compass, drawing the shortest way home. The blue trail is a cloud.
  </figcaption>
</figure>

So the green line is not emergent. It's ants carrying food walking more or
less straight home, because they were told where home is. Of course their
trail is a straight line. And the agent's final check, "PATH FORMED: 80% of
the green trail near the straight nest-food line", passes with the smell
switched off too, in all three seeds. It was written *after* the agent
had seen the picture, so it measured the picture it already had. In
fairness, it warned me: "the corridor check is partly easy... treat it as a
sanity check, not strong evidence on its own."

But look at the blue panels. *That's* the emergent part. With smell, the
searching ants find the carriers' trail and follow it out to the food, and
their own trail becomes the same narrow band. Without smell, they wander
everywhere. That half is real: nobody tells a searching ant where the food
is, and 50% more food gets home because of it.

So: half a path. One half drawn by a compass, the other half emerging. Not
bad for two cents. And Claude's version in the first post has no compass at
all: ants find their way home by the trail the searchers leave behind,
which is the harder half the tiny agent skipped twice.

What made the difference between the two runs here? Not the model, it's the
same one. The harness: seeing the whole output and seeing the picture. What
still was missing: a comparison with the smell switched off. The step 2
agent did that one on its own; this one didn't. Each run makes different
choices, and nothing in my twenty lines makes it do the right experiment.

**[TODO: same prompt on Opus for the fair comparison with Claude. Maybe
also: tell it "no compass" and see if it finds the harder half.]**

## What the real ones add

**[TODO]** The problems the tiny agent runs into, found by hitting them.
So far:
- Cut output with nothing saying it was cut (the "Run A:" mystery).
- Clumsy edits: it only has "overwrite the whole file", so it edited
  `ants.py` with long `sed` one-liners and inline Python scripts, and broke
  it once (a constant used before it was defined).
- Re-sent conversation: the input grew from 793 to 28,008 tokens in 13 steps.
- Typing `y` dozens of times. Permissions are a real design problem.

These are the things products like Claude Code solve.

## What I take away

**[TODO]**

Also this time, Claude did the first draft of the post and I iterated. And
the tiny agent is a hundred lines.

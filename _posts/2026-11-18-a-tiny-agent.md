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

**[TODO]** Give the tiny agent the same ant task I gave Claude, with the same
short prompt. Success or failure, compare honestly with what Claude did.

## What the real ones add

**[TODO]** The problems the tiny agent runs into, found by hitting them:
forgetting things on long tasks (all those re-sent tokens), clumsy edits to
big files (it can only overwrite whole files), commands it shouldn't run.
These are the things products like Claude Code solve.

## What I take away

**[TODO]**

Also this time, Claude did the first draft of the post and I iterated. And
the tiny agent is a hundred lines.

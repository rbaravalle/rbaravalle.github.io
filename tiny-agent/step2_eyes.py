"""
Step 2: give it eyes. Same tools, same loop as step 1.

In step 1 the model saw the program's output, but I didn't: the script only
printed the tool names, and I had to trust the model's summary.
Two changes:
  1. Every tool result is printed for me too, so I see what the model sees.
  2. The model is told to measure: check results with numbers the program
     prints, quote that output in its answer, and never claim a result it
     did not see.

SAFETY: this agent writes files and runs shell commands. Run it only inside
an empty throwaway folder, never in your home directory. Every command asks
for your y/N first.

Run:
    pip install anthropic
    export ANTHROPIC_API_KEY=...        # from platform.claude.com
    mkdir ~/agent-sandbox && cd ~/agent-sandbox
    python3 /path/to/step2_eyes.py                      # Haiku, 25 steps
    python3 /path/to/step2_eyes.py --steps 60 --model opus

Type a task and press Enter. Ctrl+D (or an empty line) quits.
"""
import argparse
import json
import subprocess
from pathlib import Path

import anthropic

# Prices in USD per million tokens (input, output).
# Check https://platform.claude.com/docs/en/about-claude/pricing for current values.
MODELS = {
    "haiku": ("claude-haiku-5-5", 0.10, 0.50),   # prompts over 100K tokens: 0.50 / 2.50
    "opus":  ("claude-opus-5-5", 4.00, 20.00),
}

args = argparse.ArgumentParser()
args.add_argument("--model", choices=MODELS, default="haiku")
args.add_argument("--steps", type=int, default=25,
                  help="brake: a confused loop must not spend credits forever")
args = args.parse_args()

MODEL, PRICE_IN, PRICE_OUT = MODELS[args.model]
MAX_STEPS = args.steps

SHOW_LINES = 30  # how much of each tool result to show me

SYSTEM = """You are a coding agent working in the current directory.
Use the tools to write, run and check code. Keep answers short.

Measure, don't assume:
- When you claim something works, back it with a check the program runs
  itself and prints as numbers or a clear PASS/FAIL line.
- In your final answer, quote the exact output lines that show the result.
- Never claim a result you did not see in a tool result. If a check fails,
  say so, and fix it or explain what is wrong."""

# The tools are only descriptions. The model reads them and may ask for one.
TOOLS = [
    {
        "name": "read_file",
        "description": "Read a text file and return its contents.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a text file with the given content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "run_command",
        "description": "Run a shell command and return its exit code and output.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
]


def run_tool(name, args):
    """The hands: plain Python doing what the model asked for."""
    try:
        if name == "read_file":
            return Path(args["path"]).read_text()
        if name == "write_file":
            Path(args["path"]).write_text(args["content"])
            return f"Wrote {len(args['content'])} characters to {args['path']}"
        if name == "run_command":
            answer = input(f"\n  run `{args['command']}`? [y/N] ")
            if answer.strip().lower() != "y":
                return "The user declined to run this command."
            p = subprocess.run(args["command"], shell=True, capture_output=True,
                               text=True, timeout=300)
            return (f"exit code {p.returncode}\n"
                    f"stdout:\n{p.stdout[-4000:]}\nstderr:\n{p.stderr[-4000:]}")
        return f"Unknown tool: {name}"
    except Exception as e:
        return f"Error: {e}"


def show(output):
    """Print a tool result for the human, trimmed to the last SHOW_LINES lines."""
    lines = output.splitlines()
    if len(lines) > SHOW_LINES:
        print(f"  | ... ({len(lines) - SHOW_LINES} lines hidden)")
        lines = lines[-SHOW_LINES:]
    for line in lines:
        print("  | " + line)


def main():
    client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY from the environment
    messages = []
    total_cost = 0.0

    while True:
        try:
            text = input("\nyou> ").strip()
        except EOFError:
            break
        if not text:
            break
        messages.append({"role": "user", "content": text})

        # The agent loop: ask, run the tools it wants, send results, ask again.
        for step in range(MAX_STEPS):
            response = client.messages.create(
                model=MODEL,
                max_tokens=16000,
                system=SYSTEM,
                tools=TOOLS,
                messages=messages,
            )
            messages.append({"role": "assistant", "content": response.content})

            for block in response.content:
                if block.type == "text" and block.text.strip():
                    print("\nclaude> " + block.text)

            u = response.usage
            price_in, price_out = PRICE_IN, PRICE_OUT
            if args.model == "haiku" and u.input_tokens > 100_000:
                price_in, price_out = 0.50, 2.50   # Haiku's long-prompt price
            cost = (u.input_tokens * price_in + u.output_tokens * price_out) / 1_000_000
            total_cost += cost
            print(f"\n  [step {step + 1}: {u.input_tokens} tokens in, {u.output_tokens} out, "
                  f"${cost:.5f}, ${total_cost:.4f} total]")

            if response.stop_reason == "refusal":
                print("\n[the model declined to answer]")
                break
            if response.stop_reason != "tool_use":
                break   # no tool requested: the model says it is done

            results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"\n  [tool] {block.name} {json.dumps(block.input)[:120]}")
                    output = run_tool(block.name, block.input)
                    show(output)   # the eyes: I see what the model sees
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                    })
            # All results go back together, in one user message.
            messages.append({"role": "user", "content": results})
        else:
            print(f"\n[stopped after {MAX_STEPS} steps]")
            # Close the dangling turn so the next task starts from a valid conversation.
            messages.append({"role": "assistant", "content": "I stopped: step limit reached."})


if __name__ == "__main__":
    main()

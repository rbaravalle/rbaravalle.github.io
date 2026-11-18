"""
Step 1: give it hands. Three tools and a loop.

The model still can't touch anything itself. It can only reply "please run
this tool with these inputs". This script runs the tool, sends back the
result, and asks again, until the model says it is done.
The script is now the loop, not you.

SAFETY: this agent writes files and runs shell commands. Run it only inside
an empty throwaway folder, never in your home directory. Every command asks
for your y/N first.

Run:
    pip install anthropic
    export ANTHROPIC_API_KEY=...        # from platform.claude.com
    mkdir ~/agent-sandbox && cd ~/agent-sandbox
    python3 /path/to/step1_tools.py

Type a task and press Enter. Ctrl+D (or an empty line) quits.
"""
import json
import subprocess
from pathlib import Path

import anthropic

MODEL = "claude-haiku-5-5"

# Prices in USD per million tokens, for prompts up to 100K tokens.
# Check https://platform.claude.com/docs/en/about-claude/pricing for current values.
PRICE_IN, PRICE_OUT = 0.10, 0.50

MAX_STEPS = 25   # brake: a confused loop must not spend credits forever

SYSTEM = ("You are a coding agent working in the current directory. "
          "Use the tools to write, run and check code. Keep answers short.")

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
                               text=True, timeout=60)
            return (f"exit code {p.returncode}\n"
                    f"stdout:\n{p.stdout[-4000:]}\nstderr:\n{p.stderr[-4000:]}")
        return f"Unknown tool: {name}"
    except Exception as e:
        return f"Error: {e}"


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
            cost = (u.input_tokens * PRICE_IN + u.output_tokens * PRICE_OUT) / 1_000_000
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
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": run_tool(block.name, block.input),
                    })
            # All results go back together, in one user message.
            messages.append({"role": "user", "content": results})
        else:
            print(f"\n[stopped after {MAX_STEPS} steps]")
            # Close the dangling turn so the next task starts from a valid conversation.
            messages.append({"role": "assistant", "content": "I stopped: step limit reached."})


if __name__ == "__main__":
    main()

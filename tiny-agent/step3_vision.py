"""
Step 3: real eyes. Step 2 plus two fixes found by running the ant test.

  1. Long output is no longer silently cut. Step 2 kept only the last 4000
     characters, so the agent saw output whose first lines were missing and
     decided its own program "didn't match". Now it gets the start AND the
     end, with a note saying how much was cut from the middle.
  2. A view_image tool. In step 2 the agent saved ants.png but could never
     look at it. Now it can open an image, and the model sees the picture.

SAFETY: this agent writes files and runs shell commands. Run it only inside
an empty throwaway folder, never in your home directory. Every command asks
for your y/N first.

Run:
    pip install anthropic
    export ANTHROPIC_API_KEY=...        # from platform.claude.com
    mkdir ~/agent-sandbox && cd ~/agent-sandbox
    python3 /path/to/step3_vision.py                     # Haiku, 25 steps
    python3 /path/to/step3_vision.py --steps 60 --model opus

Type a task and press Enter. Ctrl+D (or an empty line) quits.
"""
import argparse
import base64
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
  say so, and fix it or explain what is wrong.
- When the program saves an image, look at it with view_image and judge
  whether it shows what was asked for, not only whether the numbers pass."""

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
        "name": "view_image",
        "description": "Look at an image file (PNG, JPEG, GIF or WebP), "
                       "for example a plot or a screenshot the program saved.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
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


MAX_CHARS = 8000   # how much of a command's output the model gets


def clip(text):
    """Keep the start and the end of long output, and say what was cut."""
    if len(text) <= MAX_CHARS:
        return text
    head, tail = text[:MAX_CHARS // 3], text[-2 * MAX_CHARS // 3:]
    cut = len(text) - len(head) - len(tail)
    return f"{head}\n[... {cut} characters cut from the middle ...]\n{tail}"


IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".gif": "image/gif", ".webp": "image/webp"}


def run_tool(name, args):
    """The hands: plain Python doing what the model asked for."""
    try:
        if name == "read_file":
            return Path(args["path"]).read_text()
        if name == "write_file":
            Path(args["path"]).write_text(args["content"])
            return f"Wrote {len(args['content'])} characters to {args['path']}"
        if name == "view_image":
            path = Path(args["path"])
            data = base64.standard_b64encode(path.read_bytes()).decode()
            # A tool result can hold an image instead of text.
            return [{"type": "image",
                     "source": {"type": "base64",
                                "media_type": IMAGE_TYPES[path.suffix.lower()],
                                "data": data}}]
        if name == "run_command":
            answer = input(f"\n  run `{args['command']}`? [y/N] ")
            if answer.strip().lower() != "y":
                return "The user declined to run this command."
            p = subprocess.run(args["command"], shell=True, capture_output=True,
                               text=True, timeout=300)
            return (f"exit code {p.returncode}\n"
                    f"stdout:\n{clip(p.stdout)}\nstderr:\n{clip(p.stderr)}")
        return f"Unknown tool: {name}"
    except Exception as e:
        return f"Error: {e}"


def show(output):
    """Print a tool result for the human, trimmed to the last SHOW_LINES lines."""
    if isinstance(output, list):   # an image: the model sees it, I get a note
        size = len(output[0]["source"]["data"]) * 3 // 4
        print(f"  | [image sent to the model, {size // 1024} KB]")
        return
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

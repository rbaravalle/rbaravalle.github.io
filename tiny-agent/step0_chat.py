"""
Step 0: a chatbot. No tools, no hands, no eyes.

The model can only talk. If you ask it to build something, it can only tell
you what to type, and you have to run it and paste back what happened.
You are the loop.

Run:
    pip install anthropic
    export ANTHROPIC_API_KEY=...        # from platform.claude.com
    python3 step0_chat.py

Type a message and press Enter. Ctrl+D (or an empty line) quits.
"""
import anthropic

MODEL = "claude-haiku-5-5"

# Prices in USD per million tokens, for prompts up to 100K tokens.
# Check https://platform.claude.com/docs/en/about-claude/pricing for current values.
PRICE_IN, PRICE_OUT = 0.10, 0.50

SYSTEM = "You are a helpful programming assistant. Keep answers short."


def main():
    client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY from the environment
    messages = []                    # the whole conversation; the API itself remembers nothing
    total_cost = 0.0

    while True:
        try:
            text = input("\nyou> ").strip()
        except EOFError:
            break
        if not text:
            break

        messages.append({"role": "user", "content": text})
        response = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM,
            messages=messages,
        )
        # Keep the full reply (not just the text) so the next request carries it unchanged.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "refusal":
            print("\n[the model declined to answer]")
        for block in response.content:
            if block.type == "text":
                print("\nclaude> " + block.text)

        # Every request re-sends the whole conversation, so input tokens grow each turn.
        u = response.usage
        cost = (u.input_tokens * PRICE_IN + u.output_tokens * PRICE_OUT) / 1_000_000
        total_cost += cost
        print(f"\n  [{u.input_tokens} tokens in, {u.output_tokens} out, "
              f"${cost:.5f} this turn, ${total_cost:.4f} total]")


if __name__ == "__main__":
    main()

"""
Run many robot runs and log everything to files.

    python3 batch.py --name pilot --houses 5 --runs-per-house 1          # paid
    python3 batch.py --name test  --houses 3 --runs-per-house 2 --fake   # free

Each batch writes runs/<name>/:
    terminal.log            a copy of everything printed
    results.jsonl, .csv     one row per run
    summary.md              the results table, plus anything that went wrong
    notes.md                every notebook the notebook agent wrote, in order
    <run>/transcript.jsonl  every message sent to the model, every reply, every
                            tool call and result, the notes, tokens and cost per call
    <run>/replay.json       for the viewer (viewer.html)
    bundle.zip              all of the above in one file, to upload as-is

The last line printed is the path of the bundle.

Seeds: house h has floor plan seed h and lidar noise seed h. Repeated runs of
one house differ only in what the model does. If a batch is interrupted, run
the same command again: finished runs are skipped.
"""
import argparse
import csv
import json
import math
import os
import statistics
import sys
import threading
import time
import traceback
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import agent
import sim

HERE = Path(__file__).resolve().parent
ALL = ["wall"] + agent.SETTINGS
COLUMNS = ["run_id", "setting", "house_seed", "noise_seed", "rep", "model", "effort",
           "outcome", "success", "steps", "bumps", "calls", "nudges", "note_writes",
           "note_reads", "input_tokens", "output_tokens", "cache_creation_input_tokens",
           "cache_read_input_tokens", "cost", "seconds", "error", "final_notes"]


class Tee:
    """Print to the terminal and to terminal.log at the same time."""

    def __init__(self, path):
        self.file = open(path, "a", buffering=1)
        self.stdout = sys.stdout
        self.lock = threading.Lock()

    def write(self, s):
        with self.lock:
            self.stdout.write(s)
            self.file.write(s)

    def flush(self):
        self.stdout.flush()
        self.file.flush()


def wilson(k, n, z=1.96):
    """95% confidence interval for a success rate."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def detectable_gap(n):
    """Roughly the smallest gap in success rate (two settings, n runs each) that
    a test at 95% would pick up with 80% power, at the worst case p = 0.5."""
    return (1.96 + 0.84) * math.sqrt(2 * 0.25 / n) if n else 1.0


def fmt_money(x):
    return f"${x:.4f}" if x < 1 else f"${x:.2f}"


def summarize(batch_dir, rows, args, problems, interrupted):
    lines = [f"# Batch `{args.name}`", ""]
    models = sorted({r["model"] for r in rows if r["setting"] != "wall"})
    lines += [f"- Date: {time.strftime('%Y-%m-%d')}",
              f"- Model: {', '.join(models) or '-'}" + ("  (FAKE: scripted stand-in, no API calls; "
                                                         "token counts are estimates)" if args.fake else ""),
              f"- Effort: {args.effort}",
              f"- Scan the model reads: {'8 sectors (clear + farthest)' if args.scan == 'sectors' else 'all 72 rays'}",
              f"- Houses: seeds {args.house_start}..{args.house_start + args.houses - 1}, "
              f"{args.runs_per_house} run(s) per house per setting (the wall follower is "
              "deterministic: 1 run per house)",
              f"- Step limit: {args.steps} actions (move or turn), the same for every setting",
              f"- Command: `{' '.join(sys.argv)}`", ""]
    if interrupted:
        lines += ["**The batch was interrupted: this summary covers the finished runs only.**", ""]

    lines += ["## Results", "",
              "| setting | runs | success | 95% CI | steps (median, successes) | bumps (mean) "
              "| cost per run | cost per success | total cost | cache read share |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    by = {s: [r for r in rows if r["setting"] == s] for s in ALL}
    for s in ALL:
        rs = by[s]
        if not rs:
            continue
        n, k = len(rs), sum(r["success"] for r in rs)
        lo, hi = wilson(k, n)
        st = [r["steps"] for r in rs if r["success"]]
        cost = sum(r["cost"] for r in rs)
        prompt = sum(r["input_tokens"] + r["cache_read_input_tokens"]
                     + r["cache_creation_input_tokens"] for r in rs)
        share = sum(r["cache_read_input_tokens"] for r in rs) / prompt if prompt else 0
        lines.append(
            f"| {s} | {n} | {k}/{n} = {k / n:.0%} | {lo:.0%}-{hi:.0%} | "
            f"{statistics.median(st) if st else '-'} | {statistics.mean(r['bumps'] for r in rs):.1f} | "
            f"{fmt_money(cost / n)} | {fmt_money(cost / k) if k else '-'} | {fmt_money(cost)} | "
            f"{share:.0%} |")
    total = sum(r["cost"] for r in rows)
    lines += ["", f"Total cost of this batch: **{fmt_money(total)}**.", ""]
    if by["wall"]:
        # The guarantee, checked: the same houses with no step limit (free).
        free = []
        for r in by["wall"]:
            robot = sim.SimRobot(sim.make_house(r["house_seed"]), r["noise_seed"])
            n_steps = agent.wall_follower.run(robot, 20000)
            free.append((robot.outside, n_steps))
        k = sum(o for o, _ in free)
        st = sorted(n for o, n in free if o)
        lines += [f"Wall follower on the same houses with no step limit: {k}/{len(free)} out"
                  + (f", median {statistics.median(st)} steps, max {st[-1]}." if st else "."), ""]

    ns = sorted({len(by[s]) for s in agent.SETTINGS if by[s]})
    if ns:
        n = ns[0]
        lines += [f"**What this sample can detect:** with {n} runs per setting, only gaps of "
                  f"roughly {detectable_gap(n):.0%} or more in success rate between two settings "
                  "are distinguishable from noise. Don't over-read smaller differences.", ""]

    lines += ["## How the runs ended", "", "| setting | " + " | ".join(
        ["success", "step_limit", "done_inside", "no_action", "call_limit", "refusal", "error"]) + " |",
        "|---|---|---|---|---|---|---|---|"]
    for s in ALL:
        if by[s]:
            c = [sum(r["outcome"] == o for r in by[s]) for o in
                 ["success", "step_limit", "done_inside", "no_action", "call_limit", "refusal", "error"]]
            lines.append(f"| {s} | " + " | ".join(map(str, c)) + " |")
    lines.append("")

    lines += ["## Tokens per run (mean)", "",
              "| setting | model calls | uncached input | cache write | cache read | output | nudges | note writes | note reads |",
              "|---|---|---|---|---|---|---|---|---|"]
    for s in agent.SETTINGS:
        rs = by[s]
        if rs:
            m = lambda key: statistics.mean(r[key] for r in rs)  # noqa: E731
            lines.append(f"| {s} | {m('calls'):.0f} | {m('input_tokens'):,.0f} | "
                         f"{m('cache_creation_input_tokens'):,.0f} | {m('cache_read_input_tokens'):,.0f} | "
                         f"{m('output_tokens'):,.0f} | {m('nudges'):.1f} | {m('note_writes'):.1f} | "
                         f"{m('note_reads'):.1f} |")
    lines.append("")

    houses = sorted({r["house_seed"] for r in rows})
    lines += ["## Successes per house", "", "| house | " + " | ".join(s for s in ALL if by[s]) + " |",
              "|---|" + "---|" * len([s for s in ALL if by[s]])]
    for h in houses:
        cells = []
        for s in ALL:
            if by[s]:
                rs = [r for r in by[s] if r["house_seed"] == h]
                cells.append(f"{sum(r['success'] for r in rs)}/{len(rs)}" if rs else "-")
        lines.append(f"| {h} | " + " | ".join(cells) + " |")
    lines.append("")

    agent_rows = [r for r in rows if r["setting"] != "wall"]
    if agent_rows:
        per_run = {s: statistics.mean(r["cost"] for r in by[s]) for s in agent.SETTINGS if by[s]}
        lines += ["## Cost projection", "",
                  "Mean cost per run in this batch, times the number of runs:", "",
                  "| setting | per run | 50 runs | 100 runs |", "|---|---|---|---|"]
        for s, c in per_run.items():
            lines.append(f"| {s} | {fmt_money(c)} | {fmt_money(50 * c)} | {fmt_money(100 * c)} |")
        allc = sum(per_run.values())
        lines += [f"| **all four** | {fmt_money(allc)} | {fmt_money(50 * allc)} | {fmt_money(100 * allc)} |", ""]

    warn = list(problems)
    for s in agent.SETTINGS:
        rs = by[s]
        if (rs and not args.fake and sum(r["calls"] for r in rs) > 0
                and sum(r["cache_read_input_tokens"] for r in rs) == 0):
            warn.append(f"{s}: no cache reads at all. Is the cached prefix below the model's minimum?")
    errs = [r for r in rows if r["outcome"] == "error"]
    for r in errs[:20]:
        warn.append(f"{r['run_id']}: {r['error']}")
    if len(errs) > 20:
        warn.append(f"... and {len(errs) - 20} more errors (see results.csv)")
    lines += ["## What went wrong", ""] + ([f"- {w}" for w in warn] if warn else ["Nothing."]) + [""]
    lines += ["## Files", "",
              "- `results.csv` / `results.jsonl`: one row per run",
              "- `notes.md`: the notebook agent's notes, in order",
              "- `<run>/transcript.jsonl`: everything sent and received; each call record holds "
              "only the text blocks that changed (`kept_blocks` = how many leading blocks are the "
              "same as in the previous call)",
              "- `<run>/replay.json`: open with `viewer.html`",
              "- `terminal.log`: everything printed", ""]
    (batch_dir / "summary.md").write_text("\n".join(lines))


def write_notes(batch_dir, run_ids):
    out = ["# What the notebook agent wrote", ""]
    for rid in run_ids:
        path = batch_dir / rid / "transcript.jsonl"
        if not rid.startswith("notebook") or not path.exists():
            continue
        recs = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        end = next((r for r in recs if r["type"] == "end"), {})
        out += [f"## {rid}: {end.get('outcome', '?')} after {end.get('steps', '?')} steps", ""]
        notes = [r for r in recs if r["type"] == "notes"]
        if not notes:
            out += ["(no notes written)", ""]
        for r in notes:
            out += [f"**after step {r['steps']}:**", "", "```", r["text"], "```", ""]
    (batch_dir / "notes.md").write_text("\n".join(out))


def bundle(batch_dir):
    path = batch_dir / "bundle.zip"
    tmp = batch_dir / "bundle.zip.tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(batch_dir.rglob("*")):
            if p.is_file() and p.name not in ("bundle.zip", "bundle.zip.tmp"):
                z.write(p, Path(batch_dir.name) / p.relative_to(batch_dir))
    os.replace(tmp, path)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True, help="batch name; files go to runs/<name>/")
    ap.add_argument("--settings", default=",".join(ALL),
                    help=f"comma-separated, from {','.join(ALL)}")
    ap.add_argument("--houses", type=int, default=5)
    ap.add_argument("--house-start", type=int, default=0)
    ap.add_argument("--runs-per-house", type=int, default=1)
    ap.add_argument("--steps", type=int, default=200, help="step limit (moves + turns)")
    ap.add_argument("--model", choices=agent.MODELS, default="haiku")
    ap.add_argument("--effort", choices=["low", "medium", "high"], default="medium")
    ap.add_argument("--workers", type=int, default=4, help="runs in parallel")
    ap.add_argument("--max-cost", type=float, default=5.0,
                    help="stop starting new runs once the batch has spent this many USD")
    ap.add_argument("--scan", choices=["sectors", "rays"], default="sectors",
                    help="what the model reads: 8 sectors (clear + farthest), or all 72 rays")
    ap.add_argument("--fake", action="store_true", help="scripted stand-in for the model: free")
    args = ap.parse_args()

    agent.SCAN_FORMAT = args.scan
    settings = [s.strip() for s in args.settings.split(",") if s.strip()]
    bad = [s for s in settings if s not in ALL]
    if bad:
        ap.error(f"unknown settings: {bad}")

    batch_dir = HERE / "runs" / args.name
    batch_dir.mkdir(parents=True, exist_ok=True)
    sys.stdout = Tee(batch_dir / "terminal.log")
    print(f"\n=== batch {args.name}, {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    print("command: " + " ".join(sys.argv))

    client = None
    if not args.fake and any(s != "wall" for s in settings):
        import anthropic
        client = anthropic.Anthropic(max_retries=6)   # reads ANTHROPIC_API_KEY
        # Check the key before anything runs. Counting tokens is free.
        try:
            client.messages.count_tokens(model=agent.MODELS[args.model][0],
                                         messages=[{"role": "user", "content": "hi"}])
        except anthropic.AuthenticationError as e:
            sys.exit(f"\nThe API rejected the key: {e}\nCheck ANTHROPIC_API_KEY. Nothing was run or spent.")
        except anthropic.APIConnectionError as e:
            sys.exit(f"\nCould not reach the API: {e}\nCheck the network. Nothing was run or spent.")
        except TypeError as e:   # the SDK found no credentials at all
            sys.exit("\nNo API key found in this terminal. Run\n"
                     "    export ANTHROPIC_API_KEY=...\n"
                     "in this same terminal (a new terminal window does not keep it), "
                     f"then the same command again. Nothing was run or spent.\n({e})")

    # House-major order, so an interrupted batch is still balanced across settings.
    jobs = []
    for h in range(args.house_start, args.house_start + args.houses):
        for rep in range(args.runs_per_house):
            for s in settings:
                if s == "wall" and rep > 0:
                    continue
                jobs.append((f"{s}-h{h:03d}-r{rep}", s, h, rep))

    results_path = batch_dir / "results.jsonl"
    done = {}
    if results_path.exists():
        for line in results_path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r["outcome"] == "error":
                    continue          # a failed run is tried again
                done[r["run_id"]] = r
    todo = [j for j in jobs if j[0] not in done]
    if done:
        print(f"resuming: {len(done)} runs already finished, {len(todo)} to go")
    print(f"{len(todo)} runs: settings {settings}, houses {args.house_start}.."
          f"{args.house_start + args.houses - 1}, step limit {args.steps}, "
          f"model {'FAKE' if args.fake else agent.MODELS[args.model][0]}, effort {args.effort}, scan {args.scan}, "
          f"cost cap ${args.max_cost:.2f}")

    lock = threading.Lock()
    spent = [sum(r["cost"] for r in done.values())]
    stop = threading.Event()
    problems = []
    errors_in_a_row = [0]

    def one(job):
        run_id, s, h, rep = job
        if stop.is_set():
            return None
        run_dir = batch_dir / run_id
        run_dir.mkdir(exist_ok=True)
        tpath = run_dir / "transcript.jsonl"
        tfile = open(tpath, "w")

        def log(rec):
            tfile.write(json.dumps(rec, default=str) + "\n")
            tfile.flush()

        house = sim.make_house(h)
        try:
            if s == "wall":
                row, replay = agent.run_wall_follower(house, h, args.steps, log=log)
            else:
                c = agent.FakeClient(hash((h, rep)) & 0xffff) if args.fake else client
                row, replay = agent.run_agent(c, s, house, h, args.steps, args.model,
                                              effort=args.effort, log=log, fake=args.fake,
                                              say=lambda m: print(f"  [{run_id}] {m}"))
        except Exception as e:  # noqa: BLE001
            row = {"setting": s, "house_seed": h, "noise_seed": h, "model": "?", "effort": args.effort,
                   "outcome": "error", "success": False, "steps": 0, "bumps": 0, "calls": 0,
                   "nudges": 0, "note_writes": 0, "note_reads": 0, "final_notes": "",
                   "input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0,
                   "cache_read_input_tokens": 0, "cost": 0.0, "seconds": 0,
                   "error": f"{type(e).__name__}: {e}"}
            replay = None
            log({"type": "crash", "traceback": traceback.format_exc()})
        finally:
            tfile.close()
        if replay is not None:
            (run_dir / "replay.json").write_text(json.dumps(replay))
        row = {"run_id": run_id, "rep": rep, **row}
        with lock:
            with open(results_path, "a") as f:
                f.write(json.dumps(row) + "\n")
            done[run_id] = row
            spent[0] += row["cost"]
            if row["outcome"] == "error":
                errors_in_a_row[0] += 1
            elif s != "wall":
                errors_in_a_row[0] = 0
            n_done = len(done)
            if spent[0] >= args.max_cost and not stop.is_set():
                stop.set()
                problems.append(f"Stopped early: the batch reached the cost cap "
                                f"(${spent[0]:.2f} >= ${args.max_cost:.2f}).")
            if errors_in_a_row[0] >= 5 and not stop.is_set():
                stop.set()
                problems.append("Stopped early: 5 agent runs in a row ended in an error "
                                f"(last: {row['error']}).")
        print(f"[{n_done}/{len(jobs)}] {run_id}: {row['outcome']} after {row['steps']} steps, "
              f"{row['bumps']} bumps, {row['calls']} calls, ${row['cost']:.4f} "
              f"(batch ${spent[0]:.3f})" + (f" - {row['error']}" if row["error"] else ""))
        return row

    interrupted = False
    try:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futures = [pool.submit(one, j) for j in todo]
            for f in as_completed(futures):
                f.result()
    except KeyboardInterrupt:
        interrupted = True
        stop.set()
        print("\ninterrupted: writing the summary for the finished runs")

    order = {j[0]: i for i, j in enumerate(jobs)}
    rows = sorted([r for r in done.values() if r["run_id"] in order], key=lambda r: order[r["run_id"]])
    with open(batch_dir / "results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    write_notes(batch_dir, [r["run_id"] for r in rows])
    summarize(batch_dir, rows, args, problems, interrupted or stop.is_set())
    print((batch_dir / "summary.md").read_text())
    for p in problems:
        print("WARNING: " + p)
    sys.stdout.flush()
    path = bundle(batch_dir)
    print(f"bundle: {path}")


if __name__ == "__main__":
    main()

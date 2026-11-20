# robot-agent: a robot agent with a small memory

Post 3's code. The agent loop is post 2's (`tiny-agent/step3_vision.py`), with
the shell tools swapped for a robot. The robot gets no map, no SLAM, no planner
and no odometry: only an 8-sector lidar scan after each action.

| file | what it is |
|---|---|
| `sim.py` | random floor plans (5 x 6 m, a few rooms, one exit), a Create 3-sized `SimRobot` with `move(m)` / `turn(deg)` and an 8-sector lidar |
| `wall_follower.py` | the baseline without a model: keep the wall on your right |
| `agent.py` | the agent loop, the four memory settings, cost per call, and `FakeClient`, a scripted stand-in for the model |
| `batch.py` | runs many runs and logs everything to `runs/<batch>/` |
| `viewer.html` | replays a run (`../assets/robot-agent/replay.js` is the same player for the blog) |
| `test_robot_agent.py` | free tests: `python3 -m pytest -q test_robot_agent.py` |

## The four memory settings

Every call is one fresh message, built from what the robot remembers: a list of
entries like `Step 12. You said: "..." You called move(0.5). Result: Moved 0.50 m. Scan: ...`.

- **goldfish**: the last action and its scan
- **window**: the last 10 actions
- **notebook**: the last 10 actions, plus a 500-character notebook it writes with `write_note` (and can read with `read_notes`); the notebook is also shown at the top of every message
- **full**: everything since the start

The model's own thinking from earlier calls is never sent back, in any setting.
What it remembers of its reasoning is what it said out loud.

Prompt caching: tools and system prompt are cached in every setting; then the
task (and notebook). Full history only ever appends, so it reads almost
everything back from the cache; the window changes every call, so it can't.

## Commands (run these yourself; they need `ANTHROPIC_API_KEY`)

From this folder (`robot-agent/`), with `pip install anthropic` done as in post 2.

**1. Smoke test, a few cents.** One house, 15 steps per setting. It checks that
the API accepts every request before anything bigger:

```bash
python3 batch.py --name smoke --houses 1 --steps 15 --max-cost 0.25
```

**2. Pilot batch: 5 runs per setting** (5 houses x 1 run), plus the wall follower.
It stops by itself if it spends more than $5:

```bash
python3 batch.py --name pilot --houses 5 --runs-per-house 1 --max-cost 5
```

Upload `runs/pilot/bundle.zip`. Its `summary.md` has a cost projection for the main batch.

**3. Main batch**, sized from the pilot. For example 20 houses x 5 runs = 100 runs per setting:

```bash
python3 batch.py --name main --houses 20 --runs-per-house 5 --max-cost 40
```

or, on a smaller budget, 10 houses x 3 runs = 30 runs per setting:

```bash
python3 batch.py --name main --houses 10 --runs-per-house 3 --max-cost 15
```

If a batch is interrupted (Ctrl+C, network), run the same command again: finished runs are skipped.
The last line printed is always the path of the bundle to upload.

Free versions of all of the above: add `--fake`.

## What every batch writes

`runs/<batch>/`:

- `summary.md`: results table (success rate with 95% CI, steps, bumps, cost per run and per success), how runs ended, tokens, per-house table, cost projection, and anything that went wrong
- `results.csv`, `results.jsonl`: one row per run
- `notes.md`: everything the notebook agent wrote, in order
- `<run>/transcript.jsonl`: the system prompt and tools, then every call (the request blocks that changed, the full reply, tokens, cached tokens, cost), every tool call and result with the true pose, every note, and the end
- `<run>/replay.json`: for `viewer.html`
- `terminal.log`: everything printed
- `bundle.zip`: all of it

## Setup details worth knowing

- Seeds: house `h` has floor-plan seed `h` and lidar-noise seed `h`, so repeated runs of one house differ only in what the model does.
- The robot never starts in the exit's room, so every run has to find at least one door first. (The pilot ran before this rule: 3 of its 5 houses started in the exit room.)
- Step limit: 200 actions (moves and turns) by default, the same for every setting.
- Success is judged by the simulator: the robot's centre leaves the outer wall. The run ends there. Calling `done` inside counts as a failure.
- The walls are 8 cm thick. With zero-thickness walls, a wall seen end-on can slip between two lidar rays: invisible, but solid.
- The wall follower is guaranteed to get out (every interior wall connects to the outer wall; `sim.check_house` verifies this for every house), but it is slow: it got out of all of the first 200 houses (median 170 steps, max 1075), but only 55% within 200 steps. The summary reports it with and without the step limit.

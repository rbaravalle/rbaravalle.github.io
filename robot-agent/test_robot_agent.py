"""
Tests that cost nothing:  python3 -m pytest -q test_robot_agent.py

The last group runs the real Anthropic SDK against a fake HTTP server (no key,
no network), to check the exact requests the paid runs will send.
"""
import json
import math
import subprocess
import sys
from pathlib import Path

import httpx2 as httpx   # the HTTP library the Anthropic SDK uses
import pytest

import agent
import sim
import wall_follower

HERE = Path(__file__).resolve().parent


# ---------------------------------------------------------------- the world

@pytest.mark.parametrize("seed", range(40))
def test_houses_are_valid(seed):
    h = sim.make_house(seed)
    assert h.width <= 5.0 and h.height <= 6.0
    assert 2 <= len(h.rooms) <= 4
    assert sim.check_house(h) == []


def test_same_seed_same_house():
    assert sim.make_house(7).to_json() == sim.make_house(7).to_json()
    assert sim.make_house(7).to_json() != sim.make_house(8).to_json()


def test_inside_readings_stay_below_lidar_range():
    """With the exit closed, no reading from inside the house is ever '>8 m'."""
    for seed in range(10):
        h = sim.make_house(seed)
        h.walls = h.walls + [h.exit]
        r = sim.SimRobot(h, seed)
        for k in range(30):
            r.turn(37)
            r.move(0.5)
            assert all(d is not None and d < sim.LIDAR_RANGE for d in r.scan())


def test_exit_shows_as_open_space():
    """Somewhere near the exit, looking out, the lidar reads '>8 m'."""
    h = sim.make_house(3)
    x1, y1, x2, y2 = h.exit
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    cx, cy = h.width / 2, h.height / 2
    r = sim.SimRobot(h, 0)
    # stand 0.5 m inside the exit, facing out
    d = math.hypot(mx - cx, my - cy)
    r.x, r.y = mx + (cx - mx) / d * 0.5, my + (cy - my) / d * 0.5
    r.heading = math.degrees(math.atan2(my - cy, mx - cx))
    assert r.scan()[0] is None


def test_move_stops_on_bump():
    h = sim.make_house(0)
    r = sim.SimRobot(h, 0)
    for _ in range(20):
        res = r.move(2.0)
        if res["bump"]:
            break
    assert res["bump"] and res["done"] < 2.0
    assert sim._clearance(h.walls, r.x, r.y) >= sim.ROBOT_RADIUS - 1e-9
    assert r.bumps >= 1


def test_commands_are_clamped():
    r = sim.SimRobot(sim.make_house(0), 0)
    assert r.turn(400)["done"] == 180.0
    res = r.move(-5)
    assert res["clamped"] and abs(res["done"]) <= sim.MAX_BACK


def test_scan_text_leaks_no_position():
    r = sim.SimRobot(sim.make_house(0), 0)
    text = agent.describe(r.move(0.3), 1, 200)
    assert "Scan:" in text
    assert f"{r.x:.2f}" not in text and f"{r.y:.2f}" not in text


@pytest.mark.parametrize("seed", range(12))
def test_wall_follower_gets_out_eventually(seed):
    r = sim.SimRobot(sim.make_house(seed), seed)
    wall_follower.run(r, 3000)
    assert r.outside


# ---------------------------------------------------------------- memory settings

def _entries(n, notes_at=None):
    """A run of n robot actions, as run_agent stores it."""
    out = [{"text": "Start. Scan: front 9.99 m", "robot_action": 0}]
    for i in range(1, n + 1):
        out.append({"robot_action": 1, "text": f"Step {i}. You called move(0.5). Result: "
                                               f"Moved 0.50 m.\nScan: front {i}.00 m"})
        if i == notes_at:
            out.append({"robot_action": 0, "text": "(Not an action.) You called write_note(5 "
                                                   "characters). Result: Notebook saved."})
    return out


def _texts(messages):
    assert len(messages) == 1 and messages[0]["role"] == "user"
    return [b["text"] for b in messages[0]["content"]]


def test_goldfish_sees_only_the_last_action():
    t = _texts(agent.build_messages("goldfish", _entries(25), ""))
    assert len(t) == 2 and "front 25.00 m" in t[1]
    assert "front 24.00 m" not in "".join(t)
    assert "Start." in "".join(_texts(agent.build_messages("goldfish", _entries(0), "")))


def test_goldfish_keeps_its_scan_after_a_non_action():
    t = "".join(_texts(agent.build_messages("goldfish", _entries(5, notes_at=5), "")))
    assert "front 5.00 m" in t and "write_note" in t


def test_window_keeps_last_ten_actions():
    t = "".join(_texts(agent.build_messages("window", _entries(25), "")))
    assert "front 16.00 m" in t and "front 15.00 m" not in t
    assert "Start." not in t and "forgotten" in t
    t = "".join(_texts(agent.build_messages("window", _entries(9), "")))
    assert "Start." in t and "forgotten" not in t


def test_window_counts_actions_not_note_calls():
    t = _texts(agent.build_messages("notebook", _entries(20, notes_at=15), "my notes"))
    assert len(t) == 1 + agent.WINDOW + 1          # head, 10 actions, the note call among them
    assert "my notes" in t[0]
    assert "my notes" not in "".join(_texts(agent.build_messages("window", _entries(20), "my notes")))


def test_full_history_only_appends():
    prev = None
    for n in range(0, 30):
        m = agent.add_cache_marks("full", agent.build_messages("full", _entries(n), ""))
        blocks = [{k: v for k, v in b.items() if k != "cache_control"} for b in m[0]["content"]]
        if prev is not None:
            assert blocks[:len(prev)] == prev
        prev = blocks
    assert len(prev) == 31


def test_cache_marks():
    for setting in agent.SETTINGS:
        m = agent.add_cache_marks(setting, agent.build_messages(setting, _entries(15), "n"))
        marked = [i for i, b in enumerate(m[0]["content"]) if "cache_control" in b]
        assert marked == ([len(m[0]["content"]) - 1] if setting == "full" else [0])
    raw = agent.build_messages("full", _entries(3), "")
    agent.add_cache_marks("full", raw)
    assert "cache_control" not in json.dumps(raw)    # marking never changes the original


def test_price():
    u = {"input_tokens": 50_000, "output_tokens": 0,
         "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    assert agent.price("haiku", u) == pytest.approx(50_000 * 0.10 / 1e6)
    u = {"input_tokens": 0, "output_tokens": 50_000,
         "cache_creation_input_tokens": 10_000, "cache_read_input_tokens": 30_000}
    assert agent.price("haiku", u) == pytest.approx((50_000 * 0.50 + 10_000 * 0.125
                                                     + 30_000 * 0.01) / 1e6)
    u = {"input_tokens": 200_000, "output_tokens": 0,     # over 100K: the long-prompt rate card
         "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    assert agent.price("haiku", u) == pytest.approx(200_000 * 0.50 / 1e6)


# ---------------------------------------------------------------- fake model runs

@pytest.mark.parametrize("setting", agent.SETTINGS)
def test_fake_runs_every_setting(setting):
    recs = []
    row, replay = agent.run_agent(agent.FakeClient(1), setting, sim.make_house(2), 2, 60,
                                  fake=True, log=recs.append)
    assert row["outcome"] in ("success", "step_limit"), row
    assert row["error"] is None
    assert row["steps"] == len(replay["steps"])
    assert recs[0]["type"] == "header" and recs[-1]["type"] == "end"
    calls = [r for r in recs if r["type"] == "call"]
    assert len(calls) == row["calls"]
    assert sum(c["cost"] for c in calls) == pytest.approx(row["cost"], abs=1e-6)
    if setting == "notebook":
        assert row["note_writes"] > 0 and row["final_notes"]
    if setting == "full":
        assert row["cache_read_input_tokens"] > row["input_tokens"]


def test_done_inside_is_a_failure():
    class Quitter(agent.FakeClient):
        def create(self, **kw):
            r = super().create(**kw)
            from types import SimpleNamespace
            r.content = [SimpleNamespace(type="tool_use", id="q", name="done", input={})]
            r.stop_reason = "tool_use"
            return r
    row, _ = agent.run_agent(Quitter(0), "full", sim.make_house(0), 0, 50, fake=True)
    assert row["outcome"] == "done_inside" and not row["success"]


def test_fake_batch_writes_every_file(tmp_path):
    name = "pytest-fake"
    out = subprocess.run([sys.executable, str(HERE / "batch.py"), "--name", name, "--houses", "2",
                          "--fake", "--steps", "40", "--workers", "2"],
                         capture_output=True, text=True, timeout=600, cwd=HERE)
    assert out.returncode == 0, out.stderr
    last = out.stdout.strip().splitlines()[-1]
    assert last.startswith("bundle: ") and last.endswith("bundle.zip")
    d = HERE / "runs" / name
    for f in ("summary.md", "results.csv", "results.jsonl", "notes.md", "terminal.log", "bundle.zip"):
        assert (d / f).exists(), f
    import zipfile
    names = zipfile.ZipFile(d / "bundle.zip").namelist()
    assert any(n.endswith("transcript.jsonl") for n in names)
    assert any(n.endswith("replay.json") for n in names)
    assert "| full |" in (d / "summary.md").read_text()
    import shutil
    shutil.rmtree(d)


# ---------------------------------------------------------------- the real SDK, fake server

class FakeServer:
    """Answers POST /v1/messages like the API would, and keeps every request."""

    def __init__(self):
        self.requests = []
        self.policy = agent.FakeClient(0)

    def __call__(self, request):
        body = json.loads(request.content)
        self.requests.append(body)
        # Let the scripted policy choose the action, then wrap it as API JSON.
        r = self.policy.create(model=body["model"], max_tokens=body["max_tokens"],
                               system=body["system"], tools=body["tools"],
                               messages=body["messages"])
        content = []
        for b in r.content:
            d = agent.to_jsonable(b)
            if d["type"] == "thinking":
                d = {"type": "thinking", "thinking": "", "signature": f"sig-{len(self.requests)}"}
            content.append(d)
        return httpx.Response(200, json={
            "id": f"msg_{len(self.requests)}", "type": "message", "role": "assistant",
            "model": body["model"], "content": content, "stop_reason": r.stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 100, "output_tokens": 50,
                      "cache_creation_input_tokens": 10, "cache_read_input_tokens": 1000}})


@pytest.mark.parametrize("setting", agent.SETTINGS)
def test_real_sdk_requests(setting):
    import anthropic
    server = FakeServer()
    client = anthropic.Anthropic(api_key="test-key",
                                 http_client=httpx.Client(transport=httpx.MockTransport(server)))
    row, _ = agent.run_agent(client, setting, sim.make_house(2), 2, 25, model="haiku")
    assert row["error"] is None, row["error"]
    assert row["calls"] == len(server.requests) > 0
    assert row["cost"] == pytest.approx(row["calls"] * agent.price("haiku", {
        "input_tokens": 100, "output_tokens": 50,
        "cache_creation_input_tokens": 10, "cache_read_input_tokens": 1000}))
    for body in server.requests:
        assert body["model"] == "claude-haiku-5-5"
        assert body["tool_choice"] == {"type": "auto", "disable_parallel_tool_use": True}
        assert body["output_config"] == {"effort": "medium"}
        assert "temperature" not in body and "thinking" not in body
        assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
        assert {t["name"] for t in body["tools"]} >= {"move", "turn", "done"}
        assert ("write_note" in {t["name"] for t in body["tools"]}) == (setting == "notebook")
        assert len([1 for m in body["messages"] for b in m["content"]
                    if isinstance(b, dict) and "cache_control" in b]) <= 3
    # the stable parts never change between calls
    assert all(b["system"] == server.requests[0]["system"] for b in server.requests)
    assert all(b["tools"] == server.requests[0]["tools"] for b in server.requests)
    # One user message per call; the model's thinking is never sent back.
    for body in server.requests:
        assert len(body["messages"]) == 1
        assert '"thinking"' not in json.dumps(body["messages"])
    if setting == "full":
        # Append-only: each request starts with the previous one (cache marks aside).
        def strip(msgs):
            return [{k: v for k, v in b.items() if k != "cache_control"} for b in msgs[0]["content"]]
        for a, b in zip(server.requests, server.requests[1:]):
            assert strip(b["messages"])[:len(a["messages"][0]["content"])] == strip(a["messages"])


@pytest.mark.parametrize("seed", range(40))
def test_start_is_not_in_the_exit_room(seed):
    h = sim.make_house(seed)
    x, y, _ = h.start
    mx, my = (h.exit[0] + h.exit[2]) / 2, (h.exit[1] + h.exit[3]) / 2
    room = next(r for r in h.rooms if r[0] <= x <= r[2] and r[1] <= y <= r[3])
    assert not (room[0] - 1e-6 <= mx <= room[2] + 1e-6 and room[1] - 1e-6 <= my <= room[3] + 1e-6)

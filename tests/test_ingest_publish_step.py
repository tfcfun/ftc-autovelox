"""The publish step must survive losing a push race.

The snapshot is a pure function of what a run fetched -- it is not a patch on
top of another run's snapshot. So when two ingests overlap and one pushes
first, there is nothing to merge: the loser must simply re-apply its own output
on top of the new tip.

`git pull --rebase` cannot do that. On 2026-08-24 two runs both produced the
first-ever data/2026-W35/ directory; the loser's rebase hit
`CONFLICT (add/add): data/2026-W35/index.json`, which has no automatic
resolution, and the run died with exit 1 holding a finished snapshot.

These tests drive the real `Commit snapshot` script out of the workflow file
against a real git remote, so they fail if that recovery regresses.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ingest.yml"


def publish_script() -> str:
    """Lift the `Commit snapshot` step's shell body out of the workflow."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if re.match(r"\s*- name:\s*Commit snapshot\s*$", line):
            break
    else:  # pragma: no cover - guarded by test_publish_step_exists
        raise AssertionError("no 'Commit snapshot' step in ingest.yml")

    for j in range(i + 1, len(lines)):
        m = re.match(r"(\s*)run:\s*\|\s*$", lines[j])
        if m:
            indent = len(m.group(1)) + 2
            body = []
            for line in lines[j + 1:]:
                if line.strip() and len(line) - len(line.lstrip()) < indent:
                    break
                body.append(line[indent:] if len(line) >= indent else line)
            return "\n".join(body).rstrip() + "\n"
    raise AssertionError("'Commit snapshot' step has no 'run: |' block")


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def write_snapshot(repo: Path, week: str, marker: str) -> None:
    """Stand in for velox.publish.write_snapshot: a week dir plus data/latest."""
    for folder in (repo / "data" / week, repo / "data" / "latest"):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "index.json").write_text(
            json.dumps({"week": week, "produced_by": marker}), encoding="utf-8"
        )
    cache = repo / "cache" / "segments"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "seg.json").write_text(f'{{"by": "{marker}"}}', encoding="utf-8")


@pytest.fixture
def race(tmp_path: Path):
    """A remote that already holds one week, plus two clones about to collide."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)],
                   check=True, capture_output=True)

    seed = tmp_path / "seed"
    subprocess.run(["git", "clone", str(origin), str(seed)],
                   check=True, capture_output=True)
    git("config", "user.email", "seed@example.com", cwd=seed)
    git("config", "user.name", "seed", cwd=seed)
    # A previous week that must still be on the branch afterwards.
    write_snapshot(seed, "2026-W34", "seed")
    (seed / "README.md").write_text("velox\n", encoding="utf-8")
    git("add", "-A", cwd=seed)
    git("commit", "-m", "seed", cwd=seed)
    git("push", "origin", "main", cwd=seed)

    # Two runs check out the same commit, then both produce a brand-new week.
    winner, loser = tmp_path / "winner", tmp_path / "loser"
    for clone in (winner, loser):
        subprocess.run(["git", "clone", str(origin), str(clone)],
                       check=True, capture_output=True)

    write_snapshot(winner, "2026-W35", "winner")
    git("add", "-A", cwd=winner)
    git("-c", "user.email=w@e.com", "-c", "user.name=w", "commit", "-m",
        "data: snapshot winner", cwd=winner)
    git("push", "origin", "main", cwd=winner)

    write_snapshot(loser, "2026-W35", "loser")
    return origin, loser


def run_publish(repo: Path):
    return subprocess.run(
        ["bash", "-e", "-c", publish_script()],
        cwd=repo, capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
             "HOME": str(repo), "GITHUB_REF_NAME": "main", "BRANCH": "main"},
    )


def test_publish_step_exists():
    assert "git push" in publish_script()


def test_loser_of_a_push_race_still_publishes(race):
    """The add/add on a first-ever data/<week>/ must not kill the run."""
    origin, loser = race
    result = run_publish(loser)
    assert result.returncode == 0, (
        "publish step failed after losing a push race:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    checkout = origin.parent / "verify"
    subprocess.run(["git", "clone", str(origin), str(checkout)],
                   check=True, capture_output=True)
    published = json.loads((checkout / "data" / "latest" / "index.json").read_text())
    assert published["produced_by"] == "loser", (
        "the run that finished last must win: its snapshot is the newer read of "
        "the source, not a patch to be merged into the earlier one"
    )


def test_push_race_recovery_keeps_earlier_weeks(race):
    """Re-applying this run's output must not wipe the branch's history."""
    origin, loser = race
    assert run_publish(loser).returncode == 0

    checkout = origin.parent / "verify_history"
    subprocess.run(["git", "clone", str(origin), str(checkout)],
                   check=True, capture_output=True)
    assert (checkout / "data" / "2026-W34" / "index.json").exists(), (
        "data/2026-W34 was destroyed; only the week this run generates may be "
        "overwritten, never the archive"
    )
    assert (checkout / "README.md").exists(), "a file outside data/ was reverted"


@pytest.fixture
def solo(tmp_path: Path):
    """A clone with nobody else pushing -- the ordinary case."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)],
                   check=True, capture_output=True)
    seed = tmp_path / "seed"
    subprocess.run(["git", "clone", str(origin), str(seed)],
                   check=True, capture_output=True)
    git("config", "user.email", "seed@example.com", cwd=seed)
    git("config", "user.name", "seed", cwd=seed)
    write_snapshot(seed, "2026-W34", "seed")
    git("add", "-A", cwd=seed)
    git("commit", "-m", "seed", cwd=seed)
    git("push", "origin", "main", cwd=seed)

    run = tmp_path / "run"
    subprocess.run(["git", "clone", str(origin), str(run)],
                   check=True, capture_output=True)
    return origin, run


def test_uncontested_push_publishes(solo):
    origin, run = solo
    write_snapshot(run, "2026-W35", "run")
    result = run_publish(run)
    assert result.returncode == 0, result.stderr

    checkout = origin.parent / "verify_solo"
    subprocess.run(["git", "clone", str(origin), str(checkout)],
                   check=True, capture_output=True)
    published = json.loads((checkout / "data" / "latest" / "index.json").read_text())
    assert published["produced_by"] == "run"
    assert (checkout / "data" / "2026-W35" / "index.json").exists()


def test_unchanged_data_publishes_nothing(solo):
    """A rerun that finds the same data must not push an empty churn commit."""
    origin, run = solo
    before = git("rev-parse", "HEAD", cwd=run)
    result = run_publish(run)
    assert result.returncode == 0, result.stderr
    assert "no change to publish" in result.stdout
    assert git("rev-parse", "HEAD", cwd=run) == before, "committed with nothing to say"

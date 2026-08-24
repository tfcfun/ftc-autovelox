"""The ingest schedule must survive a late Monday republication.

The Polizia di Stato republishes the weekly PDFs at a variable time on Monday
morning, not at a fixed hour. Verified against the live feed:

  * Mon 2026-08-17 -- the 06:39 and 07:57 UTC runs BOTH still read the previous
    week (valid 2026-08-10 -> 2026-08-16). The new week only landed on the
    Tuesday 07:54 run.
  * Mon 2026-08-24 -- the 06:41 UTC run still read 2026-08-17 -> 2026-08-23,
    yet the live Lombardia PDF already read "Validita da lunedi 24 agosto" when
    checked at 07:54 UTC.

When the run lands before the republication, data/latest carries an expired
programme for the rest of the day. The app clamps its date picker to the
published validity window -- correctly, since offering an uncovered day would
show "no checks" where the truth is "not published" -- so the newest day it can
offer is the previous Sunday. That is the "it gives me yesterday's data"
symptom, and it repeats every Monday.

One retry an hour after the weekly run is not enough, because the republication
time varies. The next attempt must not be a whole day later.
"""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ingest.yml"

# The hours the app is expected to be usable on a Monday. The republication has
# been observed as late as after 07:57 UTC, so cover the whole morning and the
# early afternoon rather than betting on a single hour.
REQUIRED_MONDAY_HOURS = set(range(6, 13))

MONDAY = 1


def _expand(field: str, lo: int, hi: int) -> set[int]:
    """Expand one cron field into the set of values it matches."""
    values: set[int] = set()
    for part in field.split(","):
        step = 1
        if "/" in part:
            part, _, raw_step = part.partition("/")
            step = int(raw_step)
        if part == "*":
            start, end = lo, hi
        elif "-" in part:
            raw_start, _, raw_end = part.partition("-")
            start, end = int(raw_start), int(raw_end)
        else:
            start = end = int(part)
        values.update(range(start, end + 1, step))
    return values


def _crons() -> list[str]:
    text = WORKFLOW.read_text(encoding="utf-8")
    return re.findall(r"""^\s*-\s*cron:\s*['"]([^'"]+)['"]""", text, re.MULTILINE)


def monday_hours() -> set[int]:
    """Every UTC hour at which some schedule entry fires on a Monday."""
    hours: set[int] = set()
    for expr in _crons():
        _minute, hour, _dom, _month, dow = expr.split()
        if MONDAY not in _expand(dow, 0, 6):
            continue
        hours |= _expand(hour, 0, 23)
    return hours


def test_workflow_declares_schedules():
    assert _crons(), "ingest.yml declares no cron schedule at all"


def test_monday_retries_cover_the_republication_window():
    missing = sorted(REQUIRED_MONDAY_HOURS - monday_hours())
    assert not missing, (
        "no ingest attempt at "
        + ", ".join(f"{h:02d}:00 UTC" for h in missing)
        + " on Monday. The Polizia republish at a variable time that morning, so"
        " a gap here leaves data/latest on the expired previous week and the app"
        " can only offer days up to the previous Sunday."
    )


def test_a_daily_retry_still_exists():
    """A Monday-only schedule would cost a week if the Monday runs all failed."""
    every_day = [
        expr for expr in _crons() if _expand(expr.split()[4], 0, 6) == set(range(7))
    ]
    assert every_day, "no every-day retry left; a bad Monday would cost a whole week"

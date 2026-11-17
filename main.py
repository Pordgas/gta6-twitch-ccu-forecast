"""Forecast GTA VI's launch-day Twitch viewers hour by hour (gta6-twitch-ccu-forecast-01).

The entrypoint the grader runs: `python3 -P -s /bot/main.py` (PYTHONHASHSEED=0),
Python 3.13, standard library only: no network, no pip packages, fully
deterministic. It reads every <id>.in in the input directory (MAKEFUN_INPUT_DIR
or /input) and writes <id>.out to the output directory (MAKEFUN_OUTPUT_DIR or
/output): {"hours": [{"hour": 2, "q": [q05, q25, q50, q75, q95]}, ...]} for
hours 2..24 of the release day.

Approach (scale-free, learned from the case's own comparables)
-------------------------------------------------------------
A launch day's shape is a ratio to its first hour, not an absolute level:
hour 1 is 00:00-01:00 UTC, when only New Zealand, Australia, central Europe
and the UK have unlocked; the US East unlocks at 05:00Z and the US West at
08:00Z, so a console launch that unlocks at local midnight typically dips in
the small hours and then climbs to a peak in the US afternoon/evening. But
how much it climbs depends on how big hour 1 already is: across past
launches the log-ratio log(v_h / v_1) falls steeply with log(v_1) -- a launch
whose first hour is already enormous has little headroom left, while a small
first hour leaves room to grow several-fold. The two effects are fit
together, per hour, on the launches most like this one:

1. Train on the case's comparables that are console-only launches with a
   rolling midnight-local unlock (no PC, no simultaneous global unlock, no
   early access): the same unlock pattern as GTA VI, which is PS5/Xbox only,
   rolling midnight, no early access. The Grand Theft Auto VI category's own
   pre-release history is not a launch day and is left out.
2. For each hour h = 2..24, regress log(v_h / v_1) on log(v_1) across those
   launches (ordinary least squares), and take the median as the fitted value
   at this case's hour-1 print, with the slope shrunk 20% toward zero (only
   a handful of launches train it, so the raw slope overfits) and clipped to
   the log-ratios actually seen that hour, so an hour-1 print far beyond any
   past launch saturates at the flattest shape seen rather than extrapolating
   to a decline no launch showed.
3. The spread is the residual standard deviation of that regression at the
   hour, inflated 1.5x: with so few launches the residuals understate how
   far the next launch can sit from the line. Quantiles are then
   q_tau = p1 * exp(median + z_tau * spread), z the normal quantiles.

Fallbacks keep every case valid: if fewer than three console-only launches
are usable, the same regression runs on every usable comparable; if fewer
than three comparables are usable at all, the per-hour median log-ratio over
them is used with its own spread; if there is nothing usable, the program
falls back to the house persistence baseline. A missing or zero hour-1 print
falls back to the last pre-checkpoint hourly point, then to 1.
"""

import json
import math
import os
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first, so a module
# shipped beside this file would import. (This entry is one file.)
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# The quantile levels the contest scores, in the order each row lists them.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# The standard normal's quantile at each level.
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]

# Slope shrinkage: the per-hour regression trains on a handful of launches,
# so its slope is pulled 20% toward zero (a flatter, safer scale effect).
SLOPE_SHRINK = 0.8
# Spread inflation: the residual spread of a few launches understates the
# next launch's spread, so it is widened 1.5x.
SPREAD_MULT = 1.5
# A spread never collapses below this, in log units.
MIN_SPREAD = 0.05
# The persistence baseline's spread, per square-root hour, used only when
# no training data exists for an hour at all.
BASE_SIGMA = 0.15
# Minimum launches needed to fit the scale regression.
MIN_TRAIN = 3


def round2(x: float) -> float | int:
    """x rounded to 2 decimals, half up, as JavaScript's Math.round(x * 100) / 100 rounds it.

    A whole number comes back as an int, so json.dumps writes 1240 where
    JavaScript writes 1240 (not 1240.0).
    """
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


def parse_ts(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def release_day(comp: dict) -> dict:
    """{hour: viewers} for hours 1..24 of a comparable's release day.

    Hours come from `from` relative to the comparable's own `day_start`;
    hours with no point or no viewers are left out.
    """
    try:
        day_start = parse_ts(comp["day_start"])
    except (KeyError, TypeError, ValueError):
        return {}
    out = {}
    for row in comp.get("hourly") or []:
        try:
            when = parse_ts(row["from"])
            viewers = row["viewers"]
        except (KeyError, TypeError, ValueError):
            continue
        if viewers is None or viewers <= 0:
            continue
        hour = int((when - day_start).total_seconds() // 3600) + 1
        if 1 <= hour <= 24:
            out[hour] = viewers
    return out


def is_console_rolling(comp: dict) -> bool:
    """True for a console-only launch with a rolling midnight-local unlock.

    That is the unlock pattern of this contest's game (PS5/Xbox only, rolling
    midnight, no early access, no PC), so these are the launches whose
    release-day shape the forecast learns from. The Grand Theft Auto VI
    category's own pre-release history is not a launch day and is excluded.
    """
    name = (comp.get("name") or "").lower()
    if "grand theft auto vi" in name:
        return False
    tokens = set(re.split(r"[^a-z0-9]+", (comp.get("platforms") or "").lower())) - {""}
    if "pc" in tokens:
        return False
    if not tokens & {"ps4", "ps5", "xbox", "switch"}:
        return False
    unlock = (comp.get("unlock") or "").lower()
    if "early-access-contaminated" in unlock or "tier: weak" in unlock:
        return False
    if "midnight local" in unlock or "rolling" in unlock:
        return True
    if "simultaneous" in unlock or "single global" in unlock:
        return False
    # An unverified unlock on a Sony / Nintendo / Microsoft-only launch: the
    # first-party norm is a rolling midnight-local unlock.
    return tokens <= {"ps4", "ps5", "xbox", "switch", "only"}


def _ols(xs: list, ys: list) -> tuple:
    """Ordinary least squares of ys on xs: (intercept, slope, mean_x, mean_y)."""
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx <= 0:
        return mean_y, 0.0, mean_x, mean_y
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / sxx
    return mean_y - slope * mean_x, slope, mean_x, mean_y


def fit_scale_model(days: list) -> dict:
    """Per-hour regression of log(v_h / v_1) on log(v_1) over launch days.

    days: [{hour: viewers}, ...], each with hour 1 present. Returns
    {hour: (intercept, slope, mean_x, mean_y, resid_sd, lo, hi)} for the
    hours with at least MIN_TRAIN launches carrying that hour.
    """
    model = {}
    for hour in range(2, 25):
        points = [
            (math.log(day[1]), math.log(day[hour] / day[1]))
            for day in days
            if hour in day
        ]
        if len(points) < MIN_TRAIN:
            continue
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        intercept, slope, mean_x, mean_y = _ols(xs, ys)
        residuals = [y - (intercept + slope * x) for x, y in points]
        sd = statistics.pstdev(residuals) if len(residuals) > 1 else 0.5
        model[hour] = (intercept, slope, mean_x, mean_y, sd, min(ys), max(ys))
    return model


def median_curve(days: list) -> dict:
    """Fallback shape: per-hour (median log-ratio, spread) over launch days."""
    out = {}
    for hour in range(2, 25):
        vals = sorted(math.log(day[hour] / day[1]) for day in days if hour in day)
        if not vals:
            continue
        median = statistics.median(vals)
        sd = statistics.pstdev(vals) if len(vals) > 1 else 0.5
        out[hour] = (median, sd)
    return out


def hour_quantiles(p1: float, hour: int, model: dict, medians: dict) -> list:
    """The five quantiles of hour `hour`'s count, around hour 1's print."""
    log_p1 = math.log(max(p1, 1))
    if hour in model:
        _intercept, slope, mean_x, mean_y, sd, lo, hi = model[hour]
        median = mean_y + SLOPE_SHRINK * slope * (log_p1 - mean_x)
        median = min(max(median, lo), hi)
        spread = max(sd, MIN_SPREAD) * SPREAD_MULT
    elif hour in medians:
        median, sd = medians[hour]
        spread = max(sd, MIN_SPREAD) * SPREAD_MULT
    else:
        # No training data for this hour at all: stay at hour 1's print,
        # with the house baseline's widening spread.
        median = 0.0
        spread = BASE_SIGMA * math.sqrt(hour - 1)
    quantiles = []
    previous = 0.0
    for z in Z:
        q = p1 * math.exp(median + z * spread)
        q = min(max(q, 1.0), 1e9)
        q = round2(q)
        # Rounding must never break the non-decreasing order.
        if q < previous:
            q = previous
        quantiles.append(q)
        previous = q
    return quantiles


def hour1_print(case: dict) -> float:
    """Hour 1's print, or the last pre-checkpoint hourly point, or 1."""
    for row in case.get("known") or []:
        if row.get("hour") == 1 and row.get("viewers"):
            return max(1, row["viewers"])
    history = case.get("history_hourly") or []
    if history and history[-1].get("viewers"):
        return max(1, history[-1]["viewers"])
    return 1


def forecast_case(case: dict, name: str) -> dict:
    if case.get("levels") != LEVELS:
        raise ValueError(f"{name} asks for levels {case.get('levels')}, not {LEVELS}")
    p1 = hour1_print(case)
    days = []
    for comp in case.get("comparables") or []:
        if "grand theft auto vi" in (comp.get("name") or "").lower():
            continue
        day = release_day(comp)
        if 1 in day and len(day) >= 2:
            days.append((comp, day))
    console = [day for comp, day in days if is_console_rolling(comp)]
    train = console if len(console) >= MIN_TRAIN else [day for _comp, day in days]
    model = fit_scale_model(train) if len(train) >= MIN_TRAIN else {}
    medians = median_curve(train)
    # The output must hold exactly hours 2..24, each once. Take the hours
    # from the case's forecast list when it covers exactly that, and fall
    # back to the full range otherwise, so a malformed list can never make
    # the output malformed.
    wanted = [row["hour"] for row in case.get("forecast") or []]
    hours = sorted(wanted) if sorted(wanted) == list(range(2, 25)) else list(range(2, 25))
    return {
        "hours": [
            {"hour": hour, "q": hour_quantiles(p1, hour, model, medians)}
            for hour in hours
        ]
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()

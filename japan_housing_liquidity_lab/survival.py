"""Small Kaplan-Meier reference baseline; no external dependencies."""
from collections import defaultdict
import math
import random


def synthetic_listings(n=500, seed=42):
    """Independent exponential event/censor clocks; prices are illustrative only."""
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ValueError("n must be a positive integer")
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        event_time = rng.expovariate(1 / 90)
        censor_time = rng.uniform(30, 180)
        rows.append({
            "listing_id": f"SYN-{i:06d}",
            "duration_days": min(event_time, censor_time),
            "event_observed": int(event_time <= censor_time),
            "asking_price_jpy": rng.randrange(2000, 9000) * 10000,
        })
    return rows


def kaplan_meier(durations, events):
    """Right-censored KM. Tied censors remain at risk for tied events."""
    durations, events = list(durations), list(events)
    if not durations or len(durations) != len(events):
        raise ValueError("nonempty equal-length durations and events required")
    groups = defaultdict(lambda: [0, 0])
    for duration, event in zip(durations, events):
        if not math.isfinite(duration) or duration < 0:
            raise ValueError("durations must be finite and nonnegative")
        if event not in (0, 1):
            raise ValueError("events must be 0 or 1")
        groups[float(duration)][0 if event else 1] += 1
    at_risk, survival = len(durations), 1.0
    curve = []
    for time, (deaths, censored) in sorted(groups.items()):
        survival *= 1 - deaths / at_risk
        curve.append({"time_days": time, "at_risk": at_risk,
                      "events": deaths, "censored": censored,
                      "survival": survival})
        at_risk -= deaths + censored
    return curve


def survival_at(curve, time):
    """Return S(time) within observed follow-up; never extrapolate its tail."""
    if not curve or not math.isfinite(time) or time < 0:
        raise ValueError("valid curve and finite nonnegative time required")
    if time > curve[-1]["time_days"]:
        raise ValueError("time exceeds observed follow-up")
    value = 1.0
    for row in curve:
        if row["time_days"] > time:
            break
        value = row["survival"]
    return value


def conditional_risk(curve, age, horizon):
    """P(T <= age+horizon | T > age) = 1 - S(age+horizon)/S(age)."""
    if not math.isfinite(horizon) or horizon < 0:
        raise ValueError("horizon must be finite and nonnegative")
    base = survival_at(curve, age)
    future = survival_at(curve, age + horizon)
    if base == 0:
        raise ValueError("no survivors at conditioning age")
    return 1 - future / base

"""The trade signal. Deliberately simple — an SMA crossover — because the
point of this project is the risk layer around the signal, not the signal
itself. Swap this out; risk_rules.py and agent.py don't change."""


def sma(closes: list[float], window: int) -> float | None:
    if len(closes) < window:
        return None
    return sum(closes[-window:]) / window


def signal(bars: list[dict], short_window: int = 5, long_window: int = 15) -> dict:
    """Returns the signal plus the SMA values that produced it, so the
    decision log can show the actual numbers behind 'long' or 'flat'
    instead of just the label."""
    closes = [bar["c"] for bar in bars]
    short = sma(closes, short_window)
    long = sma(closes, long_window)

    if short is None or long is None:
        return {"direction": "flat", "reason": "not enough bars for SMA window", "sma_short": short, "sma_long": long}

    direction = "long" if short > long else "flat"
    return {"direction": direction, "sma_short": round(short, 2), "sma_long": round(long, 2)}

"""Thin subprocess wrapper around the `alpaca` CLI binary.

Every call to Alpaca goes through the exact same binary you'd run by hand at
the terminal — there's no separate SDK code path with its own bugs. Anything
you can verify by typing the command yourself is exactly what the agent did,
which matters when you're debugging a scheduled run you didn't watch live.
"""

import json
import subprocess
from datetime import date, timedelta


class AlpacaCLIError(RuntimeError):
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


def _run(*args: str) -> dict | list:
    result = subprocess.run(["alpaca", *args], capture_output=True, text=True)
    if result.returncode != 0:
        # The CLI writes its JSON error body to stderr when stdout isn't a
        # TTY (i.e. every time this runs from a subprocess) — checking both
        # streams is what makes get_position()'s 404-as-None translation work.
        raw = result.stdout.strip() or result.stderr.strip()
        try:
            err = json.loads(raw)
            raise AlpacaCLIError(err.get("error", raw), code=err.get("code"))
        except json.JSONDecodeError:
            raise AlpacaCLIError(raw)
    return json.loads(result.stdout)


def get_account() -> dict:
    return _run("account", "get")


def get_positions() -> list[dict]:
    return _run("position", "list")


def get_position(symbol: str) -> dict | None:
    """Alpaca returns HTTP 404 / code 40410000 when there's no open position —
    that's not a failure, it's the normal "flat" state, so it's translated to None
    rather than left as an exception the caller has to know to catch."""
    try:
        return _run("position", "get", "--symbol-or-asset-id", symbol)
    except AlpacaCLIError as e:
        if e.code == 40410000:
            return None
        raise


def get_recent_bars(symbol: str, lookback_days: int = 30, timeframe: str = "1Day", limit: int = 20) -> list[dict]:
    start = (date.today() - timedelta(days=lookback_days)).isoformat()
    data = _run(
        "data", "bars",
        "--symbol", symbol,
        "--timeframe", timeframe,
        "--start", start,
        "--limit", str(limit),
    )
    return data.get("bars", [])


def get_latest_trade_price(symbol: str) -> float:
    data = _run("data", "latest-trade", "--symbol", symbol)
    return float(data["trade"]["p"])


def submit_bracket_order(
    symbol: str,
    qty: int,
    side: str,
    stop_price: float,
    take_profit_price: float,
    client_order_id: str,
    dry_run: bool,
) -> dict:
    """A bracket order, not a plain market order: entry + stop-loss + take-profit
    submitted as one unit. Alpaca requires both legs once --stop-loss is set
    (a stop-only "oto" order is rejected server-side) — confirmed against the
    live paper API, not assumed from docs. That's a feature here, not a
    workaround: every entry this agent makes already has its exit defined."""
    args = [
        "order", "submit",
        "--symbol", symbol,
        "--side", side,
        "--qty", str(qty),
        "--type", "market",
        "--time-in-force", "day",
        "--order-class", "bracket",
        "--stop-loss", str(stop_price),
        "--take-profit", str(take_profit_price),
        "--client-order-id", client_order_id,
    ]
    if dry_run:
        args.append("--dry-run")
    return _run(*args)

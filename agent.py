"""Single-shot entry point, meant to be invoked by cron every N minutes
during market hours — not a long-running loop. Each run re-derives the
account's current state from Alpaca and re-decides from scratch; nothing
about "what did I decide last run" is trusted from memory, only from the
decision log and the account/position state Alpaca itself reports.
"""

import json
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from alpaca_cli import get_account, get_position, get_recent_bars, get_latest_trade_price, submit_bracket_order
from decision_log import log_decision
from risk_rules import (
    RiskLimits,
    breaches_concentration_limit,
    breaches_daily_loss_limit,
    position_size,
    stop_loss_price,
    take_profit_price,
)
from strategy import signal

WATCHLIST_PATH = Path(__file__).parent / "watchlist.json"
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() != "false"


def run() -> None:
    limits = RiskLimits()
    watchlist = json.loads(WATCHLIST_PATH.read_text())

    account = get_account()
    equity = float(account["equity"])
    last_equity = float(account["last_equity"])
    daily_halt = breaches_daily_loss_limit(equity, last_equity, limits)

    for symbol in watchlist:
        decision = {"symbol": symbol, "equity": equity, "dry_run": DRY_RUN}

        if daily_halt:
            decision.update(action="skip", reason="daily loss limit breached — no new entries today")
            log_decision(decision)
            print(f"{symbol}: SKIP (daily loss limit breached)")
            continue

        bars = get_recent_bars(symbol)
        sig = signal(bars)
        decision["signal"] = sig

        existing_position = get_position(symbol)
        if existing_position is not None:
            decision.update(action="skip", reason="position already open")
            log_decision(decision)
            print(f"{symbol}: SKIP (position already open)")
            continue

        if sig["direction"] != "long":
            decision.update(action="skip", reason="no long signal (SMA short <= SMA long)")
            log_decision(decision)
            print(f"{symbol}: SKIP (no long signal)")
            continue

        entry_price = get_latest_trade_price(symbol)
        stop = stop_loss_price(entry_price, limits)
        take_profit = take_profit_price(entry_price, stop, limits)
        qty = position_size(equity, entry_price, stop, limits)

        risk_math = {
            "entry_price": entry_price,
            "stop_price": stop,
            "take_profit_price": take_profit,
            "risk_per_share": round(entry_price - stop, 4),
            "dollar_risk_budget": round(equity * limits.max_risk_per_trade_pct, 2),
            "qty": qty,
        }
        decision["risk_math"] = risk_math

        if qty < 1:
            decision.update(action="skip", reason="position size rounds to zero shares")
            log_decision(decision)
            print(f"{symbol}: SKIP (size rounds to zero)")
            continue

        new_order_value = qty * entry_price
        if breaches_concentration_limit(equity, existing_position_value=0.0, new_order_value=new_order_value, limits=limits):
            decision.update(
                action="skip",
                reason=(
                    f"position value ${new_order_value:,.2f} would exceed "
                    f"{limits.max_position_concentration_pct:.0%} of equity concentration cap"
                ),
            )
            log_decision(decision)
            print(f"{symbol}: SKIP (concentration cap)")
            continue

        client_order_id = f"risk-agent-{symbol.lower()}-{uuid.uuid4().hex[:8]}"
        order = submit_bracket_order(
            symbol=symbol,
            qty=qty,
            side="buy",
            stop_price=stop,
            take_profit_price=take_profit,
            client_order_id=client_order_id,
            dry_run=DRY_RUN,
        )
        decision.update(action="buy", client_order_id=client_order_id, order=order)
        log_decision(decision)
        print(f"{symbol}: BUY {qty} shares @ ~{entry_price} (stop {stop}, take-profit {take_profit})")


if __name__ == "__main__":
    run()
    sys.exit(0)

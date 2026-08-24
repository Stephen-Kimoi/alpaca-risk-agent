"""Read-only dashboard over the same state agent.py produces — no trading
logic lives here. It exists so a reader (or a hackathon judge) can see the
risk layer's reasoning without tailing a JSONL file: live account/positions
pulled straight from alpaca_cli, and the decision log's rationale next to
each entry so a bracket order and the risk math that sized it sit side by side.
"""

import gradio as gr
import pandas as pd

from alpaca_cli import get_account, get_positions
from decision_log import read_decisions


def load_account_summary() -> pd.DataFrame:
    account = get_account()
    rows = [
        ("Equity", f"${float(account['equity']):,.2f}"),
        ("Cash", f"${float(account['cash']):,.2f}"),
        ("Buying power", f"${float(account['buying_power']):,.2f}"),
        ("Last equity (prior close)", f"${float(account['last_equity']):,.2f}"),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Value"])


def load_positions() -> pd.DataFrame:
    positions = get_positions()
    if not positions:
        return pd.DataFrame(columns=["Symbol", "Qty", "Avg entry", "Current price", "Unrealized P/L"])
    return pd.DataFrame(
        [
            {
                "Symbol": p["symbol"],
                "Qty": p["qty"],
                "Avg entry": f"${float(p['avg_entry_price']):.2f}",
                "Current price": f"${float(p['current_price']):.2f}",
                "Unrealized P/L": f"${float(p['unrealized_pl']):.2f}",
            }
            for p in positions
        ]
    )


def load_decisions() -> pd.DataFrame:
    decisions = read_decisions(limit=50)
    if not decisions:
        return pd.DataFrame(columns=["Time", "Symbol", "Action", "Rationale"])
    rows = []
    for d in reversed(decisions):
        if d["action"] == "buy":
            rm = d["risk_math"]
            rationale = (
                f"SMA long signal (short {d['signal']['sma_short']} > long {d['signal']['sma_long']}); "
                f"sized {rm['qty']} sh @ ${rm['entry_price']} to risk ${rm['dollar_risk_budget']:.0f} "
                f"(stop ${rm['stop_price']}, take-profit ${rm['take_profit_price']})"
            )
        else:
            rationale = d.get("reason", "")
        rows.append(
            {
                "Time": d["timestamp"],
                "Symbol": d["symbol"],
                "Action": d["action"].upper(),
                "Rationale": rationale,
            }
        )
    return pd.DataFrame(rows)


def refresh():
    return load_account_summary(), load_positions(), load_decisions()


with gr.Blocks(title="Risk-Managed Trading Agent") as demo:
    gr.Markdown("# Risk-Managed Trading Agent — Dashboard")
    gr.Markdown(
        "Read-only view over the same account and decision log `agent.py` writes to on its cron schedule. "
        "Nothing here places trades — click **Refresh** to pull the latest state."
    )
    refresh_btn = gr.Button("Refresh", variant="primary")

    gr.Markdown("## Account")
    account_table = gr.Dataframe(headers=["Metric", "Value"], interactive=False)

    gr.Markdown("## Open positions")
    positions_table = gr.Dataframe(interactive=False)

    gr.Markdown("## Decision log — what the agent did and why")
    decisions_table = gr.Dataframe(interactive=False, wrap=True)

    demo.load(refresh, outputs=[account_table, positions_table, decisions_table])
    refresh_btn.click(refresh, outputs=[account_table, positions_table, decisions_table])

if __name__ == "__main__":
    demo.launch()

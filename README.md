# Alpaca Risk Agent

A cron-scheduled paper-trading agent built on [Alpaca's Trading CLI](https://docs.alpaca.markets/us/docs/alpacas-cli): every run re-derives account state, checks a real risk layer (position sizing from stop distance, a daily-loss circuit breaker, a per-symbol concentration cap), and logs *why* it acted or skipped — not just what it did. The [Alpaca MCP server](https://github.com/alpacahq/alpaca-mcp-server) is wired in as a second, read-only interface, so you can ask a connected assistant plain-English questions about the running agent without touching its scheduled loop.

Companion project for a [lablab.ai](https://lablab.ai) tutorial and a starter for the [Alpaca AI Trading Agents Hackathon](https://lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon).

## What's in here and why

| File | Why it exists |
|---|---|
| `risk_rules.py` | Pure risk math — position sizing, stop/take-profit prices, daily-loss and concentration checks. No API calls, so it's the one module you can unit-test without touching the network. |
| `alpaca_cli.py` | Thin subprocess wrapper around the `alpaca` binary. The agent runs the exact same commands you'd type by hand — no separate SDK code path to diverge from what you can verify manually. |
| `strategy.py` | The trade signal (SMA crossover). Deliberately simple — the point of this project is the risk layer around the signal, not the signal itself. |
| `decision_log.py` | Append-only JSONL log of every decision — buys *and* skips, each with a reason. This is what an assistant reads to explain the agent's behavior after the fact. |
| `agent.py` | The cron entry point. Single-shot: loads the watchlist, checks the daily-loss breaker, evaluates each symbol, and either places a bracket order or logs why it didn't. |
| `ui.py` | Read-only Gradio dashboard over the same account state and decision log — for watching the agent's reasoning without tailing a JSONL file. |
| `watchlist.json` | Sample watchlist (`AAPL`, `MSFT`, `SPY`). |

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # fill in your Alpaca PAPER trading key/secret
```

Get paper trading keys from the **Trading Dashboard** (not the docs site) → make sure the top-left switcher says "Paper Trading" → **Home** → the API Keys panel. This is separate from any live brokerage account application.

Verify the CLI is authenticated:

```bash
alpaca account get
```

## Run it

```bash
DRY_RUN=true python3 agent.py    # prints what it would do, places no orders
DRY_RUN=false python3 agent.py   # places real (paper) bracket orders
```

Point cron at the same command on whatever interval fits your strategy (e.g. every 15 minutes during market hours):

```
*/15 9-16 * * 1-5 cd /path/to/alpaca-risk-agent && .venv/bin/python agent.py >> agent.log 2>&1
```

Run the dashboard separately, any time:

```bash
python3 ui.py   # http://127.0.0.1:7860
```

## Connect the MCP server

```bash
claude mcp add alpaca -e ALPACA_API_KEY=your_key -e ALPACA_SECRET_KEY=your_secret -e ALPACA_PAPER_TRADE=true -- uvx alpaca-mcp-server
```

Restart your Claude session after adding a new MCP server — tools registered mid-session don't show up until the client reconnects. Once it's live, ask your assistant things like *"why did you size AAPL that way today?"* — it cross-references the official Alpaca MCP tools (live account/position state) with a direct read of this project's `decisions.jsonl` (the rationale Alpaca's own API doesn't know about).

## Risk defaults (`risk_rules.py`)

- Risk at most **0.5%** of equity per trade, sized from the stop distance
- Stop-loss **3%** below entry, take-profit at **2x** the stop distance
- Halt all new entries once the account is down **3%** on the day
- Cap any single symbol at **20%** of equity — this is what stops a tight-stop, high-risk-budget trade from ballooning into an oversized position; sizing from risk alone isn't sufficient on its own

## A note on paper trading

`ALPACA_PAPER=true` in `.env` and the CLI profile defaulting to paper trading are both load-bearing — this project has only ever been run against `https://paper-api.alpaca.markets`. Flip to live trading at your own risk and only after you've read Alpaca's live-trading requirements.

---

This is the companion repo for the [lablab.ai](https://lablab.ai) tutorial *"A Trading Agent That Sizes Its Own Risk and Explains Itself, Built on Alpaca's CLI and MCP Server"* — read it for the full walkthrough of why each piece here is shaped the way it is.

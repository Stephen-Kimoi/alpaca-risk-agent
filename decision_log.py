"""Append-only JSONL log of every decision the agent makes — buys, skips,
and halts alike. This is the file an LLM reads to answer 'why did you do
that' questions later; every skip needs a reason for the same reason every
trade needs a rationale."""

import json
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).parent / "decisions.jsonl"


def log_decision(record: dict) -> None:
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), **record}
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(record) + "\n")


def read_decisions(symbol: str | None = None, limit: int = 20) -> list[dict]:
    if not LOG_PATH.exists():
        return []
    records = [json.loads(line) for line in LOG_PATH.read_text().splitlines() if line.strip()]
    if symbol:
        records = [r for r in records if r.get("symbol") == symbol]
    return records[-limit:]

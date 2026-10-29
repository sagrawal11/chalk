"""Append-only experiment ledger: the public progression record.

One JSON object per line at artifacts/experiments_ledger.jsonl (tracked + diffable,
so the model's climb is visible in git history, on-brand for build-in-public). Every
experiment is recorded REGARDLESS of outcome (duds are content).

ARCHITECTURE §5d names data/experiments_ledger.parquet for the /api/experiments feed;
we keep the canonical record here as diffable JSONL and project it to parquet for the
API in M6 (a parquet in gitignored data/ wouldn't be a visible public record).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

BACKEND_ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = BACKEND_ROOT / "artifacts" / "experiments_ledger.jsonl"


def append_result(row: Dict[str, Any], path: Path = LEDGER_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def load_ledger(path: Path = LEDGER_PATH) -> List[Dict[str, Any]]:
    if not Path(path).exists():
        return []
    return [json.loads(ln) for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]


def run_ids(sport: str, path: Path = LEDGER_PATH) -> set:
    return {r.get("id") for r in load_ledger(path) if r.get("sport") == sport}


def counts(sport: str, path: Path = LEDGER_PATH) -> Dict[str, int]:
    """Multiple-comparisons exposure: experiments run vs kept (per sport)."""
    rows = [r for r in load_ledger(path) if r.get("sport") == sport]
    kept = sum(1 for r in rows if r.get("decision") == "keep")
    return {"run": len(rows), "kept": kept, "dropped": len(rows) - kept}

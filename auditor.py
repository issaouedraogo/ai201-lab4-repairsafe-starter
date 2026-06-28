import json
import os
from datetime import datetime, timezone
from config import LOG_FILE


def log_interaction(question: str, tier: str, response: str) -> None:
    """
    Append a structured record of this interaction to the audit log.

    Writes one JSON object per line to LOG_FILE (logs/audit.jsonl), creating the
    log directory if it doesn't exist yet. The question and response are truncated
    in the record (300 / 200 chars), with their full lengths stored separately so
    truncation and leaked-instruction cases stay diagnosable. Also prints a
    one-line summary to the terminal for live monitoring.
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tier": tier,
        "question": question[:300],
        "response_preview": response[:200],
        "question_length": len(question),
        "response_length": len(response),
    }

    # Create the log directory on demand so a fresh clone/container can log too.
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    question_preview = question[:50] + ("…" if len(question) > 50 else "")
    print(f'[LOGGED] tier={tier} | "{question_preview}" → {len(response)} chars')

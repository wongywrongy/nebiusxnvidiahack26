"""Quote-gate counts for this item, including investigated sources and replacement candidates.

`drop` records why each rejected claim or web value was rejected (first failing gate), so a run can show
whether the model misquotes, reads the wrong metric, or simply returns properties nobody asked for.
"""
from contextvars import ContextVar

FIELDS = ("claims_extracted", "claims_kept", "web_values_read", "web_values_kept")
COUNTS: ContextVar[dict | None] = ContextVar("quote_counts", default=None)
REASONS: ContextVar[dict | None] = ContextVar("quote_drop_reasons", default=None)


def count(read_key: str, kept_key: str, read: int, kept: int) -> None:
    counters = COUNTS.get()
    if counters is not None:
        counters[read_key] += read
        counters[kept_key] += kept


def drop(kind: str, reason: str | None) -> None:
    """kind: 'claim' or 'web'. reason None means the value was kept."""
    reasons = REASONS.get()
    if reasons is not None and reason:
        key = f"{kind}:{reason}"
        reasons[key] = reasons.get(key, 0) + 1

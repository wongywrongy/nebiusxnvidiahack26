"""Quote-gate counts for this item, including investigated sources and replacement candidates."""
from contextvars import ContextVar

FIELDS = ("claims_extracted", "claims_kept", "web_values_read", "web_values_kept")
COUNTS: ContextVar[dict | None] = ContextVar("quote_counts", default=None)


def count(read_key: str, kept_key: str, read: int, kept: int) -> None:
    counters = COUNTS.get()
    if counters is not None:
        counters[read_key] += read
        counters[kept_key] += kept

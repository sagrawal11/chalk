"""Track record: the credibility flywheel.

LOCK the day's predictions immutably before tip (provenance), GRADE them against
actual outcomes after, and AGGREGATE into the public record (SU/ATS/O-U hit
rates, streaks, units). An honest, tamper-evident record is what grows the page.
"""
from track_record.lock import lock_predictions, load_lock, verify_lock  # noqa: F401
from track_record.grade import append_ledger, grade_date  # noqa: F401
from track_record.aggregate import headline, summarize  # noqa: F401

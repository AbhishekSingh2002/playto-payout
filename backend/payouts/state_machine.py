from django.utils import timezone
from django.db import transaction


class InvalidStatusTransition(Exception):
    """Raised when a state transition is not allowed."""
    pass


def transition(payout, new_status, failure_reason="", save=True):
    """
    Transition a Payout to a new status.

    Rules enforced here:
      pending    → processing
      processing → completed | failed
      completed  → (nothing)  — terminal
      failed     → (nothing)  — terminal

    Raises InvalidStatusTransition for any other move.
    Always updates payout.updated_at.
    """
    allowed = payout.VALID_TRANSITIONS.get(payout.status, [])
    if new_status not in allowed:
        raise InvalidStatusTransition(
            f"Cannot transition payout {payout.id} from '{payout.status}' to '{new_status}'. "
            f"Allowed: {allowed or ['(none — terminal state)']}"
        )

    payout.status = new_status

    if new_status == payout.STATUS_PROCESSING:
        payout.processing_started_at = timezone.now()

    if new_status == payout.STATUS_FAILED and failure_reason:
        payout.failure_reason = failure_reason

    if save:
        payout.save(update_fields=["status", "failure_reason", "processing_started_at", "updated_at"])

    return payout
import random
import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from .models import Payout
from .state_machine import transition, InvalidStatusTransition
from merchants.models import LedgerEntry

logger = logging.getLogger(__name__)

# How long before a processing payout is considered "stuck"
STUCK_THRESHOLD_SECONDS = 30

# Maximum retries before marking a payout as permanently failed
MAX_RETRIES = 3


def _simulate_gateway():
    """
    Fake payment gateway response.
    Returns: "success" | "failed" | "stuck"
    Distribution: 70% / 20% / 10%
    """
    roll = random.random()
    if roll < 0.70:
        return "success"
    elif roll < 0.90:
        return "failed"
    else:
        return "stuck"


def _refund_payout(payout):
    """
    When a payout fails, create a CREDIT ledger entry to reverse the held debit.
    This restores the merchant's available balance.
    """
    LedgerEntry.objects.create(
        merchant=payout.merchant,
        payout=payout,
        entry_type="credit",
        amount_paise=payout.amount_paise,
        description=f"Refund for failed payout {payout.id}",
    )
    logger.info("Refunded ₹%s paise for failed payout %s", payout.amount_paise, payout.id)


@shared_task(bind=True, max_retries=MAX_RETRIES)
def process_payout(self, payout_id: str):
    """
    Main background worker for processing a payout.

    Flow:
        pending → processing → completed (70%)
        pending → processing → failed    (20%) + refund
        pending → processing → [stuck]   (10%) → retried → failed after MAX_RETRIES + refund

    Retry uses exponential backoff: 2^retry_count * 5 seconds.
    """
    try:
        payout = Payout.objects.select_related("merchant", "bank_account").get(id=payout_id)
    except Payout.DoesNotExist:
        logger.error("Payout %s not found — aborting task.", payout_id)
        return

    # Guard: only process pending payouts (idempotent task execution)
    if payout.status not in (Payout.STATUS_PENDING, Payout.STATUS_PROCESSING):
        logger.info("Payout %s already in terminal state '%s' — skipping.", payout_id, payout.status)
        return

    # Move to PROCESSING
    try:
        with transaction.atomic():
            # Re-fetch with lock to prevent concurrent task execution
            payout = Payout.objects.select_for_update().get(id=payout_id)
            if payout.status == Payout.STATUS_PENDING:
                transition(payout, Payout.STATUS_PROCESSING)
    except InvalidStatusTransition as exc:
        logger.warning("State transition error for %s: %s", payout_id, exc)
        return

    # Simulate gateway call
    result = _simulate_gateway()
    logger.info("Gateway result for payout %s: %s", payout_id, result)

    if result == "success":
        with transaction.atomic():
            payout.refresh_from_db()
            transition(payout, Payout.STATUS_COMPLETED)
        logger.info("Payout %s completed successfully.", payout_id)

    elif result == "failed":
        with transaction.atomic():
            payout.refresh_from_db()
            transition(payout, Payout.STATUS_FAILED, failure_reason="Gateway declined the transaction.")
            _refund_payout(payout)
        logger.info("Payout %s failed — funds refunded.", payout_id)

    else:
        # "stuck" — retry with exponential backoff
        retry_count = payout.retry_count + 1
        Payout.objects.filter(id=payout_id).update(retry_count=retry_count)

        if retry_count >= MAX_RETRIES:
            with transaction.atomic():
                payout.refresh_from_db()
                transition(
                    payout, Payout.STATUS_FAILED,
                    failure_reason=f"Payout stuck after {MAX_RETRIES} retries.",
                )
                _refund_payout(payout)
            logger.error("Payout %s exceeded max retries — marked failed and refunded.", payout_id)
        else:
            # Exponential backoff: 5s, 10s, 20s
            countdown = (2 ** retry_count) * 5
            logger.warning(
                "Payout %s stuck (attempt %s/%s) — retrying in %ss.",
                payout_id, retry_count, MAX_RETRIES, countdown,
            )
            raise self.retry(countdown=countdown, exc=Exception("Gateway stuck"))


@shared_task
def retry_stuck_payouts():
    """
    Periodic task (runs every 60 s via Celery Beat).
    Finds payouts stuck in PROCESSING for > STUCK_THRESHOLD_SECONDS
    and re-dispatches them for retry.
    """
    cutoff = timezone.now() - timedelta(seconds=STUCK_THRESHOLD_SECONDS)
    stuck = Payout.objects.filter(
        status=Payout.STATUS_PROCESSING,
        processing_started_at__lt=cutoff,
        retry_count__lt=MAX_RETRIES,
    )
    for payout in stuck:
        logger.info("Re-queuing stuck payout %s (retry %s)", payout.id, payout.retry_count)
        # Reset to pending so process_payout can pick it up cleanly
        Payout.objects.filter(id=payout.id, status=Payout.STATUS_PROCESSING).update(
            status=Payout.STATUS_PENDING
        )
        process_payout.delay(str(payout.id))
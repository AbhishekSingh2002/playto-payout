import uuid
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.conf import settings


class Payout(models.Model):
    STATUS_PENDING    = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED  = "completed"
    STATUS_FAILED     = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING,    "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED,  "Completed"),
        (STATUS_FAILED,     "Failed"),
    ]

    # Valid transitions — enforced in state_machine.py
    VALID_TRANSITIONS = {
        STATUS_PENDING:    [STATUS_PROCESSING],
        STATUS_PROCESSING: [STATUS_COMPLETED, STATUS_FAILED],
        STATUS_COMPLETED:  [],  # Terminal — no transitions allowed
        STATUS_FAILED:     [],  # Terminal — no transitions allowed
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        "merchants.Merchant", on_delete=models.PROTECT, related_name="payouts"
    )
    bank_account = models.ForeignKey(
        "merchants.BankAccount", on_delete=models.PROTECT, related_name="payouts"
    )
    amount_paise = models.PositiveBigIntegerField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    failure_reason = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=255, db_index=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["merchant", "status"]),
            models.Index(fields=["status", "processing_started_at"]),
        ]

    def __str__(self):
        return f"Payout {self.id} — ₹{self.amount_paise / 100:.2f} [{self.status}]"


class IdempotencyKey(models.Model):
    """
    Stores request fingerprint per (merchant, key) pair.
    Expires after IDEMPOTENCY_KEY_TTL seconds (default 24 h).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        "merchants.Merchant", on_delete=models.CASCADE, related_name="idempotency_keys"
    )
    key = models.CharField(max_length=255)
    payout = models.OneToOneField(
        Payout, on_delete=models.CASCADE, null=True, blank=True, related_name="idempotency_record"
    )
    # Store the full response body so we can replay it exactly
    response_body = models.JSONField(null=True, blank=True)
    response_status = models.PositiveSmallIntegerField(default=201)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        unique_together = [("merchant", "key")]
        indexes = [models.Index(fields=["expires_at"])]

    def save(self, *args, **kwargs):
        if not self.expires_at:
            ttl = getattr(settings, "IDEMPOTENCY_KEY_TTL", 86400)
            self.expires_at = timezone.now() + timedelta(seconds=ttl)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"IdempotencyKey({self.key}) for {self.merchant.name}"
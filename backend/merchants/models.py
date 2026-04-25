import uuid
from django.db import models


class Merchant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_balance(self):
        """
        Balance is ALWAYS derived from DB aggregation — never stored directly.
        available_balance = sum(credits) - sum(debits, only COMPLETED payouts)
        held_balance     = sum(debits, only PENDING/PROCESSING payouts)
        """
        from django.db.models import Sum, Q
        result = self.ledger_entries.aggregate(
            total_credits=Sum("amount_paise", filter=Q(entry_type="credit")),
            total_debits=Sum(
                "amount_paise",
                filter=Q(entry_type="debit", payout__status="completed"),
            ),
            total_held=Sum(
                "amount_paise",
                filter=Q(entry_type="debit", payout__status__in=["pending", "processing"]),
            ),
        )
        credits = result["total_credits"] or 0
        debits  = result["total_debits"]  or 0
        held    = result["total_held"]    or 0
        return {
            "available_paise": credits - debits - held,
            "held_paise":      held,
            "total_paise":     credits - debits,
        }

    def __str__(self):
        return self.name


class BankAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="bank_accounts")
    account_number = models.CharField(max_length=20)
    ifsc_code = models.CharField(max_length=11)
    account_holder_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.account_holder_name} — {self.account_number[-4:].rjust(len(self.account_number), '*')}"


class LedgerEntry(models.Model):
    ENTRY_TYPES = [
        ("credit", "Credit"),
        ("debit",  "Debit"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name="ledger_entries")
    # Nullable — credits have no associated payout; debits always do
    payout = models.ForeignKey(
        "payouts.Payout",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    entry_type = models.CharField(max_length=6, choices=ENTRY_TYPES)
    # All amounts stored as integer paise — NEVER floats
    amount_paise = models.PositiveBigIntegerField()
    description = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["merchant", "entry_type"]),
            models.Index(fields=["merchant", "created_at"]),
        ]

    def __str__(self):
        return f"{self.entry_type} ₹{self.amount_paise / 100:.2f} for {self.merchant.name}"
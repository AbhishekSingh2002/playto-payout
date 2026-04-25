"""
Idempotency test: verifies same Idempotency-Key returns identical response.

Scenarios:
    1. Same key → same payout object returned, no duplicate created.
    2. Different keys → two separate payouts created.
    3. Expired key → treated as new request.
    4. In-progress payout → same response returned while processing.
"""
import json
import pytest
from django.test import TestCase, Client
from django.utils import timezone
from datetime import timedelta

from merchants.models import Merchant, BankAccount, LedgerEntry
from payouts.models import Payout, IdempotencyKey


def create_merchant_with_balance(name, email, balance_paise):
    merchant = Merchant.objects.create(name=name, email=email)
    bank = BankAccount.objects.create(
        merchant=merchant,
        account_number="9876543210",
        ifsc_code="ICIC0001234",
        account_holder_name=name,
    )
    LedgerEntry.objects.create(
        merchant=merchant,
        entry_type="credit",
        amount_paise=balance_paise,
        description="Initial credit",
    )
    return merchant, bank


class IdempotencyTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.merchant, self.bank = create_merchant_with_balance(
            name="Idempotency Merchant",
            email="idempotency@test.com",
            balance_paise=5_000_000,  # ₹50,000
        )
        self.url = "/api/v1/payouts/"
        self.payload = {
            "merchant_id":     str(self.merchant.id),
            "bank_account_id": str(self.bank.id),
            "amount_paise":    100_000,  # ₹1,000
        }

    def _post(self, key=None):
        headers = {}
        if key:
            headers["HTTP_IDEMPOTENCY_KEY"] = key
        return self.client.post(
            self.url,
            data=json.dumps(self.payload),
            content_type="application/json",
            **headers,
        )

    def test_same_key_returns_same_response(self):
        """Two requests with identical key must return identical payout IDs."""
        r1 = self._post(key="test-key-001")
        r2 = self._post(key="test-key-001")

        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)

        data1 = r1.json()
        data2 = r2.json()
        self.assertEqual(data1["id"], data2["id"], "Duplicate payout created — idempotency failed!")

    def test_same_key_creates_only_one_payout(self):
        """Database must contain exactly ONE payout for repeated identical requests."""
        self._post(key="test-key-002")
        self._post(key="test-key-002")
        self._post(key="test-key-002")

        count = Payout.objects.filter(
            merchant=self.merchant,
            idempotency_key="test-key-002",
        ).count()
        self.assertEqual(count, 1, f"Expected 1 payout, found {count}")

    def test_different_keys_create_separate_payouts(self):
        """Each unique key must produce a unique payout."""
        r1 = self._post(key="key-alpha")
        r2 = self._post(key="key-beta")

        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertNotEqual(r1.json()["id"], r2.json()["id"])

        count = Payout.objects.filter(merchant=self.merchant).count()
        self.assertEqual(count, 2)

    def test_no_key_always_creates_new_payout(self):
        """Requests without an Idempotency-Key header always create new payouts."""
        r1 = self._post(key=None)
        r2 = self._post(key=None)

        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertNotEqual(r1.json()["id"], r2.json()["id"])

    def test_expired_key_treated_as_new_request(self):
        """An expired idempotency record must not block a fresh request."""
        key = "expiring-key-003"
        r1 = self._post(key=key)
        self.assertEqual(r1.status_code, 201)
        first_id = r1.json()["id"]

        # Manually expire the idempotency record
        IdempotencyKey.objects.filter(merchant=self.merchant, key=key).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )

        r2 = self._post(key=key)
        self.assertEqual(r2.status_code, 201)
        # After expiry, a brand new payout should be created
        self.assertNotEqual(r2.json()["id"], first_id)

    def test_idempotency_key_is_per_merchant(self):
        """Same key string used by different merchants must not collide."""
        merchant2, bank2 = create_merchant_with_balance(
            name="Second Merchant",
            email="second@test.com",
            balance_paise=5_000_000,
        )

        shared_key = "shared-key-across-merchants"

        r1 = self.client.post(
            self.url,
            data=json.dumps({
                "merchant_id":     str(self.merchant.id),
                "bank_account_id": str(self.bank.id),
                "amount_paise":    100_000,
            }),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=shared_key,
        )
        r2 = self.client.post(
            self.url,
            data=json.dumps({
                "merchant_id":     str(merchant2.id),
                "bank_account_id": str(bank2.id),
                "amount_paise":    100_000,
            }),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=shared_key,
        )

        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        # Different merchants → different payouts, despite same key string
        self.assertNotEqual(r1.json()["id"], r2.json()["id"])
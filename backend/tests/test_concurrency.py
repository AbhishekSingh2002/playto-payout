"""
Concurrency test: verifies SELECT FOR UPDATE prevents double-spending.

Scenario:
    Merchant has ₹10,000 (1,000,000 paise) balance.
    Two threads simultaneously request ₹6,000 payouts.
    Only ONE should succeed; the other must get HTTP 402.
"""
import threading
import pytest
from django.test import TestCase, Client
from django.urls import reverse
import json

from merchants.models import Merchant, BankAccount, LedgerEntry
from payouts.models import Payout


def create_merchant_with_balance(name, email, balance_paise):
    merchant = Merchant.objects.create(name=name, email=email)
    bank = BankAccount.objects.create(
        merchant=merchant,
        account_number="1234567890",
        ifsc_code="HDFC0001234",
        account_holder_name=name,
    )
    # Credit the merchant
    LedgerEntry.objects.create(
        merchant=merchant,
        entry_type="credit",
        amount_paise=balance_paise,
        description="Initial credit",
    )
    return merchant, bank


class ConcurrencyTest(TestCase):
    def setUp(self):
        # ₹10,000 = 1,000,000 paise
        self.merchant, self.bank = create_merchant_with_balance(
            name="Concurrent Merchant",
            email="concurrent@test.com",
            balance_paise=1_000_000,
        )

    def test_only_one_of_two_concurrent_payouts_succeeds(self):
        """
        Two threads fire identical ₹6,000 payout requests at the same time.
        Exactly ONE must succeed (HTTP 201); the other must be rejected (HTTP 402).
        """
        client = Client()
        url = "/api/v1/payouts/"
        payload = {
            "merchant_id":    str(self.merchant.id),
            "bank_account_id": str(self.bank.id),
            "amount_paise":   600_000,  # ₹6,000
        }

        results = []

        def fire_request(thread_id):
            response = client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
                HTTP_IDEMPOTENCY_KEY=f"concurrent-test-thread-{thread_id}",
            )
            results.append(response.status_code)

        threads = [threading.Thread(target=fire_request, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        success_count = results.count(201)
        rejected_count = results.count(402)

        self.assertEqual(success_count, 1, f"Expected exactly 1 success, got: {results}")
        self.assertEqual(rejected_count, 1, f"Expected exactly 1 rejection, got: {results}")

    def test_balance_never_goes_negative(self):
        """
        Fire 10 concurrent requests each for 15% of balance (total 150%).
        Final balance must be >= 0 regardless of how many succeed.
        """
        client = Client()
        url = "/api/v1/payouts/"
        amount = 150_000  # ₹1,500 each × 10 = ₹15,000 total against ₹10,000 balance
        results = []

        def fire(i):
            payload = {
                "merchant_id":    str(self.merchant.id),
                "bank_account_id": str(self.bank.id),
                "amount_paise":   amount,
            }
            r = client.post(
                url,
                data=json.dumps(payload),
                content_type="application/json",
                HTTP_IDEMPOTENCY_KEY=f"flood-test-{i}",
            )
            results.append(r.status_code)

        threads = [threading.Thread(target=fire, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        balance = self.merchant.get_balance()
        self.assertGreaterEqual(
            balance["available_paise"] + balance["held_paise"],
            0,
            "Balance went negative — concurrency control failed!",
        )

        success_count = results.count(201)
        # At ₹10,000 balance and ₹1,500 per payout: max 6 should succeed
        self.assertLessEqual(success_count, 6, f"Too many payouts succeeded: {success_count}")
"""
Ledger & state machine tests.

Covers:
    - Balance is sum(credits) - sum(debits) via DB query, never Python
    - Held balance tracks pending/processing payouts
    - Completed payout → funds gone
    - Failed payout → funds returned
    - Illegal state transitions raise InvalidStatusTransition
"""
from django.test import TestCase

from merchants.models import Merchant, BankAccount, LedgerEntry
from payouts.models import Payout
from payouts.state_machine import transition, InvalidStatusTransition


def make_merchant(name="Test Merchant", email="test@test.com"):
    m = Merchant.objects.create(name=name, email=email)
    b = BankAccount.objects.create(
        merchant=m,
        account_number="1111222233",
        ifsc_code="SBIN0001234",
        account_holder_name=name,
    )
    return m, b


class LedgerTest(TestCase):
    def setUp(self):
        self.merchant, self.bank = make_merchant()

    def _credit(self, amount):
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type="credit",
            amount_paise=amount,
            description="Test credit",
        )

    def _make_payout(self, amount, status=Payout.STATUS_PENDING):
        p = Payout.objects.create(
            merchant=self.merchant,
            bank_account=self.bank,
            amount_paise=amount,
            status=status,
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            payout=p,
            entry_type="debit",
            amount_paise=amount,
            description="Test debit",
        )
        return p

    def test_balance_starts_at_zero(self):
        b = self.merchant.get_balance()
        self.assertEqual(b["available_paise"], 0)
        self.assertEqual(b["held_paise"], 0)

    def test_credit_increases_available_balance(self):
        self._credit(500_000)
        b = self.merchant.get_balance()
        self.assertEqual(b["available_paise"], 500_000)

    def test_multiple_credits_sum_correctly(self):
        self._credit(100_000)
        self._credit(200_000)
        self._credit(300_000)
        b = self.merchant.get_balance()
        self.assertEqual(b["available_paise"], 600_000)

    def test_pending_payout_reduces_available_and_increases_held(self):
        self._credit(500_000)
        self._make_payout(200_000, status=Payout.STATUS_PENDING)
        b = self.merchant.get_balance()
        self.assertEqual(b["available_paise"], 300_000)
        self.assertEqual(b["held_paise"], 200_000)

    def test_completed_payout_removes_funds_permanently(self):
        self._credit(500_000)
        p = self._make_payout(200_000, status=Payout.STATUS_PENDING)
        transition(p, Payout.STATUS_PROCESSING)
        transition(p, Payout.STATUS_COMPLETED)
        b = self.merchant.get_balance()
        self.assertEqual(b["available_paise"], 300_000)
        self.assertEqual(b["held_paise"], 0)

    def test_failed_payout_refunds_via_credit_entry(self):
        self._credit(500_000)
        p = self._make_payout(200_000, status=Payout.STATUS_PENDING)
        transition(p, Payout.STATUS_PROCESSING)
        transition(p, Payout.STATUS_FAILED, failure_reason="Gateway error")
        # Simulate refund (as tasks.py does it)
        LedgerEntry.objects.create(
            merchant=self.merchant,
            payout=p,
            entry_type="credit",
            amount_paise=200_000,
            description="Refund",
        )
        b = self.merchant.get_balance()
        # After refund, full balance restored
        self.assertEqual(b["available_paise"], 500_000)
        self.assertEqual(b["held_paise"], 0)


class StateMachineTest(TestCase):
    def setUp(self):
        self.merchant, self.bank = make_merchant(email="sm@test.com")
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type="credit",
            amount_paise=1_000_000,
        )

    def _payout(self, status=Payout.STATUS_PENDING):
        return Payout.objects.create(
            merchant=self.merchant,
            bank_account=self.bank,
            amount_paise=100_000,
            status=status,
        )

    def test_pending_to_processing_allowed(self):
        p = self._payout(Payout.STATUS_PENDING)
        transition(p, Payout.STATUS_PROCESSING)
        p.refresh_from_db()
        self.assertEqual(p.status, Payout.STATUS_PROCESSING)
        self.assertIsNotNone(p.processing_started_at)

    def test_processing_to_completed_allowed(self):
        p = self._payout(Payout.STATUS_PROCESSING)
        transition(p, Payout.STATUS_COMPLETED)
        p.refresh_from_db()
        self.assertEqual(p.status, Payout.STATUS_COMPLETED)

    def test_processing_to_failed_allowed(self):
        p = self._payout(Payout.STATUS_PROCESSING)
        transition(p, Payout.STATUS_FAILED, failure_reason="timeout")
        p.refresh_from_db()
        self.assertEqual(p.status, Payout.STATUS_FAILED)
        self.assertIn("timeout", p.failure_reason)

    def test_completed_to_anything_blocked(self):
        p = self._payout(Payout.STATUS_COMPLETED)
        for bad_status in [Payout.STATUS_PENDING, Payout.STATUS_PROCESSING, Payout.STATUS_FAILED]:
            with self.assertRaises(InvalidStatusTransition):
                transition(p, bad_status)

    def test_failed_to_completed_blocked(self):
        p = self._payout(Payout.STATUS_FAILED)
        with self.assertRaises(InvalidStatusTransition):
            transition(p, Payout.STATUS_COMPLETED)

    def test_pending_to_completed_directly_blocked(self):
        """Must go through PROCESSING — no skipping."""
        p = self._payout(Payout.STATUS_PENDING)
        with self.assertRaises(InvalidStatusTransition):
            transition(p, Payout.STATUS_COMPLETED)
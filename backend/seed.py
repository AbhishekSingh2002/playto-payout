#!/usr/bin/env python
"""
Seed script — run with:
    python manage.py shell < seed.py
or:
    cd backend && python seed.py  (if DJANGO_SETTINGS_MODULE is set)
"""
import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from merchants.models import Merchant, BankAccount, LedgerEntry
from payouts.models import Payout, IdempotencyKey

print("Clearing existing data...")
IdempotencyKey.objects.all().delete()
LedgerEntry.objects.all().delete()
Payout.objects.all().delete()
BankAccount.objects.all().delete()
Merchant.objects.all().delete()

print("Creating merchants...")

merchants_data = [
    {
        "name":  "Arjun Sharma Freelancer",
        "email": "arjun@example.com",
        "balance_paise": 5_000_000,  # ₹50,000
        "bank": {
            "account_number":     "11223344556677",
            "ifsc_code":          "HDFC0001234",
            "account_holder_name": "Arjun Sharma",
        },
    },
    {
        "name":  "Priya Designs Studio",
        "email": "priya@example.com",
        "balance_paise": 12_500_000,  # ₹1,25,000
        "bank": {
            "account_number":     "99887766554433",
            "ifsc_code":          "ICIC0005678",
            "account_holder_name": "Priya Verma",
        },
    },
    {
        "name":  "TechWave Solutions",
        "email": "techwave@example.com",
        "balance_paise": 2_000_000,  # ₹20,000
        "bank": {
            "account_number":     "55443322110011",
            "ifsc_code":          "SBIN0009012",
            "account_holder_name": "Rahul Mehta",
        },
    },
]

for data in merchants_data:
    merchant = Merchant.objects.create(name=data["name"], email=data["email"])

    BankAccount.objects.create(merchant=merchant, **data["bank"])

    # Seed credit entries broken into realistic transactions
    total = data["balance_paise"]
    LedgerEntry.objects.create(
        merchant=merchant,
        entry_type="credit",
        amount_paise=int(total * 0.6),
        description="Client payment — Invoice #001",
    )
    LedgerEntry.objects.create(
        merchant=merchant,
        entry_type="credit",
        amount_paise=int(total * 0.4),
        description="Client payment — Invoice #002",
    )

    balance = merchant.get_balance()
    print(
        f"  ✓ {merchant.name} | "
        f"₹{balance['available_paise'] / 100:,.2f} available | "
        f"ID: {merchant.id}"
    )

print("\nSeed complete. Run the server and open the dashboard.")
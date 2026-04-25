from rest_framework import serializers
from .models import Merchant, BankAccount, LedgerEntry


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = ["id", "account_number", "ifsc_code", "account_holder_name", "is_active"]


class LedgerEntrySerializer(serializers.ModelSerializer):
    payout_id = serializers.UUIDField(source="payout.id", read_only=True, allow_null=True)

    class Meta:
        model = LedgerEntry
        fields = ["id", "entry_type", "amount_paise", "description", "payout_id", "created_at"]


class BalanceSerializer(serializers.Serializer):
    merchant_id   = serializers.UUIDField()
    merchant_name = serializers.CharField()
    available_paise = serializers.IntegerField()
    held_paise      = serializers.IntegerField()
    total_paise     = serializers.IntegerField()


class MerchantSerializer(serializers.ModelSerializer):
    bank_accounts = BankAccountSerializer(many=True, read_only=True)

    class Meta:
        model = Merchant
        fields = ["id", "name", "email", "bank_accounts", "created_at"]
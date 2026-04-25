from rest_framework import serializers
from .models import Payout
from merchants.models import BankAccount


class CreatePayoutSerializer(serializers.Serializer):
    merchant_id    = serializers.UUIDField()
    bank_account_id = serializers.UUIDField()
    amount_paise   = serializers.IntegerField(min_value=1)

    def validate_amount_paise(self, value):
        # Must be a positive integer — no floats allowed at the API layer either
        if not isinstance(value, int):
            raise serializers.ValidationError("amount_paise must be an integer (paise).")
        return value

    def validate(self, attrs):
        from merchants.models import Merchant
        try:
            merchant = Merchant.objects.get(id=attrs["merchant_id"])
        except Merchant.DoesNotExist:
            raise serializers.ValidationError({"merchant_id": "Merchant not found."})

        try:
            bank_account = BankAccount.objects.get(
                id=attrs["bank_account_id"], merchant=merchant, is_active=True
            )
        except BankAccount.DoesNotExist:
            raise serializers.ValidationError({"bank_account_id": "Bank account not found or inactive."})

        attrs["merchant"] = merchant
        attrs["bank_account"] = bank_account
        return attrs


class PayoutSerializer(serializers.ModelSerializer):
    merchant_id    = serializers.UUIDField(source="merchant.id", read_only=True)
    merchant_name  = serializers.CharField(source="merchant.name", read_only=True)
    bank_account_id = serializers.UUIDField(source="bank_account.id", read_only=True)

    class Meta:
        model = Payout
        fields = [
            "id", "merchant_id", "merchant_name", "bank_account_id",
            "amount_paise", "status", "failure_reason", "retry_count",
            "idempotency_key", "created_at", "updated_at",
        ]
        read_only_fields = fields
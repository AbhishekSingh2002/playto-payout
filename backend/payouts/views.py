from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Payout, IdempotencyKey
from .serializers import CreatePayoutSerializer, PayoutSerializer
from merchants.models import Merchant, LedgerEntry


class PayoutCreateView(APIView):
    """
    POST /api/v1/payouts

    Headers:
        Idempotency-Key: <unique string per merchant per request>

    Body:
        {
            "merchant_id": "<uuid>",
            "bank_account_id": "<uuid>",
            "amount_paise": <integer>
        }

    Concurrency safety: SELECT FOR UPDATE on the Merchant row ensures
    only one request can check & deduct balance at a time.

    Idempotency: Same (merchant, Idempotency-Key) → identical response, no duplicate payout.
    """

    def post(self, request):
        idempotency_key_value = request.headers.get("Idempotency-Key", "")

        serializer = CreatePayoutSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        merchant    = serializer.validated_data["merchant"]
        bank_account = serializer.validated_data["bank_account"]
        amount_paise = serializer.validated_data["amount_paise"]

        # ── Idempotency check ────────────────────────────────────────────────
        if idempotency_key_value:
            try:
                existing = IdempotencyKey.objects.select_related("payout").get(
                    merchant=merchant,
                    key=idempotency_key_value,
                )
                if not existing.is_expired:
                    # Return the exact same response as the original request
                    return Response(
                        existing.response_body,
                        status=existing.response_status,
                    )
            except IdempotencyKey.DoesNotExist:
                pass  # First time seeing this key — proceed normally

        # ── Atomic block: balance check + payout creation ────────────────────
        try:
            with transaction.atomic():
                # SELECT FOR UPDATE locks this merchant row for the duration of
                # the transaction — prevents concurrent requests from both
                # seeing the same available balance and both succeeding.
                locked_merchant = (
                    Merchant.objects.select_for_update().get(id=merchant.id)
                )

                balance = locked_merchant.get_balance()
                available = balance["available_paise"]

                if available < amount_paise:
                    return Response(
                        {
                            "error": "Insufficient balance.",
                            "available_paise": available,
                            "requested_paise": amount_paise,
                        },
                        status=status.HTTP_402_PAYMENT_REQUIRED,
                    )

                # Create the payout
                payout = Payout.objects.create(
                    merchant=locked_merchant,
                    bank_account=bank_account,
                    amount_paise=amount_paise,
                    status=Payout.STATUS_PENDING,
                    idempotency_key=idempotency_key_value,
                )

                # Create the DEBIT ledger entry immediately — this holds the funds.
                # The payout is still pending; get_balance() counts pending debits
                # as "held", so available balance drops right away.
                LedgerEntry.objects.create(
                    merchant=locked_merchant,
                    payout=payout,
                    entry_type="debit",
                    amount_paise=amount_paise,
                    description=f"Payout to {bank_account.account_number[-4:].rjust(len(bank_account.account_number), '*')}",
                )

                response_data = PayoutSerializer(payout).data

                # Store idempotency record inside the same transaction
                if idempotency_key_value:
                    IdempotencyKey.objects.update_or_create(
                        merchant=locked_merchant,
                        key=idempotency_key_value,
                        defaults={
                            "payout": payout,
                            "response_body": response_data,
                            "response_status": 201,
                        },
                    )

        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Dispatch background worker AFTER the transaction commits
        from .tasks import process_payout
        process_payout.delay(str(payout.id))

        return Response(response_data, status=status.HTTP_201_CREATED)


class PayoutListView(APIView):
    """GET /api/v1/payouts/?merchant_id=<uuid>"""

    def get(self, request):
        merchant_id = request.query_params.get("merchant_id")
        qs = Payout.objects.select_related("merchant", "bank_account")
        if merchant_id:
            qs = qs.filter(merchant__id=merchant_id)
        return Response(PayoutSerializer(qs, many=True).data)


class PayoutDetailView(APIView):
    """GET /api/v1/payouts/<payout_id>/"""

    def get(self, request, payout_id):
        try:
            payout = Payout.objects.select_related("merchant", "bank_account").get(id=payout_id)
        except Payout.DoesNotExist:
            return Response({"error": "Payout not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(PayoutSerializer(payout).data)
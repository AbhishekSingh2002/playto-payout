from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Merchant, LedgerEntry
from .serializers import BalanceSerializer, LedgerEntrySerializer, MerchantSerializer


class MerchantListView(APIView):
    def get(self, request):
        merchants = Merchant.objects.prefetch_related("bank_accounts").all()
        data = MerchantSerializer(merchants, many=True).data
        return Response(data)


class MerchantBalanceView(APIView):
    def get(self, request, merchant_id):
        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response({"error": "Merchant not found"}, status=status.HTTP_404_NOT_FOUND)

        balance = merchant.get_balance()
        data = {
            "merchant_id":   str(merchant.id),
            "merchant_name": merchant.name,
            **balance,
        }
        return Response(BalanceSerializer(data).data)


class MerchantTransactionsView(APIView):
    def get(self, request, merchant_id):
        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response({"error": "Merchant not found"}, status=status.HTTP_404_NOT_FOUND)

        entries = LedgerEntry.objects.filter(merchant=merchant).select_related("payout")
        return Response(LedgerEntrySerializer(entries, many=True).data)
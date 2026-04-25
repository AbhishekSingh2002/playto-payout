from django.urls import path
from .views import PayoutCreateView, PayoutListView, PayoutDetailView

urlpatterns = [
    path("payouts/",            PayoutCreateView.as_view(), name="payout-create"),
    path("payouts/list/",       PayoutListView.as_view(),   name="payout-list"),
    path("payouts/<uuid:payout_id>/", PayoutDetailView.as_view(), name="payout-detail"),
]
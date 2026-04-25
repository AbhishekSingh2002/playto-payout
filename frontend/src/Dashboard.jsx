import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import Balance from "./components/Balance";
import PayoutForm from "./components/PayoutForm";
import PayoutList from "./components/PayoutList";

const API = "/api/v1";
const POLL_INTERVAL = 4000; // ms

export default function Dashboard({ merchant }) {
  const [balance, setBalance] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [payouts, setPayouts] = useState([]);
  const [loadingBalance, setLoadingBalance] = useState(true);
  const [loadingTx, setLoadingTx] = useState(true);

  const fetchBalance = useCallback(() => {
    axios
      .get(`${API}/merchants/${merchant.id}/balance/`)
      .then((r) => setBalance(r.data))
      .catch(console.error)
      .finally(() => setLoadingBalance(false));
  }, [merchant.id]);

  const fetchTransactions = useCallback(() => {
    axios
      .get(`${API}/merchants/${merchant.id}/transactions/`)
      .then((r) => setTransactions(r.data))
      .catch(console.error)
      .finally(() => setLoadingTx(false));
  }, [merchant.id]);

  const fetchPayouts = useCallback(() => {
    axios
      .get(`${API}/payouts/list/?merchant_id=${merchant.id}`)
      .then((r) => setPayouts(r.data))
      .catch(console.error);
  }, [merchant.id]);

  // Initial fetch
  useEffect(() => {
    setLoadingBalance(true);
    setLoadingTx(true);
    fetchBalance();
    fetchTransactions();
    fetchPayouts();
  }, [merchant.id, fetchBalance, fetchTransactions, fetchPayouts]);

  // Live polling
  useEffect(() => {
    const interval = setInterval(() => {
      fetchBalance();
      fetchTransactions();
      fetchPayouts();
    }, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchBalance, fetchTransactions, fetchPayouts]);

  const handlePayoutCreated = () => {
    // Immediately refresh everything after a new payout
    fetchBalance();
    fetchTransactions();
    fetchPayouts();
  };

  return (
    <div className="space-y-8">
      {/* Balance cards */}
      <Balance balance={balance} loading={loadingBalance} />

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Payout form */}
        <PayoutForm
          merchant={merchant}
          onPayoutCreated={handlePayoutCreated}
        />

        {/* Transaction ledger */}
        <section>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-4">
            Ledger Entries
          </h2>
          {loadingTx ? (
            <div className="text-gray-600 text-sm animate-pulse">Loading…</div>
          ) : transactions.length === 0 ? (
            <div className="text-gray-600 text-sm">No transactions yet.</div>
          ) : (
            <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
              {transactions.map((tx) => (
                <div
                  key={tx.id}
                  className="flex items-center justify-between bg-gray-900 border border-gray-800 rounded-lg px-4 py-3"
                >
                  <div>
                    <p className="text-sm text-gray-300">{tx.description || "—"}</p>
                    <p className="text-xs text-gray-600 mt-0.5">
                      {new Date(tx.created_at).toLocaleString()}
                    </p>
                  </div>
                  <span
                    className={`font-mono text-sm font-semibold ${
                      tx.entry_type === "credit"
                        ? "text-emerald-400"
                        : "text-rose-400"
                    }`}
                  >
                    {tx.entry_type === "credit" ? "+" : "−"}₹
                    {(tx.amount_paise / 100).toLocaleString("en-IN", {
                      minimumFractionDigits: 2,
                    })}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Payout history — full width */}
      <PayoutList payouts={payouts} />
    </div>
  );
}
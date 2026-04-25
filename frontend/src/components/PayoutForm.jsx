import { useState } from "react";
import axios from "axios";

const API = "/api/v1";

function generateIdempotencyKey() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export default function PayoutForm({ merchant, onPayoutCreated }) {
  const bankAccounts = merchant.bank_accounts || [];

  const [form, setForm] = useState({
    bank_account_id: bankAccounts[0]?.id || "",
    amount_rupees: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null); // { type: "success"|"error", message }

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setResult(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setResult(null);

    const amountRupees = parseFloat(form.amount_rupees);
    if (!amountRupees || amountRupees <= 0) {
      setResult({ type: "error", message: "Enter a valid amount." });
      return;
    }

    // Convert rupees → paise as integer
    const amount_paise = Math.round(amountRupees * 100);

    setSubmitting(true);
    try {
      const response = await axios.post(
        `${API}/payouts/`,
        {
          merchant_id:     merchant.id,
          bank_account_id: form.bank_account_id,
          amount_paise,
        },
        {
          headers: {
            "Content-Type":  "application/json",
            "Idempotency-Key": generateIdempotencyKey(),
          },
        }
      );

      setResult({
        type:    "success",
        message: `Payout of ₹${amountRupees.toFixed(2)} queued. ID: ${response.data.id.slice(0, 8)}…`,
      });
      setForm((prev) => ({ ...prev, amount_rupees: "" }));
      onPayoutCreated();
    } catch (err) {
      const msg =
        err.response?.data?.error ||
        (err.response?.status === 402 ? "Insufficient balance." : "Request failed.");
      setResult({ type: "error", message: msg });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section>
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-4">
        New Payout
      </h2>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-5">
        {/* Bank account */}
        <div>
          <label className="block text-xs text-gray-500 mb-1.5">Bank Account</label>
          {bankAccounts.length === 0 ? (
            <p className="text-sm text-rose-400">No bank accounts seeded.</p>
          ) : (
            <select
              name="bank_account_id"
              value={form.bank_account_id}
              onChange={handleChange}
              className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              {bankAccounts.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.account_holder_name} — ****{b.account_number.slice(-4)} ({b.ifsc_code})
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Amount */}
        <div>
          <label className="block text-xs text-gray-500 mb-1.5">Amount (₹)</label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm">₹</span>
            <input
              type="number"
              name="amount_rupees"
              value={form.amount_rupees}
              onChange={handleChange}
              placeholder="0.00"
              min="0.01"
              step="0.01"
              className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg pl-7 pr-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-emerald-500 [appearance:textfield]"
            />
          </div>
          <p className="text-xs text-gray-600 mt-1">
            Stored as paise internally.{" "}
            {form.amount_rupees
              ? `= ${Math.round(parseFloat(form.amount_rupees) * 100).toLocaleString()} paise`
              : ""}
          </p>
        </div>

        {/* Feedback */}
        {result && (
          <div
            className={`text-sm rounded-lg px-4 py-3 ${
              result.type === "success"
                ? "bg-emerald-900/40 border border-emerald-700 text-emerald-300"
                : "bg-rose-900/40 border border-rose-700 text-rose-300"
            }`}
          >
            {result.message}
          </div>
        )}

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={submitting || bankAccounts.length === 0}
          className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg py-2.5 transition-colors"
        >
          {submitting ? "Submitting…" : "Request Payout"}
        </button>
      </div>
    </section>
  );
}
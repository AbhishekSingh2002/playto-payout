const STATUS_STYLES = {
  pending:    "bg-yellow-900/40 text-yellow-300 border-yellow-700",
  processing: "bg-blue-900/40   text-blue-300   border-blue-700",
  completed:  "bg-emerald-900/40 text-emerald-300 border-emerald-700",
  failed:     "bg-rose-900/40   text-rose-300   border-rose-700",
};

const STATUS_DOTS = {
  pending:    "bg-yellow-400 animate-pulse",
  processing: "bg-blue-400   animate-pulse",
  completed:  "bg-emerald-400",
  failed:     "bg-rose-400",
};

function StatusBadge({ status }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-medium border rounded-full px-2.5 py-1 ${
        STATUS_STYLES[status] || "bg-gray-800 text-gray-400 border-gray-700"
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOTS[status] || "bg-gray-500"}`} />
      {status}
    </span>
  );
}

export default function PayoutList({ payouts }) {
  return (
    <section>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest">
          Payout History
        </h2>
        <span className="text-xs text-gray-600">Live • refreshes every 4s</span>
      </div>

      {payouts.length === 0 ? (
        <div className="text-gray-600 text-sm text-center py-10 bg-gray-900 border border-gray-800 rounded-xl">
          No payouts yet. Use the form above to request one.
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-xs text-gray-500 uppercase tracking-wider">
                <th className="text-left px-5 py-3 font-medium">Payout ID</th>
                <th className="text-right px-5 py-3 font-medium">Amount</th>
                <th className="text-center px-5 py-3 font-medium">Status</th>
                <th className="text-left px-5 py-3 font-medium hidden md:table-cell">Note</th>
                <th className="text-right px-5 py-3 font-medium hidden md:table-cell">Created</th>
              </tr>
            </thead>
            <tbody>
              {payouts.map((p, idx) => (
                <tr
                  key={p.id}
                  className={`border-b border-gray-800/50 last:border-0 transition-colors hover:bg-gray-800/30 ${
                    idx % 2 === 0 ? "" : "bg-gray-800/10"
                  }`}
                >
                  <td className="px-5 py-3 font-mono text-gray-400 text-xs">
                    {p.id.slice(0, 8)}…
                  </td>
                  <td className="px-5 py-3 text-right font-mono font-semibold text-gray-200">
                    ₹{(p.amount_paise / 100).toLocaleString("en-IN", {
                      minimumFractionDigits: 2,
                    })}
                  </td>
                  <td className="px-5 py-3 text-center">
                    <StatusBadge status={p.status} />
                  </td>
                  <td className="px-5 py-3 text-gray-500 text-xs hidden md:table-cell max-w-xs truncate">
                    {p.failure_reason || (p.status === "completed" ? "Funds transferred" : "—")}
                  </td>
                  <td className="px-5 py-3 text-right text-gray-600 text-xs hidden md:table-cell">
                    {new Date(p.created_at).toLocaleTimeString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
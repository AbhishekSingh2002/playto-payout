export default function Balance({ balance, loading }) {
  const fmt = (paise) =>
    "₹" +
    ((paise ?? 0) / 100).toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

  const cards = [
    {
      label: "Available Balance",
      value: fmt(balance?.available_paise),
      sub: "Ready to withdraw",
      color: "emerald",
      icon: "✓",
    },
    {
      label: "Held Balance",
      value: fmt(balance?.held_paise),
      sub: "Pending / processing",
      color: "amber",
      icon: "⏳",
    },
    {
      label: "Total Balance",
      value: fmt(balance?.total_paise),
      sub: "Credits − completed debits",
      color: "blue",
      icon: "Σ",
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className={`relative bg-gray-900 border rounded-xl px-6 py-5 overflow-hidden
            ${card.color === "emerald" ? "border-emerald-800/60" : ""}
            ${card.color === "amber"   ? "border-amber-800/60"   : ""}
            ${card.color === "blue"    ? "border-blue-800/60"     : ""}
          `}
        >
          {/* Background glow */}
          <div
            className={`absolute inset-0 opacity-5 rounded-xl
              ${card.color === "emerald" ? "bg-emerald-400" : ""}
              ${card.color === "amber"   ? "bg-amber-400"   : ""}
              ${card.color === "blue"    ? "bg-blue-400"     : ""}
            `}
          />

          <div className="relative">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-widest mb-3">
              {card.label}
            </p>

            {loading ? (
              <div className="h-8 bg-gray-800 rounded animate-pulse w-3/4" />
            ) : (
              <p
                className={`text-2xl font-bold font-mono tracking-tight
                  ${card.color === "emerald" ? "text-emerald-400" : ""}
                  ${card.color === "amber"   ? "text-amber-400"   : ""}
                  ${card.color === "blue"    ? "text-blue-400"     : ""}
                `}
              >
                {card.value}
              </p>
            )}

            <p className="text-xs text-gray-600 mt-2">{card.sub}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
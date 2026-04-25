import { useState, useEffect } from "react";
import axios from "axios";
import Dashboard from "./Dashboard";

const API = "/api/v1";

export default function App() {
  const [merchants, setMerchants] = useState([]);
  const [selectedMerchant, setSelectedMerchant] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    axios
      .get(`${API}/merchants/`)
      .then((res) => {
        setMerchants(res.data);
        if (res.data.length > 0) setSelectedMerchant(res.data[0]);
      })
      .catch(() => setError("Cannot connect to backend. Is the server running?"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-400 text-lg animate-pulse">Loading merchants…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-xl px-8 py-6 max-w-md text-center">
          <div className="text-2xl mb-2">⚠</div>
          <p className="font-semibold">Connection Error</p>
          <p className="text-sm mt-1 text-red-400">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Top nav */}
      <nav className="border-b border-gray-800 bg-gray-900/60 backdrop-blur sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500 flex items-center justify-center text-gray-950 font-bold text-sm">
              P
            </div>
            <span className="font-semibold text-white text-lg">Playto</span>
            <span className="text-gray-600 text-sm">Payout Dashboard</span>
          </div>

          {/* Merchant selector */}
          <div className="flex items-center gap-3">
            <span className="text-gray-500 text-sm">Merchant:</span>
            <select
              value={selectedMerchant?.id || ""}
              onChange={(e) =>
                setSelectedMerchant(merchants.find((m) => m.id === e.target.value))
              }
              className="bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-500 cursor-pointer"
            >
              {merchants.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main className="max-w-6xl mx-auto px-6 py-8">
        {selectedMerchant ? (
          <Dashboard merchant={selectedMerchant} />
        ) : (
          <div className="text-center text-gray-500 mt-20">No merchants found. Run the seed script.</div>
        )}
      </main>
    </div>
  );
}
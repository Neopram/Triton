import { useEffect, useState } from "react";
import PnLChart from "./PnLChart"; // ✅ Modular chart
import PnLTable from "./PnLTable"; // ✅ Modular table
import Button from "@/components/Button";
import api from "@/services/api";

interface PnLRecord {
  voyage_id: number;
  vessel_name: string;
  revenue_usd: number;
  total_costs_usd: number;
  profit_usd: number;
  pnl_margin_pct: number;
  comment?: string;
  created_at: string;
}

export default function PnLPanel() {
  const [data, setData] = useState<PnLRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPnL = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get("/finance");
      setData(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load financial records.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPnL();
  }, []);

  return (
    <div className="p-6 bg-white rounded-xl shadow border space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-blue-700">📊 Financial Performance Panel</h2>
        <Button variant="secondary" onClick={fetchPnL} loading={loading}>
          Refresh
        </Button>
      </div>

      {error && <div className="text-red-600 font-medium">{error}</div>}

      {data.length > 0 ? (
        <>
          <PnLChart data={aggregateByMonth(data)} />
          <PnLTable records={data} />
        </>
      ) : (
        !loading && <p className="text-gray-500">No financial data available.</p>
      )}
    </div>
  );
}

// Utility: Aggregate by month for chart data
function aggregateByMonth(records: PnLRecord[]) {
  const result: { [key: string]: number } = {};

  for (const rec of records) {
    const month = new Date(rec.created_at).toLocaleDateString("en-US", {
      month: "short",
      year: "numeric",
    });

    if (!result[month]) result[month] = 0;
    result[month] += rec.profit_usd;
  }

  return Object.entries(result).map(([month, profit_usd]) => ({
    month,
    profit_usd,
  }));
}

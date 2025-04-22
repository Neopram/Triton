import { useEffect, useState } from "react";
import Chart from "@/components/Chart";
import Table from "@/components/Table";
import Button from "@/components/Button";
import api from "@/services/api";

interface MarketSummary {
  route: string;
  month: string;
  average_rate: number;
}

export default function MarketSummaryPanel() {
  const [data, setData] = useState<MarketSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get("/market/summary");
      setData(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to fetch market summary data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, []);

  return (
    <div className="p-6 bg-white rounded-xl shadow border space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-indigo-700">📈 Market Summary by Route & Month</h2>
        <Button onClick={fetchSummary} loading={loading}>
          Refresh
        </Button>
      </div>

      {error && <p className="text-red-600">{error}</p>}

      {data.length > 0 ? (
        <>
          <Chart
            type="bar"
            title="Monthly Average Freight Rate (USD/ton)"
            data={data}
            dataKeyX="month"
            dataKeysY={["average_rate"]}
            groupBy="route"
          />

          <Table
            columns={["Route", "Month", "Average Rate (USD/ton)"]}
            data={data.map((entry, idx) => ({
              id: idx,
              Route: entry.route,
              Month: entry.month,
              "Average Rate (USD/ton)": `$${entry.average_rate.toFixed(2)}`,
            }))}
            emptyMessage="No market summary available."
          />
        </>
      ) : (
        !loading && <p className="text-gray-500 italic">No summary data available yet.</p>
      )}
    </div>
  );
}

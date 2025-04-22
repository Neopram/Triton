import { useEffect, useState } from "react";
import Chart from "@/components/Chart";
import Table from "@/components/Table";
import Button from "@/components/Button";
import api from "@/services/api";

export default function FinancePanel() {
  const [data, setData] = useState<Array<any>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchFinanceData = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get("/finance/pnl-summary");
      setData(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to fetch financial data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFinanceData();
  }, []);

  return (
    <div className="p-6 bg-white rounded-xl shadow border space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-blue-700">📈 Profit & Loss Dashboard</h2>
        <Button onClick={fetchFinanceData} loading={loading}>
          Refresh
        </Button>
      </div>

      {error && <p className="text-red-600">{error}</p>}

      {data.length > 0 && (
        <>
          <Chart
            type="bar"
            title="PnL by Voyage"
            data={data.map((d: any) => ({
              Voyage: d.voyage_id,
              Profit: d.pnl,
            }))}
            dataKeyX="Voyage"
            dataKeysY={["Profit"]}
          />

          <Table
            columns={[
              "Vessel",
              "Voyage",
              "Revenue (USD)",
              "Expenses (USD)",
              "TCE (USD/day)",
              "Profit (USD)",
              "Status",
            ]}
            data={data.map((d, i) => ({
              id: i,
              Vessel: d.vessel,
              Voyage: d.voyage_id,
              "Revenue (USD)": d.revenue,
              "Expenses (USD)": d.expenses,
              "TCE (USD/day)": d.tce,
              "Profit (USD)": d.pnl,
              Status: d.status,
            }))}
          />
        </>
      )}

      {data.length === 0 && !loading && (
        <p className="text-gray-500 text-sm italic">No financial data available.</p>
      )}
    </div>
  );
}

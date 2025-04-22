import { useState } from "react";
import Button from "@/components/Button";
import Chart from "@/components/Chart";
import Table from "@/components/Table";
import api from "@/services/api";

const defaultInputs = {
  voyage_days: 14,
  distance_nm: 5000,
  daily_consumption_mt: 30,
  bunker_price_usd_per_mt: 600,
  freight_rate_usd: 30000,
  cargo_quantity_mt: 35000,
  port_fees_usd: 30000,
  canal_fees_usd: 20000,
  other_costs_usd: 10000,
  cargo_type: "clean",
  useAI: true,
};

export default function VoyagePlanner() {
  const [form, setForm] = useState(defaultInputs);
  const [results, setResults] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === "number" ? parseFloat(value) : value,
    }));
  };

  const calculateTCE = async () => {
    setError(null);
    setLoading(true);
    try {
      const { useAI, ...payload } = form;
      const res = await api.post("/tce/calculate", payload);
      setResults(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "TCE calculation failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6 bg-white rounded-xl shadow border max-w-5xl mx-auto">
      <h2 className="text-2xl font-bold text-blue-700">🚢 Voyage Economics Simulator</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        <Input label="Voyage Days" name="voyage_days" value={form.voyage_days} onChange={handleChange} />
        <Input label="Distance (NM)" name="distance_nm" value={form.distance_nm} onChange={handleChange} />
        <Input label="Daily Fuel Consumption (MT)" name="daily_consumption_mt" value={form.daily_consumption_mt} onChange={handleChange} />
        <Input label="Bunker Price (USD/MT)" name="bunker_price_usd_per_mt" value={form.bunker_price_usd_per_mt} onChange={handleChange} />
        <Input label="Freight Rate (USD/1,000 MT)" name="freight_rate_usd" value={form.freight_rate_usd} onChange={handleChange} />
        <Input label="Cargo Quantity (MT)" name="cargo_quantity_mt" value={form.cargo_quantity_mt} onChange={handleChange} />
        <Input label="Port Fees (USD)" name="port_fees_usd" value={form.port_fees_usd} onChange={handleChange} />
        <Input label="Canal Fees (USD)" name="canal_fees_usd" value={form.canal_fees_usd} onChange={handleChange} />
        <Input label="Other Costs (USD)" name="other_costs_usd" value={form.other_costs_usd} onChange={handleChange} />
        <div>
          <label className="block font-medium mb-1">Cargo Type</label>
          <select
            name="cargo_type"
            value={form.cargo_type}
            onChange={handleChange}
            className="input"
          >
            <option value="clean">Clean</option>
            <option value="dirty">Dirty</option>
            <option value="dry">Dry</option>
          </select>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <label className="flex items-center space-x-2 text-sm">
          <input
            type="checkbox"
            checked={form.useAI}
            onChange={() => setForm((f) => ({ ...f, useAI: !f.useAI }))}
          />
          <span>Use AI Analysis (DeepSeek / Phi-3)</span>
        </label>
        <Button onClick={calculateTCE} loading={loading}>
          Run Simulation
        </Button>
      </div>

      {error && <div className="text-red-600 font-medium">{error}</div>}

      {results && (
        <div className="space-y-6">
          <h3 className="text-lg font-semibold text-gray-700">📈 Results</h3>

          <Chart
            type="bar"
            title="Cost Breakdown (USD)"
            data={[
              { item: "Fuel", value: results.total_bunker_cost },
              { item: "Total Costs", value: results.total_costs },
              { item: "Revenue", value: results.gross_revenue },
              { item: "Profit", value: results.net_profit },
            ]}
            dataKeyX="item"
            dataKeysY={["value"]}
          />

          <Table
            columns={["Parameter", "Value"]}
            data={[
              { Parameter: "TCE (USD/day)", Value: results.tce_usd_per_day.toFixed(2) },
              { Parameter: "Gross Revenue", Value: `$${results.gross_revenue}` },
              { Parameter: "Net Profit", Value: `$${results.net_profit}` },
              { Parameter: "Margin (%)", Value: `${results.pnl_margin_pct}` },
              { Parameter: "Voyage Days", Value: results.voyage_days },
            ]}
          />
        </div>
      )}
    </div>
  );
}

function Input({ label, name, value, onChange }: any) {
  return (
    <div>
      <label className="block font-medium mb-1">{label}</label>
      <input
        type="number"
        name={name}
        value={value}
        onChange={onChange}
        className="input"
        step="any"
      />
    </div>
  );
}

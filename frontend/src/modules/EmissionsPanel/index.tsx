import { useEffect, useState } from "react";
import Chart from "@/components/Chart";
import Table from "@/components/Table";
import Button from "@/components/Button";
import api from "@/services/api";

interface EmissionSummary {
  vessel: string;
  voyage_id: number;
  co2: number;
  cii: string;
  eexi: number;
  status: string;
}

export default function EmissionsPanel() {
  const [data, setData] = useState<EmissionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchEmissions = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get("/emissions/summary");
      setData(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Error loading emissions data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEmissions();
  }, []);

  return (
    <div className="p-6 bg-white rounded-xl shadow border space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-green-700">🌱 ESG & Emissions Dashboard</h2>
        <Button onClick={fetchEmissions} loading={loading}>
          Refresh
        </Button>
      </div>

      {error && <p className="text-red-600">{error}</p>}

      {data.length > 0 ? (
        <>
          <Chart
            type="area"
            title="CO₂ Emissions per Voyage"
            data={data.map((d) => ({
              Voyage: d.voyage_id,
              Emissions: d.co2,
            }))}
            dataKeyX="Voyage"
            dataKeysY={["Emissions"]}
          />

          <Table
            columns={[
              "Vessel",
              "Voyage",
              "CO₂ Emissions (MT)",
              "CII Rating",
              "EEXI Index",
              "Status"
            ]}
            data={data.map((d, i) => ({
              id: i,
              Vessel: d.vessel,
              Voyage: d.voyage_id,
              "CO₂ Emissions (MT)": d.co2.toFixed(2),
              "CII Rating": d.cii,
              "EEXI Index": d.eexi.toFixed(1),
              Status: renderStatus(d.status)
            }))}
          />
        </>
      ) : (
        !loading && <p className="text-gray-500 italic">No emissions data available yet.</p>
      )}
    </div>
  );
}

// Optional: color-coded status with emojis/icons
function renderStatus(status: string) {
  if (status === "compliant") return "🟢 Compliant";
  if (status === "warning") return "🟡 Warning";
  if (status === "non-compliant") return "🔴 Non-Compliant";
  return status;
}

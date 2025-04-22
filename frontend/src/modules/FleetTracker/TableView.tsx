import { useEffect, useState } from "react";
import Table from "@/components/Table";
import Button from "@/components/Button";
import api from "@/services/api";

export default function TableView() {
  const [fleet, setFleet] = useState<Array<any>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchFleet = async () => {
    setError(null);
    setLoading(true);
    try {
      const response = await api.get("/vessels/fleet-status");
      setFleet(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load fleet data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFleet();
  }, []);

  return (
    <div className="bg-white rounded-xl shadow p-6 border space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-bold text-blue-700">📋 Fleet Table View</h3>
        <Button variant="secondary" onClick={fetchFleet} loading={loading}>
          Refresh
        </Button>
      </div>

      {error && <div className="text-red-600">{error}</div>}

      <Table
        columns={[
          "Vessel",
          "IMO",
          "Latitude",
          "Longitude",
          "Speed (kn)",
          "Destination",
          "ETA",
          "Status"
        ]}
        data={fleet.map((vessel: any, index: number) => ({
          id: index,
          Vessel: vessel.name,
          IMO: vessel.imo,
          Latitude: vessel.lat,
          Longitude: vessel.lon,
          "Speed (kn)": vessel.speed,
          Destination: vessel.destination,
          ETA: vessel.eta,
          Status: vessel.status,
        }))}
        emptyMessage="No active vessels found."
      />
    </div>
  );
}

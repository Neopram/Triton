import { useState } from "react";
import MapView from "./MapView";
import TableView from "./TableView";
import Button from "@/components/Button";

export default function FleetTrackerModule() {
  const [view, setView] = useState<"map" | "table">("table");

  return (
    <div className="p-6 space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-blue-800">🛰️ Fleet Monitoring</h2>
        <Button
          onClick={() => setView(view === "map" ? "table" : "map")}
          variant="secondary"
        >
          {view === "map" ? "Switch to Table View" : "Switch to Map View"}
        </Button>
      </div>

      {view === "map" ? <MapView /> : <TableView />}
    </div>
  );
}

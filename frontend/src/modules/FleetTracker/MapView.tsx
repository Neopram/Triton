import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import api from "@/services/api";
import { MapPin, Ship, Clock } from "lucide-react";

// Dynamic import of map (avoid SSR issues)
const Map = dynamic(() => import("react-map-gl"), { ssr: false });

interface Vessel {
  name: string;
  type: string;
  lat: number;
  lon: number;
  origin: string;
  destination: string;
  eta: string;
  speed_knots: number;
  distance_nm: number;
  status: string;
}

export default function MapView() {
  const [vessels, setVessels] = useState<Vessel[]>([]);
  const [viewport, setViewport] = useState({
    latitude: 20,
    longitude: 0,
    zoom: 2,
  });

  const [selected, setSelected] = useState<Vessel | null>(null);

  useEffect(() => {
    const fetchAIS = async () => {
      try {
        const res = await api.get("/vessels/tracking");
        setVessels(res.data);
      } catch (err) {
        console.error("AIS fetch error", err);
      }
    };

    fetchAIS();
  }, []);

  return (
    <div className="relative h-[80vh] rounded-xl overflow-hidden shadow border">
      <Map
        mapboxAccessToken={process.env.NEXT_PUBLIC_MAPBOX_TOKEN}
        initialViewState={viewport}
        mapStyle="mapbox://styles/mapbox/light-v10"
        style={{ width: "100%", height: "100%" }}
        onMove={(evt) =>
          setViewport({
            latitude: evt.viewState.latitude,
            longitude: evt.viewState.longitude,
            zoom: evt.viewState.zoom,
          })
        }
      >
        {vessels.map((v, i) => (
          <div
            key={i}
            className="absolute"
            style={{
              transform: `translate(-50%, -50%)`,
              left: `${v.lon}%`,
              top: `${v.lat}%`,
            }}
            onClick={() => setSelected(v)}
          >
            <div className="bg-blue-600 rounded-full w-4 h-4 shadow-lg cursor-pointer" />
          </div>
        ))}
      </Map>

      {selected && (
        <div className="absolute bottom-6 left-6 bg-white rounded-xl shadow-lg p-6 w-[340px] z-50 border border-gray-200">
          <h3 className="text-lg font-bold text-blue-800 flex items-center mb-2">
            <Ship size={18} className="mr-2" /> {selected.name}
          </h3>
          <p className="text-sm text-gray-700"><strong>Type:</strong> {selected.type}</p>
          <p className="text-sm text-gray-700"><strong>Status:</strong> {selected.status}</p>
          <p className="text-sm text-gray-700"><strong>From:</strong> {selected.origin}</p>
          <p className="text-sm text-gray-700"><strong>To:</strong> {selected.destination}</p>
          <p className="text-sm text-gray-700">
            <Clock size={14} className="inline-block mr-1" />
            <strong>ETA:</strong> {new Date(selected.eta).toLocaleString()}
          </p>
          <p className="text-sm text-gray-700">
            <MapPin size={14} className="inline-block mr-1" />
            <strong>Distance:</strong> {selected.distance_nm} NM
          </p>
          <p className="text-sm text-gray-700"><strong>Speed:</strong> {selected.speed_knots} knots</p>
        </div>
      )}
    </div>
  );
}

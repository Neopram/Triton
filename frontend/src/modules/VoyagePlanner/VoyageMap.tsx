// src/modules/VoyagePlanner/VoyageMap.tsx
import React, { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Types for the component
interface Position {
  latitude: number;
  longitude: number;
}

interface WeatherRisk {
  position: Position;
  risk: 'low' | 'medium' | 'high';
  description: string;
}

interface RouteOptimizationResult {
  waypoints: Position[];
  weatherRisks?: WeatherRisk[];
}

interface VoyageMapProps {
  optimizedRoute: RouteOptimizationResult | null;
  initialCenter?: [number, number];
  initialZoom?: number;
}

// Component to fit bounds when route changes
const RouteBounds: React.FC<{ waypoints: Position[] }> = ({ waypoints }) => {
  const map = useMap();
  
  useEffect(() => {
    if (waypoints && waypoints.length > 0) {
      const latLngs = waypoints.map(wp => [wp.latitude, wp.longitude]);
      const bounds = L.latLngBounds(latLngs as [number, number][]);
      
      map.fitBounds(bounds, {
        padding: [50, 50],
        maxZoom: 10,
        animate: true
      });
    }
  }, [map, waypoints]);
  
  return null;
};

// Custom port icon
const portIcon = L.divIcon({
  html: `
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#475569" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 2v20"></path>
      <path d="M5 14H2a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1h3"></path>
      <path d="M22 9h-3a1 1 0 0 0-1 1v4a1 1 0 0 0 1 1h3"></path>
      <path d="M5 10a5 5 0 0 1 14 0"></path>
    </svg>
  `,
  className: '',
  iconSize: [20, 20],
  iconAnchor: [10, 10],
  popupAnchor: [0, -10],
});

// Custom weather risk icon
const createRiskIcon = (risk: 'low' | 'medium' | 'high') => {
  let color = '#3b82f6'; // blue-500
  
  if (risk === 'high') color = '#ef4444'; // red-500
  if (risk === 'medium') color = '#f59e0b'; // amber-500
  
  return L.divIcon({
    html: `
      <svg 
        width="24" 
        height="24" 
        viewBox="0 0 24 24" 
        fill="none" 
        stroke="${color}" 
        stroke-width="2" 
        stroke-linecap="round" 
        stroke-linejoin="round"
        class="weather-risk-marker"
        style="filter: drop-shadow(0px 2px 2px rgba(0, 0, 0, 0.25));"
      >
        <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
        <line x1="12" y1="9" x2="12" y2="13"></line>
        <line x1="12" y1="17" x2="12.01" y2="17"></line>
      </svg>
    `,
    className: '',
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -12],
  });
};

const VoyageMap: React.FC<VoyageMapProps> = ({ 
  optimizedRoute, 
  initialCenter = [20, 0],
  initialZoom = 2
}) => {
  return (
    <MapContainer 
      center={initialCenter}
      zoom={initialZoom}
      style={{ height: '100%', width: '100%' }}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      />
      
      {optimizedRoute && optimizedRoute.waypoints && optimizedRoute.waypoints.length > 1 && (
        <>
          {/* Fit map to route */}
          <RouteBounds waypoints={optimizedRoute.waypoints} />
          
          {/* Origin marker */}
          <Marker 
            position={[optimizedRoute.waypoints[0].latitude, optimizedRoute.waypoints[0].longitude]} 
            icon={portIcon}
          >
            <Popup>
              <div className="font-medium">Origin Port</div>
              <div className="text-xs text-gray-500">
                {optimizedRoute.waypoints[0].latitude.toFixed(4)}, {optimizedRoute.waypoints[0].longitude.toFixed(4)}
              </div>
            </Popup>
          </Marker>
          
          {/* Destination marker */}
          <Marker 
            position={[
              optimizedRoute.waypoints[optimizedRoute.waypoints.length - 1].latitude, 
              optimizedRoute.waypoints[optimizedRoute.waypoints.length - 1].longitude
            ]} 
            icon={portIcon}
          >
            <Popup>
              <div className="font-medium">Destination Port</div>
              <div className="text-xs text-gray-500">
                {optimizedRoute.waypoints[optimizedRoute.waypoints.length - 1].latitude.toFixed(4)}, 
                {optimizedRoute.waypoints[optimizedRoute.waypoints.length - 1].longitude.toFixed(4)}
              </div>
            </Popup>
          </Marker>
          
          {/* Route line */}
          <Polyline
            positions={optimizedRoute.waypoints.map(wp => [wp.latitude, wp.longitude])}
            color="#3b82f6"  // blue-500
            weight={4}
            opacity={0.8}
          />
          
          {/* Weather risk markers */}
          {optimizedRoute.weatherRisks && optimizedRoute.weatherRisks.map((risk, index) => (
            <Marker
              key={`risk-${index}`}
              position={[risk.position.latitude, risk.position.longitude]}
              icon={createRiskIcon(risk.risk)}
            >
              <Popup>
                <div className={`px-2 py-1 rounded-full text-xs font-medium ${
                  risk.risk === 'high' ? 'bg-red-100 text-red-800' :
                  risk.risk === 'medium' ? 'bg-amber-100 text-amber-800' :
                  'bg-blue-100 text-blue-800'
                }`}>
                  {risk.risk.toUpperCase()} RISK
                </div>
                <div className="font-medium mt-1">{risk.description}</div>
              </Popup>
            </Marker>
          ))}
        </>
      )}
    </MapContainer>
  );
};

export default VoyageMap;
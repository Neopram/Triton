// src/modules/FleetTracker/MapView.tsx
import React, { useRef, useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Ship, Anchor, Navigation } from 'lucide-react';

// Define interfaces for expected props
interface Position {
  latitude: number;
  longitude: number;
}

export interface Vessel {
  id: string;
  name: string;
  type: string;
  flag: string;
  imo: string;
  position: Position;
  speed: number;
  heading: number;
  status: 'sailing' | 'anchored' | 'docked' | 'maintenance';
  destination?: string;
  eta?: string;
  origin?: string;
}

export interface Port {
  id: string;
  name: string;
  country: string;
  latitude: number;
  longitude: number;
  status: 'operational' | 'limited' | 'closed';
}

export interface Route {
  id: string;
  vesselId: string;
  origin: string;
  destination: string;
  waypoints: Array<{latitude: number; longitude: number}>;
  active: boolean;
  completed: boolean;
}

interface MapViewProps {
  vessels: Vessel[];
  ports?: Port[];
  routes?: Route[];
  selectedVessel?: Vessel | null;
  onVesselSelect?: (vessel: Vessel) => void;
}

// Component to fly to a position
const FlyToPosition = ({ position }: { position: [number, number] }) => {
  const map = useMap();
  
  useEffect(() => {
    if (position && position.length === 2) {
      map.flyTo(position, 13, {
        duration: 1.5
      });
    }
  }, [map, position]);
  
  return null;
};

// Custom ship icon
const createShipIcon = (status: string, isSelected: boolean) => {
  let color = '#3b82f6'; // blue-500
  
  if (status === 'sailing') color = '#22c55e'; // green-500
  if (status === 'anchored') color = '#f59e0b'; // amber-500
  if (status === 'docked') color = '#6366f1'; // indigo-500
  if (status === 'maintenance') color = '#64748b'; // slate-500
  
  return L.divIcon({
    html: `
      <svg 
        width="24" 
        height="24" 
        viewBox="0 0 24 24" 
        fill="none" 
        stroke="${color}" 
        stroke-width="${isSelected ? 3 : 2}" 
        stroke-linecap="round" 
        stroke-linejoin="round"
        class="vessel-marker ${isSelected ? 'scale-125' : ''}"
        style="filter: drop-shadow(0px 2px 2px rgba(0, 0, 0, 0.25));"
      >
        <path d="M18 17L14 8H3L2 11.5h6L7 17"></path>
        <path d="M7 17h11"></path>
        <path d="M8 11.5L9 8"></path>
      </svg>
    `,
    className: '',
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -12],
  });
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

const MapView: React.FC<MapViewProps> = ({ 
  vessels, 
  ports = [], 
  routes = [], 
  selectedVessel,
  onVesselSelect = () => {} 
}) => {
  // Default center if no vessels or selectedVessel
  const defaultCenter: [number, number] = [25.7617, -80.1918]; // Miami
  const selectedPosition = selectedVessel 
    ? [selectedVessel.position.latitude, selectedVessel.position.longitude] as [number, number]
    : undefined;
  
  return (
    <MapContainer 
      center={selectedPosition || defaultCenter} 
      zoom={selectedPosition ? 10 : 3} 
      style={{ height: '100%', width: '100%', borderRadius: '0.5rem' }}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      />
      
      {/* Fly to selected vessel */}
      {selectedPosition && <FlyToPosition position={selectedPosition} />}
      
      {/* Render vessels */}
      {vessels.map(vessel => (
        <Marker
          key={vessel.id}
          position={[vessel.position.latitude, vessel.position.longitude]}
          icon={createShipIcon(vessel.status, selectedVessel?.id === vessel.id)}
          eventHandlers={{
            click: () => onVesselSelect(vessel),
          }}
        >
          <Popup className="vessel-popup">
            <div className="text-sm">
              <div className="font-medium text-base mb-1">{vessel.name}</div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                <div>
                  <span className="text-gray-500">Type:</span> {vessel.type}
                </div>
                <div>
                  <span className="text-gray-500">Flag:</span> {vessel.flag}
                </div>
                <div>
                  <span className="text-gray-500">Speed:</span> {vessel.speed} knots
                </div>
                <div>
                  <span className="text-gray-500">Heading:</span> {vessel.heading}°
                </div>
              </div>
              <div className="mt-2">
                <button 
                  onClick={() => onVesselSelect(vessel)}
                  className="w-full bg-blue-600 text-white text-xs py-1 px-2 rounded hover:bg-blue-700 transition"
                >
                  View Details
                </button>
              </div>
            </div>
          </Popup>
        </Marker>
      ))}
      
      {/* Render ports */}
      {ports.map(port => (
        <Marker
          key={port.id}
          position={[port.latitude, port.longitude]}
          icon={portIcon}
        >
          <Popup>
            <div className="text-sm">
              <div className="font-medium">{port.name}</div>
              <div><span className="text-gray-500">Country:</span> {port.country}</div>
              <div>
                <span className="text-gray-500">Status:</span> 
                <span className={
                  port.status === 'operational' ? 'text-green-600' : 
                  port.status === 'limited' ? 'text-amber-600' : 
                  'text-red-600'
                }>
                  {' '}{port.status}
                </span>
              </div>
            </div>
          </Popup>
        </Marker>
      ))}
      
      {/* Render routes */}
      {routes.map((route, index) => (
        <Polyline
          key={`route-${index}`}
          positions={route.waypoints.map(wp => [wp.latitude, wp.longitude])}
          color={route.completed ? "#94a3b8" : "#3b82f6"}
          weight={route.active ? 4 : 3}
          opacity={route.active ? 1 : 0.7}
          dashArray={route.completed ? "5, 5" : ""}
        />
      ))}
    </MapContainer>
  );
};

export default MapView;
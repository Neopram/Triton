// src/modules/VoyagePlanner/index.tsx
import React, { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import RouteOptimizer from './RouteOptimizer';
import dynamic from 'next/dynamic';
import { Ship, Calendar, FileText, ChevronDown } from 'lucide-react';

// Import map component dynamically to avoid SSR issues with Leaflet
const VoyageMap = dynamic(() => import('./VoyageMap'), { 
  ssr: false,
  loading: () => <div className="h-[500px] bg-gray-100 flex items-center justify-center">Loading map...</div>
});

// Types
interface RouteOptimizationResult {
  waypoints: Array<{latitude: number; longitude: number}>;
  distance: number;
  duration: number;
  fuelConsumption: number;
  eta: string;
  weatherRisks: Array<{
    position: {latitude: number; longitude: number};
    risk: 'low' | 'medium' | 'high';
    description: string;
  }>;
}

interface Vessel {
  id: string;
  name: string;
  type: string;
  flag: string;
}

// Mock vessels data
const MOCK_VESSELS: Vessel[] = [
  { id: 'v1', name: 'Neptune Carrier', type: 'Container Ship', flag: 'Panama' },
  { id: 'v2', name: 'Atlantic Explorer', type: 'Bulk Carrier', flag: 'Liberia' },
  { id: 'v3', name: 'Pacific Star', type: 'Tanker', flag: 'Marshall Islands' },
];

const VoyagePlanner: React.FC = () => {
  const [activeTab, setActiveTab] = useState('new');
  const [selectedVessel, setSelectedVessel] = useState<string>('');
  const [optimizedRoute, setOptimizedRoute] = useState<RouteOptimizationResult | null>(null);
  
  // Handle receiving optimized route
  const handleRouteCalculated = (route: RouteOptimizationResult) => {
    setOptimizedRoute(route);
  };
  
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-800">Voyage Planner</h1>
        <div className="flex space-x-2">
          <button className="px-3 py-1.5 border border-gray-300 rounded-md text-sm hover:bg-gray-50 transition">
            History
          </button>
          <button className="px-3 py-1.5 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700 transition">
            Save Plan
          </button>
        </div>
      </div>
      
      <Tabs defaultValue="new" onValueChange={setActiveTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="new">New Voyage</TabsTrigger>
          <TabsTrigger value="active">Active Voyages</TabsTrigger>
          <TabsTrigger value="scheduled">Scheduled</TabsTrigger>
        </TabsList>
        
        <TabsContent value="new" className="space-y-6">
          {/* Vessel Selection */}
          <div className="bg-white rounded-lg shadow-sm p-4">
            <h3 className="font-semibold text-gray-800 mb-3">Select Vessel</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {MOCK_VESSELS.map(vessel => (
                <div
                  key={vessel.id}
                  className={`border p-3 rounded-lg cursor-pointer transition ${
                    selectedVessel === vessel.id ? 'border-blue-500 bg-blue-50' : 'hover:bg-gray-50'
                  }`}
                  onClick={() => setSelectedVessel(vessel.id)}
                >
                  <div className="font-medium">{vessel.name}</div>
                  <div className="text-sm text-gray-500">{vessel.type} • {vessel.flag}</div>
                </div>
              ))}
            </div>
          </div>
          
          {/* Main planning section */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Route optimizer */}
            <div className="lg:col-span-1">
              <RouteOptimizer 
                vesselId={selectedVessel} 
                onRouteCalculated={handleRouteCalculated} 
              />
            </div>
            
            {/* Map and additional options */}
            <div className="lg:col-span-2 space-y-6">
              {/* Map view */}
              <div className="bg-white rounded-lg shadow-sm overflow-hidden h-[500px]">
                <VoyageMap optimizedRoute={optimizedRoute} />
              </div>
              
              {/* Schedule details (visible when route is optimized) */}
              {optimizedRoute && (
                <div className="bg-white rounded-lg shadow-sm p-4">
                  <div className="flex justify-between items-center mb-3">
                    <h3 className="font-semibold text-gray-800">Voyage Schedule</h3>
                    <button className="text-blue-600 text-sm hover:underline flex items-center">
                      <Calendar size={14} className="mr-1" />
                      Add to Calendar
                    </button>
                  </div>
                  
                  <div className="border-b pb-3 mb-3">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <div className="text-sm text-gray-500 mb-1">Departure</div>
                        <div className="font-medium">Now</div>
                      </div>
                      
                      <div>
                        <div className="text-sm text-gray-500 mb-1">Estimated Arrival</div>
                        <div className="font-medium">
                          {new Date(optimizedRoute.eta).toLocaleString()}
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <div className="border-b pb-3 mb-3">
                    <details className="group">
                      <summary className="flex justify-between items-center cursor-pointer">
                        <span className="font-medium text-gray-800">Waypoints</span>
                        <ChevronDown size={16} className="group-open:rotate-180 transition-transform" />
                      </summary>
                      <div className="pt-2 space-y-2">
                        {optimizedRoute.waypoints.map((waypoint, index) => (
                          <div key={index} className="text-sm">
                            {index === 0 ? 'Departure: ' : 
                             index === optimizedRoute.waypoints.length - 1 ? 'Arrival: ' : 
                             `Waypoint ${index}: `}
                            <span className="text-gray-600">
                              {waypoint.latitude.toFixed(4)}, {waypoint.longitude.toFixed(4)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </details>
                  </div>
                  
                  <div className="flex justify-end">
                    <button className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition text-sm flex items-center">
                      <FileText size={14} className="mr-1" />
                      Generate Voyage Plan
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </TabsContent>
        
        <TabsContent value="active">
          <div className="bg-white rounded-lg shadow-sm p-6 text-center">
            <Ship size={48} className="mx-auto mb-3 text-gray-400" />
            <h3 className="text-lg font-medium text-gray-800 mb-1">No Active Voyages</h3>
            <p className="text-gray-500">Currently there are no vessels in transit.</p>
          </div>
        </TabsContent>
        
        <TabsContent value="scheduled">
          <div className="bg-white rounded-lg shadow-sm p-6 text-center">
            <Calendar size={48} className="mx-auto mb-3 text-gray-400" />
            <h3 className="text-lg font-medium text-gray-800 mb-1">No Scheduled Voyages</h3>
            <p className="text-gray-500">No future voyages have been planned yet.</p>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default VoyagePlanner;
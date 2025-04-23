// src/modules/FleetTracker/MaritimeDashboard.tsx
import React, { useState, useEffect } from 'react';
import MapView, { Vessel, Port, Route } from './MapView';
import { useVesselStore } from '../../store/vesselStore';
import { useAiConfigStore } from '../../store/aiConfigStore';
import { Ship, Wind, AlertTriangle, Anchor, Navigation } from 'lucide-react';
import { aiClient } from '../../services/aiClient';

// Component for the vessel list
const VesselList: React.FC<{
  vessels: Vessel[]; 
  selectedVessel: Vessel | null;
  onVesselSelect: (vessel: Vessel) => void;
}> = ({ vessels, selectedVessel, onVesselSelect }) => {
  return (
    <div className="bg-white rounded-lg shadow-sm overflow-hidden">
      <div className="p-4 border-b">
        <h3 className="font-semibold text-gray-800">Vessel Fleet</h3>
        <p className="text-sm text-gray-500">{vessels.length} vessels monitored</p>
      </div>
      <div className="divide-y max-h-[400px] overflow-y-auto">
        {vessels.map(vessel => (
          <div
            key={vessel.id}
            className={`p-3 hover:bg-gray-50 cursor-pointer transition ${
              selectedVessel?.id === vessel.id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
            }`}
            onClick={() => onVesselSelect(vessel)}
          >
            <div className="flex justify-between items-start">
              <div>
                <div className="font-medium text-gray-900">{vessel.name}</div>
                <div className="text-sm text-gray-500">{vessel.type}</div>
              </div>
              <div className={`text-xs px-2 py-1 rounded-full ${
                vessel.status === 'sailing' ? 'bg-green-100 text-green-800' :
                vessel.status === 'anchored' ? 'bg-blue-100 text-blue-800' :
                vessel.status === 'docked' ? 'bg-amber-100 text-amber-800' :
                'bg-gray-100 text-gray-800'
              }`}>
                {vessel.status.charAt(0).toUpperCase() + vessel.status.slice(1)}
              </div>
            </div>
            {vessel.destination && (
              <div className="text-xs text-gray-500 mt-1">
                {vessel.origin ? `${vessel.origin} → ` : ''}
                {vessel.destination}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// Component for the weather widget
const WeatherWidget: React.FC<{
  location: { latitude: number; longitude: number };
}> = ({ location }) => {
  const [weather, setWeather] = useState({
    description: 'Partly cloudy',
    temperature: 24,
    windSpeed: 15,
    windDirection: 270,
    waveHeight: 1.5
  });
  
  // In a real app, you would fetch weather data based on location
  
  return (
    <div className="bg-gradient-to-br from-blue-500 to-blue-700 text-white rounded-lg shadow-sm overflow-hidden">
      <div className="p-4">
        <h3 className="font-semibold">Weather Conditions</h3>
        <p className="text-sm text-blue-100">Near selected position</p>
        
        <div className="mt-4 flex justify-between items-center">
          <div className="text-3xl font-light">{weather.temperature}°C</div>
          <div className="text-right">
            <div className="text-lg">{weather.description}</div>
            <div className="text-sm text-blue-100">
              Wind: {weather.windSpeed} knots ({weather.windDirection}°)
            </div>
          </div>
        </div>
        
        <div className="mt-4 pt-4 border-t border-blue-400">
          <div className="flex justify-between text-sm">
            <div>Wave Height</div>
            <div>{weather.waveHeight}m</div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Component for alerts panel
const AlertsPanel: React.FC = () => {
  const [alerts, setAlerts] = useState([
    { id: '1', type: 'weather', severity: 'high', message: 'Storm warning in Gulf of Mexico', time: '1h ago' },
    { id: '2', type: 'vessel', severity: 'medium', message: 'Maintenance schedule for Pacific Star approaching', time: '3h ago' },
    { id: '3', type: 'route', severity: 'low', message: 'Optimized route available for Neptune Carrier', time: '5h ago' },
  ]);
  
  return (
    <div className="bg-white rounded-lg shadow-sm overflow-hidden">
      <div className="p-4 border-b flex justify-between items-center">
        <h3 className="font-semibold text-gray-800">Active Alerts</h3>
        <span className="text-sm text-gray-500">{alerts.length} alert(s)</span>
      </div>
      <div className="divide-y max-h-[250px] overflow-y-auto">
        {alerts.map(alert => (
          <div 
            key={alert.id}
            className="p-3 hover:bg-gray-50 cursor-pointer transition"
          >
            <div className="flex items-start">
              <div className={`p-2 rounded-full mr-3 ${
                alert.severity === 'high' ? 'bg-red-100 text-red-600' :
                alert.severity === 'medium' ? 'bg-amber-100 text-amber-600' : 
                'bg-blue-100 text-blue-600'
              }`}>
                <AlertTriangle size={14} />
              </div>
              <div>
                <div className="flex justify-between w-full">
                  <div className="font-medium text-sm">{alert.message}</div>
                  <div className="text-xs text-gray-500">{alert.time}</div>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {alert.type.charAt(0).toUpperCase() + alert.type.slice(1)} Alert
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// Component for AI Panel
const AIPanel: React.FC<{
  selectedVessel: Vessel | null;
}> = ({ selectedVessel }) => {
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const { aiModel, aiStatus } = useAiConfigStore();
  
  const handleQuery = async () => {
    if (!query.trim()) return;
    
    setLoading(true);
    setResponse(null);
    
    try {
      // In a real app, this would use your aiClient
      // const result = await aiClient.query(query, { selectedVessel });
      
      // Mock response for now
      setTimeout(() => {
        if (selectedVessel) {
          setResponse(`Based on the current data for ${selectedVessel.name}, the vessel is ${selectedVessel.status} at ${selectedVessel.speed} knots. It's currently headed toward ${selectedVessel.destination || 'unknown destination'} with an estimated arrival time of ${selectedVessel.eta || 'unknown'}.`);
        } else {
          setResponse("I can provide more specific information if you select a vessel. Currently monitoring 3 vessels in the fleet.");
        }
        setLoading(false);
      }, 1500);
    } catch (error) {
      setResponse("Sorry, I encountered an error processing your request.");
      setLoading(false);
    }
  };
  
  return (
    <div className="bg-white rounded-lg shadow-sm overflow-hidden">
      <div className="p-4 border-b flex justify-between items-center">
        <h3 className="font-semibold text-gray-800">Triton AI Assistant</h3>
        <div className="flex items-center space-x-2">
          <div className="flex items-center">
            <div className={`w-2 h-2 rounded-full mr-1 ${aiStatus.cloud === 'online' ? 'bg-green-500' : 'bg-red-500'}`}></div>
            <span className="text-xs text-gray-500">DeepSeek</span>
          </div>
          <div className="flex items-center">
            <div className={`w-2 h-2 rounded-full mr-1 ${aiStatus.local === 'online' ? 'bg-green-500' : 'bg-red-500'}`}></div>
            <span className="text-xs text-gray-500">Phi-3</span>
          </div>
        </div>
      </div>
      
      <div className="p-4">
        {response && (
          <div className="bg-gray-50 p-3 rounded-lg mb-4 text-sm">
            {response}
          </div>
        )}
        
        <div className="flex">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask about vessels, routes, or maritime operations..."
            className="flex-1 border rounded-l-md px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            disabled={loading}
          />
          <button
            onClick={handleQuery}
            disabled={loading || !query.trim()}
            className="bg-blue-600 text-white px-4 py-2 rounded-r-md hover:bg-blue-700 transition disabled:bg-blue-300"
          >
            {loading ? "..." : "Ask"}
          </button>
        </div>
        
        <div className="mt-3 text-xs text-gray-500">
          Using {aiModel === 'hybrid' ? 'Hybrid' : aiModel === 'cloud' ? 'DeepSeek Cloud' : 'Phi-3 Local'} model
        </div>
      </div>
    </div>
  );
};

// Mock data for development (can be replaced with your store)
const MOCK_VESSELS: Vessel[] = [
  {
    id: '1',
    name: 'Neptune Carrier',
    type: 'Container Ship',
    flag: 'Panama',
    imo: 'IMO9395044',
    position: { latitude: 25.7617, longitude: -80.1918 },
    speed: 15.2,
    heading: 90,
    status: 'sailing',
    destination: 'Rotterdam',
    eta: '2023-11-15T14:00:00Z',
    origin: 'Miami'
  },
  {
    id: '2',
    name: 'Atlantic Explorer',
    type: 'Bulk Carrier',
    flag: 'Liberia',
    imo: 'IMO9283721',
    position: { latitude: 40.7128, longitude: -74.0060 },
    speed: 0,
    heading: 0,
    status: 'docked',
    destination: 'Charleston',
    eta: '2023-11-10T08:00:00Z',
    origin: 'New York'
  },
  {
    id: '3',
    name: 'Pacific Star',
    type: 'Tanker',
    flag: 'Marshall Islands',
    imo: 'IMO9173537',
    position: { latitude: 37.7749, longitude: -122.4194 },
    speed: 12.7,
    heading: 270,
    status: 'sailing',
    destination: 'Tokyo',
    eta: '2023-11-28T10:00:00Z',
    origin: 'San Francisco'
  }
];

const MOCK_PORTS: Port[] = [
  {
    id: 'p1',
    name: 'Port of Miami',
    country: 'USA',
    latitude: 25.7617,
    longitude: -80.1918,
    status: 'operational'
  },
  {
    id: 'p2',
    name: 'Port of New York',
    country: 'USA',
    latitude: 40.7128,
    longitude: -74.0060,
    status: 'operational'
  },
  {
    id: 'p3',
    name: 'Port of San Francisco',
    country: 'USA',
    latitude: 37.7749,
    longitude: -122.4194,
    status: 'limited'
  }
];

const MaritimeDashboard: React.FC = () => {
  // In a real implementation, you would use your stores here
  // const { vessels } = useVesselStore();
  
  const [loading, setLoading] = useState(true);
  const [vessels, setVessels] = useState<Vessel[]>(MOCK_VESSELS);
  const [ports, setPorts] = useState<Port[]>(MOCK_PORTS);
  const [selectedVessel, setSelectedVessel] = useState<Vessel | null>(null);
  const [routes, setRoutes] = useState<Route[]>([]);
  
  // Simulate loading data
  useEffect(() => {
    setTimeout(() => {
      setLoading(false);
    }, 1000);
  }, []);
  
  // Handle vessel selection
  const handleVesselSelect = (vessel: Vessel) => {
    setSelectedVessel(vessel);
    
    // In a real app, you would fetch routes for the selected vessel
    // For now, create a mock route if Neptune Carrier is selected
    if (vessel.id === '1') {
      setRoutes([
        {
          id: 'r1',
          vesselId: '1',
          origin: 'Miami',
          destination: 'Rotterdam',
          waypoints: [
            { latitude: 25.7617, longitude: -80.1918 },
            { latitude: 30.0, longitude: -70.0 },
            { latitude: 40.0, longitude: -50.0 },
            { latitude: 50.0, longitude: -20.0 },
            { latitude: 51.9066, longitude: 4.4828 }
          ],
          active: true,
          completed: false
        }
      ]);
    } else {
      setRoutes([]);
    }
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-[600px]">
        <div className="text-center">
          <div className="animate-spin w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <h2 className="text-xl font-semibold text-gray-700">Loading Fleet Data...</h2>
        </div>
      </div>
    );
  }
  
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-800">Fleet Tracker</h1>
        <div className="flex space-x-2">
          <button className="px-3 py-1.5 border border-gray-300 rounded-md text-sm hover:bg-gray-50 transition">
            Filter
          </button>
          <button className="px-3 py-1.5 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700 transition">
            Generate Report
          </button>
        </div>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left sidebar */}
        <div className="lg:col-span-1 space-y-6">
          <VesselList 
            vessels={vessels} 
            selectedVessel={selectedVessel}
            onVesselSelect={handleVesselSelect}
          />
          
          <AIPanel selectedVessel={selectedVessel} />
          
          {selectedVessel && (
            <WeatherWidget 
              location={selectedVessel.position}
            />
          )}
          
          <AlertsPanel />
        </div>
        
        {/* Main content */}
        <div className="lg:col-span-3 space-y-6">
          {/* Map container */}
          <div className="bg-white rounded-lg shadow-sm overflow-hidden h-[500px]">
            <MapView 
              vessels={vessels} 
              ports={ports} 
              routes={routes} 
              selectedVessel={selectedVessel}
              onVesselSelect={handleVesselSelect}
            />
          </div>
          
          {/* Vessel details panel */}
          {selectedVessel && (
            <div className="bg-white rounded-lg shadow-sm p-5">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h2 className="text-xl font-semibold text-gray-800">{selectedVessel.name}</h2>
                  <p className="text-gray-500">{selectedVessel.type} • IMO: {selectedVessel.imo}</p>
                </div>
                <div className={`px-3 py-1 rounded-full text-sm font-medium ${
                  selectedVessel.status === 'sailing' ? 'bg-green-100 text-green-800' :
                  selectedVessel.status === 'anchored' ? 'bg-blue-100 text-blue-800' :
                  selectedVessel.status === 'docked' ? 'bg-amber-100 text-amber-800' :
                  'bg-gray-100 text-gray-800'
                }`}>
                  {selectedVessel.status.charAt(0).toUpperCase() + selectedVessel.status.slice(1)}
                </div>
              </div>
              
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="bg-gray-50 p-3 rounded-md">
                  <div className="flex items-center text-gray-500 mb-1">
                    <Ship size={14} className="mr-1" />
                    <span className="text-xs">Flag</span>
                  </div>
                  <div className="font-medium">{selectedVessel.flag}</div>
                </div>
                
                <div className="bg-gray-50 p-3 rounded-md">
                  <div className="flex items-center text-gray-500 mb-1">
                    <Navigation size={14} className="mr-1" />
                    <span className="text-xs">Heading</span>
                  </div>
                  <div className="font-medium">{selectedVessel.heading}°</div>
                </div>
                
                <div className="bg-gray-50 p-3 rounded-md">
                  <div className="flex items-center text-gray-500 mb-1">
                    <Wind size={14} className="mr-1" />
                    <span className="text-xs">Speed</span>
                  </div>
                  <div className="font-medium">{selectedVessel.speed} knots</div>
                </div>
                
                <div className="bg-gray-50 p-3 rounded-md">
                  <div className="flex items-center text-gray-500 mb-1">
                    <Anchor size={14} className="mr-1" />
                    <span className="text-xs">Position</span>
                  </div>
                  <div className="font-medium text-sm">
                    {selectedVessel.position.latitude.toFixed(4)}, {selectedVessel.position.longitude.toFixed(4)}
                  </div>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <div className="text-sm text-gray-500 mb-1">Origin</div>
                  <div className="font-medium">{selectedVessel.origin || 'N/A'}</div>
                </div>
                
                <div>
                  <div className="text-sm text-gray-500 mb-1">Destination</div>
                  <div className="font-medium">{selectedVessel.destination || 'N/A'}</div>
                </div>
                
                <div>
                  <div className="text-sm text-gray-500 mb-1">ETA</div>
                  <div className="font-medium">
                    {selectedVessel.eta 
                      ? new Date(selectedVessel.eta).toLocaleString() 
                      : 'N/A'}
                  </div>
                </div>
              </div>
              
              <div className="mt-6 pt-4 border-t flex justify-between">
                <button className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition">
                  View Full Details
                </button>
                
                <div className="space-x-2">
                  <button className="px-4 py-2 border rounded-md hover:bg-gray-50 transition">
                    Get AI Insights
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MaritimeDashboard;
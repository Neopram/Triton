// src/modules/VoyagePlanner/RouteOptimizer.tsx
import React, { useState, useEffect } from 'react';
import { aiClient } from '../../services/aiClient';
import { useAiConfigStore } from '../../store/aiConfigStore';
import { Ship, Wind, Anchor, Navigation, BarChart, Clock, Fuel, Shield } from 'lucide-react';

// Types for the component
interface Port {
  id: string;
  name: string;
  country: string;
  latitude: number;
  longitude: number;
}

interface OptimizationPreferences {
  prioritizeFuel: number;      // 0-100
  prioritizeTime: number;      // 0-100
  prioritizeSafety: number;    // 0-100
  avoidHighSeas: boolean;      // Prefer coastal routes
  considerWeather: boolean;    // Consider weather forecasts
}

interface RouteOptimizationResult {
  waypoints: Array<{latitude: number; longitude: number}>;
  distance: number;   // Nautical miles
  duration: number;   // Hours
  fuelConsumption: number;
  eta: string;
  weatherRisks: Array<{
    position: {latitude: number; longitude: number};
    risk: 'low' | 'medium' | 'high';
    description: string;
  }>;
  alternativeRoutes?: number;
}

interface RouteOptimizerProps {
  availablePorts?: Port[];
  vesselId?: string;
  onRouteCalculated?: (route: RouteOptimizationResult) => void;
}

const RouteOptimizer: React.FC<RouteOptimizerProps> = ({ 
  availablePorts = [], 
  vesselId,
  onRouteCalculated 
}) => {
  // Default ports if none provided
  const defaultPorts: Port[] = [
    { id: 'p1', name: 'Port of Miami', country: 'USA', latitude: 25.7617, longitude: -80.1918 },
    { id: 'p2', name: 'Port of New York', country: 'USA', latitude: 40.7128, longitude: -74.0060 },
    { id: 'p3', name: 'Port of Rotterdam', country: 'Netherlands', latitude: 51.9066, longitude: 4.4828 },
    { id: 'p4', name: 'Port of Singapore', country: 'Singapore', latitude: 1.2655, longitude: 103.8244 },
    { id: 'p5', name: 'Port of Shanghai', country: 'China', latitude: 31.2339, longitude: 121.4828 },
  ];
  
  const ports = availablePorts.length > 0 ? availablePorts : defaultPorts;
  
  // State for the component
  const [originPort, setOriginPort] = useState<string>('');
  const [destinationPort, setDestinationPort] = useState<string>('');
  const [preferences, setPreferences] = useState<OptimizationPreferences>({
    prioritizeFuel: 33,
    prioritizeTime: 33,
    prioritizeSafety: 34,
    avoidHighSeas: false,
    considerWeather: true
  });
  const [isCalculating, setIsCalculating] = useState(false);
  const [result, setResult] = useState<RouteOptimizationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Get AI config from store
  const { aiModel, aiStatus } = useAiConfigStore();
  
  // Effect to reset results when ports change
  useEffect(() => {
    setResult(null);
    setError(null);
  }, [originPort, destinationPort]);
  
  // Handle preferences change
  const handlePreferenceChange = (key: keyof OptimizationPreferences, value: any) => {
    setPreferences(prev => ({
      ...prev,
      [key]: value
    }));
  };
  
  // Calculate route
  const calculateRoute = async () => {
    if (!originPort || !destinationPort) {
      setError('Please select origin and destination ports');
      return;
    }
    
    setIsCalculating(true);
    setError(null);
    
    try {
      // Find the port objects
      const origin = ports.find(p => p.id === originPort);
      const destination = ports.find(p => p.id === destinationPort);
      
      if (!origin || !destination) {
        throw new Error('Invalid ports selected');
      }
      
      // Call the AI service
      const response = await aiClient.optimizeRoute(
        vesselId || 'default',
        origin,
        destination,
        preferences
      );
      
      if (response.success) {
        setResult(response.data.optimizedRoute);
        
        // Notify parent component if callback provided
        if (onRouteCalculated) {
          onRouteCalculated(response.data.optimizedRoute);
        }
      } else {
        setError(response.error || 'Failed to calculate route');
      }
    } catch (error: any) {
      console.error('Error calculating route:', error);
      setError(error.message || 'An error occurred while calculating the route');
    } finally {
      setIsCalculating(false);
    }
  };
  
  return (
    <div className="bg-white rounded-lg shadow-sm">
      <div className="p-4 border-b">
        <h3 className="font-semibold text-gray-800">AI Route Optimizer</h3>
        <p className="text-sm text-gray-500">Calculate optimal maritime routes with AI assistance</p>
      </div>
      
      <div className="p-4">
        {/* Port selection */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Origin Port</label>
            <select
              value={originPort}
              onChange={(e) => setOriginPort(e.target.value)}
              className="w-full border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isCalculating}
            >
              <option value="">Select origin port</option>
              {ports.map(port => (
                <option key={port.id} value={port.id}>
                  {port.name}, {port.country}
                </option>
              ))}
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Destination Port</label>
            <select
              value={destinationPort}
              onChange={(e) => setDestinationPort(e.target.value)}
              className="w-full border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isCalculating}
            >
              <option value="">Select destination port</option>
              {ports.map(port => (
                <option key={port.id} value={port.id} disabled={port.id === originPort}>
                  {port.name}, {port.country}
                </option>
              ))}
            </select>
          </div>
        </div>
        
        {/* Optimization preferences */}
        <div className="mb-6">
          <h4 className="text-sm font-medium text-gray-700 mb-3">Route Preferences</h4>
          
          <div className="space-y-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Priority Balance</label>
              <div className="grid grid-cols-3 gap-2 mb-1">
                <div className="text-xs text-center">Fuel Efficiency</div>
                <div className="text-xs text-center">Speed</div>
                <div className="text-xs text-center">Safety</div>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={preferences.prioritizeFuel}
                  onChange={(e) => {
                    const fuel = parseInt(e.target.value);
                    const remaining = 100 - fuel;
                    handlePreferenceChange('prioritizeFuel', fuel);
                    handlePreferenceChange('prioritizeTime', Math.floor(remaining / 2));
                    handlePreferenceChange('prioritizeSafety', Math.ceil(remaining / 2));
                  }}
                  className="w-full"
                  disabled={isCalculating}
                />
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={preferences.prioritizeTime}
                  onChange={(e) => {
                    const time = parseInt(e.target.value);
                    const remaining = 100 - time;
                    handlePreferenceChange('prioritizeTime', time);
                    handlePreferenceChange('prioritizeFuel', Math.floor(remaining / 2));
                    handlePreferenceChange('prioritizeSafety', Math.ceil(remaining / 2));
                  }}
                  className="w-full"
                  disabled={isCalculating}
                />
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={preferences.prioritizeSafety}
                  onChange={(e) => {
                    const safety = parseInt(e.target.value);
                    const remaining = 100 - safety;
                    handlePreferenceChange('prioritizeSafety', safety);
                    handlePreferenceChange('prioritizeFuel', Math.floor(remaining / 2));
                    handlePreferenceChange('prioritizeTime', Math.ceil(remaining / 2));
                  }}
                  className="w-full"
                  disabled={isCalculating}
                />
              </div>
            </div>
            
            <div className="flex space-x-4">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={preferences.avoidHighSeas}
                  onChange={(e) => handlePreferenceChange('avoidHighSeas', e.target.checked)}
                  className="mr-2"
                  disabled={isCalculating}
                />
                <span className="text-sm">Prefer coastal routes</span>
              </label>
              
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={preferences.considerWeather}
                  onChange={(e) => handlePreferenceChange('considerWeather', e.target.checked)}
                  className="mr-2"
                  disabled={isCalculating}
                />
                <span className="text-sm">Consider weather forecasts</span>
              </label>
            </div>
          </div>
        </div>
        
        {/* AI Model Indicator */}
        <div className="mb-4 flex justify-between items-center">
          <div className="text-xs text-gray-500">
            Using {aiModel === 'hybrid' ? 'Hybrid' : aiModel === 'cloud' ? 'DeepSeek Cloud' : 'Phi-3 Local'} model
          </div>
          
          <div className="flex items-center space-x-2">
            <div className="flex items-center">
              <div className={`w-2 h-2 rounded-full mr-1 ${
                aiStatus.cloud === 'online' ? 'bg-green-500' : 'bg-red-500'
              }`}></div>
              <span className="text-xs">DeepSeek</span>
            </div>
            
            <div className="flex items-center">
              <div className={`w-2 h-2 rounded-full mr-1 ${
                aiStatus.local === 'online' ? 'bg-green-500' : 'bg-red-500'
              }`}></div>
              <span className="text-xs">Phi-3</span>
            </div>
          </div>
        </div>
        
        {/* Calculate button */}
        <button
          onClick={calculateRoute}
          disabled={!originPort || !destinationPort || isCalculating}
          className="w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700 transition disabled:bg-blue-300 flex items-center justify-center"
        >
          {isCalculating ? (
            <>
              <div className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full mr-2"></div>
              Calculating Optimal Route...
            </>
          ) : (
            'Calculate Route'
          )}
        </button>
        
        {/* Error message */}
        {error && (
          <div className="mt-4 text-sm text-red-600 bg-red-50 p-3 rounded-md">
            {error}
          </div>
        )}
        
        {/* Results */}
        {result && (
          <div className="mt-6 border-t pt-4">
            <h4 className="font-medium text-gray-800 mb-3">Optimized Route Details</h4>
            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <div className="bg-gray-50 p-3 rounded-md">
                <div className="flex items-center text-gray-500 mb-1">
                  <Navigation size={14} className="mr-1" />
                  <span className="text-xs">Distance</span>
                </div>
                <div className="font-medium">{result.distance.toLocaleString()} nm</div>
              </div>
              
              <div className="bg-gray-50 p-3 rounded-md">
                <div className="flex items-center text-gray-500 mb-1">
                  <Clock size={14} className="mr-1" />
                  <span className="text-xs">Duration</span>
                </div>
                <div className="font-medium">{result.duration.toLocaleString()} hours</div>
              </div>
              
              <div className="bg-gray-50 p-3 rounded-md">
                <div className="flex items-center text-gray-500 mb-1">
                  <Fuel size={14} className="mr-1" />
                  <span className="text-xs">Fuel</span>
                </div>
                <div className="font-medium">{result.fuelConsumption.toLocaleString()} mt</div>
              </div>
              
              <div className="bg-gray-50 p-3 rounded-md">
                <div className="flex items-center text-gray-500 mb-1">
                  <Ship size={14} className="mr-1" />
                  <span className="text-xs">ETA</span>
                </div>
                <div className="font-medium">{new Date(result.eta).toLocaleString()}</div>
              </div>
            </div>
            
            {/* Weather risks */}
            {result.weatherRisks.length > 0 && (
              <div className="mb-4">
                <h5 className="text-sm font-medium text-gray-700 mb-2">Weather Risks</h5>
                <div className="space-y-2">
                  {result.weatherRisks.map((risk, index) => (
                    <div 
                      key={index}
                      className={`text-xs p-2 rounded-md ${
                        risk.risk === 'high' ? 'bg-red-50 text-red-800' :
                        risk.risk === 'medium' ? 'bg-amber-50 text-amber-800' :
                        'bg-blue-50 text-blue-800'
                      }`}
                    >
                      <div className="flex items-start">
                        <Shield size={14} className="mr-1 mt-0.5" />
                        <div>
                          <div className="font-medium">{risk.description}</div>
                          <div>Near {risk.position.latitude.toFixed(2)}, {risk.position.longitude.toFixed(2)}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* AI Commentary */}
            <div className="bg-blue-50 p-3 rounded-md text-sm text-blue-800 mb-4">
              <div className="flex items-start">
                <BarChart size={16} className="mr-2 mt-0.5" />
                <div>
                  This route was optimized based on your preferences for {preferences.prioritizeFuel}% fuel efficiency, 
                  {preferences.prioritizeTime}% speed, and {preferences.prioritizeSafety}% safety. 
                  {result.alternativeRoutes && result.alternativeRoutes > 0 && (
                    ` ${result.alternativeRoutes} alternative routes were considered.`
                  )}
                  {preferences.considerWeather && ' Weather forecast data was incorporated in this calculation.'}
                </div>
              </div>
            </div>
            
            <div className="flex justify-between">
              <button className="px-4 py-2 border rounded-md hover:bg-gray-50 transition text-sm">
                View on Map
              </button>
              
              <button className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition text-sm">
                Apply Route
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// Mock function for generating demo results (not used in production)
const generateMockResult = (origin: Port, destination: Port): RouteOptimizationResult => {
  const distance = Math.floor(Math.random() * 5000) + 1000;
  const speed = 15 + Math.random() * 5;
  const duration = Math.round(distance / speed);
  
  const fuelConsumption = Math.round(duration * (20 + Math.random() * 10));
  
  const now = new Date();
  const etaDate = new Date(now.getTime() + duration * 60 * 60 * 1000);
  
  // Generate waypoints between origin and destination
  const waypoints = [
    { latitude: origin.latitude, longitude: origin.longitude }
  ];
  
  const steps = 5 + Math.floor(Math.random() * 5);
  for (let i = 1; i < steps; i++) {
    const ratio = i / steps;
    const lat = origin.latitude + ratio * (destination.latitude - origin.latitude);
    const lon = origin.longitude + ratio * (destination.longitude - origin.longitude);
    
    // Add some randomness to make it look like a realistic route
    const latVar = (Math.random() - 0.5) * 5;
    const lonVar = (Math.random() - 0.5) * 5;
    
    waypoints.push({
      latitude: lat + latVar,
      longitude: lon + lonVar
    });
  }
  
  waypoints.push({ latitude: destination.latitude, longitude: destination.longitude });
  
  // Generate some weather risks
  const weatherRisks = [];
  if (Math.random() > 0.3) {
    const riskTypes = ['high', 'medium', 'low'];
    const riskDescriptions = [
      'Strong winds exceeding 30 knots',
      'Moderate wave height of 3-4 meters',
      'Limited visibility due to fog',
      'Potential storm system developing',
      'High traffic area requiring caution'
    ];
    
    const numRisks = Math.floor(Math.random() * 3) + 1;
    for (let i = 0; i < numRisks; i++) {
      const waypointIndex = Math.floor(Math.random() * (waypoints.length - 2)) + 1;
      const riskType = riskTypes[Math.floor(Math.random() * riskTypes.length)] as 'low' | 'medium' | 'high';
      const description = riskDescriptions[Math.floor(Math.random() * riskDescriptions.length)];
      
      weatherRisks.push({
        position: waypoints[waypointIndex],
        risk: riskType,
        description
      });
    }
  }
  
  return {
    waypoints,
    distance,
    duration,
    fuelConsumption,
    eta: etaDate.toISOString(),
    weatherRisks,
    alternativeRoutes: Math.floor(Math.random() * 5)
  };
};

export default RouteOptimizer;
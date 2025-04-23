// src/modules/FleetTracker/index.tsx
import React, { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import MaritimeDashboard from './MaritimeDashboard';
import TableView from './TableView';

const FleetTracker: React.FC = () => {
  const [activeView, setActiveView] = useState<'map' | 'table'>('map');
  
  return (
    <div className="space-y-6">
      <Tabs defaultValue="map" onValueChange={(value) => setActiveView(value as 'map' | 'table')}>
        <div className="flex justify-between items-center mb-4">
          <h1 className="text-2xl font-bold text-gray-800">Fleet Tracker</h1>
          <TabsList>
            <TabsTrigger value="map">Map View</TabsTrigger>
            <TabsTrigger value="table">Table View</TabsTrigger>
          </TabsList>
        </div>
        
        <TabsContent value="map" className="m-0">
          <MaritimeDashboard />
        </TabsContent>
        
        <TabsContent value="table" className="m-0">
          <TableView />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default FleetTracker;
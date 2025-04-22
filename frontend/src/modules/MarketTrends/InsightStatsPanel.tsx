import React, { useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { PieChart, Pie, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, Cell, ResponsiveContainer } from 'recharts';
import { Star, BarChart2 } from 'lucide-react';
import useInsightStore from '../../store/insightStore';

const InsightStatsPanel: React.FC = () => {
  const { stats, fetchStats, loading } = useInsightStore();
  
  useEffect(() => {
    fetchStats();
  }, [fetchStats]);
  
  if (loading || !stats) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <BarChart2 className="h-10 w-10 text-gray-400 mx-auto mb-2" />
          <p>Loading statistics...</p>
        </div>
      </div>
    );
  }
  
  if (stats.total_count === 0) {
    return (
      <div className="text-center py-12">
        <div className="mb-4">
          <BarChart2 size={48} className="mx-auto text-gray-400" />
        </div>
        <h3 className="text-lg font-medium mb-2">No insight data available</h3>
        <p className="text-gray-500">
          Generate market insights to view statistics
        </p>
      </div>
    );
  }
  
  // Prepare data for engine distribution chart
  const engineData = Object.entries(stats.engine_counts || {}).map(([name, value]) => ({
    name,
    value: Number(value)
  })).filter(item => item.value > 0);
  
  // Generate rating distribution if we had that data
  // For now, using placeholder data that would come from backend
  const getRatingDistribution = () => {
    // In a real implementation, this would come from the backend
    // Here we're creating sample data for visualization purposes
    return [
      { name: "5 Stars", count: Math.floor(Math.random() * 5) + 1 },
      { name: "4 Stars", count: Math.floor(Math.random() * 8) + 2 },
      { name: "3 Stars", count: Math.floor(Math.random() * 6) + 1 },
      { name: "2 Stars", count: Math.floor(Math.random() * 3) },
      { name: "1 Star", count: Math.floor(Math.random() * 2) }
    ];
  };
  
  const ratingData = getRatingDistribution();
  
  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8'];
  
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Total Insights</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{stats.total_count}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Average Rating</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center">
              <div className="text-3xl font-bold">
                {stats.average_rating ? stats.average_rating.toFixed(1) : "—"}
              </div>
              {stats.average_rating && (
                <Star className="ml-2 h-6 w-6 text-yellow-500 fill-yellow-500" />
              )}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Rated Insights</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{stats.rated_count || 0}</div>
            <div className="text-sm text-gray-500">
              {stats.total_count ? 
                `${Math.round((stats.rated_count || 0) / stats.total_count * 100)}% of total` : 
                '0%'}
            </div>
          </CardContent>
        </Card>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Engine Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={engineData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {engineData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
        
        {stats.rated_count > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Rating Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={ratingData}
                    margin={{
                      top: 5,
                      right: 30,
                      left: 20,
                      bottom: 5,
                    }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="count" fill="#fbbf24" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default InsightStatsPanel;
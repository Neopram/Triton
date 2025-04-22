import React, { useEffect, useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Upload, BarChart2, Lightbulb, History, BarChart, PieChart } from 'lucide-react';
import MarketSummaryPanel from './MarketSummaryPanel';
import MarketAnalysisPanel from './MarketAnalysisPanel';
import MarketInsightPanel from './MarketInsightPanel';
import InsightHistoryPanel from './InsightHistoryPanel';
import InsightStatsPanel from './InsightStatsPanel';
import ReportUploadPanel from './ReportUploadPanel';
import useInsightStore from '../../store/insightStore';

const MarketTrends: React.FC = () => {
  const [activeTab, setActiveTab] = useState('summary');
  const { fetchLatestInsight, latestInsight, loading } = useInsightStore();
  
  useEffect(() => {
    // When showing insights tab, fetch the latest insight
    if (activeTab === 'insights') {
      fetchLatestInsight();
    }
  }, [activeTab, fetchLatestInsight]);
  
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Market Trends</CardTitle>
              <CardDescription>
                Analyze market rates, trends, and AI-powered insights
              </CardDescription>
            </div>
            <Button onClick={() => setActiveTab('upload')} className="flex items-center gap-2">
              <Upload size={16} />
              Analyze New Report
            </Button>
          </div>
        </CardHeader>
        
        <CardContent>
          <Tabs defaultValue="summary" value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-5">
              <TabsTrigger value="summary" className="flex items-center gap-2">
                <BarChart2 size={16} />
                Market Summary
              </TabsTrigger>
              <TabsTrigger value="analysis" className="flex items-center gap-2">
                <BarChart size={16} />
                Rate Analysis
              </TabsTrigger>
              <TabsTrigger value="insights" className="flex items-center gap-2">
                <Lightbulb size={16} />
                AI Insights
              </TabsTrigger>
              <TabsTrigger value="history" className="flex items-center gap-2">
                <History size={16} />
                Insight History
              </TabsTrigger>
              <TabsTrigger value="stats" className="flex items-center gap-2">
                <PieChart size={16} />
                Insight Stats
              </TabsTrigger>
            </TabsList>
            
            <TabsContent value="summary">
              <MarketSummaryPanel />
            </TabsContent>
            
            <TabsContent value="analysis">
              <MarketAnalysisPanel />
            </TabsContent>
            
            <TabsContent value="insights">
              <MarketInsightPanel 
                insight={latestInsight} 
                loading={loading} 
                onAnalyzeNew={() => setActiveTab('upload')}
              />
            </TabsContent>
            
            <TabsContent value="history">
              <InsightHistoryPanel />
            </TabsContent>
            
            <TabsContent value="stats">
              <InsightStatsPanel />
            </TabsContent>
            
            <TabsContent value="upload">
              <div className="py-4">
                <ReportUploadPanel onSuccess={() => setActiveTab('insights')} />
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
};

export default MarketTrends;
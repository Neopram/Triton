import React, { useEffect, useState } from 'react';
import { useKnowledgeStore } from '../../store/knowledgeStore';
import DocumentUploader from './DocumentUploader';
import KnowledgeExplorer from './KnowledgeExplorer';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { RefreshCw, Database, AlertCircle } from 'lucide-react';
import { Button } from '../../components/Button';
import { formatDistanceToNow } from 'date-fns';

const KnowledgeBase: React.FC = () => {
  const { 
    documents, 
    stats, 
    isLoading, 
    error, 
    fetchDocuments, 
    fetchStats,
    refreshIndex
  } = useKnowledgeStore();
  
  const [activeTab, setActiveTab] = useState<string>('explorer');
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  
  useEffect(() => {
    fetchDocuments();
    fetchStats();
  }, [fetchDocuments, fetchStats]);
  
  const handleRefreshIndex = async () => {
    setIsRefreshing(true);
    await refreshIndex();
    setIsRefreshing(false);
  };
  
  return (
    <div className="container mx-auto p-4 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Knowledge Base</h1>
          <p className="text-gray-600">Manage and explore your contextual knowledge for enhanced AI responses</p>
        </div>
        <Button 
          onClick={handleRefreshIndex}
          disabled={isRefreshing || isLoading}
          className="flex items-center gap-2"
        >
          <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          {isRefreshing ? 'Refreshing...' : 'Refresh Index'}
        </Button>
      </div>
      
      {error && (
        <div className="bg-red-50 p-4 rounded-lg flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-red-500 mt-0.5" />
          <div>
            <h3 className="text-red-800 font-medium">Error</h3>
            <p className="text-red-600">{error}</p>
          </div>
        </div>
      )}
      
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="md:col-span-3">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="explorer">Document Explorer</TabsTrigger>
              <TabsTrigger value="upload">Upload Documents</TabsTrigger>
            </TabsList>
            <TabsContent value="explorer">
              <KnowledgeExplorer />
            </TabsContent>
            <TabsContent value="upload">
              <DocumentUploader />
            </TabsContent>
          </Tabs>
        </div>
        
        <div className="md:col-span-1">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5" />
                Index Statistics
              </CardTitle>
              <CardDescription>
                Knowledge base metrics
              </CardDescription>
            </CardHeader>
            <CardContent>
              {stats ? (
                <div className="space-y-4">
                  <div>
                    <p className="text-sm font-medium text-gray-500">Documents</p>
                    <p className="text-2xl font-bold">{stats.total_documents}</p>
                  </div>
                  
                  <div>
                    <p className="text-sm font-medium text-gray-500">Knowledge Chunks</p>
                    <p className="text-2xl font-bold">{stats.total_chunks}</p>
                  </div>
                  
                  <div>
                    <p className="text-sm font-medium text-gray-500">Index Size</p>
                    <p className="text-2xl font-bold">{stats.index_size_mb.toFixed(2)} MB</p>
                  </div>
                  
                  <div className="pt-2 border-t border-gray-200">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-xs">
                        Last updated
                      </Badge>
                      <span className="text-xs text-gray-500">
                        {formatDistanceToNow(new Date(stats.last_updated), { addSuffix: true })}
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-40 flex items-center justify-center">
                  <p className="text-gray-500">Loading statistics...</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBase;
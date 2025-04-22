import React, { useEffect, useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { 
  Database, 
  BookOpen, 
  Brain, 
  BarChart, 
  Activity, 
  Settings 
} from 'lucide-react';
import { useTrainingStore } from '../../store/trainingStore';
import DatasetManager from './DatasetManager';
import TrainingConfig from './TrainingConfig';
import TrainingMonitor from './TrainingMonitor';
import ModelEvaluation from './ModelEvaluation';
import ModelSelector from './ModelSelector';
import { useAuthStore } from '../../store/authStore';

const Training: React.FC = () => {
  const { user } = useAuthStore();
  const { 
    fetchDatasets, 
    fetchTrainingJobs, 
    fetchDeployedModels,
    loading,
    error
  } = useTrainingStore();
  
  const [activeTab, setActiveTab] = useState('datasets');
  
  // Load data on component mount
  useEffect(() => {
    fetchDatasets();
    fetchTrainingJobs();
    fetchDeployedModels();
  }, [fetchDatasets, fetchTrainingJobs, fetchDeployedModels]);
  
  // Check permissions
  if (!user || !['admin', 'researcher'].includes(user.role)) {
    return (
      <div className="container mx-auto p-8 text-center">
        <div className="bg-yellow-50 p-6 rounded-lg">
          <div className="mx-auto w-12 h-12 bg-yellow-100 text-yellow-600 rounded-full flex items-center justify-center mb-4">
            <Settings className="h-6 w-6" />
          </div>
          <h3 className="text-lg font-medium mb-2">Access Restricted</h3>
          <p className="text-gray-600">
            The model training system requires administrator or researcher privileges.
          </p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="container mx-auto px-4 py-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Model Training Platform</h1>
        <p className="text-gray-600">
          Fine-tune domain-specific models for maritime intelligence using LoRA (Low-Rank Adaptation)
        </p>
      </div>
      
      {error && (
        <div className="bg-red-50 text-red-700 p-4 mb-6 rounded-md flex items-center">
          <div className="mr-3 flex-shrink-0">
            <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-medium">{error}</p>
          </div>
        </div>
      )}
      
      <Card>
        <CardHeader className="pb-4">
          <CardTitle>Model Training Pipeline</CardTitle>
          <CardDescription>
            Create datasets, configure and run training jobs, and deploy fine-tuned models
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <Tabs 
            value={activeTab} 
            onValueChange={setActiveTab}
            className="w-full"
          >
            <TabsList className="grid grid-cols-5 mb-6">
              <TabsTrigger value="datasets" className="flex items-center gap-2">
                <Database className="h-4 w-4" />
                <span>Datasets</span>
              </TabsTrigger>
              <TabsTrigger value="training" className="flex items-center gap-2">
                <BookOpen className="h-4 w-4" />
                <span>Training</span>
              </TabsTrigger>
              <TabsTrigger value="monitoring" className="flex items-center gap-2">
                <Activity className="h-4 w-4" />
                <span>Monitoring</span>
              </TabsTrigger>
              <TabsTrigger value="evaluation" className="flex items-center gap-2">
                <BarChart className="h-4 w-4" />
                <span>Evaluation</span>
              </TabsTrigger>
              <TabsTrigger value="models" className="flex items-center gap-2">
                <Brain className="h-4 w-4" />
                <span>Models</span>
              </TabsTrigger>
            </TabsList>
            
            <div className="px-6 pb-6">
              <TabsContent value="datasets">
                <DatasetManager />
              </TabsContent>
              
              <TabsContent value="training">
                <TrainingConfig />
              </TabsContent>
              
              <TabsContent value="monitoring">
                <TrainingMonitor />
              </TabsContent>
              
              <TabsContent value="evaluation">
                <ModelEvaluation />
              </TabsContent>
              
              <TabsContent value="models">
                <ModelSelector />
              </TabsContent>
            </div>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
};

export default Training;
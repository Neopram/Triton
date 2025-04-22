import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { 
  Brain, 
  Settings, 
  RefreshCw, 
  CheckCircle, 
  XCircle,
  Zap,
  Star,
  AlertTriangle
} from 'lucide-react';
import { useTrainingStore } from '../../store/trainingStore';
import { format } from 'date-fns';

const ModelTrainingPanel: React.FC = () => {
  const { 
    deployedModels,
    fetchDeployedModels,
    setDefaultModel,
    loading,
    error
  } = useTrainingStore();
  
  // Local state
  const [aiEnabledDefault, setAiEnabledDefault] = useState<boolean>(true);
  const [ragEnabledDefault, setRagEnabledDefault] = useState<boolean>(true);
  const [defaultTemperature, setDefaultTemperature] = useState<string>('0.7');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  
  // Load data on mount
  useEffect(() => {
    fetchDeployedModels();
  }, [fetchDeployedModels]);
  
  // Handle setting default model
  const handleSetDefaultModel = async (modelId: string) => {
    setIsLoading(true);
    try {
      await setDefaultModel(modelId);
      await fetchDeployedModels();
    } catch (err) {
      console.error('Error setting default model:', err);
    } finally {
      setIsLoading(false);
    }
  };
  
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Fine-Tuned Model Settings</CardTitle>
          <CardDescription>
            Configure the default models and behavior for AI inference
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex flex-col space-y-4">
            <div className="flex items-center justify-between border p-4 rounded-md">
              <div>
                <Label htmlFor="ai-enabled" className="font-medium">AI Enabled by Default</Label>
                <p className="text-sm text-gray-500">Enable AI assistant functionality by default</p>
              </div>
              <Switch 
                id="ai-enabled" 
                checked={aiEnabledDefault} 
                onCheckedChange={setAiEnabledDefault} 
              />
            </div>
            
            <div className="flex items-center justify-between border p-4 rounded-md">
              <div>
                <Label htmlFor="rag-enabled" className="font-medium">RAG Enabled by Default</Label>
                <p className="text-sm text-gray-500">Augment AI responses with knowledge base context</p>
              </div>
              <Switch 
                id="rag-enabled" 
                checked={ragEnabledDefault} 
                onCheckedChange={setRagEnabledDefault} 
              />
            </div>
            
            <div className="border p-4 rounded-md">
              <Label htmlFor="default-temperature" className="font-medium">Default Temperature</Label>
              <p className="text-sm text-gray-500 mb-2">Control the randomness of AI responses</p>
              <div className="flex space-x-4 items-center">
                <Select 
                  value={defaultTemperature} 
                  onValueChange={setDefaultTemperature}
                >
                  <SelectTrigger id="default-temperature" className="w-full">
                    <SelectValue placeholder="Select temperature" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="0.0">0.0 - Deterministic</SelectItem>
                    <SelectItem value="0.3">0.3 - Conservative</SelectItem>
                    <SelectItem value="0.5">0.5 - Balanced</SelectItem>
                    <SelectItem value="0.7">0.7 - Creative</SelectItem>
                    <SelectItem value="1.0">1.0 - Very Creative</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          
          <div className="pt-4 border-t">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-medium">Deployed Models</h3>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => fetchDeployedModels()}
                disabled={loading}
              >
                <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </div>
            
            {loading ? (
              <div className="flex justify-center items-center h-32">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-800"></div>
              </div>
            ) : deployedModels.length === 0 ? (
              <div className="text-center py-8 border rounded-md border-dashed">
                <Brain className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900">No models deployed</h3>
                <p className="text-gray-500 mt-1">
                  Fine-tune and deploy models using the training module
                </p>
                <Button
                  variant="default"
                  className="mt-4"
                  asChild
                >
                  <a href="/training">
                    <Zap className="h-4 w-4 mr-2" />
                    Go to Training
                  </a>
                </Button>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[250px]">Model</TableHead>
                    <TableHead>Base Model</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Inference Count</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {deployedModels.map(model => (
                    <TableRow key={model.id}>
                      <TableCell>
                        <div className="font-medium">
                          {model.name}
                          {model.is_default && (
                            <Badge className="ml-2 bg-blue-100 text-blue-800">Default</Badge>
                          )}
                        </div>
                        <div className="text-sm text-gray-500 mt-1">{model.description || ''}</div>
                      </TableCell>
                      <TableCell>{model.base_model.split('/').pop()}</TableCell>
                      <TableCell>
                        {model.is_active ? (
                          <div className="flex items-center text-green-600">
                            <CheckCircle className="h-4 w-4 mr-1" />
                            Active
                          </div>
                        ) : (
                          <div className="flex items-center text-gray-500">
                            <XCircle className="h-4 w-4 mr-1" />
                            Inactive
                          </div>
                        )}
                      </TableCell>
                      <TableCell>{model.inference_count.toLocaleString()}</TableCell>
                      <TableCell>
                        {!model.is_default && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleSetDefaultModel(model.id)}
                            disabled={isLoading}
                          >
                            <Star className="h-4 w-4 mr-1" />
                            Set as Default
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
            
            {deployedModels.length > 0 && (
              <div className="bg-blue-50 border border-blue-200 rounded-md p-4 mt-4 flex items-start">
                <AlertTriangle className="h-5 w-5 text-blue-600 mr-3 mt-0.5" />
                <div>
                  <h4 className="font-medium text-blue-800">Performance Note</h4>
                  <p className="text-sm text-blue-700 mt-1">
                    Fine-tuned models may have different performance characteristics than base models.
                    Always test a model thoroughly before setting it as the system default.
                  </p>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default ModelTrainingPanel;
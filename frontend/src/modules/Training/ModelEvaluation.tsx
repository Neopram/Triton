import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Slider } from '@/components/ui/slider';
import { Input } from '@/components/ui/input';
import { 
  BarChart, 
  Brain, 
  LineChart, 
  Send, 
  Sparkles, 
  Zap,
  Clock,
  Filter,
  Loader,
  ThumbsUp,
  ThumbsDown
} from 'lucide-react';
import { useTrainingStore, DeployedModel } from '../../store/trainingStore';
import { trainingClient } from '../../services/trainingClient';
import { format } from 'date-fns';

interface ComparisonResult {
  prompt: string;
  baseResponse: string;
  fineTunedResponse: string;
  baseResponseTime: number;
  fineTunedResponseTime: number;
  userPreference?: 'base' | 'fine-tuned' | 'equal';
}

const ModelEvaluation: React.FC = () => {
  const { 
    deployedModels,
    fetchDeployedModels,
    loading,
    error
  } = useTrainingStore();
  
  // Local state
  const [activeTab, setActiveTab] = useState<string>('comparison');
  const [selectedModelId, setSelectedModelId] = useState<string>('');
  const [prompt, setPrompt] = useState<string>('');
  const [responseLoading, setResponseLoading] = useState<boolean>(false);
  const [baseModelResponse, setBaseModelResponse] = useState<string | null>(null);
  const [fineTunedResponse, setFineTunedResponse] = useState<string | null>(null);
  const [baseResponseTime, setBaseResponseTime] = useState<number | null>(null);
  const [fineTunedResponseTime, setFineTunedResponseTime] = useState<number | null>(null);
  const [comparisonResults, setComparisonResults] = useState<ComparisonResult[]>([]);
  const [temperature, setTemperature] = useState<number>(0.7);
  const [maxTokens, setMaxTokens] = useState<number>(256);
  
  // Fetch deployed models on mount
  useEffect(() => {
    fetchDeployedModels();
  }, [fetchDeployedModels]);
  
  // Get the selected model
  const selectedModel = deployedModels.find(model => model.id === selectedModelId);
  
  // Select the first model if none selected
  useEffect(() => {
    if (deployedModels.length > 0 && !selectedModelId) {
      setSelectedModelId(deployedModels[0].id);
    }
  }, [deployedModels, selectedModelId]);
  
  // Generate responses from both models
  const handleCompare = async () => {
    if (!prompt || !selectedModelId) return;
    
    setResponseLoading(true);
    setBaseModelResponse(null);
    setFineTunedResponse(null);
    setBaseResponseTime(null);
    setFineTunedResponseTime(null);
    
    try {
      // Generate response from the base model
      const baseStart = performance.now();
      const baseResponse = await trainingClient.generateText(
        prompt,
        null, // Use default model (not fine-tuned)
        maxTokens,
        temperature
      );
      const baseEnd = performance.now();
      setBaseModelResponse(baseResponse.response);
      setBaseResponseTime(baseEnd - baseStart);
      
      // Generate response from the fine-tuned model
      const ftStart = performance.now();
      const ftResponse = await trainingClient.generateText(
        prompt,
        selectedModelId,
        maxTokens,
        temperature
      );
      const ftEnd = performance.now();
      setFineTunedResponse(ftResponse.response);
      setFineTunedResponseTime(ftEnd - ftStart);
      
    } catch (err) {
      console.error('Error generating responses:', err);
    } finally {
      setResponseLoading(false);
    }
  };
  
  // Save comparison result
  const saveComparison = (preference: 'base' | 'fine-tuned' | 'equal') => {
    if (!prompt || !baseModelResponse || !fineTunedResponse) return;
    
    const newResult: ComparisonResult = {
      prompt,
      baseResponse: baseModelResponse,
      fineTunedResponse,
      baseResponseTime: baseResponseTime || 0,
      fineTunedResponseTime: fineTunedResponseTime || 0,
      userPreference: preference
    };
    
    setComparisonResults([newResult, ...comparisonResults]);
    
    // Clear current comparison
    setPrompt('');
    setBaseModelResponse(null);
    setFineTunedResponse(null);
  };
  
  // Calculate speed difference
  const calculateSpeedDifference = () => {
    if (!baseResponseTime || !fineTunedResponseTime) return null;
    
    const difference = ((baseResponseTime - fineTunedResponseTime) / baseResponseTime) * 100;
    
    if (difference > 0) {
      return `${difference.toFixed(1)}% faster`;
    } else if (difference < 0) {
      return `${Math.abs(difference).toFixed(1)}% slower`;
    } else {
      return 'Same speed';
    }
  };
  
  // Get preference stats
  const getPreferenceStats = () => {
    if (comparisonResults.length === 0) return { base: 0, fineTuned: 0, equal: 0 };
    
    const base = comparisonResults.filter(r => r.userPreference === 'base').length;
    const fineTuned = comparisonResults.filter(r => r.userPreference === 'fine-tuned').length;
    const equal = comparisonResults.filter(r => r.userPreference === 'equal').length;
    
    return { base, fineTuned, equal };
  };
  
  const stats = getPreferenceStats();
  
  // Check if there are any models available
  if (deployedModels.length === 0 && !loading) {
    return (
      <div className="text-center py-16 border rounded-md border-dashed">
        <Brain className="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900">No models deployed</h3>
        <p className="text-gray-500 mt-1">
          You need to deploy at least one fine-tuned model to perform evaluation
        </p>
        <Button
          variant="default"
          className="mt-4"
          onClick={() => setActiveTab('models')}
        >
          <Zap className="h-4 w-4 mr-2" />
          Deploy a Model
        </Button>
      </div>
    );
  }
  
  return (
    <div className="space-y-6">
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="comparison">Model Comparison</TabsTrigger>
          <TabsTrigger value="results">Evaluation Results</TabsTrigger>
        </TabsList>
        
        <TabsContent value="comparison">
          <Card>
            <CardHeader>
              <CardTitle>Compare Models</CardTitle>
              <CardDescription>
                Compare responses between base and fine-tuned models
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <label className="block text-sm font-medium">Fine-Tuned Model</label>
                <Select 
                  value={selectedModelId} 
                  onValueChange={setSelectedModelId}
                  disabled={deployedModels.length === 0}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a model" />
                  </SelectTrigger>
                  <SelectContent>
                    {deployedModels.map((model) => (
                      <SelectItem key={model.id} value={model.id}>
                        {model.name} ({model.base_model.split('/').pop()})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <label className="block text-sm font-medium">Prompt</label>
                <Textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Enter your prompt to compare model responses..."
                  rows={4}
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="block text-sm font-medium">Temperature</label>
                  <div className="flex items-center space-x-4">
                    <Slider
                      value={[temperature * 100]}
                      min={0}
                      max={100}
                      step={1}
                      onValueChange={([value]) => setTemperature(value / 100)}
                      className="flex-1"
                    />
                    <span className="text-sm w-12 text-right">{temperature.toFixed(2)}</span>
                  </div>
                </div>
                
                <div className="space-y-2">
                  <label className="block text-sm font-medium">Max Tokens</label>
                  <div className="flex items-center space-x-4">
                    <Slider
                      value={[maxTokens]}
                      min={50}
                      max={1000}
                      step={10}
                      onValueChange={([value]) => setMaxTokens(value)}
                      className="flex-1"
                    />
                    <span className="text-sm w-12 text-right">{maxTokens}</span>
                  </div>
                </div>
              </div>
              
              <div className="flex justify-end">
                <Button
                  onClick={handleCompare}
                  disabled={responseLoading || !prompt || !selectedModelId}
                >
                  {responseLoading ? (
                    <>
                      <Loader className="h-4 w-4 mr-2 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Send className="h-4 w-4 mr-2" />
                      Compare Responses
                    </>
                  )}
                </Button>
              </div>
              
              {(baseModelResponse || fineTunedResponse || responseLoading) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4 border-t pt-6">
                  <div>
                    <h3 className="text-base font-medium mb-3 flex items-center">
                      <Brain className="h-4 w-4 mr-2" />
                      Base Model Response
                    </h3>
                    <div className="border rounded-md p-4 bg-gray-50 h-64 overflow-auto">
                      {responseLoading && !baseModelResponse ? (
                        <div className="flex items-center justify-center h-full">
                          <Loader className="h-6 w-6 animate-spin text-gray-400" />
                        </div>
                      ) : baseModelResponse ? (
                        <div className="whitespace-pre-wrap">{baseModelResponse}</div>
                      ) : (
                        <div className="text-gray-400 italic flex items-center justify-center h-full">
                          No response generated yet
                        </div>
                      )}
                    </div>
                    {baseResponseTime && (
                      <div className="mt-2 text-xs text-gray-500 flex items-center">
                        <Clock className="h-3 w-3 mr-1" />
                        Generated in {(baseResponseTime / 1000).toFixed(2)}s
                      </div>
                    )}
                  </div>
                  
                  <div>
                    <h3 className="text-base font-medium mb-3 flex items-center">
                      <Sparkles className="h-4 w-4 mr-2" />
                      Fine-Tuned Model Response
                    </h3>
                    <div className="border rounded-md p-4 bg-gray-50 h-64 overflow-auto">
                      {responseLoading && !fineTunedResponse ? (
                        <div className="flex items-center justify-center h-full">
                          <Loader className="h-6 w-6 animate-spin text-gray-400" />
                        </div>
                      ) : fineTunedResponse ? (
                        <div className="whitespace-pre-wrap">{fineTunedResponse}</div>
                      ) : (
                        <div className="text-gray-400 italic flex items-center justify-center h-full">
                          No response generated yet
                        </div>
                      )}
                    </div>
                    {fineTunedResponseTime && (
                      <div className="mt-2 text-xs text-gray-500 flex items-center justify-between">
                        <div className="flex items-center">
                          <Clock className="h-3 w-3 mr-1" />
                          Generated in {(fineTunedResponseTime / 1000).toFixed(2)}s
                        </div>
                        {calculateSpeedDifference() && (
                          <div className="text-blue-600 font-medium">
                            {calculateSpeedDifference()}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              {baseModelResponse && fineTunedResponse && (
                <div className="border-t pt-6">
                  <h3 className="text-base font-medium mb-3">Which response do you prefer?</h3>
                  <div className="flex space-x-4">
                    <Button
                      variant="outline"
                      className="flex-1"
                      onClick={() => saveComparison('base')}
                    >
                      <ThumbsUp className="h-4 w-4 mr-2" />
                      Base Model
                    </Button>
                    <Button
                      variant="outline"
                      className="flex-1"
                      onClick={() => saveComparison('equal')}
                    >
                      Both Equal
                    </Button>
                    <Button
                      variant="outline"
                      className="flex-1"
                      onClick={() => saveComparison('fine-tuned')}
                    >
                      <ThumbsUp className="h-4 w-4 mr-2" />
                      Fine-Tuned
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="results">
          <Card>
            <CardHeader>
              <CardTitle>Evaluation Results</CardTitle>
              <CardDescription>
                Summary of model comparison results
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {comparisonResults.length === 0 ? (
                <div className="text-center py-8 border rounded-md border-dashed">
                  <BarChart className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900">No comparisons yet</h3>
                  <p className="text-gray-500 mt-1">
                    Compare models to see evaluation results
                  </p>
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-gray-500">Base Model Preferred</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="text-3xl font-bold">{stats.base}</div>
                        <div className="text-sm text-gray-500 mt-1">
                          {comparisonResults.length > 0 
                            ? `${((stats.base / comparisonResults.length) * 100).toFixed(1)}% of responses`
                            : '0% of responses'
                          }
                        </div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-gray-500">Fine-Tuned Model Preferred</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="text-3xl font-bold">{stats.fineTuned}</div>
                        <div className="text-sm text-gray-500 mt-1">
                          {comparisonResults.length > 0 
                            ? `${((stats.fineTuned / comparisonResults.length) * 100).toFixed(1)}% of responses`
                            : '0% of responses'
                          }
                        </div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-gray-500">Equal Preference</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="text-3xl font-bold">{stats.equal}</div>
                        <div className="text-sm text-gray-500 mt-1">
                          {comparisonResults.length > 0 
                            ? `${((stats.equal / comparisonResults.length) * 100).toFixed(1)}% of responses`
                            : '0% of responses'
                          }
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                  
                  <div className="mt-6">
                    <h3 className="text-base font-medium mb-3">Comparison History</h3>
                    <div className="border rounded-md overflow-hidden">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="w-1/4">Prompt</TableHead>
                            <TableHead className="w-1/4">Base Response</TableHead>
                            <TableHead className="w-1/4">Fine-Tuned Response</TableHead>
                            <TableHead className="w-1/4">Preference</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {comparisonResults.map((result, index) => (
                            <TableRow key={index}>
                              <TableCell className="align-top">
                                <div className="truncate max-w-[15rem]" title={result.prompt}>
                                  {result.prompt}
                                </div>
                              </TableCell>
                              <TableCell className="align-top">
                                <div className="truncate max-w-[15rem]" title={result.baseResponse}>
                                  {result.baseResponse}
                                </div>
                                <div className="text-xs text-gray-500 mt-1">
                                  {(result.baseResponseTime / 1000).toFixed(2)}s
                                </div>
                              </TableCell>
                              <TableCell className="align-top">
                                <div className="truncate max-w-[15rem]" title={result.fineTunedResponse}>
                                  {result.fineTunedResponse}
                                </div>
                                <div className="text-xs text-gray-500 mt-1">
                                  {(result.fineTunedResponseTime / 1000).toFixed(2)}s
                                </div>
                              </TableCell>
                              <TableCell className="align-top">
                                {result.userPreference === 'base' && (
                                  <Badge className="bg-blue-100 text-blue-800">Base Model</Badge>
                                )}
                                {result.userPreference === 'fine-tuned' && (
                                  <Badge className="bg-green-100 text-green-800">Fine-Tuned</Badge>
                                )}
                                {result.userPreference === 'equal' && (
                                  <Badge className="bg-gray-100 text-gray-800">Equal</Badge>
                                )}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default ModelEvaluation;
import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { 
  Play, 
  Settings, 
  Info, 
  AlertCircle, 
  Check, 
  ChevronDown, 
  ChevronUp,
  Clock
} from 'lucide-react';
import { useTrainingStore, LoraConfig, TrainingDataset } from '../../store/trainingStore';
import { format } from 'date-fns';

// Base model options
const baseModelOptions = [
  { value: 'mistralai/Mistral-7B-v0.1', label: 'Mistral 7B' },
  { value: 'meta-llama/Llama-2-7b-hf', label: 'Llama 2 7B' },
  { value: 'microsoft/phi-2', label: 'Phi-2' },
  { value: 'PhiNet/AiroMed', label: 'AiroMed 7B' }
];

// Default LoRA configuration
const defaultLoraConfig: LoraConfig = {
  lora_r: 8,
  lora_alpha: 16,
  lora_dropout: 0.05,
  learning_rate: 0.0003,
  num_train_epochs: 3,
  per_device_train_batch_size: 4,
  gradient_accumulation_steps: 1,
  target_modules: ["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
  weight_decay: 0.001,
  optimizer: "adamw_torch",
  warmup_ratio: 0.03,
  max_grad_norm: 1.0
};

const TrainingConfig: React.FC = () => {
  const { 
    datasets, 
    trainingJobs,
    loading, 
    error,
    createTrainingJob,
    fetchDatasets,
    fetchTrainingJobs
  } = useTrainingStore();
  
  // Component state
  const [jobName, setJobName] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [selectedDatasetId, setSelectedDatasetId] = useState('');
  const [selectedModel, setSelectedModel] = useState('mistralai/Mistral-7B-v0.1');
  const [config, setConfig] = useState<LoraConfig>({...defaultLoraConfig});
  const [advancedMode, setAdvancedMode] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  
  // Update datasets on mount
  useEffect(() => {
    fetchDatasets();
    fetchTrainingJobs();
  }, [fetchDatasets, fetchTrainingJobs]);
  
  // Update config
  const updateConfig = (key: keyof LoraConfig, value: any) => {
    setConfig(prev => ({
      ...prev,
      [key]: value
    }));
  };
  
  // Calculate estimated time
  const calculateEstimatedTime = (): string => {
    // This is a simplistic estimation - in a real app you'd have a more accurate model
    const dataset = datasets.find(d => d.id === selectedDatasetId);
    if (!dataset) return 'Unknown';
    
    const sampleCount = dataset.sample_count;
    const epochs = config.num_train_epochs;
    const batchSize = config.per_device_train_batch_size;
    
    // Rough estimate: 0.5 second per sample per epoch at batch size 4
    const baseTimePerSample = 0.5; // seconds
    const batchSizeFactor = 4 / batchSize;
    const totalSeconds = sampleCount * epochs * baseTimePerSample * batchSizeFactor;
    
    if (totalSeconds < 60) {
      return `${Math.ceil(totalSeconds)} seconds`;
    } else if (totalSeconds < 3600) {
      return `${Math.ceil(totalSeconds / 60)} minutes`;
    } else {
      const hours = Math.floor(totalSeconds / 3600);
      const minutes = Math.ceil((totalSeconds % 3600) / 60);
      return `${hours} hour${hours !== 1 ? 's' : ''} ${minutes} minute${minutes !== 1 ? 's' : ''}`;
    }
  };
  
  // Submit form
  const handleSubmit = async () => {
    if (!jobName.trim()) {
      setFormError('Job name is required');
      return;
    }
    
    if (!selectedDatasetId) {
      setFormError('Please select a dataset');
      return;
    }
    
    setFormError(null);
    setIsSubmitting(true);
    
    try {
      await createTrainingJob({
        name: jobName,
        description: jobDescription,
        dataset_id: selectedDatasetId,
        base_model: selectedModel,
        config
      });
      
      // Reset form
      setJobName('');
      setJobDescription('');
      setSelectedDatasetId('');
      setConfig({...defaultLoraConfig});
      
    } catch (err) {
      console.error('Error creating training job:', err);
      setFormError(err instanceof Error ? err.message : 'Failed to create training job');
    } finally {
      setIsSubmitting(false);
    }
  };
  
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Create New Training Job</CardTitle>
          <CardDescription>
            Configure a new LoRA fine-tuning job for domain adaptation
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="block text-sm font-medium">Job Name</label>
            <Input
              value={jobName}
              onChange={(e) => setJobName(e.target.value)}
              placeholder="Enter job name"
            />
          </div>
          
          <div className="space-y-2">
            <label className="block text-sm font-medium">Description (Optional)</label>
            <Textarea
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              placeholder="Describe the purpose of this training job"
              rows={3}
            />
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="block text-sm font-medium">Training Dataset</label>
              <Select 
                value={selectedDatasetId} 
                onValueChange={setSelectedDatasetId}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a dataset" />
                </SelectTrigger>
                <SelectContent>
                  {datasets.map((dataset) => (
                    <SelectItem key={dataset.id} value={dataset.id}>
                      {dataset.name} ({dataset.sample_count} samples)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            <div className="space-y-2">
              <label className="block text-sm font-medium">Base Model</label>
              <Select 
                value={selectedModel} 
                onValueChange={setSelectedModel}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a model" />
                </SelectTrigger>
                <SelectContent>
                  {baseModelOptions.map((model) => (
                    <SelectItem key={model.value} value={model.value}>
                      {model.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          
          <div className="space-y-4 mt-6">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-medium">LoRA Configuration</h3>
              <div className="flex items-center space-x-2">
                <Switch
                  checked={advancedMode}
                  onCheckedChange={setAdvancedMode}
                  id="advanced-mode"
                />
                <Label htmlFor="advanced-mode">Advanced Mode</Label>
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="block text-sm font-medium">
                    LoRA Rank (r)
                  </label>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger>
                        <Info className="h-4 w-4 text-gray-400" />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="w-80 text-xs">
                          Controls the number of parameters in the adaptation. Higher values allow more flexibility but increase the risk of overfitting.
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <div className="flex items-center space-x-4">
                  <Slider
                    value={[config.lora_r]}
                    min={1}
                    max={64}
                    step={1}
                    onValueChange={([value]) => updateConfig('lora_r', value)}
                    className="flex-1"
                  />
                  <Input
                    type="number"
                    className="w-16"
                    value={config.lora_r}
                    onChange={(e) => updateConfig('lora_r', parseInt(e.target.value) || 1)}
                    min={1}
                    max={64}
                  />
                </div>
              </div>
              
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="block text-sm font-medium">
                    LoRA Alpha
                  </label>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger>
                        <Info className="h-4 w-4 text-gray-400" />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="w-80 text-xs">
                          Scaling factor for LoRA updates. Higher values increase the impact of the adaptation.
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <div className="flex items-center space-x-4">
                  <Slider
                    value={[config.lora_alpha]}
                    min={1}
                    max={128}
                    step={1}
                    onValueChange={([value]) => updateConfig('lora_alpha', value)}
                    className="flex-1"
                  />
                  <Input
                    type="number"
                    className="w-16"
                    value={config.lora_alpha}
                    onChange={(e) => updateConfig('lora_alpha', parseInt(e.target.value) || 1)}
                    min={1}
                    max={128}
                  />
                </div>
              </div>
              
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="block text-sm font-medium">
                    Learning Rate
                  </label>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger>
                        <Info className="h-4 w-4 text-gray-400" />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="w-80 text-xs">
                          Controls how quickly the model adapts. Higher values can lead to faster learning but risk instability.
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <div className="flex items-center space-x-4">
                  <Slider
                    value={[config.learning_rate * 10000]}
                    min={1}
                    max={100}
                    step={1}
                    onValueChange={([value]) => updateConfig('learning_rate', value / 10000)}
                    className="flex-1"
                  />
                  <Input
                    type="text"
                    className="w-24"
                    value={config.learning_rate.toExponential(4)}
                    onChange={(e) => {
                      const value = parseFloat(e.target.value);
                      if (!isNaN(value) && value > 0) {
                        updateConfig('learning_rate', value);
                      }
                    }}
                  />
                </div>
              </div>
              
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="block text-sm font-medium">
                    Training Epochs
                  </label>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger>
                        <Info className="h-4 w-4 text-gray-400" />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="w-80 text-xs">
                          Number of complete passes through the training dataset. More epochs allow more learning but increase risk of overfitting.
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <div className="flex items-center space-x-4">
                  <Slider
                    value={[config.num_train_epochs]}
                    min={1}
                    max={20}
                    step={1}
                    onValueChange={([value]) => updateConfig('num_train_epochs', value)}
                    className="flex-1"
                  />
                  <Input
                    type="number"
                    className="w-16"
                    value={config.num_train_epochs}
                    onChange={(e) => updateConfig('num_train_epochs', parseInt(e.target.value) || 1)}
                    min={1}
                    max={20}
                  />
                </div>
              </div>
              
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="block text-sm font-medium">
                    Batch Size
                  </label>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger>
                        <Info className="h-4 w-4 text-gray-400" />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="w-80 text-xs">
                          Number of training examples processed together. Larger batch sizes can speed up training but require more memory.
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <div className="flex items-center space-x-4">
                  <Slider
                    value={[config.per_device_train_batch_size]}
                    min={1}
                    max={32}
                    step={1}
                    onValueChange={([value]) => updateConfig('per_device_train_batch_size', value)}
                    className="flex-1"
                  />
                  <Input
                    type="number"
                    className="w-16"
                    value={config.per_device_train_batch_size}
                    onChange={(e) => updateConfig('per_device_train_batch_size', parseInt(e.target.value) || 1)}
                    min={1}
                    max={32}
                  />
                </div>
              </div>
              
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="block text-sm font-medium">
                    LoRA Dropout
                  </label>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger>
                        <Info className="h-4 w-4 text-gray-400" />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="w-80 text-xs">
                          Probability of dropping connections during training. Higher values can reduce overfitting.
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <div className="flex items-center space-x-4">
                  <Slider
                    value={[config.lora_dropout * 100]}
                    min={0}
                    max={50}
                    step={1}
                    onValueChange={([value]) => updateConfig('lora_dropout', value / 100)}
                    className="flex-1"
                  />
                  <Input
                    type="text"
                    className="w-16"
                    value={`${(config.lora_dropout * 100).toFixed(0)}%`}
                    onChange={(e) => {
                      const value = parseFloat(e.target.value.replace('%', '')) / 100;
                      if (!isNaN(value) && value >= 0 && value <= 0.5) {
                        updateConfig('lora_dropout', value);
                      }
                    }}
                  />
                </div>
              </div>
            </div>
            
            {advancedMode && (
              <div className="pt-4 border-t">
                <h4 className="text-sm font-medium mb-4">Advanced Parameters</h4>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label className="block text-sm font-medium">Gradient Accumulation Steps</label>
                    <Input
                      type="number"
                      value={config.gradient_accumulation_steps}
                      onChange={(e) => updateConfig('gradient_accumulation_steps', parseInt(e.target.value) || 1)}
                      min={1}
                      max={16}
                    />
                    <p className="text-xs text-gray-500">
                      Number of steps to accumulate gradients before updating weights
                    </p>
                  </div>
                  
                  <div className="space-y-2">
                    <label className="block text-sm font-medium">Weight Decay</label>
                    <Input
                      type="number"
                      value={config.weight_decay}
                      onChange={(e) => updateConfig('weight_decay', parseFloat(e.target.value) || 0)}
                      min={0}
                      max={0.1}
                      step={0.001}
                    />
                    <p className="text-xs text-gray-500">
                      L2 regularization penalty to reduce overfitting
                    </p>
                  </div>
                  
                  <div className="space-y-2">
                    <label className="block text-sm font-medium">Warmup Ratio</label>
                    <Input
                      type="number"
                      value={config.warmup_ratio}
                      onChange={(e) => updateConfig('warmup_ratio', parseFloat(e.target.value) || 0)}
                      min={0}
                      max={0.5}
                      step={0.01}
                    />
                    <p className="text-xs text-gray-500">
                      Portion of training steps for learning rate warmup
                    </p>
                  </div>
                  
                  <div className="space-y-2">
                    <label className="block text-sm font-medium">Max Gradient Norm</label>
                    <Input
                      type="number"
                      value={config.max_grad_norm}
                      onChange={(e) => updateConfig('max_grad_norm', parseFloat(e.target.value) || 1)}
                      min={0}
                      max={10}
                      step={0.1}
                    />
                    <p className="text-xs text-gray-500">
                      Maximum gradient norm for gradient clipping
                    </p>
                  </div>
                  
                  <div className="space-y-2 col-span-2">
                    <label className="block text-sm font-medium">Optimizer</label>
                    <Select 
                      value={config.optimizer} 
                      onValueChange={(value) => updateConfig('optimizer', value)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select optimizer" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="adamw_torch">AdamW (PyTorch)</SelectItem>
                        <SelectItem value="adam">Adam</SelectItem>
                        <SelectItem value="sgd">SGD</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>
            )}
          </div>
          
          <div className="mt-6 bg-blue-50 p-4 rounded-md flex">
            <div className="flex-shrink-0 mr-3">
              <Clock className="h-6 w-6 text-blue-500" />
            </div>
            <div>
              <h3 className="text-sm font-medium text-blue-900">Estimated Training Time</h3>
              <p className="text-sm text-blue-700 mt-1">
                {selectedDatasetId ? (
                  <>
                    Based on your configuration, this job will take approximately <strong>{calculateEstimatedTime()}</strong> to complete.
                  </>
                ) : (
                  'Select a dataset to see estimated training time'
                )}
              </p>
            </div>
          </div>
          
          {formError && (
            <div className="bg-red-50 text-red-700 p-3 rounded-md flex items-center">
              <AlertCircle className="h-5 w-5 mr-2" />
              <span>{formError}</span>
            </div>
          )}
        </CardContent>
        <CardFooter className="flex justify-between">
          <Button variant="outline" onClick={() => {
            setConfig({...defaultLoraConfig});
            setAdvancedMode(false);
          }}>
            Reset
          </Button>
          <Button 
            onClick={handleSubmit} 
            disabled={isSubmitting || !jobName.trim() || !selectedDatasetId}
            className="flex items-center gap-2"
          >
            {isSubmitting ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                Starting...
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Start Training
              </>
            )}
          </Button>
        </CardFooter>
      </Card>
      
      <div>
        <h3 className="text-lg font-medium mb-4">Recent Training Jobs</h3>
        
        {loading ? (
          <div className="flex justify-center items-center h-32">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-800"></div>
          </div>
        ) : trainingJobs.length === 0 ? (
          <div className="text-center py-8 border rounded-md border-dashed">
            <Settings className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900">No training jobs yet</h3>
            <p className="text-gray-500 mt-1">
              Configure and start your first training job above
            </p>
          </div>
        ) : (
          <div className="border rounded-md overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Dataset</TableHead>
                  <TableHead>Base Model</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {trainingJobs.slice(0, 5).map((job) => {
                  // Find dataset name
                  const dataset = datasets.find(d => d.id === job.dataset_id);
                  
                  return (
                    <TableRow key={job.id}>
                      <TableCell className="font-medium">{job.name}</TableCell>
                      <TableCell>{dataset?.name || job.dataset_id}</TableCell>
                      <TableCell>
                        {baseModelOptions.find(m => m.value === job.base_model)?.label || job.base_model}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center">
                          <div className={`
                            rounded-full h-2 w-2 mr-2
                            ${job.status === 'completed' ? 'bg-green-500' : ''}
                            ${job.status === 'running' ? 'bg-blue-500' : ''}
                            ${job.status === 'pending' ? 'bg-yellow-500' : ''}
                            ${job.status === 'failed' ? 'bg-red-500' : ''}
                            ${job.status === 'cancelled' ? 'bg-gray-500' : ''}
                          `}></div>
                          <span className="capitalize">{job.status}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        {format(new Date(job.created_at), 'MMM d, yyyy')}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </div>
  );
};

export default TrainingConfig;
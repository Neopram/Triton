import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { 
  Brain, 
  Zap, 
  Trash, 
  Star, 
  Download, 
  Upload, 
  Settings, 
  AlertTriangle,
  AlertCircle,
  Check,
  CheckCircle,
  ActivitySquare
} from 'lucide-react';
import { useTrainingStore, TrainingJob } from '../../store/trainingStore';
import { format } from 'date-fns';

const ModelSelector: React.FC = () => {
  const { 
    trainingJobs, 
    deployedModels,
    fetchTrainingJobs, 
    fetchDeployedModels,
    deployModel,
    undeployModel,
    setDefaultModel,
    loading, 
    error 
  } = useTrainingStore();
  
  // Local state
  const [completedJobs, setCompletedJobs] = useState<TrainingJob[]>([]);
  const [deployDialogOpen, setDeployDialogOpen] = useState<boolean>(false);
  const [selectedJob, setSelectedJob] = useState<TrainingJob | null>(null);
  const [modelName, setModelName] = useState<string>('');
  const [modelDescription, setModelDescription] = useState<string>('');
  const [makeDefault, setMakeDefault] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [undeployDialogOpen, setUndeployDialogOpen] = useState<boolean>(false);
  const [modelToUndeploy, setModelToUndeploy] = useState<string | null>(null);
  
  // Load data on mount
  useEffect(() => {
    const fetchData = async () => {
      await fetchTrainingJobs();
      await fetchDeployedModels();
    };
    
    fetchData();
  }, [fetchTrainingJobs, fetchDeployedModels]);
  
  // Filter completed jobs
  useEffect(() => {
    const completed = trainingJobs
      .filter(job => job.status === 'completed')
      .sort((a, b) => new Date(b.end_time || 0).getTime() - new Date(a.end_time || 0).getTime());
    
    setCompletedJobs(completed);
  }, [trainingJobs]);
  
  // Open deploy dialog
  const handleOpenDeployDialog = (job: TrainingJob) => {
    setSelectedJob(job);
    setModelName(job.name);
    setModelDescription(job.description || '');
    setMakeDefault(deployedModels.length === 0);
    setDeployDialogOpen(true);
  };
  
  // Handle deploy model
  const handleDeployModel = async () => {
    if (!selectedJob || !modelName) return;
    
    setIsSubmitting(true);
    
    try {
      await deployModel(
        selectedJob.id,
        modelName,
        modelDescription,
        makeDefault
      );
      
      setDeployDialogOpen(false);
      
      // Reset form
      setSelectedJob(null);
      setModelName('');
      setModelDescription('');
      setMakeDefault(false);
      
      // Refresh models
      await fetchDeployedModels();
      
    } catch (err) {
      console.error('Error deploying model:', err);
    } finally {
      setIsSubmitting(false);
    }
  };
  
  // Open undeploy dialog
  const handleOpenUndeployDialog = (modelId: string) => {
    setModelToUndeploy(modelId);
    setUndeployDialogOpen(true);
  };
  
  // Handle undeploy model
  const handleUndeployModel = async () => {
    if (!modelToUndeploy) return;
    
    setIsSubmitting(true);
    
    try {
      await undeployModel(modelToUndeploy);
      
      setUndeployDialogOpen(false);
      setModelToUndeploy(null);
      
      // Refresh models
      await fetchDeployedModels();
      
    } catch (err) {
      console.error('Error undeploying model:', err);
    } finally {
      setIsSubmitting(false);
    }
  };
  
  // Handle set default model
  const handleSetDefaultModel = async (modelId: string) => {
    setIsSubmitting(true);
    
    try {
      await setDefaultModel(modelId);
      
      // Refresh models
      await fetchDeployedModels();
      
    } catch (err) {
      console.error('Error setting default model:', err);
    } finally {
      setIsSubmitting(false);
    }
  };
  
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Deployed Models</CardTitle>
          <CardDescription>
            Fine-tuned models available for inference
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center items-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-800"></div>
            </div>
          ) : deployedModels.length === 0 ? (
            <div className="text-center py-8 border rounded-md border-dashed">
              <Brain className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900">No models deployed</h3>
              <p className="text-gray-500 mt-1">
                Deploy a fine-tuned model to use it for inference
              </p>
            </div>
          ) : (
            <div className="border rounded-md overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Model</TableHead>
                    <TableHead>Base Model</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Deployed</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {deployedModels.map(model => (
                    <TableRow key={model.id}>
                      <TableCell>
                        <div className="font-medium">{model.name}</div>
                        <div className="text-sm text-gray-500">{model.description || ''}</div>
                      </TableCell>
                      <TableCell>{model.base_model.split('/').pop()}</TableCell>
                      <TableCell>
                        <div className="flex items-center space-x-2">
                          {model.is_active && <Badge className="bg-green-100 text-green-800">Active</Badge>}
                          {model.is_default && <Badge className="bg-blue-100 text-blue-800">Default</Badge>}
                        </div>
                      </TableCell>
                      <TableCell>
                        {format(new Date(model.deployed_at), 'MMM d, yyyy')}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end space-x-2">
                          {!model.is_default && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleSetDefaultModel(model.id)}
                              disabled={isSubmitting}
                            >
                              <Star className="h-4 w-4 mr-1" />
                              Set Default
                            </Button>
                          )}
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => handleOpenUndeployDialog(model.id)}
                            disabled={isSubmitting}
                          >
                            <Trash className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader>
          <CardTitle>Available Models</CardTitle>
          <CardDescription>
            Completed fine-tuning jobs ready for deployment
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center items-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-800"></div>
            </div>
          ) : completedJobs.length === 0 ? (
            <div className="text-center py-8 border rounded-md border-dashed">
              <ActivitySquare className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900">No completed training jobs</h3>
              <p className="text-gray-500 mt-1">
                Complete a training job to deploy the model
              </p>
            </div>
          ) : (
            <div className="border rounded-md overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Job Name</TableHead>
                    <TableHead>Base Model</TableHead>
                    <TableHead>Completed</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {completedJobs.map(job => {
                    // Check if this job is already deployed
                    const isDeployed = deployedModels.some(model => model.id === job.id);
                    
                    return (
                      <TableRow key={job.id}>
                        <TableCell>
                          <div className="font-medium">{job.name}</div>
                          <div className="text-sm text-gray-500">{job.description || ''}</div>
                        </TableCell>
                        <TableCell>{job.base_model.split('/').pop()}</TableCell>
                        <TableCell>
                          {job.end_time ? format(new Date(job.end_time), 'MMM d, yyyy') : 'N/A'}
                        </TableCell>
                        <TableCell>
                          {isDeployed ? (
                            <Badge className="bg-green-100 text-green-800">Deployed</Badge>
                          ) : (
                            <Badge className="bg-yellow-100 text-yellow-800">Ready</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          {!isDeployed && (
                            <Button
                              variant="default"
                              size="sm"
                              onClick={() => handleOpenDeployDialog(job)}
                              disabled={isSubmitting}
                            >
                              <Zap className="h-4 w-4 mr-1" />
                              Deploy
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
      
      {/* Deploy Model Dialog */}
      <Dialog open={deployDialogOpen} onOpenChange={setDeployDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Deploy Model</DialogTitle>
            <DialogDescription>
              Make this fine-tuned model available for inference
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Model Name</label>
              <Input
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                placeholder="Enter a name for this model"
              />
            </div>
            
            <div className="space-y-2">
              <label className="text-sm font-medium">Description (Optional)</label>
              <Textarea
                value={modelDescription}
                onChange={(e) => setModelDescription(e.target.value)}
                placeholder="Describe the purpose or capabilities of this model"
                rows={3}
              />
            </div>
            
            <div className="flex items-center space-x-2 pt-2">
              <input
                type="checkbox"
                id="make-default"
                checked={makeDefault}
                onChange={(e) => setMakeDefault(e.target.checked)}
                className="rounded border-gray-300"
              />
              <label htmlFor="make-default" className="text-sm">
                Make this the default model for inference
              </label>
            </div>
          </div>
          
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeployDialogOpen(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              onClick={handleDeployModel}
              disabled={isSubmitting || !modelName}
            >
              {isSubmitting ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Deploying...
                </>
              ) : (
                <>
                  <Zap className="h-4 w-4 mr-2" />
                  Deploy Model
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      
      {/* Undeploy Model Dialog */}
      <Dialog open={undeployDialogOpen} onOpenChange={setUndeployDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Undeploy Model</DialogTitle>
            <DialogDescription>
              Remove this model from active deployment
            </DialogDescription>
          </DialogHeader>
          
          <div className="bg-yellow-50 p-4 rounded-md border border-yellow-200 flex items-start">
            <AlertTriangle className="h-5 w-5 text-yellow-600 mr-3 mt-0.5" />
            <div>
              <h4 className="font-medium text-yellow-800">Warning</h4>
              <p className="text-sm text-yellow-700 mt-1">
                Undeploying this model will remove it from the active models list. 
                Any applications using this model will no longer be able to access it.
              </p>
            </div>
          </div>
          
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setUndeployDialogOpen(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleUndeployModel}
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Undeploying...' : 'Confirm Undeploy'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ModelSelector;
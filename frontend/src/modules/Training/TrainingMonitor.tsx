import React, { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { 
  Activity, 
  AlertCircle, 
  Pause, 
  Play, 
  ChevronRight,
  Clock,
  AlertTriangle,
  CheckCircle,
  XCircle,
  BarChart
} from 'lucide-react';

import { useTrainingStore, TrainingJob, TrainingProgress } from '../../store/trainingStore';
import { format, formatDistanceToNow } from 'date-fns';

// Helper to format time
const formatTime = (seconds: number | undefined): string => {
  if (!seconds) return 'Unknown';
  
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  } else if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`;
  } else {
    return `${remainingSeconds}s`;
  }
};

const TrainingMonitor: React.FC = () => {
  const { 
    trainingJobs, 
    trainingProgress,
    fetchTrainingJobs, 
    fetchJobById,
    fetchJobProgress,
    cancelTrainingJob,
    clearCurrentJob,
    loading, 
    error 
  } = useTrainingStore();
  
  // Local state
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [pollingInterval, setPollingInterval] = useState<number | null>(null);
  const [cancelConfirmOpen, setCancelConfirmOpen] = useState<boolean>(false);
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  
  // Polling ref to avoid closure issues
  const pollingIntervalRef = useRef<number | null>(null);
  
  // Select job for monitoring
  const handleSelectJob = async (jobId: string) => {
    // Clear existing polling
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    
    setSelectedJobId(jobId);
    
    // Load job details
    setIsUpdating(true);
    await fetchJobById(jobId);
    await fetchJobProgress(jobId);
    setIsUpdating(false);
    
    // Start polling for active jobs
    const job = trainingJobs.find(j => j.id === jobId);
    if (job && ['pending', 'running'].includes(job.status)) {
      const interval = window.setInterval(async () => {
        await fetchJobProgress(jobId);
        await fetchJobById(jobId);
      }, 5000); // Update every 5 seconds
      
      setPollingInterval(interval);
      pollingIntervalRef.current = interval;
    }
  };
  
  // Stop polling when component unmounts
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);
  
  // Refresh job list periodically
  useEffect(() => {
    fetchTrainingJobs();
    
    const interval = setInterval(() => {
      fetchTrainingJobs();
    }, 30000); // Update every 30 seconds
    
    return () => clearInterval(interval);
  }, [fetchTrainingJobs]);
  
  // Get the selected job
  const selectedJob = trainingJobs.find(job => job.id === selectedJobId);
  
  // Cancel job
  const handleCancelJob = async () => {
    if (!selectedJobId) return;
    
    setIsUpdating(true);
    try {
      await cancelTrainingJob(selectedJobId);
      setCancelConfirmOpen(false);
      
      // Stop polling
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
        setPollingInterval(null);
      }
    } finally {
      setIsUpdating(false);
    }
  };
  
  // Filter relevant jobs (those that are in progress or recently completed)
  const activeJobs = trainingJobs.filter(job => 
    ['pending', 'running'].includes(job.status) ||
    (job.status === 'completed' && new Date(job.end_time || 0) > new Date(Date.now() - 24 * 60 * 60 * 1000))
  );
  
  // Recent jobs (including failed/cancelled)
  const recentJobs = trainingJobs
    .filter(job => job.status !== 'pending' && job.status !== 'running')
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);
  
  return (
    <div className="space-y-6">
      {selectedJob ? (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
            <div>
              <CardTitle className="text-xl font-bold">{selectedJob.name}</CardTitle>
              <CardDescription>
                {selectedJob.description || 'No description provided'}
              </CardDescription>
            </div>
            
            <div className="flex items-center space-x-2">
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => {
                  // Stop polling
                  if (pollingIntervalRef.current) {
                    clearInterval(pollingIntervalRef.current);
                    pollingIntervalRef.current = null;
                    setPollingInterval(null);
                  }
                  
                  setSelectedJobId(null);
                  clearCurrentJob();
                }}
              >
                Back to All Jobs
              </Button>
              
              {selectedJob.status === 'running' && (
                <Button 
                  variant="destructive" 
                  size="sm"
                  onClick={() => setCancelConfirmOpen(true)}
                >
                  <Pause className="h-4 w-4 mr-1" />
                  Cancel
                </Button>
              )}
            </div>
          </CardHeader>
          
          <CardContent className="space-y-6">
            {/* Progress Card */}
            <div className="bg-gray-50 p-4 rounded-md">
              <div className="flex flex-wrap items-center justify-between mb-4">
                <div className="flex items-center">
                  {selectedJob.status === 'pending' && (
                    <Badge className="bg-yellow-100 text-yellow-800 mr-3">Pending</Badge>
                  )}
                  {selectedJob.status === 'running' && (
                    <Badge className="bg-blue-100 text-blue-800 mr-3">Running</Badge>
                  )}
                  {selectedJob.status === 'completed' && (
                    <Badge className="bg-green-100 text-green-800 mr-3">Completed</Badge>
                  )}
                  {selectedJob.status === 'failed' && (
                    <Badge className="bg-red-100 text-red-800 mr-3">Failed</Badge>
                  )}
                  {selectedJob.status === 'cancelled' && (
                    <Badge className="bg-gray-100 text-gray-800 mr-3">Cancelled</Badge>
                  )}
                  
                  <div>
                    <h3 className="font-medium">Training Progress</h3>
                    {trainingProgress ? (
                      <p className="text-sm text-gray-500">
                        Epoch {trainingProgress.current_epoch}/{trainingProgress.total_epochs}
                        {trainingProgress.loss !== null && ` • Loss: ${trainingProgress.loss.toFixed(4)}`}
                      </p>
                    ) : (
                      <p className="text-sm text-gray-500">
                        {selectedJob.status === 'pending' ? 'Waiting to start...' : 
                         selectedJob.status === 'completed' ? 'Training completed' : 
                         selectedJob.status === 'failed' ? 'Training failed' : 
                         selectedJob.status === 'cancelled' ? 'Training cancelled' : 
                         'Initializing...'}
                      </p>
                    )}
                  </div>
                </div>
                
                {(selectedJob.start_time || trainingProgress?.start_time) && (
                  <div className="text-right text-sm text-gray-500">
                    <div className="flex items-center">
                      <Clock className="h-4 w-4 mr-1" />
                      Started {formatDistanceToNow(new Date(selectedJob.start_time || trainingProgress?.start_time || ''), { addSuffix: true })}
                    </div>
                    {selectedJob.end_time && (
                      <div>
                        Finished {formatDistanceToNow(new Date(selectedJob.end_time), { addSuffix: true })}
                      </div>
                    )}
                  </div>
                )}
              </div>
              
              {/* Progress bar */}
              {trainingProgress && (
                <div className="space-y-2">
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>Progress: {Math.round(trainingProgress.progress * 100)}%</span>
                    {trainingProgress.estimated_time_remaining !== null && trainingProgress.status === 'running' && (
                      <span>Time remaining: {formatTime(trainingProgress.estimated_time_remaining)}</span>
                    )}
                  </div>
                  <Progress value={trainingProgress.progress * 100} className="h-2" />
                </div>
              )}
              
              {/* Status messages */}
              {selectedJob.status === 'failed' && selectedJob.error_message && (
                <div className="mt-4 bg-red-50 p-3 rounded-md border border-red-200 flex items-start">
                  <AlertCircle className="h-5 w-5 text-red-500 mr-2 mt-0.5" />
                  <div>
                    <h4 className="font-medium text-red-800">Training Failed</h4>
                    <p className="text-sm text-red-700 mt-1">{selectedJob.error_message}</p>
                  </div>
                </div>
              )}
            </div>
            
            {/* Job Details */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h3 className="text-base font-medium mb-3">Job Details</h3>
                <div className="bg-white p-4 rounded-md border space-y-3">
                  <div className="grid grid-cols-3 gap-1 text-sm">
                    <div className="font-medium text-gray-500">ID</div>
                    <div className="col-span-2 font-mono">{selectedJob.id}</div>
                  </div>
                  
                  <div className="grid grid-cols-3 gap-1 text-sm">
                    <div className="font-medium text-gray-500">Dataset</div>
                    <div className="col-span-2">{selectedJob.dataset_id}</div>
                  </div>
                  
                  <div className="grid grid-cols-3 gap-1 text-sm">
                    <div className="font-medium text-gray-500">Base Model</div>
                    <div className="col-span-2">{selectedJob.base_model}</div>
                  </div>
                  
                  <div className="grid grid-cols-3 gap-1 text-sm">
                    <div className="font-medium text-gray-500">Created</div>
                    <div className="col-span-2">{format(new Date(selectedJob.created_at), 'PPP pp')}</div>
                  </div>
                  
                  {selectedJob.start_time && (
                    <div className="grid grid-cols-3 gap-1 text-sm">
                      <div className="font-medium text-gray-500">Started</div>
                      <div className="col-span-2">{format(new Date(selectedJob.start_time), 'PPP pp')}</div>
                    </div>
                  )}
                  
                  {selectedJob.end_time && (
                    <div className="grid grid-cols-3 gap-1 text-sm">
                      <div className="font-medium text-gray-500">Ended</div>
                      <div className="col-span-2">{format(new Date(selectedJob.end_time), 'PPP pp')}</div>
                    </div>
                  )}
                </div>
              </div>
              
              <div>
                <h3 className="text-base font-medium mb-3">LoRA Configuration</h3>
                <div className="bg-white p-4 rounded-md border space-y-3">
                  {selectedJob.lora_config && (
                    <>
                      <div className="grid grid-cols-3 gap-1 text-sm">
                        <div className="font-medium text-gray-500">LoRA Rank</div>
                        <div className="col-span-2">{selectedJob.lora_config.lora_r}</div>
                      </div>
                      
                      <div className="grid grid-cols-3 gap-1 text-sm">
                        <div className="font-medium text-gray-500">LoRA Alpha</div>
                        <div className="col-span-2">{selectedJob.lora_config.lora_alpha}</div>
                      </div>
                      
                      <div className="grid grid-cols-3 gap-1 text-sm">
                        <div className="font-medium text-gray-500">Dropout</div>
                        <div className="col-span-2">{selectedJob.lora_config.lora_dropout}</div>
                      </div>
                      
                      <div className="grid grid-cols-3 gap-1 text-sm">
                        <div className="font-medium text-gray-500">Learning Rate</div>
                        <div className="col-span-2">{selectedJob.lora_config.learning_rate}</div>
                      </div>
                      
                      <div className="grid grid-cols-3 gap-1 text-sm">
                        <div className="font-medium text-gray-500">Epochs</div>
                        <div className="col-span-2">{selectedJob.lora_config.num_train_epochs}</div>
                      </div>
                      
                      <div className="grid grid-cols-3 gap-1 text-sm">
                        <div className="font-medium text-gray-500">Batch Size</div>
                        <div className="col-span-2">{selectedJob.lora_config.per_device_train_batch_size}</div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
            
            {/* Training Metrics (if completed) */}
            {selectedJob.status === 'completed' && selectedJob.metrics && (
              <div>
                <h3 className="text-base font-medium mb-3">Training Metrics</h3>
                <div className="bg-white p-4 rounded-md border grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <div className="text-sm font-medium text-gray-500">Training Time</div>
                    <div className="text-xl font-medium mt-1">
                      {formatTime(selectedJob.metrics.training_time)}
                    </div>
                  </div>
                  
                  <div>
                    <div className="text-sm font-medium text-gray-500">Model Size</div>
                    <div className="text-xl font-medium mt-1">
                      {(selectedJob.metrics.model_size / (1024 * 1024)).toFixed(2)} MB
                    </div>
                  </div>
                  
                  <div>
                    <div className="text-sm font-medium text-gray-500">Final Loss</div>
                    <div className="text-xl font-medium mt-1">
                      {selectedJob.metrics.final_loss?.toFixed(4) || 'N/A'}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-medium">Active Training Jobs</h3>
            <Button
              variant="outline"
              size="sm"
              onClick={() => fetchTrainingJobs()}
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
          ) : activeJobs.length === 0 ? (
            <div className="text-center py-8 border rounded-md border-dashed">
              <Activity className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900">No active jobs</h3>
              <p className="text-gray-500 mt-1">
                No training jobs are currently running or pending
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {activeJobs.map(job => (
                <Card key={job.id} className="overflow-hidden">
                  <div className={`h-1 ${
                    job.status === 'running' ? 'bg-blue-500' : 
                    job.status === 'pending' ? 'bg-yellow-500' : 
                    job.status === 'completed' ? 'bg-green-500' : 
                    'bg-gray-300'
                  }`}></div>
                  <CardContent className="pt-4">
                    <div className="flex justify-between items-start">
                      <div>
                        <h4 className="font-medium text-base">{job.name}</h4>
                        <p className="text-sm text-gray-500 mt-1">
                          {job.base_model} • Started {job.start_time ? formatDistanceToNow(new Date(job.start_time), { addSuffix: true }) : 'pending'}
                        </p>
                      </div>
                      <div className="flex space-x-2">
                        <Badge className={`
                          ${job.status === 'running' ? 'bg-blue-100 text-blue-800' : ''}
                          ${job.status === 'pending' ? 'bg-yellow-100 text-yellow-800' : ''}
                          ${job.status === 'completed' ? 'bg-green-100 text-green-800' : ''}
                        `}>
                          {job.status === 'running' && 'Running'}
                          {job.status === 'pending' && 'Pending'}
                          {job.status === 'completed' && 'Completed'}
                        </Badge>
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          onClick={() => handleSelectJob(job.id)}
                        >
                          Details <ChevronRight className="h-4 w-4 ml-1" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
          
          <div className="mt-8">
            <h3 className="text-lg font-medium mb-4">Recent Training Jobs</h3>
            
            {recentJobs.length === 0 ? (
              <div className="text-center py-8 border rounded-md border-dashed">
                <BarChart className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900">No recent jobs</h3>
                <p className="text-gray-500 mt-1">
                  Completed training jobs will appear here
                </p>
              </div>
            ) : (
              <div className="border rounded-md overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[250px]">Name</TableHead>
                      <TableHead>Base Model</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Completed</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {recentJobs.map(job => (
                      <TableRow key={job.id}>
                        <TableCell className="font-medium">{job.name}</TableCell>
                        <TableCell>{job.base_model.split('/').pop()}</TableCell>
                        <TableCell>
                          <div className="flex items-center">
                            {job.status === 'completed' && <CheckCircle className="h-4 w-4 text-green-500 mr-2" />}
                            {job.status === 'failed' && <XCircle className="h-4 w-4 text-red-500 mr-2" />}
                            {job.status === 'cancelled' && <AlertTriangle className="h-4 w-4 text-yellow-500 mr-2" />}
                            <span className="capitalize">{job.status}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          {job.end_time 
                            ? formatDistanceToNow(new Date(job.end_time), { addSuffix: true })
                            : 'N/A'
                          }
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleSelectJob(job.id)}
                          >
                            Details
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        </>
      )}
      
      {/* Cancel Confirmation Dialog */}
      <Dialog open={cancelConfirmOpen} onOpenChange={setCancelConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel Training Job</DialogTitle>
            <DialogDescription>
              Are you sure you want to cancel this training job? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          
          <div className="flex items-center p-4 bg-yellow-50 rounded-md border border-yellow-200 mt-2">
            <AlertTriangle className="h-6 w-6 text-yellow-500 mr-3" />
            <div>
              <h4 className="font-medium text-yellow-800">Warning</h4>
              <p className="text-sm text-yellow-700 mt-1">
                Cancelling this job will stop the training process and any progress will be lost.
                The job's status will be changed to "cancelled" and cannot be resumed.
              </p>
            </div>
          </div>
          
          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={() => setCancelConfirmOpen(false)}
              disabled={isUpdating}
            >
              Keep Training
            </Button>
            <Button 
              variant="destructive" 
              onClick={handleCancelJob}
              disabled={isUpdating}
            >
              {isUpdating ? 'Cancelling...' : 'Yes, Cancel Training'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default TrainingMonitor;
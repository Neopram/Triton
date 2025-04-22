import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { 
  Database, 
  Plus, 
  Trash, 
  Edit, 
  FileText, 
  Download, 
  Upload, 
  Search,
  AlertCircle,
  Check,
  Info
} from 'lucide-react';
import { useTrainingStore, DatasetSample, TrainingDataset } from '../../store/trainingStore';
import { format } from 'date-fns';

const DatasetManager: React.FC = () => {
  const { 
    datasets, 
    currentDataset,
    datasetSamples,
    loading, 
    error,
    fetchDatasets,
    fetchDatasetById,
    fetchDatasetSamples,
    createDataset,
    clearCurrentDataset,
    clearError
  } = useTrainingStore();
  
  // Local state
  const [activeTab, setActiveTab] = useState('browse');
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [viewDetailsOpen, setViewDetailsOpen] = useState(false);
  
  // Form state
  const [datasetName, setDatasetName] = useState('');
  const [datasetDescription, setDatasetDescription] = useState('');
  const [datasetContent, setDatasetContent] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  
  // View sample state
  const [selectedSampleIndex, setSelectedSampleIndex] = useState<number | null>(null);
  
  // Filtered datasets
  const filteredDatasets = searchQuery 
    ? datasets.filter(dataset => 
        dataset.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (dataset.description && dataset.description.toLowerCase().includes(searchQuery.toLowerCase()))
      )
    : datasets;
  
  // View dataset details
  const handleViewDetails = async (dataset: TrainingDataset) => {
    await fetchDatasetById(dataset.id);
    await fetchDatasetSamples(dataset.id);
    setViewDetailsOpen(true);
  };
  
  // Create dataset
  const handleCreateDataset = async () => {
    if (!datasetName.trim()) {
      setFormError('Dataset name is required');
      return;
    }
    
    if (!datasetContent.trim()) {
      setFormError('Dataset content is required');
      return;
    }
    
    setFormError(null);
    setIsSubmitting(true);
    
    try {
      // Parse dataset content
      let samples: DatasetSample[] = [];
      
      try {
        // First try to parse as JSON
        samples = JSON.parse(datasetContent);
        
        // Validate structure
        if (!Array.isArray(samples)) {
          throw new Error('Dataset must be an array of samples');
        }
        
        // Validate each sample
        for (const sample of samples) {
          if (!sample.instruction || !sample.response) {
            throw new Error('Each sample must contain "instruction" and "response" fields');
          }
        }
      } catch (err) {
        // If JSON parsing fails, try to parse as simple instruction/response format
        // Format: instruction \n\n response \n\n instruction \n\n response ...
        const pairs = datasetContent.split('\n\n\n');
        
        for (let i = 0; i < pairs.length; i += 2) {
          if (i + 1 < pairs.length) {
            const instruction = pairs[i].trim();
            const response = pairs[i + 1].trim();
            
            if (instruction && response) {
              samples.push({ instruction, response });
            }
          }
        }
        
        if (samples.length === 0) {
          throw new Error('Could not parse dataset. Please check the format.');
        }
      }
      
      // Create dataset
      await createDataset(datasetName, datasetDescription, samples);
      
      // Reset form
      setDatasetName('');
      setDatasetDescription('');
      setDatasetContent('');
      setCreateDialogOpen(false);
      
      // Refresh datasets
      await fetchDatasets();
      
    } catch (err) {
      console.error('Error creating dataset:', err);
      setFormError(err instanceof Error ? err.message : 'Failed to create dataset');
    } finally {
      setIsSubmitting(false);
    }
  };
  
  return (
    <div>
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <div className="flex justify-between items-center mb-4">
          <TabsList>
            <TabsTrigger value="browse">Browse Datasets</TabsTrigger>
            <TabsTrigger value="create">Create Dataset</TabsTrigger>
          </TabsList>
          
          {activeTab === 'browse' && (
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-400" />
              <Input
                type="search"
                placeholder="Search datasets..."
                className="pl-9 w-64"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          )}
        </div>
        
        <TabsContent value="browse">
          {loading ? (
            <div className="flex justify-center items-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-800"></div>
            </div>
          ) : filteredDatasets.length === 0 ? (
            <div className="text-center py-16 border rounded-md border-dashed">
              <Database className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900">No datasets found</h3>
              <p className="text-gray-500 mt-1">
                {searchQuery 
                  ? 'Try adjusting your search or clear the search field'
                  : 'Get started by creating your first training dataset'}
              </p>
              {!searchQuery && (
                <Button 
                  variant="default" 
                  className="mt-4" 
                  onClick={() => setActiveTab('create')}
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Create Dataset
                </Button>
              )}
            </div>
          ) : (
            <div className="border rounded-md overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Samples</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredDatasets.map((dataset) => (
                    <TableRow key={dataset.id}>
                      <TableCell className="font-medium">{dataset.name}</TableCell>
                      <TableCell className="max-w-md truncate">
                        {dataset.description || 
                          <span className="text-gray-400 italic">No description</span>
                        }
                      </TableCell>
                      <TableCell>{dataset.sample_count}</TableCell>
                      <TableCell>
                        {format(new Date(dataset.created_at), 'MMM d, yyyy')}
                      </TableCell>
                      <TableCell>
                        <div className="flex space-x-2">
                          <Button 
                            variant="outline" 
                            size="sm" 
                            className="h-8 px-2"
                            onClick={() => handleViewDetails(dataset)}
                          >
                            <FileText className="h-4 w-4 mr-1" />
                            Details
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>
        
        <TabsContent value="create">
          <Card>
            <CardHeader>
              <CardTitle>Create New Dataset</CardTitle>
              <CardDescription>
                Prepare a training dataset for fine-tuning with LoRA
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="block text-sm font-medium">Dataset Name</label>
                <Input
                  value={datasetName}
                  onChange={(e) => setDatasetName(e.target.value)}
                  placeholder="Enter dataset name"
                />
              </div>
              
              <div className="space-y-2">
                <label className="block text-sm font-medium">Description (Optional)</label>
                <Textarea
                  value={datasetDescription}
                  onChange={(e) => setDatasetDescription(e.target.value)}
                  placeholder="Describe the purpose and content of this dataset"
                  rows={3}
                />
              </div>
              
              <div className="space-y-2">
                <label className="block text-sm font-medium">Dataset Content</label>
                <div className="text-xs text-gray-500 mb-2">
                  <p>You can provide data in two formats:</p>
                  <ul className="list-disc pl-5 mt-1 space-y-1">
                    <li>JSON array: each item needs "instruction" and "response" fields</li>
                    <li>Text format: instruction, blank line, response, two blank lines, repeat</li>
                  </ul>
                </div>
                <Textarea
                  value={datasetContent}
                  onChange={(e) => setDatasetContent(e.target.value)}
                  placeholder='[{"instruction": "What is the capital of France?", "response": "The capital of France is Paris."}]'
                  rows={12}
                  className="font-mono text-sm"
                />
              </div>
              
              {formError && (
                <div className="bg-red-50 text-red-700 p-3 rounded-md flex items-center">
                  <AlertCircle className="h-5 w-5 mr-2" />
                  <span>{formError}</span>
                </div>
              )}
            </CardContent>
            <CardFooter className="flex justify-between">
              <Button variant="outline" onClick={() => setActiveTab('browse')}>
                Cancel
              </Button>
              <Button 
                onClick={handleCreateDataset} 
                disabled={isSubmitting || !datasetName.trim() || !datasetContent.trim()}
              >
                {isSubmitting ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    Creating...
                  </>
                ) : (
                  <>
                    <Check className="h-4 w-4 mr-2" />
                    Create Dataset
                  </>
                )}
              </Button>
            </CardFooter>
          </Card>
        </TabsContent>
      </Tabs>
      
      {/* Dataset Details Dialog */}
      <Dialog 
        open={viewDetailsOpen} 
        onOpenChange={(open) => {
          setViewDetailsOpen(open);
          if (!open) clearCurrentDataset();
        }}
      >
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>Dataset Details</DialogTitle>
            <DialogDescription>
              Examine the content and format of this training dataset
            </DialogDescription>
          </DialogHeader>
          
          {currentDataset ? (
            <div className="flex-1 overflow-hidden flex flex-col">
              <div className="mb-4 grid grid-cols-2 gap-4">
                <div>
                  <h3 className="text-sm font-medium text-gray-500">Name</h3>
                  <p className="mt-1">{currentDataset.name}</p>
                </div>
                <div>
                  <h3 className="text-sm font-medium text-gray-500">Created</h3>
                  <p className="mt-1">{format(new Date(currentDataset.created_at), 'PPP')}</p>
                </div>
                <div className="col-span-2">
                  <h3 className="text-sm font-medium text-gray-500">Description</h3>
                  <p className="mt-1">{currentDataset.description || 'No description provided'}</p>
                </div>
                <div>
                  <h3 className="text-sm font-medium text-gray-500">Sample Count</h3>
                  <p className="mt-1">{currentDataset.sample_count}</p>
                </div>
                <div>
                  <h3 className="text-sm font-medium text-gray-500">Format</h3>
                  <Badge variant="outline" className="mt-1">
                    {currentDataset.format || 'instruct'}
                  </Badge>
                </div>
              </div>
              
              <div className="flex-1 overflow-hidden">
                <h3 className="text-sm font-medium text-gray-500 mb-2">Samples</h3>
                
                {datasetSamples.length === 0 ? (
                  <div className="flex justify-center items-center h-32 border rounded-md border-dashed">
                    <p className="text-gray-500">No samples available</p>
                  </div>
                ) : (
                  <div className="border rounded-md overflow-hidden flex-1">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-1/12">#</TableHead>
                          <TableHead className="w-5/12">Instruction</TableHead>
                          <TableHead className="w-5/12">Response</TableHead>
                          <TableHead className="w-1/12">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody className="overflow-auto">
                        {datasetSamples.map((sample, index) => (
                          <TableRow key={index}>
                            <TableCell>{index + 1}</TableCell>
                            <TableCell className="max-w-xs truncate">
                              {sample.instruction}
                            </TableCell>
                            <TableCell className="max-w-xs truncate">
                              {sample.response}
                            </TableCell>
                            <TableCell>
                              <Button 
                                variant="ghost" 
                                size="sm"
                                onClick={() => setSelectedSampleIndex(index)}
                              >
                                <Info className="h-4 w-4" />
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex justify-center items-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-800"></div>
            </div>
          )}
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setViewDetailsOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      
      {/* Sample Detail Dialog */}
      <Dialog 
        open={selectedSampleIndex !== null} 
        onOpenChange={(open) => !open && setSelectedSampleIndex(null)}
      >
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Sample #{selectedSampleIndex !== null ? selectedSampleIndex + 1 : ''}</DialogTitle>
            <DialogDescription>
              Detailed view of instruction-response pair
            </DialogDescription>
          </DialogHeader>
          
          {selectedSampleIndex !== null && datasetSamples[selectedSampleIndex] && (
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-medium text-gray-500 mb-2">Instruction</h3>
                <div className="bg-gray-50 p-3 rounded-md whitespace-pre-wrap">
                  {datasetSamples[selectedSampleIndex].instruction}
                </div>
              </div>
              
              <div>
                <h3 className="text-sm font-medium text-gray-500 mb-2">Response</h3>
                <div className="bg-gray-50 p-3 rounded-md whitespace-pre-wrap">
                  {datasetSamples[selectedSampleIndex].response}
                </div>
              </div>
            </div>
          )}
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedSampleIndex(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default DatasetManager;
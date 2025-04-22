import React, { useState, useEffect } from 'react';
import { Button } from '../../components/Button';
import { knowledgeClient } from '../../services/knowledgeClient';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Slider } from '@/components/ui/slider';
import { AlertCircle, Info, Save, RefreshCw, Settings } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

interface RagConfigState {
  embeddingModel: string;
  retrievalCount: number;
  minSimilarityScore: number;
  enableRagByDefault: boolean;
  chunkSize: number;
  chunkOverlap: number;
}

const RagSettingsPanel: React.FC = () => {
  const { toast } = useToast();
  
  const [config, setConfig] = useState<RagConfigState>({
    embeddingModel: 'openai',
    retrievalCount: 3,
    minSimilarityScore: 0.7,
    enableRagByDefault: true,
    chunkSize: 1000,
    chunkOverlap: 200,
  });
  
  const [originalConfig, setOriginalConfig] = useState<RagConfigState | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isReindexing, setIsReindexing] = useState<boolean>(false);
  
  // Fetch initial configuration
  useEffect(() => {
    const fetchConfig = async () => {
      setIsLoading(true);
      try {
        const embeddingsConfig = await knowledgeClient.getEmbeddingsConfig();
        
        // Merge with other config values (in a real app, you'd get these from backend too)
        const fullConfig = {
          embeddingModel: embeddingsConfig.model,
          retrievalCount: 3, // Example default
          minSimilarityScore: 0.7,
          enableRagByDefault: true,
          chunkSize: 1000,
          chunkOverlap: 200,
        };
        
        setConfig(fullConfig);
        setOriginalConfig(fullConfig);
      } catch (error) {
        console.error('Error fetching RAG configuration:', error);
        toast({
          title: 'Error',
          description: 'Failed to load RAG configuration',
          variant: 'destructive',
        });
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchConfig();
  }, [toast]);
  
  const handleConfigChange = (key: keyof RagConfigState, value: any) => {
    setConfig(prev => ({
      ...prev,
      [key]: value
    }));
  };
  
  const handleSaveConfig = async () => {
    setIsSaving(true);
    try {
      // Save embeddings model config
      await knowledgeClient.updateEmbeddingsConfig({
        model: config.embeddingModel
      });
      
      // In a real app, you'd save other settings too
      // await knowledgeClient.updateRagConfig({ ...other settings });
      
      setOriginalConfig(config);
      
      toast({
        title: 'Success',
        description: 'RAG configuration saved successfully',
      });
    } catch (error) {
      console.error('Error saving RAG configuration:', error);
      toast({
        title: 'Error',
        description: 'Failed to save RAG configuration',
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };
  
  const handleReindexing = async () => {
    setIsReindexing(true);
    try {
      await knowledgeClient.reindexKnowledge();
      
      toast({
        title: 'Success',
        description: 'Knowledge base reindexing initiated successfully',
      });
    } catch (error) {
      console.error('Error initiating reindexing:', error);
      toast({
        title: 'Error',
        description: 'Failed to initiate reindexing',
        variant: 'destructive',
      });
    } finally {
      setIsReindexing(false);
    }
  };
  
  const hasChanges = originalConfig && (
    originalConfig.embeddingModel !== config.embeddingModel ||
    originalConfig.retrievalCount !== config.retrievalCount ||
    originalConfig.minSimilarityScore !== config.minSimilarityScore ||
    originalConfig.enableRagByDefault !== config.enableRagByDefault ||
    originalConfig.chunkSize !== config.chunkSize ||
    originalConfig.chunkOverlap !== config.chunkOverlap
  );
  
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Settings className="h-5 w-5" />
          RAG Configuration
        </CardTitle>
        <CardDescription>
          Configure knowledge retrieval and embedding settings
        </CardDescription>
      </CardHeader>
      
      <CardContent className="space-y-6">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : (
          <>
            <div className="space-y-4">
              <div>
                <Label htmlFor="embeddingModel">Embedding Model</Label>
                <Select 
                  value={config.embeddingModel} 
                  onValueChange={(value) => handleConfigChange('embeddingModel', value)}
                >
                  <SelectTrigger id="embeddingModel">
                    <SelectValue placeholder="Select embedding model" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="openai">OpenAI Embeddings</SelectItem>
                    <SelectItem value="huggingface">Hugging Face Embeddings</SelectItem>
                    <SelectItem value="cohere">Cohere Embeddings</SelectItem>
                    <SelectItem value="local">Local Embeddings (SentenceTransformers)</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-gray-500 mt-1">
                  Model used to create vector embeddings for documents
                </p>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="retrievalCount">Retrieval Count</Label>
                  <div className="flex items-center gap-2">
                    <Slider 
                      value={[config.retrievalCount]}
                      min={1}
                      max={10}
                      step={1}
                      onValueChange={(value) => handleConfigChange('retrievalCount', value[0])}
                      className="flex-1"
                    />
                    <Input 
                      type="number" 
                      id="retrievalCount"
                      min={1}
                      max={10}
                      value={config.retrievalCount} 
                      onChange={(e) => handleConfigChange('retrievalCount', parseInt(e.target.value))}
                      className="w-16"
                    />
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    Number of chunks to retrieve from knowledge base
                  </p>
                </div>
                
                <div>
                  <Label htmlFor="minSimilarityScore">Min. Similarity Score</Label>
                  <div className="flex items-center gap-2">
                    <Slider 
                      value={[config.minSimilarityScore * 100]}
                      min={0}
                      max={100}
                      step={1}
                      onValueChange={(value) => handleConfigChange('minSimilarityScore', value[0] / 100)}
                      className="flex-1"
                    />
                    <Input 
                      type="text" 
                      id="minSimilarityScore"
                      value={`${(config.minSimilarityScore * 100).toFixed(0)}%`} 
                      readOnly
                      className="w-16"
                    />
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    Minimum similarity threshold for retrieved content
                  </p>
                </div>
              </div>
              
              <div className="flex items-center justify-between border rounded-md p-3">
                <div>
                  <Label htmlFor="enableRagByDefault">Enable RAG by Default</Label>
                  <p className="text-xs text-gray-500">
                    Automatically augment AI responses with knowledge base
                  </p>
                </div>
                <Switch 
                  id="enableRagByDefault"
                  checked={config.enableRagByDefault}
                  onCheckedChange={(checked) => handleConfigChange('enableRagByDefault', checked)}
                />
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="chunkSize">Chunk Size</Label>
                  <div className="flex items-center gap-2">
                    <Slider 
                      value={[config.chunkSize]}
                      min={100}
                      max={2000}
                      step={100}
                      onValueChange={(value) => handleConfigChange('chunkSize', value[0])}
                      className="flex-1"
                    />
                    <Input 
                      type="number" 
                      id="chunkSize"
                      min={100}
                      max={2000}
                      step={100}
                      value={config.chunkSize} 
                      onChange={(e) => handleConfigChange('chunkSize', parseInt(e.target.value))}
                      className="w-24"
                    />
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    Size of document chunks (in characters)
                  </p>
                </div>
                
                <div>
                  <Label htmlFor="chunkOverlap">Chunk Overlap</Label>
                  <div className="flex items-center gap-2">
                    <Slider 
                      value={[config.chunkOverlap]}
                      min={0}
                      max={500}
                      step={50}
                      onValueChange={(value) => handleConfigChange('chunkOverlap', value[0])}
                      className="flex-1"
                    />
                    <Input 
                      type="number" 
                      id="chunkOverlap"
                      min={0}
                      max={500}
                      step={50}
                      value={config.chunkOverlap} 
                      onChange={(e) => handleConfigChange('chunkOverlap', parseInt(e.target.value))}
                      className="w-24"
                    />
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    Overlap between adjacent chunks (in characters)
                  </p>
                </div>
              </div>
            </div>
          </>
        )}
      </CardContent>
      
      <CardFooter className="flex justify-between">
        <Button
          variant="outline"
          className="flex items-center gap-2"
          onClick={handleReindexing}
          disabled={isReindexing || isLoading}
        >
          <RefreshCw className={`h-4 w-4 ${isReindexing ? 'animate-spin' : ''}`} />
          {isReindexing ? 'Reindexing...' : 'Reindex Knowledge Base'}
        </Button>
        
        <Button
          className="flex items-center gap-2"
          onClick={handleSaveConfig}
          disabled={isSaving || isLoading || !hasChanges}
        >
          <Save className="h-4 w-4" />
          {isSaving ? 'Saving...' : 'Save Configuration'}
        </Button>
      </CardFooter>
    </Card>
  );
};

export default RagSettingsPanel;
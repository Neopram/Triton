import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { RadioGroup, RadioGroupItem } from '../../components/ui/radio-group';
import { Label } from '../../components/ui/label';
import { Button } from '../../components/ui/button';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { Loader, Settings, Check, AlertCircle } from 'lucide-react';
import useAIConfigStore from '../../store/aiConfigStore';
import useAuthStore from '../../store/authStore';

const AISettingsPanel: React.FC = () => {
  const { user } = useAuthStore();
  const { config, loading, error, fetchConfig, updateConfig } = useAIConfigStore();
  const [selectedEngine, setSelectedEngine] = useState<string>('');
  const [updateStatus, setUpdateStatus] = useState<'idle' | 'success' | 'error'>('idle');

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  useEffect(() => {
    if (config && config.current_engine) {
      setSelectedEngine(config.current_engine);
    }
  }, [config]);

  const handleEngineChange = (value: string) => {
    setSelectedEngine(value);
  };

  const handleUpdateConfig = async () => {
    if (selectedEngine && selectedEngine !== config?.current_engine) {
      const success = await updateConfig(selectedEngine);
      setUpdateStatus(success ? 'success' : 'error');
      
      // Reset status after 3 seconds
      setTimeout(() => {
        setUpdateStatus('idle');
      }, 3000);
    }
  };

  // Only admins can access this panel
  if (user?.role !== 'admin') {
    return (
      <div className="p-8 text-center">
        <AlertCircle className="mx-auto h-12 w-12 text-yellow-500 mb-4" />
        <h3 className="text-lg font-medium mb-2">Access Restricted</h3>
        <p className="text-gray-500">
          Only administrators can access the AI settings panel.
        </p>
      </div>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-xl font-bold">
          <Settings className="inline-block mr-2 h-5 w-5" />
          AI Engine Configuration
        </CardTitle>
        {loading && <Loader className="h-4 w-4 animate-spin text-gray-500" />}
      </CardHeader>
      <CardContent>
        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {updateStatus === 'success' && (
          <Alert className="mb-4 bg-green-50 text-green-800 border-green-200">
            <Check className="h-4 w-4" />
            <AlertDescription>AI Engine updated successfully!</AlertDescription>
          </Alert>
        )}

        {updateStatus === 'error' && (
          <Alert variant="destructive" className="mb-4">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>Failed to update AI Engine.</AlertDescription>
          </Alert>
        )}

        <div className="space-y-6">
          <div>
            <h3 className="text-sm font-medium mb-2">Current Engine</h3>
            <div className="text-2xl font-bold">
              {config?.current_engine || 'Loading...'}
            </div>
            {!config?.is_valid && (
              <p className="text-red-500 text-sm mt-1">
                Current engine configuration is invalid.
              </p>
            )}
          </div>

          <div>
            <h3 className="text-sm font-medium mb-4">Select AI Engine</h3>
            {config?.available_engines && config.available_engines.length > 0 ? (
              <RadioGroup
                value={selectedEngine}
                onValueChange={handleEngineChange}
                className="space-y-3"
              >
                {config.available_engines.map((engine) => (
                  <div key={engine} className="flex items-center space-x-2">
                    <RadioGroupItem value={engine} id={engine} />
                    <Label htmlFor={engine} className="font-medium">
                      {engine}
                    </Label>
                  </div>
                ))}
              </RadioGroup>
            ) : (
              <p className="text-gray-500">No available engines found.</p>
            )}
          </div>

          <Button
            onClick={handleUpdateConfig}
            disabled={
              loading ||
              !selectedEngine ||
              selectedEngine === config?.current_engine
            }
            className="w-full"
          >
            {loading ? (
              <>
                <Loader className="mr-2 h-4 w-4 animate-spin" />
                Updating...
              </>
            ) : (
              'Update AI Engine'
            )}
          </Button>

          <div className="text-sm text-gray-500 mt-4">
            <p>
              <strong>phi3:</strong> Local Phi-3 model with fast response times,
              suitable for most tasks.
            </p>
            <p>
              <strong>deepseek:</strong> Cloud-based DeepSeek model with enhanced
              capabilities for complex analysis.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default AISettingsPanel;
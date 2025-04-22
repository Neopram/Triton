import React, { useState, useCallback } from 'react';
import { useKnowledgeStore } from '../../store/knowledgeStore';
import { Upload, FileText, Check, X, AlertCircle } from 'lucide-react';
import { Button } from '../../components/Button';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';

const DocumentUploader: React.FC = () => {
  const { uploadDocument } = useKnowledgeStore();
  
  const [dragActive, setDragActive] = useState<boolean>(false);
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<{[key: string]: number}>({});
  const [uploadErrors, setUploadErrors] = useState<{[key: string]: string}>({});
  const [uploadSuccess, setUploadSuccess] = useState<string[]>([]);
  
  // Handle drag events
  const handleDrag = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);
  
  // Handle drop event
  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const newFiles = Array.from(e.dataTransfer.files);
      setFiles(prev => [...prev, ...newFiles]);
    }
  }, []);
  
  // Handle file input change
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const newFiles = Array.from(e.target.files);
      setFiles(prev => [...prev, ...newFiles]);
    }
  };
  
  // Remove file from the list
  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };
  
  // Upload all files
  const handleUpload = async () => {
    if (files.length === 0) return;
    
    setUploading(true);
    
    // Reset states
    setUploadProgress({});
    setUploadErrors({});
    setUploadSuccess([]);
    
    // Process each file
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      
      try {
        // Set initial progress
        setUploadProgress(prev => ({
          ...prev,
          [file.name]: 0
        }));
        
        // Simulate progress (in a real app, you'd use an upload progress event)
        const progressInterval = setInterval(() => {
          setUploadProgress(prev => {
            const currentProgress = prev[file.name] || 0;
            if (currentProgress < 90) {
              return { ...prev, [file.name]: currentProgress + 10 };
            }
            return prev;
          });
        }, 200);
        
        // Upload the file
        await uploadDocument(file);
        
        // Clear interval and set to 100%
        clearInterval(progressInterval);
        setUploadProgress(prev => ({
          ...prev,
          [file.name]: 100
        }));
        
        // Mark as success
        setUploadSuccess(prev => [...prev, file.name]);
      } catch (error) {
        console.error('Error uploading file:', error);
        setUploadErrors(prev => ({
          ...prev,
          [file.name]: 'Failed to upload file'
        }));
      }
    }
    
    setUploading(false);
    
    // Clear successful uploads after 2 seconds
    setTimeout(() => {
      setFiles(prev => prev.filter(file => !uploadSuccess.includes(file.name)));
      setUploadProgress({});
      setUploadSuccess([]);
    }, 2000);
  };
  
  return (
    <Card className="p-4">
      <CardContent className="p-0">
        <div 
          className={`border-2 border-dashed rounded-lg p-6 ${dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300'}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <div className="flex flex-col items-center justify-center space-y-4 text-center">
            <Upload className="h-12 w-12 text-gray-400" />
            
            <div>
              <p className="text-lg font-medium text-gray-800">
                Drag & drop files here
              </p>
              <p className="text-sm text-gray-500">
                Or click to browse from your computer
              </p>
            </div>
            
            <p className="text-xs text-gray-500 max-w-md">
              Supported file types: PDF, DOCX, TXT, CSV, JSON
              <br />
              Maximum file size: 10MB
            </p>
            
            <input
              type="file"
              id="file-upload"
              multiple
              onChange={handleFileChange}
              className="hidden"
              accept=".pdf,.docx,.txt,.csv,.json"
            />
            
            <Button 
              variant="outline"
              onClick={() => document.getElementById('file-upload')?.click()}
              disabled={uploading}
            >
              Select Files
            </Button>
          </div>
        </div>
        
        {files.length > 0 && (
          <div className="mt-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-medium">Selected Files ({files.length})</h3>
              {!uploading && (
                <Button onClick={handleUpload}>
                  Upload {files.length} {files.length === 1 ? 'file' : 'files'}
                </Button>
              )}
            </div>
            
            <div className="space-y-3">
              {files.map((file, index) => {
                const fileProgress = uploadProgress[file.name] || 0;
                const fileError = uploadErrors[file.name];
                const fileSuccess = uploadSuccess.includes(file.name);
                
                return (
                  <div 
                    key={`${file.name}-${index}`}
                    className="flex items-center p-3 border rounded-md bg-gray-50"
                  >
                    <FileText className="h-5 w-5 text-gray-500 mr-3" />
                    
                    <div className="flex-1 mr-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium truncate max-w-xs">{file.name}</span>
                        <span className="text-xs text-gray-500">{(file.size / 1024).toFixed(1)} KB</span>
                      </div>
                      
                      {(uploading || fileSuccess || fileError) && (
                        <div className="w-full">
                          <Progress value={fileProgress} className="h-1" />
                        </div>
                      )}
                      
                      {fileError && (
                        <div className="flex items-center mt-1 text-xs text-red-600">
                          <AlertCircle className="h-3 w-3 mr-1" />
                          {fileError}
                        </div>
                      )}
                    </div>
                    
                    {fileSuccess ? (
                      <Check className="h-5 w-5 text-green-500" />
                    ) : (
                      <button 
                        onClick={() => removeFile(index)}
                        disabled={uploading}
                        className="p-1 hover:bg-gray-200 rounded-full"
                      >
                        <X className="h-4 w-4 text-gray-500" />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default DocumentUploader;
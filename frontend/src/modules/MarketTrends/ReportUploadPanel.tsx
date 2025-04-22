import React, { useState } from 'react';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { Upload, FileText, X, Check, Loader } from 'lucide-react';
import useInsightStore from '../../store/insightStore';

interface ReportUploadPanelProps {
  onSuccess: () => void;
}

const ReportUploadPanel: React.FC<ReportUploadPanelProps> = ({ onSuccess }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { analyzeReport, loading } = useInsightStore();
  
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };
  
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };
  
  const handleFileSelect = (file: File) => {
    // Check file type
    const allowedTypes = ['text/csv', 'text/plain', 'application/pdf', 'application/vnd.ms-excel'];
    if (!allowedTypes.includes(file.type)) {
      setError('Please upload a CSV, TXT, PDF or Excel file.');
      return;
    }
    
    // Check file size (10MB max)
    if (file.size > 10 * 1024 * 1024) {
      setError('File size exceeds the maximum allowed (10MB).');
      return;
    }
    
    setSelectedFile(file);
    setError(null);
  };
  
  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelect(e.target.files[0]);
    }
  };
  
  const handleUpload = async () => {
    if (!selectedFile) return;
    
    try {
      const result = await analyzeReport(selectedFile);
      if (result) {
        onSuccess();
      }
    } catch (err) {
      setError('Analysis failed. Please try again.');
      console.error(err);
    }
  };
  
  const handleRemoveFile = () => {
    setSelectedFile(null);
    setError(null);
  };
  
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium">Upload Market Report</h3>
        <p className="text-sm text-gray-500">
          Upload a market report to generate AI-powered insights
        </p>
      </div>
      
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-md text-sm">
          {error}
        </div>
      )}
      
      {!selectedFile ? (
        <Card 
          className={`border-2 border-dashed rounded-lg ${
            dragActive ? 'border-blue-400 bg-blue-50' : 'border-gray-300'
          }`}
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
        >
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Upload 
              size={48} 
              className={`mb-4 ${dragActive ? 'text-blue-500' : 'text-gray-400'}`} 
            />
            <h4 className="text-lg font-medium mb-2">
              {dragActive ? 'Drop your file here' : 'Drag and drop your file here'}
            </h4>
            <p className="text-sm text-gray-500 mb-4">
              or click to browse files (CSV, TXT, PDF or Excel)
            </p>
            <Button asChild>
              <label className="cursor-pointer">
                Browse Files
                <input
                  type="file"
                  accept=".csv,.txt,.pdf,.xls,.xlsx"
                  onChange={handleFileInput}
                  className="hidden"
                />
              </label>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="flex items-center justify-between py-6">
            <div className="flex items-center">
              <FileText size={24} className="text-blue-500 mr-3" />
              <div>
                <div className="font-medium">{selectedFile.name}</div>
                <div className="text-sm text-gray-500">
                  {(selectedFile.size / 1024).toFixed(0)} KB
                </div>
              </div>
            </div>
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={handleRemoveFile}
              className="text-gray-500"
            >
              <X size={18} />
            </Button>
          </CardContent>
        </Card>
      )}
      
      <div className="flex justify-end">
        <Button
          onClick={handleUpload}
          disabled={!selectedFile || loading}
          className="flex items-center gap-2"
        >
          {loading ? (
            <>
              <Loader size={16} className="animate-spin" />
              Analyzing...
            </>
          ) : (
            <>
              <Check size={16} />
              Analyze Report
            </>
          )}
        </Button>
      </div>
    </div>
  );
};

export default ReportUploadPanel;
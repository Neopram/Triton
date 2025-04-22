import React, { useState } from 'react';
import { useKnowledgeStore, KnowledgeDocument } from '../../store/knowledgeStore';
import { Search, File, FileText, FileCode, FileSpreadsheet, Trash2, AlertCircle, Info, Clock } from 'lucide-react';
import { Button } from '../../components/Button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog';
import { format } from 'date-fns';
import { knowledgeClient } from '../../services/knowledgeClient';

// Helper to get file icon based on file type
const getFileIcon = (fileType: string): React.ReactNode => {
  switch (fileType.toLowerCase()) {
    case 'pdf':
      return <File className="h-5 w-5 text-red-500" />;
    case 'docx':
    case 'doc':
      return <FileText className="h-5 w-5 text-blue-500" />;
    case 'txt':
      return <FileText className="h-5 w-5 text-gray-500" />;
    case 'csv':
    case 'xlsx':
    case 'xls':
      return <FileSpreadsheet className="h-5 w-5 text-green-500" />;
    case 'json':
      return <FileCode className="h-5 w-5 text-orange-500" />;
    default:
      return <File className="h-5 w-5 text-gray-500" />;
  }
};

// Status badge component
const StatusBadge: React.FC<{ status: KnowledgeDocument['status'] }> = ({ status }) => {
  switch (status) {
    case 'processing':
      return <Badge className="bg-yellow-100 text-yellow-800 border-yellow-200">Processing</Badge>;
    case 'indexed':
      return <Badge className="bg-green-100 text-green-800 border-green-200">Indexed</Badge>;
    case 'failed':
      return <Badge className="bg-red-100 text-red-800 border-red-200">Failed</Badge>;
    default:
      return null;
  }
};

const KnowledgeExplorer: React.FC = () => {
  const { 
    documents, 
    filteredDocuments, 
    isLoading, 
    searchQuery, 
    setSearchQuery, 
    deleteDocument,
    fetchDocuments
  } = useKnowledgeStore();
  
  const [documentContent, setDocumentContent] = useState<string | null>(null);
  const [selectedDocument, setSelectedDocument] = useState<KnowledgeDocument | null>(null);
  const [documentToDelete, setDocumentToDelete] = useState<KnowledgeDocument | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [viewDetailOpen, setViewDetailOpen] = useState<boolean>(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState<boolean>(false);
  
  // Handle search
  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
  };
  
  // View document details
  const handleViewDocument = async (document: KnowledgeDocument) => {
    setSelectedDocument(document);
    setViewDetailOpen(true);
    
    try {
      const content = await knowledgeClient.getDocumentContent(document.id);
      setDocumentContent(content);
    } catch (error) {
      console.error('Error fetching document content:', error);
      setDocumentContent('Failed to load document content');
    }
  };
  
  // Delete document confirmation
  const handleDeleteClick = (document: KnowledgeDocument) => {
    setDocumentToDelete(document);
    setDeleteDialogOpen(true);
  };
  
  // Confirm delete
  const confirmDelete = async () => {
    if (!documentToDelete) return;
    
    setIsDeleting(true);
    try {
      await deleteDocument(documentToDelete.id);
      setDeleteDialogOpen(false);
    } catch (error) {
      console.error('Error deleting document:', error);
    } finally {
      setIsDeleting(false);
    }
  };
  
  return (
    <>
      <Card className="p-4">
        <CardContent className="p-0 space-y-4">
          <div className="relative">
            <Search className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Search documents..."
              className="pl-9"
              value={searchQuery}
              onChange={handleSearch}
            />
          </div>
          
          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-800 mx-auto"></div>
                <p className="mt-2 text-gray-600">Loading documents...</p>
              </div>
            </div>
          ) : filteredDocuments.length === 0 ? (
            <div className="text-center py-12">
              {searchQuery ? (
                <>
                  <SearchX className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900">No documents found</h3>
                  <p className="text-gray-500 mt-1">Try adjusting your search term</p>
                </>
              ) : (
                <>
                  <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900">No documents yet</h3>
                  <p className="text-gray-500 mt-1">Upload documents to build your knowledge base</p>
                </>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              {filteredDocuments.map((document) => (
                <div 
                  key={document.id}
                  className="border rounded-md p-4 hover:bg-gray-50 transition-colors flex justify-between items-center"
                >
                  <div className="flex items-center space-x-3">
                    {getFileIcon(document.file_type)}
                    
                    <div>
                      <h3 className="font-medium text-gray-900">{document.title || document.filename}</h3>
                      <div className="flex items-center space-x-2 mt-1">
                        <StatusBadge status={document.status} />
                        <span className="text-xs text-gray-500">{(document.size_kb / 1024).toFixed(2)} MB</span>
                        {document.chunks_count && (
                          <span className="text-xs text-gray-500">{document.chunks_count} chunks</span>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    <Button 
                      variant="ghost" 
                      size="sm"
                      onClick={() => handleViewDocument(document)}
                    >
                      <Info className="h-4 w-4 mr-1" />
                      Details
                    </Button>
                    
                    <Button 
                      variant="ghost" 
                      size="sm"
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      onClick={() => handleDeleteClick(document)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
      
      {/* Document Detail Dialog */}
      <Dialog open={viewDetailOpen} onOpenChange={setViewDetailOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Document Details</DialogTitle>
          </DialogHeader>
          
          {selectedDocument && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm font-medium text-gray-500">File Name</p>
                  <p className="font-medium">{selectedDocument.filename}</p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-500">File Type</p>
                  <p className="font-medium uppercase">{selectedDocument.file_type}</p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-500">Status</p>
                  <StatusBadge status={selectedDocument.status} />
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-500">Size</p>
                  <p className="font-medium">{(selectedDocument.size_kb / 1024).toFixed(2)} MB</p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-500">Uploaded</p>
                  <div className="flex items-center">
                    <Clock className="h-3 w-3 text-gray-400 mr-1" />
                    <p className="font-medium">
                      {format(new Date(selectedDocument.upload_date), 'MMM d, yyyy HH:mm')}
                    </p>
                  </div>
                </div>
                
                {selectedDocument.chunks_count && (
                  <div>
                    <p className="text-sm font-medium text-gray-500">Knowledge Chunks</p>
                    <p className="font-medium">{selectedDocument.chunks_count}</p>
                  </div>
                )}
              </div>
              
              {selectedDocument.error_message && (
                <div className="bg-red-50 p-3 rounded-md flex items-start space-x-2">
                  <AlertCircle className="h-5 w-5 text-red-500 mt-0.5" />
                  <div>
                    <p className="font-medium text-red-800">Processing Error</p>
                    <p className="text-red-600">{selectedDocument.error_message}</p>
                  </div>
                </div>
              )}
              
              <div>
                <p className="text-sm font-medium text-gray-500 mb-2">Document Preview</p>
                <div className="border rounded-md p-4 bg-gray-50 h-64 overflow-auto">
                  {documentContent === null ? (
                    <div className="flex items-center justify-center h-full">
                      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-gray-800"></div>
                    </div>
                  ) : (
                    <pre className="text-xs whitespace-pre-wrap font-mono">{documentContent}</pre>
                  )}
                </div>
              </div>
            </div>
          )}
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setViewDetailOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      
      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Document</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this document? This will remove it from your knowledge base and may affect AI responses that relied on this information.
            </DialogDescription>
          </DialogHeader>
          
          {documentToDelete && (
            <div className="flex items-center space-x-3 p-4 bg-gray-50 rounded-md">
              {getFileIcon(documentToDelete.file_type)}
              <div>
                <p className="font-medium">{documentToDelete.title || documentToDelete.filename}</p>
                <p className="text-sm text-gray-500">{(documentToDelete.size_kb / 1024).toFixed(2)} MB</p>
              </div>
            </div>
          )}
          
          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={() => setDeleteDialogOpen(false)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button 
              variant="destructive"
              onClick={confirmDelete}
              disabled={isDeleting}
              className="bg-red-600 hover:bg-red-700"
            >
              {isDeleting ? 'Deleting...' : 'Delete Document'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default KnowledgeExplorer;
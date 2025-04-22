import React, { useState } from 'react';
import { File, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from './Button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

export interface Reference {
  document_id: string;
  document_title: string;
  chunk_id: string;
  content: string;
  similarity: number;
}

interface RagReferencesProps {
  references: Reference[];
  onViewDocument?: (documentId: string) => void;
}

const RagReferences: React.FC<RagReferencesProps> = ({ 
  references,
  onViewDocument 
}) => {
  const [isOpen, setIsOpen] = useState(false);
  
  if (!references || references.length === 0) {
    return null;
  }
  
  return (
    <div className="mt-4 pt-3 border-t border-gray-200">
      <Collapsible
        open={isOpen}
        onOpenChange={setIsOpen}
        className="w-full"
      >
        <div className="flex items-center justify-between">
          <CollapsibleTrigger asChild>
            <Button 
              variant="ghost" 
              size="sm" 
              className="flex items-center text-gray-600 hover:text-gray-900 p-0"
            >
              {isOpen ? <ChevronUp className="h-4 w-4 mr-2" /> : <ChevronDown className="h-4 w-4 mr-2" />}
              <span className="font-medium">
                {references.length} {references.length === 1 ? 'Source' : 'Sources'}
              </span>
            </Button>
          </CollapsibleTrigger>
          
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <div>
                  <Badge variant="outline" className="text-xs">
                    RAG Enhanced
                  </Badge>
                </div>
              </TooltipTrigger>
              <TooltipContent>
                <p className="text-xs max-w-xs">
                  This response was enhanced with information from your document knowledge base
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        
        <CollapsibleContent className="mt-2 space-y-2">
          {references.map((ref, index) => (
            <div 
              key={ref.chunk_id || index} 
              className="bg-gray-50 rounded-md p-3 border border-gray-200"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center">
                  <File className="h-4 w-4 text-blue-600 mr-2" />
                  <span className="font-medium text-sm truncate max-w-md">
                    {ref.document_title}
                  </span>
                </div>
                
                <div className="flex items-center gap-2">
                  <Badge className="bg-blue-100 text-blue-800 text-xs">
                    {Math.round(ref.similarity * 100)}% match
                  </Badge>
                  
                  {onViewDocument && (
                    <Button 
                      variant="ghost" 
                      size="xs"
                      className="text-xs p-1 h-auto"
                      onClick={() => onViewDocument(ref.document_id)}
                    >
                      <ExternalLink className="h-3 w-3 mr-1" />
                      View
                    </Button>
                  )}
                </div>
              </div>
              
              <div className="text-sm text-gray-700 bg-white p-2 rounded border border-gray-200">
                <p className="whitespace-pre-wrap text-xs">{ref.content}</p>
              </div>
            </div>
          ))}
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
};

export default RagReferences;
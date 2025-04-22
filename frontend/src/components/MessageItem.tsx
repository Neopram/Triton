import React from 'react';
import { formatDistanceToNow } from 'date-fns';
import { Paperclip, Check, CheckCheck, Book } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

interface Reference {
  document_id: string;
  document_title: string;
  chunk_id: string;
  content: string;
  similarity: number;
}

interface MessageItemProps {
  id: number;
  content: string;
  senderName: string;
  timestamp: string;
  isRead: boolean;
  hasAttachments: boolean;
  isSelected?: boolean;
  references?: Reference[];
  onClick: () => void;
}

const MessageItem: React.FC<MessageItemProps> = ({
  id,
  content,
  senderName,
  timestamp,
  isRead,
  hasAttachments,
  isSelected = false,
  references = [],
  onClick,
}) => {
  // Format time as "2 hours ago" or similar
  const formattedTime = formatDistanceToNow(new Date(timestamp), { addSuffix: true });
  
  // Truncate content if it's too long
  const truncatedContent = content.length > 100 
    ? `${content.substring(0, 100)}...` 
    : content;
  
  // Check if message has knowledge base references
  const hasReferences = references.length > 0;
  
  return (
    <div 
      className={`p-3 border-b cursor-pointer hover:bg-gray-50 transition-colors ${
        isSelected ? 'bg-blue-50' : ''
      } ${!isRead ? 'font-semibold' : ''}`}
      onClick={onClick}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium">{senderName}</span>
        <span className="text-xs text-gray-500">{formattedTime}</span>
      </div>
      
      <div className="text-sm text-gray-700">{truncatedContent}</div>
      
      <div className="flex mt-2 items-center text-gray-500">
        {hasAttachments && (
          <Paperclip size={14} className="mr-2" />
        )}
        
        {hasReferences && (
          <div className="flex items-center mr-2">
            <Book size={14} className="text-blue-500 mr-1" />
            <Badge variant="outline" className="text-xs py-0 h-4">
              {references.length}
            </Badge>
          </div>
        )}
        
        <div className="ml-auto">
          {isRead ? (
            <CheckCheck size={14} className="text-blue-500" />
          ) : (
            <Check size={14} />
          )}
        </div>
      </div>
    </div>
  );
};

export default MessageItem;
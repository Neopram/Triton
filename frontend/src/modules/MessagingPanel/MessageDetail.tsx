import React, { useState } from 'react';
import { format } from 'date-fns';
import { Button } from '../../components/ui/button';
import { 
  ArrowLeft, 
  Paperclip, 
  Download, 
  Trash, 
  Check, 
  Clock, 
  Smile,
  Plus,
  Book,
  ExternalLink,
  File
} from 'lucide-react';
import { downloadAttachment, addReaction, removeReaction, deleteMessage } from '../../services/api';
import useMessageStore from '../../store/messageStore';
import useAuthStore from '../../store/authStore';
import { Dialog, DialogContent, DialogTrigger, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { Badge } from '../../components/ui/badge';
import { get_emoji_suggestions, is_valid_emoji } from '../../core/utils/emoji';
import { knowledgeClient } from '../../services/knowledgeClient';
import { Reference } from '../../components/RagReferences';

interface MessageDetailProps {
  message: any; // Use the MessageDetail type from the store
  onBack: () => void;
}

const MessageDetail: React.FC<MessageDetailProps> = ({ message, onBack }) => {
  const { user } = useAuthStore();
  const { fetchMessage } = useMessageStore();
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [documentContent, setDocumentContent] = useState<string | null>(null);
  const [isLoadingDocument, setIsLoadingDocument] = useState<boolean>(false);
  const [documentDialogOpen, setDocumentDialogOpen] = useState<boolean>(false);
  
  const isSender = user?.id === message.sender_id;
  const formattedDate = format(new Date(message.created_at), 'MMMM d, yyyy • h:mm a');
  
  const commonEmojis = [
    '👍', '❤️', '😊', '👏', '🎉', '🚢', '⚓', '🌊'
  ];
  
  const handleAddReaction = async (emoji: string) => {
    if (!is_valid_emoji(emoji)) return;
    
    try {
      await addReaction(message.id, emoji);
      fetchMessage(message.id);
      setShowEmojiPicker(false);
    } catch (error) {
      console.error('Failed to add reaction', error);
    }
  };
  
  const handleRemoveReaction = async () => {
    try {
      await removeReaction(message.id);
      fetchMessage(message.id);
    } catch (error) {
      console.error('Failed to remove reaction', error);
    }
  };
    
  const handleDeleteMessage = async () => {
    setIsDeleting(true);
    try {
      await deleteMessage(message.id);
      onBack();
    } catch (error) {
      console.error('Failed to delete message', error);
      setIsDeleting(false);
    }
  };
    
  const handleDownload = (attachmentId: number, fileName: string) => {
    const link = document.createElement('a');
    link.href = downloadAttachment(attachmentId);
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleViewDocument = async (documentId: string) => {
    setSelectedDocumentId(documentId);
    setDocumentDialogOpen(true);
    setIsLoadingDocument(true);
    
    try {
      const content = await knowledgeClient.getDocumentContent(documentId);
      setDocumentContent(content);
    } catch (error) {
      console.error('Error fetching document content:', error);
      setDocumentContent('Failed to load document content');
    } finally {
      setIsLoadingDocument(false);
    }
  };
    
  return (
    <div className="flex-1 flex flex-col p-4">
      <div className="flex items-center mb-6">
        <Button variant="ghost" onClick={onBack} className="mr-2">
          <ArrowLeft size={18} />
        </Button>
        <h3 className="text-lg font-medium">Message</h3>
      </div>
      
      <div className="bg-gray-50 rounded-lg p-6 flex-1 overflow-auto">
        <div className="flex justify-between items-start mb-4">
          <div>
            <div className="font-medium">
              {isSender ? `To: ${message.recipient?.name}` : `From: ${message.sender?.name}`}
            </div>
            <div className="text-sm text-gray-500">{formattedDate}</div>
          </div>
          
          {message.is_read && !isSender && (
            <div className="flex items-center text-sm text-gray-500">
              <Check size={14} className="mr-1" />
              Read
            </div>
          )}
          
          {!message.is_read && !isSender && (
            <div className="flex items-center text-sm text-gray-500">
              <Clock size={14} className="mr-1" />
              Unread
            </div>
          )}
        </div>
        
        <div className="my-6 whitespace-pre-line">
          {message.content}
        </div>
        
        {message.attachments && message.attachments.length > 0 && (
          <div className="border-t border-b py-4 my-4">
            <div className="text-sm font-medium mb-2">Attachments:</div>
            <div className="space-y-2">
              {message.attachments.map((attachment: any) => (
                <div key={attachment.id} className="flex items-center justify-between bg-white p-3 rounded border">
                  <div className="flex items-center">
                    <Paperclip size={16} className="mr-2 text-gray-500" />
                    <span className="truncate max-w-xs">{attachment.file_name}</span>
                    <span className="text-xs text-gray-500 ml-2">
                      ({(attachment.file_size / 1024).toFixed(0)} KB)
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDownload(attachment.id, attachment.file_name)}
                    className="text-blue-500"
                  >
                    <Download size={16} />
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* RAG References Section */}
        {message.references && message.references.length > 0 && (
          <div className="border-t border-b py-4 my-4">
            <div className="flex items-center mb-2">
              <Book size={16} className="mr-2 text-blue-600" />
              <div className="text-sm font-medium">Knowledge Sources:</div>
              <Badge variant="outline" className="ml-2 text-xs">RAG Enhanced</Badge>
            </div>
            
            <div className="space-y-3">
              {message.references.map((reference: Reference, index: number) => (
                <div 
                  key={reference.chunk_id || index} 
                  className="bg-white rounded-md p-3 border border-gray-200"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center">
                      <File className="h-4 w-4 text-blue-600 mr-2" />
                      <span className="font-medium text-sm truncate max-w-md">
                        {reference.document_title}
                      </span>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <Badge className="bg-blue-100 text-blue-800 text-xs">
                        {Math.round(reference.similarity * 100)}% match
                      </Badge>
                      
                      <Button 
                        variant="ghost" 
                        size="sm"
                        className="text-xs p-1 h-auto"
                        onClick={() => handleViewDocument(reference.document_id)}
                      >
                        <ExternalLink className="h-3 w-3 mr-1" />
                        View
                      </Button>
                    </div>
                  </div>
                  
                  <div className="text-sm text-gray-700 bg-gray-50 p-2 rounded border border-gray-200">
                    <p className="whitespace-pre-wrap text-xs">{reference.content}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {message.reactions && Object.keys(message.reactions).length > 0 && (
          <div className="flex flex-wrap gap-2 my-4">
            {Object.entries(message.reactions).map(([emoji, count]) => (
              <div key={emoji} className="bg-gray-100 rounded-full px-3 py-1 text-sm flex items-center">
                <span className="mr-1">{emoji}</span>
                <span className="text-gray-700">{count}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      
      <div className="flex justify-between items-center mt-4 pt-4 border-t">
        <div className="flex gap-2">
          <Dialog open={showEmojiPicker} onOpenChange={setShowEmojiPicker}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm" className="flex items-center gap-1">
                <Smile size={16} />
                <span>React</span>
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-md">
              <div className="p-4">
                <h4 className="font-medium mb-4">Add a reaction</h4>
                <div className="grid grid-cols-8 gap-2">
                  {commonEmojis.map(emoji => (
                    <Button
                      key={emoji}
                      variant="ghost"
                      className="text-2xl h-10 w-10"
                      onClick={() => handleAddReaction(emoji)}
                    >
                      {emoji}
                    </Button>
                  ))}
                  <Button
                    variant="outline"
                    className="text-sm h-10 w-10 flex items-center justify-center"
                    onClick={() => setShowEmojiPicker(false)}
                  >
                    <Plus size={16} />
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
        
        {isSender && (
          <Button 
            variant="destructive" 
            size="sm" 
            onClick={handleDeleteMessage}
            disabled={isDeleting}
            className="flex items-center gap-1"
          >
            <Trash size={16} />
            <span>Delete</span>
          </Button>
        )}
      </div>
      
      {/* Document Content Dialog */}
      <Dialog open={documentDialogOpen} onOpenChange={setDocumentDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>Document Content</DialogTitle>
          </DialogHeader>
          
          <div className="flex-1 overflow-auto p-4 bg-gray-50 rounded-md">
            {isLoadingDocument ? (
              <div className="flex items-center justify-center h-full">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-800"></div>
              </div>
            ) : (
              <pre className="text-sm whitespace-pre-wrap font-mono">{documentContent}</pre>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
   
export default MessageDetail;
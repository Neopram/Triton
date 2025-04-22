import React, { useState, useEffect } from 'react';
import { Button } from '../../components/ui/button';
import { Textarea } from '../../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Paperclip, Send, X, Book } from 'lucide-react';
import useMessageStore from '../../store/messageStore';
import { uploadAttachment } from '../../services/api';
import { Badge } from '../../components/ui/badge';

// Assume we have an API call to fetch users
import { api } from '../../services/api';

interface User {
  id: number;
  name: string;
  email: string;
}

interface MessageComposerProps {
  onCancel: () => void;
  onSent: () => void;
  useRag?: boolean;
}

const MessageComposer: React.FC<MessageComposerProps> = ({ onCancel, onSent, useRag = true }) => {
  const [content, setContent] = useState('');
  const [recipientId, setRecipientId] = useState<string>('');
  const [users, setUsers] = useState<User[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const { sendNewMessage } = useMessageStore();
  
  // Fetch users
  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const response = await api.get('/users');
        setUsers(response.data);
      } catch (err) {
        setError('Failed to load users');
        console.error(err);
      }
    };
    
    fetchUsers();
  }, []);
  
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files);
      
      // Check size limits
      const oversizedFiles = newFiles.filter(file => file.size > 10 * 1024 * 1024);
      if (oversizedFiles.length > 0) {
        setError(`Some files exceed the 10MB limit: ${oversizedFiles.map(f => f.name).join(', ')}`);
        return;
      }
      
      setFiles(prev => [...prev, ...newFiles]);
      e.target.value = ''; // Reset input
    }
  };
  
  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };
  
  const handleSend = async () => {
    if (!content.trim()) {
      setError('Message cannot be empty');
      return;
    }
    
    if (!recipientId) {
      setError('Please select a recipient');
      return;
    }
    
    setIsSubmitting(true);
    setError(null);
    
    try {
      // Send message with RAG preference
      const messageId = await sendNewMessage(content, parseInt(recipientId, 10), useRag, files);
      
      // In the updated version, we're including files directly in sendNewMessage
      // instead of uploading them separately afterwards
      
      setContent('');
      setFiles([]);
      setIsSubmitting(false);
      onSent();
    } catch (err) {
      setError('Failed to send message');
      setIsSubmitting(false);
      console.error(err);
    }
  };
  
  return (
    <div className="flex-1 flex flex-col p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium">New Message</h3>
        <Button variant="ghost" size="sm" onClick={onCancel}>
          <X size={18} />
        </Button>
      </div>
      
      {error && (
        <div className="bg-red-50 text-red-700 p-3 mb-4 rounded text-sm">
          {error}
        </div>
      )}
      
      <div className="mb-4">
        <label className="block text-sm font-medium mb-1">To:</label>
        <Select value={recipientId} onValueChange={setRecipientId}>
          <SelectTrigger>
            <SelectValue placeholder="Select recipient" />
          </SelectTrigger>
          <SelectContent>
            {users.map(user => (
              <SelectItem key={user.id} value={user.id.toString()}>
                {user.name} ({user.email})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      
      <div className="mb-4 flex-1">
        <div className="flex items-center justify-between mb-1">
          <label className="block text-sm font-medium">Message:</label>
          {useRag && (
            <div className="flex items-center">
              <Book className="h-4 w-4 text-blue-600 mr-1" />
              <Badge variant="outline" className="text-xs">
                Knowledge Enhanced
              </Badge>
            </div>
          )}
        </div>
        <Textarea
          value={content}
          onChange={e => setContent(e.target.value)}
          placeholder={
            useRag
              ? "Type your message here... (Knowledge Base will automatically enhance your message)"
              : "Type your message here..."
          }
          className="resize-none h-64"
        />
      </div>
      
      {files.length > 0 && (
        <div className="mb-4">
          <label className="block text-sm font-medium mb-2">Attachments:</label>
          <div className="space-y-2">
            {files.map((file, index) => (
              <div key={index} className="flex items-center justify-between bg-gray-50 p-2 rounded">
                <div className="flex items-center">
                  <Paperclip size={14} className="mr-2 text-gray-500" />
                  <span className="text-sm truncate max-w-xs">{file.name}</span>
                  <span className="text-xs text-gray-500 ml-2">
                    ({(file.size / 1024).toFixed(0)} KB)
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeFile(index)}
                  className="text-gray-500 hover:text-red-500"
                >
                  <X size={14} />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}
      
      <div className="flex justify-between items-center mt-auto pt-4 border-t">
        <div>
          <Button variant="outline" size="sm" asChild>
            <label className="cursor-pointer">
              <Paperclip size={16} className="mr-2" />
              <span>Attach Files</span>
              <input
                type="file"
                multiple
                onChange={handleFileChange}
                className="hidden"
              />
            </label>
          </Button>
        </div>
        
        <div className="flex gap-2">
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button 
            onClick={handleSend} 
            disabled={isSubmitting || !content.trim() || !recipientId}
            className="flex items-center gap-2"
          >
            <Send size={16} />
            Send
          </Button>
        </div>
      </div>
    </div>
  );
};

export default MessageComposer;
import React, { useEffect, useState } from 'react';
import useMessageStore from '../../store/messageStore';
import useAuthStore from '../../store/authStore';
import MessageItem from '../../components/MessageItem';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Button } from '../../components/ui/button';
import MessageComposer from './MessageComposer';
import MessageDetail from './MessageDetail';
import { Inbox, Send, Plus, Loader, Book } from 'lucide-react';
import { Switch } from '../../components/ui/switch';
import { Label } from '../../components/ui/label';

const MessagingPanel: React.FC = () => {
  const { user } = useAuthStore();
  const { 
    inbox, 
    sent, 
    currentMessage, 
    loading, 
    error, 
    fetchInbox, 
    fetchSent, 
    fetchMessage, 
    clearCurrentMessage 
  } = useMessageStore();
  
  const [activeTab, setActiveTab] = useState('inbox');
  const [composingNew, setComposingNew] = useState(false);
  const [enableRag, setEnableRag] = useState<boolean>(true);
  
  // Fetch messages on mount and when tab changes
  useEffect(() => {
    if (activeTab === 'inbox') {
      fetchInbox();
    } else if (activeTab === 'sent') {
      fetchSent();
    }
  }, [activeTab, fetchInbox, fetchSent]);
  
  const handleSelectMessage = (id: number) => {
    fetchMessage(id);
  };
  
  const handleBack = () => {
    clearCurrentMessage();
  };
  
  const handleNewMessage = () => {
    clearCurrentMessage();
    setComposingNew(true);
  };
  
  const handleMessageSent = () => {
    setComposingNew(false);
    fetchSent();
  };
  
  if (!user) {
    return <div className="p-8 text-center">Please log in to use messaging</div>;
  }
  
  return (
    <div className="bg-white rounded-lg shadow-md h-full flex flex-col">
      <div className="p-4 border-b flex items-center justify-between">
        <h2 className="text-xl font-semibold">Messaging</h2>
        <Button onClick={handleNewMessage} className="flex items-center gap-2">
          <Plus size={16} />
          New Message
        </Button>
      </div>
      
      {error && (
        <div className="bg-red-50 text-red-700 p-3 text-sm">
          Error: {error}
        </div>
      )}
      
      {loading && !currentMessage && !composingNew ? (
        <div className="flex-1 flex items-center justify-center">
          <Loader className="animate-spin text-gray-500" size={32} />
        </div>
      ) : composingNew ? (
        <div className="flex-1 flex flex-col">
          <div className="p-4 border-b flex items-center justify-between">
            <h3 className="font-medium">New Message</h3>
            <div className="flex items-center space-x-2">
              <Switch
                id="rag-toggle"
                checked={enableRag}
                onCheckedChange={setEnableRag}
              />
              <Label htmlFor="rag-toggle" className="flex items-center cursor-pointer">
                <Book className="h-4 w-4 mr-1 text-blue-600" />
                Use Knowledge Base
              </Label>
            </div>
          </div>
          <MessageComposer 
            onCancel={() => setComposingNew(false)} 
            onSent={handleMessageSent}
            useRag={enableRag}
          />
        </div>
      ) : currentMessage ? (
        <MessageDetail message={currentMessage} onBack={handleBack} />
      ) : (
        <div className="flex-1 flex flex-col">
          <Tabs defaultValue="inbox" value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="inbox" className="flex items-center gap-2">
                <Inbox size={16} />
                Inbox
              </TabsTrigger>
              <TabsTrigger value="sent" className="flex items-center gap-2">
                <Send size={16} />
                Sent
              </TabsTrigger>
            </TabsList>
            
            <TabsContent value="inbox" className="flex-1 overflow-auto">
              {inbox.length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  Your inbox is empty
                </div>
              ) : (
                inbox.map(message => (
                  <MessageItem
                    key={message.id}
                    id={message.id}
                    content={message.content}
                    senderName={message.sender_name || 'Unknown'}
                    timestamp={message.created_at}
                    isRead={message.is_read}
                    hasAttachments={message.has_attachments}
                    references={message.references || []}
                    onClick={() => handleSelectMessage(message.id)}
                  />
                ))
              )}
            </TabsContent>
            
            <TabsContent value="sent" className="flex-1 overflow-auto">
              {sent.length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  No sent messages
                </div>
              ) : (
                sent.map(message => (
                  <MessageItem
                    key={message.id}
                    id={message.id}
                    content={message.content}
                    senderName={message.recipient?.name || 'Unknown'}
                    timestamp={message.created_at}
                    isRead={message.is_read}
                    hasAttachments={message.has_attachments}
                    references={message.references || []}
                    onClick={() => handleSelectMessage(message.id)}
                  />
                ))
              )}
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  );
};

export default MessagingPanel;
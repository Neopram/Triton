import { create } from 'zustand';
import { 
  getInboxMessages, 
  getSentMessages, 
  getMessageById, 
  sendMessage,
  deleteMessage
} from '../services/api';

interface Reference {
  document_id: string;
  document_title: string;
  chunk_id: string;
  content: string;
  similarity: number;
}

interface Message {
  id: number;
  content: string;
  sender_id: number;
  recipient_id: number;
  is_read: boolean;
  created_at: string;
  read_at?: string;
  sender_name?: string;
  has_attachments: boolean;
  references?: Reference[];
}

interface MessageDetail extends Message {
  sender?: {
    id: number;
    name: string;
    email: string;
  };
  recipient?: {
    id: number;
    name: string;
    email: string;
  };
  attachments: Array<{
    id: number;
    file_name: string;
    file_size: number;
    mime_type: string;
    created_at: string;
  }>;
  reactions: Record<string, number>;
  references?: Reference[];
}

interface MessageStore {
  inbox: Message[];
  sent: Message[];
  currentMessage: MessageDetail | null;
  loading: boolean;
  error: string | null;
  
  fetchInbox: (limit?: number, offset?: number) => Promise<void>;
  fetchSent: (limit?: number, offset?: number) => Promise<void>;
  fetchMessage: (id: number) => Promise<void>;
  sendNewMessage: (content: string, recipientId: number, useRag?: boolean, attachments?: File[]) => Promise<number | null>;
  deleteCurrentMessage: () => Promise<boolean>;
  clearCurrentMessage: () => void;
}

const useMessageStore = create<MessageStore>((set, get) => ({
  inbox: [],
  sent: [],
  currentMessage: null,
  loading: false,
  error: null,
  
  fetchInbox: async (limit = 20, offset = 0) => {
    set({ loading: true, error: null });
    try {
      const response = await getInboxMessages(limit, offset);
      set({ inbox: response.data, loading: false });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to fetch inbox messages', 
        loading: false 
      });
    }
  },
  
  fetchSent: async (limit = 20, offset = 0) => {
    set({ loading: true, error: null });
    try {
      const response = await getSentMessages(limit, offset);
      set({ sent: response.data, loading: false });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to fetch sent messages', 
        loading: false 
      });
    }
  },
  
  fetchMessage: async (id: number) => {
    set({ loading: true, error: null });
    try {
      const response = await getMessageById(id);
      set({ currentMessage: response.data, loading: false });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to fetch message details', 
        loading: false 
      });
    }
  },
  
  sendNewMessage: async (content: string, recipientId: number, useRag = true, attachments = []) => {
    set({ loading: true, error: null });
    try {
      // Create form data for attachments
      const formData = new FormData();
      formData.append('content', content);
      formData.append('recipient_id', recipientId.toString());
      formData.append('use_rag', useRag.toString());
      
      // Add attachments if any
      attachments.forEach(file => {
        formData.append('attachments', file);
      });
      
      const response = await sendMessage(formData);
      
      // Add to sent messages
      set(state => ({ 
        sent: [response.data, ...state.sent],
        loading: false 
      }));
      return response.data.id;
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to send message', 
        loading: false 
      });
      return null;
    }
  },
  
  deleteCurrentMessage: async () => {
    const { currentMessage } = get();
    if (!currentMessage) return false;
    
    set({ loading: true, error: null });
    try {
      await deleteMessage(currentMessage.id);
      // Remove from appropriate list
      set(state => ({
        sent: state.sent.filter(msg => msg.id !== currentMessage.id),
        inbox: state.inbox.filter(msg => msg.id !== currentMessage.id),
        currentMessage: null,
        loading: false
      }));
      return true;
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to delete message', 
        loading: false 
      });
      return false;
    }
  },
  
  clearCurrentMessage: () => {
    set({ currentMessage: null });
  }
}));

export default useMessageStore;
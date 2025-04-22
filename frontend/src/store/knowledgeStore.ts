import { create } from 'zustand';
import { api } from '../services/api';

export interface KnowledgeDocument {
  id: string;
  title: string;
  filename: string;
  file_type: string;
  upload_date: string;
  size_kb: number;
  status: 'processing' | 'indexed' | 'failed';
  chunks_count?: number;
  error_message?: string;
}

export interface KnowledgeStats {
  total_documents: number;
  total_chunks: number;
  index_size_mb: number;
  last_updated: string;
}

interface KnowledgeStore {
  // State
  documents: KnowledgeDocument[];
  stats: KnowledgeStats | null;
  isLoading: boolean;
  error: string | null;
  searchQuery: string;
  filteredDocuments: KnowledgeDocument[];
  
  // Actions
  fetchDocuments: () => Promise<void>;
  fetchStats: () => Promise<void>;
  uploadDocument: (file: File) => Promise<void>;
  deleteDocument: (id: string) => Promise<void>;
  setSearchQuery: (query: string) => void;
  refreshIndex: () => Promise<void>;
}

export const useKnowledgeStore = create<KnowledgeStore>((set, get) => ({
  // Initial state
  documents: [],
  stats: null,
  isLoading: false,
  error: null,
  searchQuery: '',
  filteredDocuments: [],
  
  // Actions
  fetchDocuments: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.get('/api/v1/knowledge/documents');
      const documents = response.data;
      set({ 
        documents,
        filteredDocuments: documents,
        isLoading: false 
      });
    } catch (error) {
      console.error('Error fetching documents:', error);
      set({ 
        error: 'Failed to fetch documents', 
        isLoading: false 
      });
    }
  },
  
  fetchStats: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.get('/api/v1/knowledge/stats');
      set({ 
        stats: response.data,
        isLoading: false 
      });
    } catch (error) {
      console.error('Error fetching knowledge stats:', error);
      set({ 
        error: 'Failed to fetch knowledge stats', 
        isLoading: false 
      });
    }
  },
  
  uploadDocument: async (file: File) => {
    set({ isLoading: true, error: null });
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await api.post('/api/v1/knowledge/documents', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      // Add the new document to the state
      const newDocument = response.data;
      set(state => ({ 
        documents: [...state.documents, newDocument],
        filteredDocuments: [...state.filteredDocuments, newDocument],
        isLoading: false 
      }));
      
      // Refresh stats after upload
      get().fetchStats();
    } catch (error) {
      console.error('Error uploading document:', error);
      set({ 
        error: 'Failed to upload document', 
        isLoading: false 
      });
    }
  },
  
  deleteDocument: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      await api.delete(`/api/v1/knowledge/documents/${id}`);
      
      // Remove the document from the state
      set(state => ({ 
        documents: state.documents.filter(doc => doc.id !== id),
        filteredDocuments: state.filteredDocuments.filter(doc => doc.id !== id),
        isLoading: false 
      }));
      
      // Refresh stats after deletion
      get().fetchStats();
    } catch (error) {
      console.error('Error deleting document:', error);
      set({ 
        error: 'Failed to delete document', 
        isLoading: false 
      });
    }
  },
  
  setSearchQuery: (query: string) => {
    const { documents } = get();
    const filtered = documents.filter(doc => 
      doc.title.toLowerCase().includes(query.toLowerCase()) || 
      doc.filename.toLowerCase().includes(query.toLowerCase())
    );
    
    set({ 
      searchQuery: query,
      filteredDocuments: filtered
    });
  },
  
  refreshIndex: async () => {
    set({ isLoading: true, error: null });
    try {
      await api.post('/api/v1/knowledge/reindex');
      
      // Refresh documents and stats after reindexing
      await get().fetchDocuments();
      await get().fetchStats();
      
      set({ isLoading: false });
    } catch (error) {
      console.error('Error refreshing index:', error);
      set({ 
        error: 'Failed to refresh knowledge index', 
        isLoading: false 
      });
    }
  }
}));
import { api } from './api';
import { KnowledgeDocument, KnowledgeStats } from '../store/knowledgeStore';

interface DocumentSearchResult {
  document_id: string;
  document_title: string;
  chunk_id: string;
  content: string;
  similarity: number;
}

export const knowledgeClient = {
  /**
   * Fetch all knowledge documents
   */
  getDocuments: async (): Promise<KnowledgeDocument[]> => {
    const response = await api.get('/api/v1/knowledge/documents');
    return response.data;
  },

  /**
   * Fetch knowledge base statistics
   */
  getStats: async (): Promise<KnowledgeStats> => {
    const response = await api.get('/api/v1/knowledge/stats');
    return response.data;
  },

  /**
   * Upload a new document to the knowledge base
   */
  uploadDocument: async (file: File): Promise<KnowledgeDocument> => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/api/v1/knowledge/documents', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    
    return response.data;
  },

  /**
   * Delete a document from the knowledge base
   */
  deleteDocument: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/knowledge/documents/${id}`);
  },

  /**
   * Search the knowledge base with a semantic query
   */
  searchKnowledge: async (query: string, limit: number = 5): Promise<DocumentSearchResult[]> => {
    const response = await api.get('/api/v1/knowledge/search', {
      params: {
        query,
        limit
      }
    });
    
    return response.data.results;
  },

  /**
   * Get document content by ID
   */
  getDocumentContent: async (id: string): Promise<string> => {
    const response = await api.get(`/api/v1/knowledge/documents/${id}/content`);
    return response.data.content;
  },

  /**
   * Force reindexing of all documents
   */
  reindexKnowledge: async (): Promise<void> => {
    await api.post('/api/v1/knowledge/reindex');
  },

  /**
   * Update document metadata
   */
  updateDocumentMetadata: async (id: string, metadata: Partial<KnowledgeDocument>): Promise<KnowledgeDocument> => {
    const response = await api.patch(`/api/v1/knowledge/documents/${id}`, metadata);
    return response.data;
  },

  /**
   * Get system embeddings configuration
   */
  getEmbeddingsConfig: async (): Promise<{model: string, dimensions: number}> => {
    const response = await api.get('/api/v1/knowledge/config');
    return response.data;
  },

  /**
   * Update system embeddings configuration
   */
  updateEmbeddingsConfig: async (config: {model: string}): Promise<void> => {
    await api.post('/api/v1/knowledge/config', config);
  }
};
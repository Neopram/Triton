import axios from "axios";

// Get base URL from env or fallback to localhost
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json"
  }
});

// Add auth token from localStorage if available
api.interceptors.request.use(
  (config) => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token");
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Global error handler
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;

    if (status === 401) {
      console.warn("🔐 Unauthorized. Redirecting to login...");
      if (typeof window !== "undefined") {
        localStorage.removeItem("access_token");
        window.location.href = "/login";
      }
    } else if (status >= 500) {
      console.error("💥 Server error:", error.response?.data);
    }

    return Promise.reject(error);
  }
);

export default api;

// Market Insights API methods
export const getMarketInsights = async () => {
  return await api.get('/market/insights');
};

export const getMarketInsightById = async (id: number) => {
  return await api.get(`/market/insights/${id}`);
};

export const getLatestMarketInsight = async () => {
  return await api.get('/market/latest-insight');
};

export const analyzeMarketReport = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  return await api.post('/market/analyze', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};

// Messaging API methods
export const getInboxMessages = async (limit = 20, offset = 0) => {
  return await api.get(`/messages/inbox?limit=${limit}&offset=${offset}`);
};

export const getSentMessages = async (limit = 20, offset = 0) => {
  return await api.get(`/messages/sent?limit=${limit}&offset=${offset}`);
};

export const getMessageById = async (id: number) => {
  return await api.get(`/messages/${id}`);
};

export const sendMessage = async (content: string, recipientId: number) => {
  return await api.post('/messages/', { content, recipient_id: recipientId });
};

export const uploadAttachment = async (messageId: number, file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  return await api.post(`/messages/${messageId}/attachments`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};

export const addReaction = async (messageId: number, emoji: string) => {
  return await api.post(`/messages/${messageId}/reactions`, { emoji });
};

export const removeReaction = async (messageId: number) => {
  return await api.delete(`/messages/${messageId}/reactions`);
};

export const deleteMessage = async (messageId: number) => {
  return await api.delete(`/messages/${messageId}`);
};

export const downloadAttachment = (attachmentId: number) => {
  return `${api.defaults.baseURL}/messages/attachments/${attachmentId}`;
};

// AI Engine Configuration
export const getAIEngineConfig = async () => {
  return await api.get('/config/ai-engine');
};

export const updateAIEngineConfig = async (engine: string) => {
  return await api.post('/config/ai-engine', { engine });
};

// Insight feedback
export const submitInsightFeedback = async (insightId: number, rating: number, feedback?: string) => {
  return await api.post(`/market/insights/${insightId}/feedback`, { 
    rating, 
    feedback 
  });
};

// Insight statistics
export const getInsightStats = async () => {
  return await api.get('/market/insights/stats');
};
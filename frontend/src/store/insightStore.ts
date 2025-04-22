import { create } from 'zustand';
import { 
  getMarketInsights, 
  getMarketInsightById, 
  getLatestMarketInsight,
  analyzeMarketReport
} from '../services/api';

interface MarketInsight {
  id: number;
  insights: string;
  engine_used: string;
  created_at: string;
  user_id: number;
  rating?: number;
  feedback?: string;
}

interface InsightStore {
  insights: MarketInsight[];
  currentInsight: MarketInsight | null;
  latestInsight: MarketInsight | null;
  loading: boolean;
  error: string | null;
  
  fetchInsights: () => Promise<void>;
  fetchInsightById: (id: number) => Promise<void>;
  fetchLatestInsight: () => Promise<void>;
  analyzeReport: (file: File) => Promise<string | null>;
  clearCurrentInsight: () => void;
}

const useInsightStore = create<InsightStore>((set) => ({
  insights: [],
  currentInsight: null,
  latestInsight: null,
  loading: false,
  error: null,
  
  fetchInsights: async () => {
    set({ loading: true, error: null });
    try {
      const response = await getMarketInsights();
      set({ insights: response.data, loading: false });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to fetch insights', 
        loading: false 
      });
    }
  },
  
  fetchInsightById: async (id: number) => {
    set({ loading: true, error: null });
    try {
      const response = await getMarketInsightById(id);
      set({ currentInsight: response.data, loading: false });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to fetch insight details', 
        loading: false 
      });
    }
  },
  
  fetchLatestInsight: async () => {
    set({ loading: true, error: null });
    try {
      const response = await getLatestMarketInsight();
      set({ latestInsight: response.data, loading: false });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to fetch latest insight', 
        loading: false 
      });
    }
  },
  
  analyzeReport: async (file: File) => {
    set({ loading: true, error: null });
    try {
      const response = await analyzeMarketReport(file);
      // Add to insights list when backend returns full object
      set({ loading: false });
      return response.data.insights;
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to analyze report', 
        loading: false 
      });
      return null;
    }
  },
  
  clearCurrentInsight: () => {
    set({ currentInsight: null });
  }
}));

export default useInsightStore;
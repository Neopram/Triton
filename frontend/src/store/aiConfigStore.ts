`import { create } from 'zustand';
import { getAIEngineConfig, updateAIEngineConfig } from '../services/api';

interface AIEngineConfig {
  current_engine: string;
  available_engines: string[];
  is_valid: boolean;
}

interface AIConfigStore {
  config: AIEngineConfig | null;
  loading: boolean;
  error: string | null;
  fetchConfig: () => Promise<void>;
  updateConfig: (engine: string) => Promise<boolean>;
}

const useAIConfigStore = create<AIConfigStore>((set) => ({
  config: null,
  loading: false,
  error: null,

  fetchConfig: async () => {
    set({ loading: true, error: null });
    try {
      const response = await getAIEngineConfig();
      set({ config: response.data, loading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch AI config',
        loading: false,
      });
    }
  },

  updateConfig: async (engine: string) => {
    set({ loading: true, error: null });
    try {
      const response = await updateAIEngineConfig(engine);
      set({ config: response.data, loading: false });
      return true;
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to update AI config',
        loading: false,
      });
      return false;
    }
  },
}));

export default useAIConfigStore;
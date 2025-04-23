// src/store/aiConfigStore.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { aiClient } from '../services/aiClient';

// Tipos para la tienda
interface AIConfigState {
  aiModel: 'cloud' | 'local' | 'hybrid';
  aiStatus: {
    cloud: 'online' | 'offline' | 'loading';
    local: 'online' | 'offline' | 'loading';
  };
  lastStatusCheck: string | null;
  
  // Acciones
  setAIModel: (model: 'cloud' | 'local' | 'hybrid') => void;
  checkAIStatus: () => Promise<void>;
}

// Crear la tienda con persistencia
export const useAiConfigStore = create<AIConfigState>()(
  persist(
    (set, get) => ({
      // Estado inicial
      aiModel: 'hybrid',
      aiStatus: {
        cloud: 'loading',
        local: 'loading'
      },
      lastStatusCheck: null,
      
      // Acción para cambiar el modelo de IA
      setAIModel: (model) => set({ aiModel: model }),
      
      // Acción para verificar el estado de los servicios de IA
      checkAIStatus: async () => {
        try {
          // Marcar como cargando
          set({
            aiStatus: {
              cloud: 'loading',
              local: 'loading'
            }
          });
          
          // Obtener el estado actual
          const status = await aiClient.getStatus();
          
          // Actualizar el estado
          set({
            aiStatus: {
              cloud: status.deepseek,
              local: status.phi3
            },
            lastStatusCheck: new Date().toISOString()
          });
        } catch (error) {
          console.error('Error checking AI status:', error);
          
          // En caso de error, marcar como offline
          set({
            aiStatus: {
              cloud: 'offline',
              local: 'offline'
            },
            lastStatusCheck: new Date().toISOString()
          });
        }
      }
    }),
    {
      name: 'triton-ai-config',
      partialize: (state) => ({ aiModel: state.aiModel })
    }
  )
);

// Verificar estado al cargar
if (typeof window !== 'undefined') {
  setTimeout(() => {
    useAiConfigStore.getState().checkAIStatus();
  }, 1000);
}
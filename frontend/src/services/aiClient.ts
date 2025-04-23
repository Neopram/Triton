// src/services/aiClient.ts
import axios from 'axios';
import { useAiConfigStore } from '../store/aiConfigStore';

// Tipos para las solicitudes y respuestas
export interface AIQueryRequest {
  query: string;
  context?: any;
  model?: 'cloud' | 'local' | 'hybrid';
  taskType?: string;
}

export interface AIQueryResponse {
  success: boolean;
  data: {
    result: string;
    source: string;
    processingTime: number;
    queryId: string;
  };
  error?: string;
}

// Tipos para la consulta de estado
export interface AIStatusResponse {
  deepseek: 'online' | 'offline';
  phi3: 'online' | 'offline';
  mode: 'online' | 'offline';
  lastChecked: string;
}

// Configuración base del cliente
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000/api';

// Cliente de AI mejorado con soporte para DeepSeek y Phi-3
class AIClient {
  // Método principal para consultar a la IA
  async query(query: string, context: any = {}, model?: 'cloud' | 'local' | 'hybrid'): Promise<AIQueryResponse> {
    try {
      // Determinar el modelo a usar
      const aiModel = model || useAiConfigStore.getState().aiModel;
      
      // Determinar el tipo de tarea basado en la consulta
      const taskType = this._determineTaskType(query);
      
      // Crear la solicitud
      const request: AIQueryRequest = {
        query,
        context,
        model: aiModel,
        taskType
      };
      
      // Realizar la llamada a la API
      const response = await axios.post(`${API_URL}/ai/query`, request);
      
      return response.data;
    } catch (error: any) {
      console.error('Error querying AI:', error);
      
      // Manejar el error y devolver una respuesta estructurada
      return {
        success: false,
        data: {
          result: 'Error processing your request. Please try again.',
          source: 'error',
          processingTime: 0,
          queryId: '0'
        },
        error: error.message || 'Unknown error'
      };
    }
  }
  
  // Método para optimizar rutas
  async optimizeRoute(vesselId: string, origin: any, destination: any, preferences: any = {}): Promise<any> {
    try {
      const response = await axios.post(`${API_URL}/ai/optimize-route`, {
        vesselId,
        origin,
        destination,
        preferences
      });
      
      return response.data;
    } catch (error: any) {
      console.error('Error optimizing route:', error);
      throw new Error(error.message || 'Failed to optimize route');
    }
  }
  
  // Método para analizar condiciones meteorológicas
  async analyzeWeather(location: any, context: any = {}): Promise<any> {
    try {
      const response = await axios.post(`${API_URL}/ai/analyze-weather`, {
        location,
        context
      });
      
      return response.data;
    } catch (error: any) {
      console.error('Error analyzing weather:', error);
      throw new Error(error.message || 'Failed to analyze weather conditions');
    }
  }
  
  // Método para predecir ETA
  async predictEta(vesselId: string, origin: any, destination: any): Promise<any> {
    try {
      const response = await axios.post(`${API_URL}/ai/predict-eta`, {
        vesselId,
        origin,
        destination
      });
      
      return response.data;
    } catch (error: any) {
      console.error('Error predicting ETA:', error);
      throw new Error(error.message || 'Failed to predict ETA');
    }
  }
  
  // Método para obtener el estado de los servicios de IA
  async getStatus(): Promise<AIStatusResponse> {
    try {
      const response = await axios.get(`${API_URL}/ai/status`);
      return response.data.data;
    } catch (error) {
      console.error('Error getting AI status:', error);
      // Estado por defecto en caso de error
      return {
        deepseek: 'offline',
        phi3: 'offline',
        mode: 'offline',
        lastChecked: new Date().toISOString()
      };
    }
  }
  
  // Método para enviar retroalimentación sobre respuestas de IA
  async submitFeedback(queryId: string, rating: number, feedback?: string): Promise<any> {
    try {
      const response = await axios.post(`${API_URL}/ai/feedback`, {
        queryId,
        rating,
        feedback
      });
      
      return response.data;
    } catch (error) {
      console.error('Error submitting feedback:', error);
      throw new Error('Failed to submit feedback');
    }
  }
  
  // Método privado para determinar el tipo de tarea basado en la consulta
  private _determineTaskType(query: string): string {
    const queryLower = query.toLowerCase();
    
    // Clasificar la consulta en diferentes tipos de tareas
    if (queryLower.includes('route') || queryLower.includes('path') || queryLower.includes('journey')) {
      return 'routeOptimization';
    }
    
    if (queryLower.includes('weather') || queryLower.includes('storm') || queryLower.includes('wind') || queryLower.includes('waves')) {
      return 'weatherAnalysis';
    }
    
    if (queryLower.includes('eta') || queryLower.includes('arrival') || queryLower.includes('when will') || queryLower.includes('time to')) {
      return 'etaPrediction';
    }
    
    if (queryLower.includes('port') || queryLower.includes('dock') || queryLower.includes('terminal')) {
      return 'portOperations';
    }
    
    if (queryLower.includes('vessel') || queryLower.includes('ship') || queryLower.includes('fleet') || queryLower.includes('track')) {
      return 'vesselTracking';
    }
    
    if (queryLower.includes('emergency') || queryLower.includes('danger') || queryLower.includes('urgent') || queryLower.includes('safety')) {
      return 'criticalSafety';
    }
    
    // Consulta general por defecto
    return 'basicQueries';
  }
}

// Exportar una instancia única del cliente
export const aiClient = new AIClient();
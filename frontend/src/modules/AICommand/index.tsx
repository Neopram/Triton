// src/modules/AICommand/index.tsx
import React, { useState, useRef, useEffect } from 'react';
import { useAiConfigStore } from '../../store/aiConfigStore';
import { aiClient } from '../../services/aiClient';
import { Brain, CornerDownLeft, Cloud, Cpu, RefreshCw } from 'lucide-react';

// Componente para los mensajes
interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'error';
  content: string;
  timestamp: string;
  source?: string;
  processingTime?: number;
}

const MessageBubble: React.FC<{message: Message}> = ({ message }) => {
  return (
    <div className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} mb-4`}>
      <div 
        className={`max-w-[75%] rounded-lg p-4 ${
          message.role === 'user' 
            ? 'bg-blue-600 text-white rounded-tr-none' 
            : message.role === 'error'
              ? 'bg-red-100 text-red-800 rounded-tl-none'
              : 'bg-gray-100 text-gray-800 rounded-tl-none'
        }`}
      >
        <div className="whitespace-pre-wrap">{message.content}</div>
        
        {message.source && (
          <div className="text-xs mt-2 opacity-75 flex items-center justify-between">
            <span>Source: {message.source}</span>
            {message.processingTime && (
              <span>{message.processingTime.toFixed(2)}s</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

const AICommand: React.FC = () => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'system',
      content: 'Welcome to Triton AI Command Center. How can I assist you with maritime operations today?',
      timestamp: new Date().toISOString()
    }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  
  const { aiModel, aiStatus, setAIModel, checkAIStatus } = useAiConfigStore();
  
  // Auto-scroll al final de los mensajes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);
  
  // Manejar envío de mensajes
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!input.trim() || isLoading) return;
    
    // Añadir mensaje del usuario
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date().toISOString()
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    
    try {
      // Crear contexto para la consulta
      const context = {
        // Aquí podrías añadir contexto, como la embarcación seleccionada,
        // datos meteorológicos, etc.
      };
      
      // Consultar a la IA
      const response = await aiClient.query(input, context, aiModel);
      
      if (response.success) {
        // Añadir respuesta de la IA
        const aiMessage: Message = {
          id: Date.now().toString(),
          role: 'assistant',
          content: response.data.result,
          timestamp: new Date().toISOString(),
          source: response.data.source,
          processingTime: response.data.processingTime
        };
        
        setMessages(prev => [...prev, aiMessage]);
      } else {
        // Añadir mensaje de error
        const errorMessage: Message = {
          id: Date.now().toString(),
          role: 'error',
          content: response.error || 'Error processing your request. Please try again.',
          timestamp: new Date().toISOString()
        };
        
        setMessages(prev => [...prev, errorMessage]);
      }
    } catch (error) {
      console.error('Error querying AI:', error);
      
      // Añadir mensaje de error
      const errorMessage: Message = {
        id: Date.now().toString(),
        role: 'error',
        content: 'Failed to communicate with AI services. Please check your connection and try again.',
        timestamp: new Date().toISOString()
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      
      // Enfocar el input
      setTimeout(() => {
        inputRef.current?.focus();
      }, 100);
    }
  };
  
  // Manejar tecla Enter para enviar
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  };
  
  return (
    <div className="flex flex-col h-[calc(100vh-200px)]">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold flex items-center">
          <Brain className="mr-2" /> AI Command Center
        </h1>
        
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-1">
            <button
              onClick={() => checkAIStatus()}
              className="p-1 rounded-full hover:bg-gray-200 transition"
              title="Refresh AI Status"
            >
              <RefreshCw size={14} />
            </button>
            <div className="flex items-center">
              <div className={`w-2 h-2 rounded-full mr-1 ${
                aiStatus.cloud === 'online' ? 'bg-green-500' : 
                aiStatus.cloud === 'loading' ? 'bg-amber-500 animate-pulse' : 'bg-red-500'
              }`}></div>
              <span className="text-xs">DeepSeek</span>
            </div>
          </div>
          
          <div className="flex items-center">
            <div className={`w-2 h-2 rounded-full mr-1 ${
              aiStatus.local === 'online' ? 'bg-green-500' : 
              aiStatus.local === 'loading' ? 'bg-amber-500 animate-pulse' : 'bg-red-500'
            }`}></div>
            <span className="text-xs">Phi-3</span>
          </div>
          
          <select
            value={aiModel}
            onChange={(e) => setAIModel(e.target.value as any)}
            className="text-sm border rounded px-2 py-1"
          >
            <option value="hybrid">Hybrid</option>
            <option value="cloud">DeepSeek Cloud</option>
            <option value="local">Phi-3 Local</option>
          </select>
        </div>
      </div>
      
      <div className="flex-1 bg-white rounded-t-lg shadow overflow-hidden flex flex-col">
        {/* Mensajes */}
        <div className="flex-1 overflow-y-auto p-4">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          
          {isLoading && (
            <div className="flex justify-start mb-4">
              <div className="bg-gray-100 text-gray-500 rounded-lg rounded-tl-none p-4 max-w-[75%]">
                <div className="flex space-x-2">
                  <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce"></div>
                  <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
        
        {/* Entrada de texto */}
        <form onSubmit={handleSubmit} className="border-t p-4">
          <div className="flex">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask Triton AI about maritime operations, routes, or vessel management..."
              className="flex-1 border rounded-l-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              rows={1}
              disabled={isLoading}
            ></textarea>
            <button
              type="submit"
              className="bg-blue-600 text-white px-4 rounded-r-lg hover:bg-blue-700 flex items-center justify-center disabled:bg-blue-300"
              disabled={!input.trim() || isLoading}
            >
              <CornerDownLeft size={18} />
            </button>
          </div>
          
          <div className="flex justify-between mt-2 text-xs text-gray-500">
            <div>
              {aiModel === 'hybrid' && (
                <div className="flex items-center">
                  <Cloud size={12} className="mr-1" />
                  <Cpu size={12} className="mr-1" />
                  <span>Using hybrid model (DeepSeek + Phi-3)</span>
                </div>
              )}
              
              {aiModel === 'cloud' && (
                <div className="flex items-center">
                  <Cloud size={12} className="mr-1" />
                  <span>Using DeepSeek cloud model</span>
                </div>
              )}
              
              {aiModel === 'local' && (
                <div className="flex items-center">
                  <Cpu size={12} className="mr-1" />
                  <span>Using Phi-3 local model</span>
                </div>
              )}
            </div>
            
            <div>
              <button
                type="button"
                onClick={() => setMessages([{
                  id: Date.now().toString(),
                  role: 'system',
                  content: 'Conversation cleared. How can I assist you with maritime operations today?',
                  timestamp: new Date().toISOString()
                }])}
                className="text-gray-500 hover:text-gray-700"
              >
                Clear conversation
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AICommand;
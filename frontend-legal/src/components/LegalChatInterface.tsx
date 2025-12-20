'use client';

import React, { useState, useRef, useEffect } from 'react';
import { apiClient } from '@/services/api';
import type { ChatResponse, ApiError, LegalSource } from '@/types/api';
import ReactMarkdown from 'react-markdown';
import SourceCard from './SourceCard';
import LoadingSkeleton from './LoadingSkeleton';
import ErrorMessage from './ErrorMessage';

interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  sources?: LegalSource[];
  timestamp: Date;
}

export default function LegalChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId] = useState(() => crypto.randomUUID());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!inputValue.trim()) return;
    if (isLoading) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      type: 'user',
      content: inputValue.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);
    setError(null);

    try {
      const response: ChatResponse = await apiClient.chat(
        userMessage.content,
        sessionId
      );

      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        type: 'assistant',
        content: response.answer,
        sources: response.sources,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const apiError = err as ApiError;
      const errorMsg = apiError.detail || apiError.error || 'Error al procesar tu consulta';
      setError(errorMsg);

      // Add error message to chat
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        type: 'assistant',
        content: `Lo siento, ocurrió un error: ${errorMsg}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
    setError(null);
  };

  return (
    <div className="flex flex-col h-screen max-w-5xl mx-auto bg-white">
      {/* Header */}
      <header className="bg-gradient-to-r from-blue-600 to-blue-800 text-white px-6 py-4 shadow-lg">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold">Legal GraphRAG</h1>
            <p className="text-sm text-blue-100">Consultas legales para artistas</p>
          </div>
          {messages.length > 0 && (
            <button
              onClick={clearChat}
              className="px-4 py-2 bg-blue-700 hover:bg-blue-600 rounded-lg transition-colors text-sm font-medium"
            >
              Nueva consulta
            </button>
          )}
        </div>
      </header>

      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto px-6 py-8 space-y-6">
        {messages.length === 0 && (
          <div className="text-center py-12">
            <div className="max-w-2xl mx-auto">
              <h2 className="text-2xl font-semibold text-gray-800 mb-4">
                Bienvenido al asistente legal para artistas
              </h2>
              <p className="text-gray-600 mb-8">
                Haz preguntas sobre normativa fiscal, derechos de autor, contratos y más.
                Las respuestas están basadas en fuentes oficiales del BOE y EUR-Lex.
              </p>
              <div className="grid md:grid-cols-2 gap-4 text-left">
                <div className="p-4 bg-blue-50 rounded-lg">
                  <h3 className="font-semibold text-blue-900 mb-2">Ejemplo 1</h3>
                  <p className="text-sm text-gray-700">
                    ¿Puedo deducir los gastos de mi home studio?
                  </p>
                </div>
                <div className="p-4 bg-blue-50 rounded-lg">
                  <h3 className="font-semibold text-blue-900 mb-2">Ejemplo 2</h3>
                  <p className="text-sm text-gray-700">
                    ¿Cuánto dura la protección de derechos de autor?
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-3xl ${
                message.type === 'user'
                  ? 'bg-blue-600 text-white rounded-2xl rounded-tr-sm'
                  : 'bg-gray-100 text-gray-900 rounded-2xl rounded-tl-sm'
              } px-6 py-4 shadow-md`}
            >
              {message.type === 'user' ? (
                <p className="text-sm md:text-base">{message.content}</p>
              ) : (
                <>
                  <div className="prose prose-sm md:prose-base max-w-none">
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  </div>

                  {message.sources && message.sources.length > 0 && (
                    <div className="mt-6 pt-4 border-t border-gray-300">
                      <h4 className="font-semibold text-sm text-gray-700 mb-3">
                        Fuentes legales ({message.sources.length})
                      </h4>
                      <div className="space-y-2">
                        {message.sources.map((source, idx) => (
                          <SourceCard key={`${source.id || 'source'}-${idx}`} source={source} />
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}

              <div className={`text-xs mt-2 ${message.type === 'user' ? 'text-blue-100' : 'text-gray-500'}`}>
                {message.timestamp.toLocaleTimeString('es-ES', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="max-w-3xl">
              <LoadingSkeleton />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Error Display */}
      {error && (
        <div className="px-6 pb-2">
          <ErrorMessage message={error} onDismiss={() => setError(null)} />
        </div>
      )}

      {/* Input Form */}
      <div className="border-t border-gray-200 bg-gray-50 px-6 py-4">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
          <div className="flex gap-3">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Escribe tu consulta legal aquí..."
              disabled={isLoading}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
              maxLength={500}
            />
            <button
              type="submit"
              disabled={isLoading || !inputValue.trim()}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? 'Consultando...' : 'Enviar'}
            </button>
          </div>
          <div className="mt-2 text-xs text-gray-500 text-right">
            {inputValue.length}/500 caracteres
          </div>
        </form>
      </div>
    </div>
  );
}

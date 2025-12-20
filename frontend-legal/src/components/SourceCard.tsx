'use client';

import React, { useState } from 'react';
import type { LegalSource } from '@/types/api';

interface SourceCardProps {
  source: LegalSource;
}

export default function SourceCard({ source }: SourceCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const getSourceTypeColor = (type: string): string => {
    const typeMap: Record<string, string> = {
      BOE: 'bg-blue-100 text-blue-800',
      'EUR-Lex': 'bg-yellow-100 text-yellow-800',
      DGT: 'bg-green-100 text-green-800',
      default: 'bg-gray-100 text-gray-800',
    };
    return typeMap[type] || typeMap.default;
  };

  const formatSourceType = (type: string): string => {
    const typeNames: Record<string, string> = {
      BOE: 'Boletín Oficial del Estado',
      'EUR-Lex': 'Diario Oficial de la Unión Europea',
      DGT: 'Dirección General de Tributos',
    };
    return typeNames[type] || type;
  };

  return (
    <div className="border border-gray-300 rounded-lg overflow-hidden hover:shadow-md transition-shadow">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-start justify-between bg-white hover:bg-gray-50 transition-colors text-left"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`px-2 py-1 text-xs font-medium rounded ${getSourceTypeColor(
                source.source_type
              )}`}
            >
              {source.source_type}
            </span>
            {source.relevance_score !== undefined && (
              <span className="text-xs text-gray-500">
                Relevancia: {(source.relevance_score * 100).toFixed(0)}%
              </span>
            )}
          </div>
          <h5 className="font-medium text-sm text-gray-900 line-clamp-2">
            {source.title}
          </h5>
        </div>
        <svg
          className={`ml-3 w-5 h-5 text-gray-500 transition-transform flex-shrink-0 ${
            isExpanded ? 'rotate-180' : ''
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {isExpanded && (
        <div className="px-4 py-3 bg-gray-50 border-t border-gray-200 space-y-3">
          <div>
            <p className="text-xs font-semibold text-gray-700 mb-1">Tipo de fuente:</p>
            <p className="text-sm text-gray-600">{formatSourceType(source.source_type)}</p>
          </div>

          {source.excerpt && (
            <div>
              <p className="text-xs font-semibold text-gray-700 mb-1">Extracto relevante:</p>
              <p className="text-sm text-gray-600 italic">{source.excerpt}</p>
            </div>
          )}

          <div>
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 font-medium"
            >
              Ver documento completo
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                />
              </svg>
            </a>
          </div>

          <div className="pt-2 border-t border-gray-200">
            <p className="text-xs text-gray-500">ID: {source.id}</p>
          </div>
        </div>
      )}
    </div>
  );
}
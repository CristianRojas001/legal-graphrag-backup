'use client';

import React, { useState } from 'react';
import type { LegalSource } from '@/types/api';

interface SourceCardProps {
  source: LegalSource;
  isCited?: boolean;
}

export default function SourceCard({ source, isCited = false }: SourceCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const getSourceTypeColor = (type: string): string => {
    const typeMap: Record<string, string> = {
      BOE: 'bg-primary/10 text-primary',
      'EUR-Lex': 'bg-secondary text-secondary-foreground',
      DGT: 'bg-emerald-100 text-emerald-800',
      default: 'bg-muted text-muted-foreground',
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
    <div
      className={`border-2 rounded-[3px] overflow-hidden shadow-soft hover:shadow-medium transition-all ${
        isCited ? 'border-primary bg-primary/5' : 'border-border bg-card'
      }`}
    >
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={`w-full px-5 py-4 flex items-start justify-between transition-colors text-left ${
          isCited ? 'bg-primary/5 hover:bg-primary/10' : 'bg-card hover:bg-muted/30'
        }`}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            {isCited && (
              <span className="px-3 py-1 text-xs font-bold bg-primary text-primary-foreground rounded-[3px] uppercase tracking-[0.5px]">
                Citada
              </span>
            )}
            <span
              className={`px-3 py-1 text-xs font-bold rounded-[3px] uppercase tracking-[0.5px] ${getSourceTypeColor(
                source.source_type
              )}`}
            >
              {source.source_type}
            </span>
            {source.relevance_score !== undefined && (
              <span className="text-xs text-muted-foreground">
                Relevancia: {(source.relevance_score * 100).toFixed(0)}%
              </span>
            )}
          </div>
          <h5 className="font-bold text-sm text-foreground line-clamp-2 tracking-normal normal-case">
            {source.title}
          </h5>
        </div>
        <svg
          className={`ml-3 w-5 h-5 text-muted-foreground transition-transform flex-shrink-0 ${
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
        <div
          className={`px-5 py-4 border-t-2 border-border space-y-4 ${
            isCited ? 'bg-primary/5' : 'bg-muted/20'
          }`}
        >
          <div>
            <p className="text-xs font-bold text-muted-foreground mb-2 uppercase tracking-[0.5px]">Tipo de fuente:</p>
            <p className="text-sm text-foreground normal-case tracking-normal font-normal">{formatSourceType(source.source_type)}</p>
          </div>

          {source.excerpt && (
            <div>
              <p className="text-xs font-bold text-muted-foreground mb-2 uppercase tracking-[0.5px]">Extracto relevante:</p>
              <p className="text-sm text-foreground italic normal-case tracking-normal font-normal">{source.excerpt}</p>
            </div>
          )}

          <div>
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-sm text-secondary hover:text-primary font-bold transition-colors normal-case tracking-normal"
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

          <div className="pt-3 border-t-2 border-border">
            <p className="text-xs text-muted-foreground normal-case tracking-normal font-normal">ID: {source.id}</p>
          </div>
        </div>
      )}
    </div>
  );
}

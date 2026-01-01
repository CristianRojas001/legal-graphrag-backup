'use client';

import React from 'react';

interface ErrorMessageProps {
  message: string;
  onDismiss?: () => void;
}

export default function ErrorMessage({ message, onDismiss }: ErrorMessageProps) {
  return (
    <div className="bg-destructive/10 border-2 border-destructive/40 rounded-[3px] px-5 py-4 flex items-start justify-between shadow-soft">
      <div className="flex items-start gap-4">
        <svg
          className="w-6 h-6 text-destructive flex-shrink-0 mt-0.5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <div>
          <h4 className="text-sm font-bold text-foreground uppercase tracking-[0.5px]">Error</h4>
          <p className="text-sm text-foreground/80 mt-2 normal-case tracking-normal font-normal">{message}</p>
        </div>
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-destructive hover:text-destructive/80 ml-4 transition-colors"
          aria-label="Cerrar error"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      )}
    </div>
  );
}

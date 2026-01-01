'use client';

import React from 'react';

export default function LoadingSkeleton() {
  return (
    <div className="bg-card rounded-[3px] px-8 py-5 shadow-soft max-w-3xl w-full animate-pulse border-2 border-border">
      {/* Text lines skeleton */}
      <div className="space-y-4">
        <div className="h-4 bg-muted rounded-[3px] w-full"></div>
        <div className="h-4 bg-muted rounded-[3px] w-11/12"></div>
        <div className="h-4 bg-muted rounded-[3px] w-10/12"></div>
        <div className="h-4 bg-muted rounded-[3px] w-9/12"></div>
      </div>

      {/* Sources skeleton */}
      <div className="mt-8 pt-4 border-t-2 border-border">
        <div className="h-4 bg-muted rounded-[3px] w-40 mb-4"></div>
        <div className="space-y-3">
          <div className="h-20 bg-muted/70 rounded-[3px]"></div>
          <div className="h-20 bg-muted/70 rounded-[3px]"></div>
        </div>
      </div>

      {/* Pulsing indicator - Artisting gold */}
      <div className="flex items-center gap-3 mt-6">
        <div className="flex gap-1.5">
          <div className="w-2.5 h-2.5 bg-primary rounded-full animate-bounce"></div>
          <div className="w-2.5 h-2.5 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
          <div className="w-2.5 h-2.5 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
        </div>
        <span className="text-xs text-muted-foreground normal-case tracking-normal font-normal">Consultando fuentes legales...</span>
      </div>
    </div>
  );
}

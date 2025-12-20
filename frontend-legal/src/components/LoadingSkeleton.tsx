'use client';

import React from 'react';

export default function LoadingSkeleton() {
  return (
    <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-6 py-4 shadow-md max-w-3xl animate-pulse">
      {/* Text lines skeleton */}
      <div className="space-y-3">
        <div className="h-4 bg-gray-300 rounded w-full"></div>
        <div className="h-4 bg-gray-300 rounded w-11/12"></div>
        <div className="h-4 bg-gray-300 rounded w-10/12"></div>
        <div className="h-4 bg-gray-300 rounded w-9/12"></div>
      </div>

      {/* Sources skeleton */}
      <div className="mt-6 pt-4 border-t border-gray-300">
        <div className="h-4 bg-gray-300 rounded w-32 mb-3"></div>
        <div className="space-y-2">
          <div className="h-16 bg-gray-200 rounded-lg"></div>
          <div className="h-16 bg-gray-200 rounded-lg"></div>
        </div>
      </div>

      {/* Pulsing indicator */}
      <div className="flex items-center gap-2 mt-4">
        <div className="flex gap-1">
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
        </div>
        <span className="text-xs text-gray-500">Consultando fuentes legales...</span>
      </div>
    </div>
  );
}
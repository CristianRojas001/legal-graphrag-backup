'use client';

import React, { useState } from 'react';

export default function LegalDisclaimer() {
  const [isVisible, setIsVisible] = useState(true);

  if (!isVisible) return null;

  return (
    <div className="bg-amber-50 border-l-4 border-amber-400 px-6 py-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <svg
            className="w-6 h-6 text-amber-600 flex-shrink-0 mt-0.5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <div>
            <h3 className="text-sm font-semibold text-amber-900 mb-1">
              Aviso Legal Importante
            </h3>
            <div className="text-sm text-amber-800 space-y-2">
              <p>
                Este sistema proporciona información legal basada en fuentes oficiales (BOE, EUR-Lex)
                con fines informativos únicamente.
              </p>
              <p>
                <strong>No constituye asesoramiento legal profesional.</strong> Para decisiones legales
                importantes, consulte siempre con un abogado o asesor fiscal cualificado.
              </p>
              <p className="text-xs">
                Las respuestas se generan mediante inteligencia artificial y pueden contener errores
                o no reflejar cambios normativos recientes. Verifique siempre la información en las
                fuentes oficiales proporcionadas.
              </p>
            </div>
          </div>
        </div>
        <button
          onClick={() => setIsVisible(false)}
          className="text-amber-600 hover:text-amber-800 flex-shrink-0"
          aria-label="Cerrar aviso"
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
      </div>
    </div>
  );
}
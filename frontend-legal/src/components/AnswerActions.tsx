'use client';

import React, { useState } from 'react';
import { apiClient } from '@/services/api';

type VoteValue = 1 | -1 | 0;

interface AnswerActionsProps {
  conversationId?: string;
  sessionId?: string;
  messageId?: string;
  answerText: string;
}

export default function AnswerActions({
  conversationId,
  sessionId,
  messageId,
  answerText,
}: AnswerActionsProps) {
  const [vote, setVote] = useState<VoteValue>(0);
  const [voteLocked, setVoteLocked] = useState(false);
  const [pendingVote, setPendingVote] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleVote = async (value: 1 | -1) => {
    if (!messageId || pendingVote || voteLocked) return;
    setPendingVote(true);
    setVote(value);
    setVoteLocked(true);
    try {
      await apiClient.sendFeedback({
        conversation_id: conversationId,
        session_id: sessionId,
        message_id: messageId,
        event_type: 'vote',
        vote_value: value,
        answer_text: answerText,
      });
    } catch {
      setVote(0);
      setVoteLocked(false);
    } finally {
      setPendingVote(false);
    }
  };

  const handleCopy = async () => {
    if (!answerText) return;
    try {
      await navigator.clipboard.writeText(answerText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      return;
    }
    if (!messageId) return;
    try {
      await apiClient.sendFeedback({
        conversation_id: conversationId,
        session_id: sessionId,
        message_id: messageId,
        event_type: 'copy',
        answer_text: answerText,
      });
    } catch {
      // Ignore errors for copy tracking.
    }
  };

  return (
    <div className="mt-3 flex items-center justify-end gap-2 text-xs text-muted-foreground">
      <button
        type="button"
        onClick={() => handleVote(1)}
        disabled={voteLocked || pendingVote}
        className={`px-2 py-1 rounded border transition-colors ${
          vote === 1
            ? 'border-primary bg-primary/10 text-foreground'
            : 'border-border hover:border-primary/60'
        } ${voteLocked ? 'opacity-60 cursor-default' : ''}`}
        aria-label="Voto positivo"
      >
        👍
      </button>
      <button
        type="button"
        onClick={() => handleVote(-1)}
        disabled={voteLocked || pendingVote}
        className={`px-2 py-1 rounded border transition-colors ${
          vote === -1
            ? 'border-primary bg-primary/10 text-foreground'
            : 'border-border hover:border-primary/60'
        } ${voteLocked ? 'opacity-60 cursor-default' : ''}`}
        aria-label="Voto negativo"
      >
        👎
      </button>
      <button
        type="button"
        onClick={handleCopy}
        className="flex items-center gap-1 px-2 py-1 rounded border border-border hover:border-primary/60 transition-colors"
        aria-label="Copiar respuesta"
      >
        {copied ? (
          <span className="text-foreground">Copiado</span>
        ) : (
          <>
            <span
              aria-hidden="true"
              className="inline-flex h-3.5 w-3.5 items-center justify-center"
            >
              ⧉
            </span>
            Copiar
          </>
        )}
      </button>
    </div>
  );
}

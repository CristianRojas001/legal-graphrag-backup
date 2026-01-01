'use client';

import React, { useState, useRef, useEffect } from 'react';
import Image from 'next/image';
import { apiClient } from '@/services/api';
import type { ChatResponse, ApiError, LegalSource } from '@/types/api';
import ReactMarkdown from 'react-markdown';
import SourceCard from './SourceCard';
import LoadingSkeleton from './LoadingSkeleton';
import ErrorMessage from './ErrorMessage';
import AnswerActions from './AnswerActions';

interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  sources?: LegalSource[];
  metadata?: any;
  timestamp: Date;
}

const SESSION_STORAGE_KEY = 'legalchat_session_id_v1_1';
const SESSION_VERSION_KEY = 'legalchat_session_version';
const CURRENT_VERSION = '1.1';

export default function LegalChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string>('');
  const [debugMode, setDebugMode] = useState(false);
  const [lastMetadata, setLastMetadata] = useState<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Initialize session ID from localStorage or create new one
  useEffect(() => {
    const storedVersion = localStorage.getItem(SESSION_VERSION_KEY);
    const storedSessionId = localStorage.getItem(SESSION_STORAGE_KEY);

    if (storedVersion === CURRENT_VERSION && storedSessionId) {
      // Valid session exists, restore it
      setSessionId(storedSessionId);
    } else {
      // Create new session (version mismatch or no session)
      const newSessionId = crypto.randomUUID();
      localStorage.setItem(SESSION_STORAGE_KEY, newSessionId);
      localStorage.setItem(SESSION_VERSION_KEY, CURRENT_VERSION);
      setSessionId(newSessionId);
    }
  }, []);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Debug mode toggle with Ctrl+Shift+D
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'D') {
        setDebugMode(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, []);

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

      if (response.session_id && response.session_id !== sessionId) {
        localStorage.setItem(SESSION_STORAGE_KEY, response.session_id);
        localStorage.setItem(SESSION_VERSION_KEY, CURRENT_VERSION);
        setSessionId(response.session_id);
      }

      // Capture metadata for debug mode
      if (response.metadata) {
        setLastMetadata(response.metadata);
      }

      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        type: 'assistant',
        content: response.answer,
        sources: response.sources,
        metadata: response.metadata,
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

    // Create new session
    const newSessionId = crypto.randomUUID();
    localStorage.setItem(SESSION_STORAGE_KEY, newSessionId);
    localStorage.setItem(SESSION_VERSION_KEY, CURRENT_VERSION);
    setSessionId(newSessionId);
  };

  return (
    <div className="flex flex-col flex-1 min-h-0 w-full bg-background text-foreground">
      {/* Top Bar - Gold with Artisting logo and disclaimer - FULL WIDTH - 2x height */}
      <div className="bg-primary text-foreground w-full h-32 px-6 flex items-center">
        <div className="flex justify-between items-center max-w-[1080px] mx-auto w-full">
          {/* Artisting Logo - Left */}
          <div className="relative h-20 w-50">
            <Image
              src="/artisting-logo.png"
              alt="Artisting"
              fill
              className="object-contain object-left"
              priority
            />
          </div>
          {/* Legal Disclaimer - Right */}
          <p className="text-xs text-foreground/90 leading-relaxed normal-case tracking-normal font-normal max-w-md text-right">
            Información legal basada en fuentes oficiales (BOE, EUR-Lex). No constituye asesoramiento profesional.
          </p>
        </div>
      </div>

      {/* Second Bar - Light beige with title - FULL WIDTH - 30% smaller */}
      <header className="bg-[#e9d79b] text-foreground w-full px-6 border-b border-border" style={{ height: '45px' }}>
        <div className="flex justify-between items-center max-w-[1080px] mx-auto h-full">
          {/* Title - Left */}
          <div>
            <h1 className="text-xl font-bold tracking-[1.25px] uppercase">Legal GraphRAG</h1>
          </div>
          {/* Subtitle and button - Right */}
          <div className="flex items-center gap-6">
            <p className="text-sm text-foreground/80 normal-case tracking-normal font-normal">
              Consultas legales para artistas
            </p>
            {messages.length > 0 && (
              <button
                onClick={clearChat}
                className="px-6 py-2 bg-secondary text-secondary-foreground hover:bg-primary hover:text-primary-foreground rounded-[3px] transition-all text-xs font-bold tracking-[0.5px] uppercase border border-secondary-foreground"
              >
                Nueva consulta
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Debug Panel (Ctrl+Shift+D to toggle) */}
      {debugMode && (
        <div className="bg-muted/60 border-b border-border px-6 py-3 text-xs font-mono text-muted-foreground">
          <div className="flex justify-between items-center mb-2">
            <span className="font-bold text-foreground">🐛 Debug Mode (Ctrl+Shift+D to close)</span>
            <button
              onClick={() => setDebugMode(false)}
              className="text-muted-foreground hover:text-foreground"
            >
              ✕
            </button>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <strong>Session ID:</strong> {sessionId.slice(0, 8)}...
            </div>
            {lastMetadata && (
              <>
                <div>
                  <strong>Topic Lock:</strong>{' '}
                  {lastMetadata.pending_topic || lastMetadata.area_principal || 'None'}
                </div>
                <div>
                  <strong>Pending Slots:</strong>{' '}
                  {lastMetadata.pending_slots?.length > 0
                    ? lastMetadata.pending_slots.join(', ')
                    : 'None'}
                </div>
                <div>
                  <strong>Base Question:</strong>{' '}
                  {lastMetadata.pending_question
                    ? `${lastMetadata.pending_question.slice(0, 40)}...`
                    : 'None'}
                </div>
                {lastMetadata.follow_up_merge && (
                  <div className="col-span-2 text-green-700">
                    <strong>✓ Merged Query:</strong>{' '}
                    {lastMetadata.merged_query?.slice(0, 80)}...
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* Messages Container */}
      <div className="flex-1 min-h-0 overflow-y-auto px-6 py-12 space-y-8 max-w-[1080px] mx-auto w-full">
        {messages.length === 0 && (
          <div className="text-center py-16">
            <div className="max-w-3xl mx-auto">
              <h2 className="text-3xl font-bold text-foreground mb-6 tracking-[1.25px] uppercase">
                Asistente Legal para Artistas
              </h2>
              <p className="text-base text-muted-foreground mb-12 leading-relaxed normal-case tracking-normal font-normal">
                Haz preguntas sobre normativa fiscal, derechos de autor, contratos y más.
                Las respuestas están basadas en fuentes oficiales del BOE y EUR-Lex.
              </p>
              <div className="grid md:grid-cols-2 gap-6 text-left">
                <div className="p-6 bg-card border border-border rounded-[3px] shadow-soft hover:shadow-medium transition-shadow">
                  <h3 className="font-bold text-foreground mb-3 text-sm uppercase tracking-[1px]">Ejemplo 1</h3>
                  <p className="text-sm text-muted-foreground normal-case tracking-normal font-normal">
                    ¿Puedo deducir los gastos de mi home studio?
                  </p>
                </div>
                <div className="p-6 bg-card border border-border rounded-[3px] shadow-soft hover:shadow-medium transition-shadow">
                  <h3 className="font-bold text-foreground mb-3 text-sm uppercase tracking-[1px]">Ejemplo 2</h3>
                  <p className="text-sm text-muted-foreground normal-case tracking-normal font-normal">
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
              className={`max-w-3xl w-full ${
                message.type === 'user'
                  ? 'bg-[#e9d79b] text-foreground rounded-[3px] border border-border'
                  : 'bg-card text-foreground rounded-[3px] border border-border'
              } px-8 py-5 shadow-soft`}
            >
              {message.type === 'user' ? (
                <p className="text-sm md:text-base user-message-text">{message.content}</p>
              ) : (
                <>
                  {(() => {
                    const extractDebugBlock = (content: string) => {
                      const lines = content.split('\n');
                      const debugLines: string[] = [];
                      const cleanLines: string[] = [];
                      let inDebug = false;

                      for (const line of lines) {
                        const trimmed = line.trim();
                        if (trimmed.startsWith('#')) {
                          inDebug = true;
                          debugLines.push(trimmed.replace(/^#+\s?/, ''));
                          continue;
                        }
                        if (inDebug && trimmed.length > 0) {
                          cleanLines.push(line);
                          inDebug = false;
                          continue;
                        }
                        if (!inDebug) {
                          cleanLines.push(line);
                        }
                      }

                      return { cleanContent: cleanLines.join('\n').trim(), debugLines };
                    };

                    const { cleanContent, debugLines } = extractDebugBlock(message.content);
                    const decision = message.metadata?.decision;
                    const debugRows: string[] = [];

                    if (decision) {
                      debugRows.push(
                        `Orchestrator: mode=${decision.mode}, reason=${decision.reason}, area=${decision.effective_area || 'none'}, question_type=${decision.question_type || 'unknown'}`
                      );
                    }
                    if (message.metadata?.area_principal) {
                      debugRows.push(`Intent: area=${message.metadata.area_principal}`);
                    }
                    if (message.metadata?.retrieval_counts) {
                      const counts = message.metadata.retrieval_counts;
                      debugRows.push(`Retrieval: combined=${counts.combined_results || 0}`);
                    }
                    if (message.metadata?.authority_pack_added !== undefined) {
                      debugRows.push(`Authority pack: added=${message.metadata.authority_pack_added}`);
                    }
                    if (message.metadata?.cited_count !== undefined) {
                      debugRows.push(`Citations: cited=${message.metadata.cited_count}, additional=${message.metadata.additional_count || 0}`);
                    }
                    if (message.metadata?.postprocess_errors?.length) {
                      debugRows.push(`Postprocess errors: ${message.metadata.postprocess_errors.join(', ')}`);
                    }

                    const combinedDebug = [...debugRows, ...debugLines];

                    const stageLabels = new Set([
                      'Orchestrator',
                      'Intent classification',
                      'Exact reference resolver',
                      'Query expansion',
                      'Hybrid search',
                      'Dedup + rank',
                      'Area filter',
                      'Authority pack',
                      'Abstain check',
                      'LLM generation',
                      'Citation extraction',
                      'Source formatting',
                      'Judge',
                    ]);

                    const filteredDebug = combinedDebug.filter((row) => {
                      const label = row.split(':')[0].trim();
                      return !stageLabels.has(label);
                    });


                    const retrievalCounts = message.metadata?.retrieval_counts;
                    const debugSummary = message.metadata?.debug_summary || {};
                    const fullTrace = message.metadata?.developer_debug?.full_trace || null;
                    const stageRows = [
                      {
                        label: 'Orchestrator',
                        value: decision
                          ? `mode=${decision.mode}, reason=${decision.reason} | thread=${fullTrace?.orchestrator?.thread_status || message.metadata?.developer_debug?.orchestrator_trace?.thread_status || 'unknown'} | lock=${fullTrace?.orchestrator?.state_before?.topic_lock || message.metadata?.developer_debug?.orchestrator_trace?.state_before?.topic_lock || 'none'} | forced=${fullTrace?.orchestrator?.decision?.forced_area_used ? 'yes' : (decision.forced_area_used ? 'yes' : 'no')}`
                          : 'off',
                        details: decision?.merged_query
                          ? [`merged_query: ${decision.merged_query.slice(0, 120)}...`]
                          : [],
                      },
                      {
                        label: 'Intent classification',
                        value: debugSummary.intent
                          ? `area=${debugSummary.intent.area_detected || 'unknown'}, conf=${(debugSummary.intent.confidence || 0).toFixed(2)}`
                          : 'unknown',
                        details: debugSummary.intent?.scores
                          ? [
                              `scores: ${Object.entries(debugSummary.intent.scores)
                                .slice(0, 4)
                                .map(([k, v]) => `${k}=${v}`)
                                .join(', ')}`,
                            ]
                          : [],
                      },
                      {
                        label: 'Exact reference resolver',
                        value: debugSummary.reference_resolver
                          ? `forced=${debugSummary.reference_resolver.forced_count || 0}`
                          : 'unknown',
                        details: debugSummary.reference_resolver?.forced_ids?.length
                          ? [`forced_ids: ${debugSummary.reference_resolver.forced_ids.join(', ')}`]
                          : [],
                      },
                      {
                        label: 'Query expansion',
                        value: debugSummary.query_expansion
                          ? `count=${debugSummary.query_expansion.count || 0}`
                          : 'unknown',
                        details: debugSummary.query_expansion?.queries?.length
                          ? debugSummary.query_expansion.queries.map((q: string) => `q: ${q.slice(0, 120)}`)
                          : [],
                      },
                      {
                        label: 'Hybrid search',
                        value: debugSummary.retrieval
                          ? `combined=${debugSummary.retrieval.combined_results || 0}`
                          : 'unknown',
                        details: [],
                      },
                      {
                        label: 'Dedup + rank',
                        value: debugSummary.dedup_rank?.after ? 'complete' : 'unknown',
                        details: debugSummary.dedup_rank?.after
                          ? [
                              `after: ${JSON.stringify(debugSummary.dedup_rank.after)}`,
                            ]
                          : [],
                      },
                      {
                        label: 'Area filter',
                        value: debugSummary.area_filter?.after ? 'complete' : 'unknown',
                        details: debugSummary.area_filter?.dropped !== undefined
                          ? [`dropped=${debugSummary.area_filter.dropped}`]
                          : [],
                      },
                      {
                        label: 'Authority pack',
                        value: debugSummary.authority_pack
                          ? (debugSummary.authority_pack.added ? 'added' : 'not added')
                          : 'unknown',
                        details: debugSummary.authority_pack?.count
                          ? [`count=${debugSummary.authority_pack.count}`]
                          : [],
                      },
                      {
                        label: 'Abstain check',
                        value: debugSummary.abstain
                          ? (debugSummary.abstain.abstained ? 'abstained' : 'answered')
                          : 'unknown',
                        details: [],
                      },
                      {
                        label: 'LLM generation',
                        value: `answer_len=${(cleanContent || message.content).length}`,
                        details: [],
                      },
                      {
                        label: 'Citation extraction',
                        value: debugSummary.citations
                          ? `cited=${debugSummary.citations.cited_count}, additional=${debugSummary.citations.additional_count}`
                          : 'unknown',
                        details: debugSummary.citations?.cited_ids?.length
                          ? [`cited_ids: ${debugSummary.citations.cited_ids.join(', ')}`]
                          : [],
                      },
                      {
                        label: 'Source formatting',
                        value: message.sources ? `sources=${message.sources.length}` : 'unknown',
                        details: debugSummary.sources_preview?.length
                          ? debugSummary.sources_preview.map((src: any) =>
                              `src: ${src.id || 'n/a'} | ${String(src.title || '').slice(0, 60)}`
                            )
                          : [],
                      },
                      {
                        label: 'Judge',
                        value: message.metadata?.judge?.verdict || 'disabled/unknown',
                        details: [],
                      },
                    ];


                    return (
                      <>
                        <div className="prose prose-sm md:prose-base max-w-none">
                          <ReactMarkdown components={{ html: () => null }}>
                            {cleanContent || message.content}
                          </ReactMarkdown>
                        </div>

                        {(combinedDebug.length > 0 || stageRows.length > 0) && (
                          <div className="mt-4 border border-border bg-muted/50 rounded-md px-3 py-2 text-xs italic text-muted-foreground">
                            <div className="font-semibold not-italic text-foreground mb-1">
                              Developer Dashboard (debug-only, not final)</div>
                            <details className="mt-2">
                              <summary className="cursor-pointer text-[11px] font-semibold not-italic text-foreground">
                                Orchestrator Trace
                              </summary>
                              <div className="mt-2 text-[11px] text-muted-foreground space-y-2">
                                {(() => {
                                  const trace = fullTrace?.orchestrator || message.metadata?.developer_debug?.orchestrator_trace;
                                  if (!trace) return <div>Trace unavailable</div>;
                                  return (
                                    <>
                                      <div>
                                        <span className="font-semibold">Decision:</span> {trace.decision?.mode} ({trace.decision?.reason}) | area={trace.decision?.effective_area || 'none'} | forced={trace.decision?.forced_area_used ? 'YES' : 'NO'}
                                      </div>
                                      <div className="pl-3">thread={trace.thread_status || 'unknown'} | lock={trace.state_before?.topic_lock || 'none'} | pending_slots={trace.state_before?.pending_slots?.length || 0}</div>

                                      <div>
                                        <span className="font-semibold">State Before:</span>
                                        <div className="pl-3">base={trace.state_before?.base_question_preview || 'none'}</div>
                                        <div className="pl-3">slots={trace.state_before?.pending_slots?.join(', ') || 'none'} | slot_keys={trace.state_before?.slot_values_keys?.join(', ') || 'none'}</div>
                                      </div>

                                      <div>
                                        <span className="font-semibold">Signals:</span>
                                        <div className="pl-3">short_message={String(trace.signals?.short_message?.value)} ({trace.signals?.short_message?.token_count})</div>
                                        <div className="pl-3">thin_turn={String(trace.signals?.thin_turn)}</div>
                                        <div className="pl-3">referential_hit={String(trace.signals?.referential_hit)} {trace.signals?.referential_matches?.length ? `(${trace.signals.referential_matches.join(', ')})` : ''}</div>
                                        <div className="pl-3">slot_fill_candidate={String(trace.signals?.slot_fill_candidate)}</div>
                                        <div className="pl-3">explicit_topic_change={String(trace.signals?.explicit_topic_change)}</div>
                                      </div>

                                      {trace.rejections?.length > 0 && (
                                        <div>
                                          <span className="font-semibold">Rejections:</span>
                                          <div className="pl-3">
                                            {trace.rejections.map((rej: string, idx: number) => (
                                              <div key={`rej-${message.id}-${idx}`}>- {rej}</div>
                                            ))}
                                          </div>
                                        </div>
                                      )}

                                      {trace.decision?.merged_query_preview && (
                                        <div>
                                          <span className="font-semibold">Merged Query:</span>
                                          <div className="pl-3">{trace.decision.merged_query_preview}</div>
                                        </div>
                                      )}

                                      {trace.state_after && (
                                        <div>
                                          <span className="font-semibold">State After / Diff:</span>
                                          <div className="pl-3">topic_lock={trace.state_after.topic_lock || 'none'} | pending_slots={trace.state_after.pending_slots?.join(', ') || 'none'} | turn_count={trace.state_after.turn_count}</div>
                                          <div className="pl-3">set={trace.state_diff?.set?.join(', ') || 'none'}</div>
                                          <div className="pl-3">cleared={trace.state_diff?.cleared?.join(', ') || 'none'}</div>
                                          <div className="pl-3">unchanged={trace.state_diff?.unchanged?.join(', ') || 'none'}</div>
                                        </div>
                                      )}
                                    </>
                                  );
                                })()}
                              </div>
                            </details>
                            <details className="mt-2">
                              <summary className="cursor-pointer text-[11px] font-semibold not-italic text-foreground">
                                Trace Panel
                              </summary>
                              <div className="mt-2 text-[11px] text-muted-foreground space-y-2">
                                {(() => {
                                  const trace = fullTrace;
                                  if (!trace) return <div>Trace unavailable</div>;
                                  return (
                                    <>
                                      <div>
                                        <span className="font-semibold">Identity:</span> request_id={trace.request_id || 'n/a'}
                                      </div>
                                      <div className="pl-3">
                                        session_id_received={trace.session_id_received || 'none'} | chat_session_db_id={trace.chat_session_db_id || 'n/a'}
                                      </div>
                                      <div className="pl-3">
                                        lookup={trace.chat_session_lookup_method || 'n/a'} | is_new_session={String(trace.is_new_session)} | turn_index={trace.orchestrator?.turn_index}
                                      </div>

                                      <div>
                                        <span className="font-semibold">State Before:</span>
                                        <div className="pl-3">topic_lock={trace.session?.state_before?.topic_lock || 'none'} | pending_slots={trace.session?.state_before?.pending_slots?.length || 0}</div>
                                        <div className="pl-3">base={trace.session?.state_before?.base_question_preview || 'none'}</div>
                                        <div className="pl-3">slot_keys={trace.session?.state_before?.slot_values_keys?.join(', ') || 'none'}</div>
                                      </div>

                                      <div>
                                        <span className="font-semibold">Decision:</span> {trace.orchestrator?.decision?.mode} ({trace.orchestrator?.decision?.reason}) | effective_area={trace.orchestrator?.decision?.effective_area || 'none'}
                                      </div>
                                      <div className="pl-3">forced_area={trace.orchestrator?.decision?.forced_area_value || 'none'} | question_type={trace.orchestrator?.decision?.question_type || 'unknown'}</div>

                                      {trace.orchestrator?.rejections?.length > 0 && (
                                        <div>
                                          <span className="font-semibold">Rejections:</span>
                                          <div className="pl-3">
                                            {trace.orchestrator.rejections.map((rej: string, idx: number) => (
                                              <div key={`trace-rej-${message.id}-${idx}`}>- {rej}</div>
                                            ))}
                                          </div>
                                        </div>
                                      )}

                                      {trace.orchestrator?.decision?.merged_query_preview && (
                                        <div>
                                          <span className="font-semibold">Merged Query:</span>
                                          <div className="pl-3">{trace.orchestrator.decision.merged_query_preview}</div>
                                        </div>
                                      )}

                                      <div>
                                        <span className="font-semibold">State After / Diff:</span>
                                        <div className="pl-3">topic_lock={trace.session?.state_after?.topic_lock || 'none'} | pending_slots={trace.session?.state_after?.pending_slots?.length || 0} | turn_count={trace.session?.state_after?.turn_count}</div>
                                        <div className="pl-3">set={trace.session?.state_diff?.set?.join(', ') || 'none'}</div>
                                        <div className="pl-3">cleared={trace.session?.state_diff?.cleared?.join(', ') || 'none'}</div>
                                        <div className="pl-3">unchanged={trace.session?.state_diff?.unchanged?.join(', ') || 'none'}</div>
                                      </div>

                                      {trace.rag?.top_sources?.length > 0 && (
                                        <div>
                                          <span className="font-semibold">Retrieval Top Sources:</span>
                                          <div className="pl-3">
                                            {trace.rag.top_sources.map((src: any, idx: number) => (
                                              <div key={`trace-src-${message.id}-${idx}`}>- {src.id} | {String(src.title || '').slice(0, 80)}</div>
                                            ))}
                                          </div>
                                        </div>
                                      )}

                                      <button
                                        type="button"
                                        onClick={() => navigator.clipboard.writeText(JSON.stringify(trace, null, 2))}
                                        className="mt-2 text-[11px] underline"
                                      >
                                        Copy trace
                                      </button>
                                    </>
                                  );
                                })()}
                              </div>
                            </details>
                            <div className="space-y-1">
                              {stageRows.map((row, idx) => (
                                <div key={`stage-${message.id}-${idx}`}>
                                  <span className="font-semibold">{row.label}:</span> {row.value}
                                  {row.details?.length > 0 && (
                                    <div className="pl-3 text-[11px]">
                                      {row.details.map((detail: string, detailIdx: number) => (
                                        <div key={`detail-${message.id}-${idx}-${detailIdx}`}>- {detail}</div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              ))}
                              {filteredDebug.map((row, idx) => (
                                <div key={`debug-${message.id}-${idx}`}>{row}</div>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    );
                  })()}

                  {message.sources && message.sources.length > 0 && (
                    <div className="mt-6 pt-4 border-t border-border">
                      {(() => {
                        const citedSources = message.sources.filter((source) => source.is_cited === true);
                        const additionalSources = message.sources.filter((source) => source.is_cited !== true);

                        return (
                          <>
                            {citedSources.length > 0 && (
                              <div className="mb-4">
                                <h4 className="font-semibold text-sm text-foreground mb-3 flex items-center gap-2">
                                  <span className="text-primary">* </span>
                                  Fuentes citadas ({citedSources.length})
                                </h4>
                                <div className="space-y-2">
                                  {citedSources.map((source, idx) => (
                                    <SourceCard
                                      key={`cited-${source.id || 'source'}-${idx}`}
                                      source={source}
                                      isCited={true}
                                    />
                                  ))}
                                </div>
                              </div>
                            )}

                            {additionalSources.length > 0 && (
                              <details className={citedSources.length > 0 ? 'mt-4' : ''}>
                                <summary className="cursor-pointer font-semibold text-sm text-muted-foreground hover:text-foreground flex items-center gap-2">
                                  <span>+</span>
                                  {citedSources.length > 0
                                    ? `Fuentes adicionales (${additionalSources.length})`
                                    : `Fuentes recuperadas (${additionalSources.length})`}
                                </summary>
                                <div className="space-y-2 mt-3">
                                  {additionalSources.map((source, idx) => (
                                    <SourceCard
                                      key={`additional-${source.id || 'source'}-${idx}`}
                                      source={source}
                                      isCited={false}
                                    />
                                  ))}
                                </div>
                              </details>
                            )}
                          </>
                        );
                      })()}
                    </div>
                  )}
                </>
              )}

              {message.type === 'assistant' && (
                <AnswerActions
                  conversationId={sessionId}
                  sessionId={sessionId}
                  messageId={message.metadata?.assistant_message_id || message.id}
                  answerText={message.content}
                />
              )}

              <div className={`text-xs mt-2 ${message.type === 'user' ? 'text-primary-foreground/70' : 'text-muted-foreground'}`}>
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

      {/* Input Form - Artisting Style */}
      <div className="border-t-2 border-border bg-background px-6 py-6">
        <form onSubmit={handleSubmit} className="max-w-[1080px] mx-auto">
          <div className="flex gap-4">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Escribe tu consulta legal aquí..."
              disabled={isLoading}
              className="flex-1 px-5 py-3 border-2 border-input bg-background rounded-[3px] focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary disabled:bg-muted/50 disabled:cursor-not-allowed text-sm normal-case tracking-normal font-normal transition-all"
              maxLength={500}
            />
            <button
              type="submit"
              disabled={isLoading || !inputValue.trim()}
              className="px-8 py-3 bg-secondary text-secondary-foreground rounded-[3px] font-bold hover:bg-primary hover:text-primary-foreground focus:outline-none focus:ring-2 focus:ring-primary disabled:bg-muted disabled:text-muted-foreground disabled:cursor-not-allowed transition-all text-xs tracking-[0.5px] uppercase border-2 border-secondary"
            >
              {isLoading ? 'Consultando...' : 'Enviar'}
            </button>
          </div>
          <div className="mt-3 text-xs text-muted-foreground text-right normal-case tracking-normal font-normal">
            {inputValue.length}/500 caracteres
          </div>
        </form>
      </div>
    </div>
  );
}

// API Client Service for Legal GraphRAG Backend

import axios, { AxiosInstance } from 'axios';
import type {
  ChatRequest,
  ChatResponse,
  FeedbackRequest,
  FeedbackResponse,
  SearchRequest,
  SearchResponse,
  SourcesResponse,
  ApiError,
} from '@/types/api';

class LegalGraphRAGApiClient {
  private client: AxiosInstance;
  private baseURL: string;

  constructor() {
    // Prefer explicit API URL, but avoid sending remote users to localhost.
    const envBaseURL = process.env.NEXT_PUBLIC_API_URL;
    let resolvedBaseURL = envBaseURL || '';
    if (envBaseURL) {
      try {
        const parsed = new URL(envBaseURL);
        if (typeof window !== 'undefined') {
          const isLocalEnv =
            parsed.hostname === 'localhost' || parsed.hostname === '127.0.0.1';
          const isRemoteHost =
            window.location.hostname !== 'localhost' &&
            window.location.hostname !== '127.0.0.1';
          if (isLocalEnv && isRemoteHost) {
            resolvedBaseURL = '';
          }
        }
      } catch {
        // Keep the env value if it's not a valid URL.
      }
    }

    this.baseURL = resolvedBaseURL;

    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: 120000, // 120 second timeout for LLM responses
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        const apiError: ApiError = {
          error: error.message || 'Unknown error occurred',
          status: error.response?.status,
          detail: error.response?.data?.detail || error.response?.data?.error,
        };
        return Promise.reject(apiError);
      }
    );
  }

  /**
   * Send a chat query to the Legal GraphRAG system
   * @param query - The user's legal question
   * @param sessionId - Optional session ID for multi-turn conversations
   * @returns ChatResponse with answer and sources
   */
  async chat(query: string, sessionId?: string): Promise<ChatResponse> {
    const request: ChatRequest = {
      query,
      ...(sessionId ? { session_id: sessionId } : {}),
    };

    const response = await this.client.post<ChatResponse>(
      '/api/v1/legal-graphrag/v1_1/chat/',
      request,
      {
        headers: {
          'X-Developer-Debug': '1',
        },
      }
    );
    return response.data;
  }

  /**
   * Search for legal documents/chunks
   * @param query - Search query
   * @param limit - Maximum number of results (default: 10)
   * @returns SearchResponse with matching chunks
   */
  async search(query: string, limit: number = 10): Promise<SearchResponse> {
    const request: SearchRequest = {
      query,
      limit,
    };

    const response = await this.client.post<SearchResponse>(
      '/api/v1/legal-graphrag/search/',
      request
    );
    return response.data;
  }

  /**
   * Get list of all corpus sources
   * @returns SourcesResponse with all available legal sources
   */
  async getSources(): Promise<SourcesResponse> {
    const response = await this.client.get<SourcesResponse>(
      '/api/v1/legal-graphrag/sources/'
    );
    return response.data;
  }

  /**
   * Health check endpoint
   * @returns True if backend is healthy
   */
  async healthCheck(): Promise<boolean> {
    try {
      await this.client.get('/api/v1/health/');
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Persist feedback events for assistant answers
   */
  async sendFeedback(payload: FeedbackRequest): Promise<FeedbackResponse> {
    const response = await this.client.post<FeedbackResponse>(
      '/api/v1/legal-graphrag/feedback/',
      payload
    );
    return response.data;
  }
}

// Export singleton instance
export const apiClient = new LegalGraphRAGApiClient();

// Export class for testing
export default LegalGraphRAGApiClient;

'use client';

import { useState, useCallback, useRef } from 'react';
import type { Message, Citation } from '@/types/project';

interface UseChatStreamReturn {
  messages: Message[];
  isStreaming: boolean;
  sendMessage: (content: string, introduced?: boolean) => Promise<void>;
  error: string | null;
}

/**
 * Streams a chat response from the project-scoped SSE endpoint:
 * POST /inference/projects/{projectId}/chat/stream
 *
 * This version uses the active ngrok tunnel target to ensure that
 * production builds hosted on Vercel can safely route downstream token streaming
 * requests directly back to your local development worker hardware infrastructure.
 */
export function useChatStream(projectId: string | null | undefined): UseChatStreamReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (content: string, introduced = false) => {
    if (!content.trim() || !projectId) return;

    // 1. Immediately push the user's prompt into the UI array state
    const userMessage: Message = { role: 'user', content };
    setMessages((prev) => [...prev, userMessage]);
    setIsStreaming(true);
    setError(null);

    // 🚀 FIXED: Route to your live production ngrok tunnel gateway instead of localhost fallback
    const apiBaseUrl = 'https://daisy-flammable-remindful.ngrok-free.dev/api/v1';

    try {
      abortControllerRef.current = new AbortController();

      const response = await fetch(`${apiBaseUrl}/inference/projects/${projectId}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('slm_token') || ''}`,
          'ngrok-skip-browser-warning': 'true',
        },
        body: JSON.stringify({ message: content, introduced }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail || 'Failed to send message');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      // 2. Pre-allocate an empty assistant message to anchor the incoming stream index mapping
      setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);

      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const dataStr = line.slice(6);
          if (!dataStr || dataStr === '[DONE]') continue;

          let data: { token?: string; citations?: Array<{ source: string; chapter: string }>; done?: boolean; error?: string };
          try {
            data = JSON.parse(dataStr);
          } catch {
            continue; // Bypass partial/malformed frames safely
          }

          if (data.error) {
            throw new Error(data.error);
          }

          // 3. Append tokens directly onto the active text array context 
          if (data.token) {
            setMessages((prev) => {
              const baseHistory = [...prev];
              const targetIdx = baseHistory.length - 1;
              if (targetIdx >= 0 && baseHistory[targetIdx].role === 'assistant') {
                baseHistory[targetIdx] = {
                  ...baseHistory[targetIdx],
                  content: baseHistory[targetIdx].content + data.token,
                };
                return baseHistory;
              }
              return prev;
            });
          }

          // 4. Bind source citation arrays onto the message object row at the finish marker
          if (data.done) {
            const citations: Citation[] = (data.citations || []).map((c, i) => ({
              id: `${i}-${c.source}-${c.chapter}`,
              documentName: c.source,
              chapter: c.chapter,
            }));

            setMessages((prev) => {
              const baseHistory = [...prev];
              const targetIdx = baseHistory.length - 1;
              if (targetIdx >= 0 && baseHistory[targetIdx].role === 'assistant') {
                baseHistory[targetIdx] = {
                  ...baseHistory[targetIdx],
                  citations,
                };
                return baseHistory;
              }
              return prev;
            });
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setError(err.message);
        // Clean up fallback rows gracefully if streaming errors out early
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.role === 'assistant' && !last.content) {
            return prev.slice(0, -1);
          }
          return prev;
        });
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }, [projectId]);

  return { messages, isStreaming, sendMessage, error };
}
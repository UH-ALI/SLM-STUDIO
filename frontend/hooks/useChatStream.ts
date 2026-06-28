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
 *   POST /inference/projects/{projectId}/chat/stream
 *
 * This replaces an earlier version that called a relative `/api/v1/inference/chat/stream`
 * path (which resolves against the Next.js dev server, not the API) with only
 * `{ message }` in the body. The legacy (non-project) endpoint requires job_id and
 * dataset_id and would 422 on that payload. The project-scoped endpoint needs neither —
 * it resolves the project's latest completed TrainingJob server-side.
 */
export function useChatStream(projectId: string | null | undefined): UseChatStreamReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (content: string, introduced = false) => {
    if (!content.trim() || !projectId) return;

    const userMessage: Message = { role: 'user', content };
    setMessages((prev) => [...prev, userMessage]);
    setIsStreaming(true);
    setError(null);

    // Placeholder assistant message — filled in token-by-token below.
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);

    const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

    try {
      abortControllerRef.current = new AbortController();

      const response = await fetch(`${apiBaseUrl}/inference/projects/${projectId}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('slm_token') || ''}`,
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

      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        // Keep any trailing partial line in the buffer for the next chunk.
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const dataStr = line.slice(6);
          if (!dataStr || dataStr === '[DONE]') continue;

          let data: { token?: string; citations?: Array<{ source: string; chapter: string }>; done?: boolean; error?: string };
          try {
            data = JSON.parse(dataStr);
          } catch {
            continue; // skip malformed SSE frame
          }

          if (data.error) {
            throw new Error(data.error);
          }

          if (data.token) {
            // Immutable update: build a new array and a new last-message object
            // rather than mutating the previous message in place, which the
            // earlier version did via `lastMsg.content += data.token`.
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (!last || last.role !== 'assistant') return prev;
              const updatedLast: Message = { ...last, content: last.content + data.token };
              return [...prev.slice(0, -1), updatedLast];
            });
          }

          if (data.done) {
            const citations: Citation[] = (data.citations || []).map((c, i) => ({
              id: `${i}-${c.source}-${c.chapter}`,
              documentName: c.source,
              chapter: c.chapter,
            }));
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (!last || last.role !== 'assistant') return prev;
              const updatedLast: Message = { ...last, citations };
              return [...prev.slice(0, -1), updatedLast];
            });
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setError(err.message);
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }, [projectId]);

  return { messages, isStreaming, sendMessage, error };
}

import { useState } from 'react';
import { ThumbsUp, ThumbsDown } from 'lucide-react';
import { classNames } from '@/lib/utils';
import type { Message } from '@/types/project';

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);

  return (
    <div
      className={classNames(
        'flex w-full',
        isUser ? 'justify-end' : 'justify-start'
      )}
    >
      <div
        className={classNames(
          'max-w-[80%] rounded-2xl px-4 py-3',
          isUser
            ? 'bg-gold/15 border border-gold/30 rounded-br-sm'
            : 'glass-card border border-white/[0.06] rounded-bl-sm !p-4'
        )}
      >
        {/* Message content */}
        <p className={classNames(
          'text-sm leading-relaxed whitespace-pre-wrap',
          isUser ? 'text-ivory' : 'text-ivory/90'
        )}>
          {message.content}
        </p>

        {/* Citations */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="mt-3 pt-2 border-t border-white/[0.06]">
            <p className="text-[0.65rem] text-muted uppercase tracking-[0.06em] mb-1.5">
              Sources
            </p>
            <div className="flex flex-wrap gap-2">
              {message.citations.map((citation) => (
                <span
                  key={citation.id}
                  className="text-xs text-sage/80 bg-sage/10 border border-sage/20 rounded-full px-2.5 py-0.5"
                >
                  {citation.documentName}
                  {citation.chapter && ` · ${citation.chapter}`}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Feedback buttons */}
        {!isUser && (
          <div className="flex items-center gap-1 mt-3 pt-2 border-t border-white/[0.06]">
            <button
              onClick={() => setFeedback(feedback === 'up' ? null : 'up')}
              className={classNames(
                'p-1 rounded transition-colors',
                feedback === 'up'
                  ? 'text-gold bg-gold/10'
                  : 'text-muted hover:text-fern hover:bg-white/[0.04]'
              )}
              aria-label="Helpful"
            >
              <ThumbsUp size={14} />
            </button>
            <button
              onClick={() => setFeedback(feedback === 'down' ? null : 'down')}
              className={classNames(
                'p-1 rounded transition-colors',
                feedback === 'down'
                  ? 'text-rose bg-rose/10'
                  : 'text-muted hover:text-fern hover:bg-white/[0.04]'
              )}
              aria-label="Not helpful"
            >
              <ThumbsDown size={14} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

'use client';

import { useEffect, useRef } from 'react';
import { classNames } from '@/lib/utils';
import { ChatMessage } from '@/components/molecules/ChatMessage';
import { ChatInput } from '@/components/molecules/ChatInput';
import { LoadingDots } from '@/components/atoms/LoadingDots';
import type { Message } from '@/types/project';

interface ChatInterfaceProps {
  messages: Message[];
  isStreaming: boolean;
  onSendMessage: (message: string) => void;
  className?: string;
}

export function ChatInterface({
  messages,
  isStreaming,
  onSendMessage,
  className,
}: ChatInterfaceProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isStreaming]);

  return (
    <div
      className={classNames(
        'flex flex-col h-full glass-card',
        className
      )}
    >
      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto space-y-4 p-4 min-h-0"
      >
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-16">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-gold/20 to-sage/20 flex items-center justify-center mb-4">
              <svg
                width="28"
                height="28"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                className="text-gold"
              >
                <path d="M12 3c.132 0 .263 0 .393 0a7.5 7.5 0 0 0 7.92 12.446a9 9 0 1 1 -8.313-12.454z" />
              </svg>
            </div>
            <h3 className="text-base font-semibold text-ivory mb-1">
              Start a conversation
            </h3>
            <p className="text-sm text-fern max-w-sm">
              Ask your AI assistant anything based on its training data
            </p>
          </div>
        ) : (
          messages.map((message, index) => (
            <ChatMessage key={index} message={message} />
          ))
        )}

        {/* Typing indicator */}
        {isStreaming && messages[messages.length - 1]?.role === 'user' && (
          <div className="flex items-start gap-3">
            <div className="glass-card !p-3 !rounded-bl-sm">
              <LoadingDots />
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-white/[0.06]">
        <ChatInput
          onSend={onSendMessage}
          isLoading={isStreaming}
          placeholder="Ask your AI assistant..."
        />
      </div>
    </div>
  );
}

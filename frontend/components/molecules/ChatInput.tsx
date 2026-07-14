import { useState, useRef, useEffect } from 'react';
import { ArrowUp } from 'lucide-react';
import { classNames } from '@/lib/utils';

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading?: boolean;
  placeholder?: string;
}

export function ChatInput({
  onSend,
  isLoading = false,
  placeholder = 'Type your message...',
}: ChatInputProps) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-grow
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 120) + 'px';
    }
  }, [value]);

  const handleSubmit = () => {
    if (!value.trim() || isLoading) return;
    onSend(value.trim());
    setValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const canSend = value.trim().length > 0 && !isLoading;

  return (
    <div className="flex items-end gap-2 p-3 bg-[#121B16]/80 border border-white/[0.06] rounded-2xl backdrop-blur-sm">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        rows={1}
        className={classNames(
          'flex-1 bg-transparent text-sm text-ivory placeholder:text-muted resize-none max-h-[120px]',
          'focus:outline-none py-2 px-1',
          'disabled:opacity-50'
        )}
        disabled={isLoading}
        aria-label="Message input"
      />
      <button
        onClick={handleSubmit}
        disabled={!canSend}
        className={classNames(
          'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-300',
          'bg-gradient-to-br from-gold to-sage text-void shadow-gold-sm',
          'hover:shadow-gold-lg hover:scale-105 active:scale-95',
          'disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:scale-100'
        )}
        aria-label="Send message"
      >
        <ArrowUp size={16} strokeWidth={2.5} />
      </button>
    </div>
  );
}

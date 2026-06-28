'use client';

import { useState } from 'react';
import { HelpCircle, BookOpen, User } from 'lucide-react';
import { classNames } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';

interface TestPrompt {
  label: string;
  icon: LucideIcon;
  prompt: string;
  description: string;
}

const testPrompts: TestPrompt[] = [
  {
    label: 'Ask a factual question',
    icon: HelpCircle,
    prompt: 'What are the key findings in the training data?',
    description: 'Test knowledge retrieval',
  },
  {
    label: 'Ask something not in docs',
    icon: BookOpen,
    prompt: 'What is the capital of France?',
    description: 'Test general knowledge',
  },
  {
    label: 'Ask who you are',
    icon: User,
    prompt: 'Who are you and what can you help me with?',
    description: 'Test persona adherence',
  },
];

interface TestPromptsProps {
  onPromptClick: (prompt: string) => void;
  className?: string;
}

export function TestPrompts({ onPromptClick, className }: TestPromptsProps) {
  const [typingIndex, setTypingIndex] = useState<number | null>(null);

  const handleClick = (prompt: string, index: number) => {
    setTypingIndex(index);

    // Simulate typewriter effect then send
    let currentText = '';
    const chars = prompt.split('');

    chars.forEach((char, i) => {
      setTimeout(() => {
        currentText += char;
        if (i === chars.length - 1) {
          setTypingIndex(null);
          onPromptClick(prompt);
        }
      }, i * 30);
    });
  };

  return (
    <div className={classNames('space-y-2', className)}>
      <p className="text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-muted mb-3">
        Try these prompts
      </p>
      {testPrompts.map((tp, index) => {
        const Icon = tp.icon;
        const isTyping = typingIndex === index;

        return (
          <button
            key={tp.label}
            onClick={() => !isTyping && handleClick(tp.prompt, index)}
            disabled={isTyping}
            className={classNames(
              'w-full text-left p-3 rounded-xl',
              'bg-[#121B16]/60 border border-white/[0.06]',
              'hover:border-gold/20 hover:bg-gold/[0.03] transition-all duration-300',
              'focus-visible:outline-2 focus-visible:outline-gold',
              isTyping && 'opacity-70 cursor-wait'
            )}
          >
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-gold/10 flex items-center justify-center flex-shrink-0">
                <Icon size={14} className="text-gold" />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-medium text-ivory truncate">
                  {tp.label}
                </p>
                <p className="text-[0.65rem] text-muted truncate">
                  {tp.description}
                </p>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}

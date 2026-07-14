'use client';

import { useState, useEffect } from 'react';
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
    prompt: 'Who are you?',
    description: 'Test persona adherence',
  },
];

interface TestPromptsProps {
  projectId: string;
  onPromptClick: (prompt: string) => void;
  className?: string;
}

export function TestPrompts({ projectId, onPromptClick, className }: TestPromptsProps) {
  const [typingIndex, setTypingIndex] = useState<number | null>(null);
  const [prompts, setPrompts] = useState<TestPrompt[]>(testPrompts);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchPrompts() {
      try {
        const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
        const res = await fetch(`${apiBaseUrl}/inference/projects/${projectId}/sample_prompts`, {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('slm_token') || ''}`,
          },
        });
        if (res.ok) {
          const data = await res.json();
          setPrompts([
            {
              label: 'Ask a factual question',
              icon: HelpCircle,
              prompt: data.factual,
              description: 'Test knowledge retrieval',
            },
            {
              label: 'Ask something not in docs',
              icon: BookOpen,
              prompt: data.negative,
              description: 'Test general knowledge',
            },
            {
              label: 'Ask who you are',
              icon: User,
              prompt: data.persona,
              description: 'Test persona adherence',
            },
          ]);
        }
      } catch (err) {
        console.error("Failed to fetch sample prompts", err);
      } finally {
        setIsLoading(false);
      }
    }
    
    if (projectId) {
      fetchPrompts();
    } else {
      setIsLoading(false);
    }
  }, [projectId]);

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
      {isLoading ? (
        <div className="space-y-2 animate-pulse">
          {[1, 2, 3].map((i) => (
            <div key={i} className="w-full h-[60px] rounded-xl bg-white/[0.02] border border-white/[0.04]"></div>
          ))}
        </div>
      ) : (
        prompts.map((tp, index) => {
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
      })
      )}
    </div>
  );
}

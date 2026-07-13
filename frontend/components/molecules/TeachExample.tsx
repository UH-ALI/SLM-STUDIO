import { classNames } from '@/lib/utils';
import { Trash2 } from 'lucide-react';
import type { FewShotExample } from '@/types/project';

interface TeachExampleProps {
  index: number;
  example: FewShotExample;
  onChange: (example: FewShotExample) => void;
  onRemove?: () => void;
  labels?: [string, string];
}

const defaultLabels: [string, string] = ['Question', 'Answer'];

export function TeachExample({
  index,
  example,
  onChange,
  onRemove,
  labels = defaultLabels,
}: TeachExampleProps) {
  const [questionLabel, answerLabel] = labels;

  const handleQuestionChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...example, question: e.target.value });
  };

  const handleAnswerChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange({ ...example, answer: e.target.value });
  };

  return (
    <div className="space-y-3">
      {/* Example label + delete button */}
      <div className="flex items-center justify-between">
        <p className="text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-muted">
          Example {index + 1}
        </p>
        {onRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="flex items-center gap-1 text-[0.65rem] text-muted hover:text-rose transition-colors"
            aria-label={`Remove example ${index + 1}`}
          >
            <Trash2 size={12} />
            Remove
          </button>
        )}
      </div>

      {/* Question */}
      <div>
        <label className="block text-xs text-fern mb-1">{questionLabel}</label>
        <input
          type="text"
          value={example.question}
          onChange={handleQuestionChange}
          placeholder={`Enter ${questionLabel.toLowerCase()}...`}
          className={classNames(
            'w-full bg-[#121B16]/60 border border-white/[0.08] rounded-button px-3 py-2 text-sm text-ivory placeholder:text-muted',
            'transition-all duration-300 ease-brand',
            'focus:outline-none focus:border-gold/40 focus:shadow-[0_0_0_3px_rgba(212,168,83,0.1)]'
          )}
        />
      </div>

      {/* Answer */}
      <div>
        <label className="block text-xs text-fern mb-1">
          {answerLabel} {example.question.trim() && !example.answer.trim() && <span className="text-rose font-medium">(Required)</span>}
        </label>
        <textarea
          value={example.answer}
          onChange={handleAnswerChange}
          placeholder={`Enter ${answerLabel.toLowerCase()}...`}
          rows={2}
          className={classNames(
            'w-full bg-[#121B16]/60 rounded-button px-3 py-2 text-sm text-ivory placeholder:text-muted resize-none',
            'transition-all duration-300 ease-brand focus:outline-none',
            example.question.trim() && !example.answer.trim()
              ? 'border border-rose/60 focus:border-rose'
              : 'border border-white/[0.08] focus:border-gold/40 focus:shadow-[0_0_0_3px_rgba(212,168,83,0.1)]'
          )}
        />
      </div>
    </div>
  );
}

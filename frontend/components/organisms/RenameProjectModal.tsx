'use client';

import { useEffect, useRef, useState } from 'react';
import { Pencil } from 'lucide-react';
import { classNames } from '@/lib/utils';
import { Button } from '@/components/atoms/Button';

interface RenameProjectModalProps {
  currentName: string;
  onCancel: () => void;
  onSubmit: (newName: string) => Promise<void> | void;
}

// [FEATURE] Replaces the "Rename coming soon" toast stub. Modeled on
// WarningModal for visual/behavioral consistency (focus trap, Escape to
// close, backdrop click to cancel).
export function RenameProjectModal({ currentName, onCancel, onSubmit }: RenameProjectModalProps) {
  const [name, setName] = useState(currentName);
  const [isSaving, setIsSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
    };

    document.addEventListener('keydown', handleKeyDown);
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [onCancel]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed || trimmed === currentName) {
      onCancel();
      return;
    }
    setIsSaving(true);
    try {
      await onSubmit(trimmed);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="rename-title"
    >
      <div className="absolute inset-0 bg-void/80 backdrop-blur-sm" onClick={onCancel} />

      <form
        onSubmit={handleSubmit}
        className={classNames('relative w-full max-w-sm glass-card z-10', 'animate-scale-in')}
      >
        <div className="w-12 h-12 rounded-xl bg-gold/10 flex items-center justify-center mb-4">
          <Pencil size={20} className="text-gold" />
        </div>

        <h3 id="rename-title" className="text-lg font-semibold text-ivory mb-3">
          Rename project
        </h3>

        <input
          ref={inputRef}
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={100}
          className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-3.5 py-2.5 text-sm text-ivory placeholder:text-fern focus:outline-none focus:border-gold/50 transition-colors mb-6"
          placeholder="Project name"
        />

        <div className="flex items-center gap-3 justify-end">
          <Button type="button" variant="secondary" onClick={onCancel} disabled={isSaving}>
            Cancel
          </Button>
          <Button type="submit" isLoading={isSaving} disabled={!name.trim()}>
            Save
          </Button>
        </div>
      </form>
    </div>
  );
}

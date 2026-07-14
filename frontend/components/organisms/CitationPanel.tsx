'use client';

import { X, FileText } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { classNames } from '@/lib/utils';
import type { Citation } from '@/types/project';

interface CitationPanelProps {
  citations: Citation[];
  isOpen: boolean;
  onClose: () => void;
  className?: string;
}

export function CitationPanel({ citations, isOpen, onClose, className }: CitationPanelProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Mobile backdrop */}
          <div
            className="fixed inset-0 bg-void/50 backdrop-blur-sm z-40 lg:hidden"
            onClick={onClose}
          />

          <motion.div
            initial={{ x: '100%', opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: '100%', opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className={classNames(
              'fixed right-0 top-0 h-full w-80 z-50',
              'bg-[#121B16]/95 backdrop-blur-xl border-l border-white/[0.06]',
              'flex flex-col',
              'lg:relative lg:w-full lg:z-auto lg:h-full lg:glass-card',
              className
            )}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-white/[0.06]">
              <div>
                <h3 className="text-sm font-semibold text-ivory">Sources</h3>
                <p className="text-xs text-fern">{citations.length} citation{citations.length !== 1 ? 's' : ''}</p>
              </div>
              <button
                onClick={onClose}
                className={classNames(
                  'w-8 h-8 rounded-lg flex items-center justify-center',
                  'text-fern hover:text-ivory hover:bg-white/[0.06] transition-colors',
                  'focus-visible:outline-2 focus-visible:outline-gold',
                  'lg:hidden'
                )}
                aria-label="Close citations"
              >
                <X size={16} />
              </button>
            </div>

            {/* Citation list */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {citations.length === 0 ? (
                <p className="text-sm text-muted text-center py-8">
                  No citations yet
                </p>
              ) : (
                citations.map((citation) => (
                  <div
                    key={citation.id}
                    className={classNames(
                      'p-3 rounded-xl bg-[#121B16]/60 border border-white/[0.06]',
                      'hover:border-gold/20 transition-colors cursor-pointer'
                    )}
                  >
                    <div className="flex items-start gap-2.5">
                      <div className="w-8 h-8 rounded-lg bg-sage/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <FileText size={14} className="text-sage" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-ivory truncate">
                          {citation.documentName}
                        </p>
                        <p className="text-xs text-sage mt-0.5">
                          {citation.chapter}
                        </p>
                        {citation.content && (
                          <p className="text-xs text-fern mt-2 line-clamp-3 leading-relaxed">
                            {citation.content}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

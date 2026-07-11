import { X, FileText } from 'lucide-react';
import { classNames } from '@/lib/utils';
import { formatFileSize } from '@/lib/utils';

interface FileListItemProps {
  name: string;
  size: number;
  onRemove: () => void;
  className?: string;
}

export function FileListItem({ name, size, onRemove, className }: FileListItemProps) {
  const ext = name.split('.').pop()?.toLowerCase() || '';

  return (
    <div
      className={classNames(
        'flex items-center gap-3 p-3 rounded-button bg-[#121B16]/60 border border-white/[0.06] group',
        className
      )}
    >
      {/* File icon */}
      <div className="w-9 h-9 rounded-lg bg-gold/10 flex items-center justify-center flex-shrink-0 relative">
        <FileText size={18} className="text-gold" />
        {ext && (
          <span className="absolute -bottom-1 -right-1 px-1 rounded text-[0.5625rem] font-bold leading-tight bg-elevated border border-white/[0.08] text-fern uppercase">
            {ext}
          </span>
        )}
      </div>

      {/* File info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm text-ivory truncate font-medium">{name}</p>
        <p className="text-xs text-muted tabular-nums">{formatFileSize(size)}</p>
      </div>

      {/* Remove button */}
      <button
        onClick={onRemove}
        className={classNames(
          'w-7 h-7 rounded-lg flex items-center justify-center opacity-0 group-hover:opacity-100',
          'text-fern hover:text-rose hover:bg-rose/10 transition-all duration-200',
          'focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-rose/50'
        )}
        aria-label={`Remove ${name}`}
      >
        <X size={14} />
      </button>
    </div>
  );
}

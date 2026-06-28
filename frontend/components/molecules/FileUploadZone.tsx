'use client';

import { useState, useRef, useCallback } from 'react';
import { Upload } from 'lucide-react';
import { classNames } from '@/lib/utils';
import { ALLOWED_FILE_EXTENSIONS, MAX_FILE_SIZE } from '@/lib/constants';

interface FileUploadZoneProps {
  onFilesSelected: (files: File[]) => void;
  acceptedTypes?: string[];
  maxSize?: number;
}

export function FileUploadZone({
  onFilesSelected,
  acceptedTypes = ALLOWED_FILE_EXTENSIONS,
  maxSize = MAX_FILE_SIZE,
}: FileUploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const acceptString = acceptedTypes.join(',');

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      const files = Array.from(e.dataTransfer.files).filter((file) => {
        if (file.size > maxSize) return false;
        const ext = '.' + file.name.split('.').pop()?.toLowerCase();
        return acceptedTypes.includes(ext);
      });

      if (files.length > 0) {
        onFilesSelected(files);
      }
    },
    [onFilesSelected, acceptedTypes, maxSize]
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files || []);
      if (files.length > 0) {
        onFilesSelected(files);
      }
      e.target.value = '';
    },
    [onFilesSelected]
  );

  const handleClick = () => {
    inputRef.current?.click();
  };

  const sizeMB = Math.round(maxSize / 1024 / 1024);

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={handleClick}
      className={classNames(
        'relative border-2 border-dashed rounded-card p-8 text-center cursor-pointer transition-all duration-300 ease-brand',
        'bg-[#121B16]/40',
        isDragging
          ? 'border-gold bg-gold-soft/[0.08] shadow-gold-sm'
          : 'border-white/[0.08] hover:border-gold/30 hover:bg-white/[0.02]'
      )}
      role="button"
      tabIndex={0}
      aria-label="Upload files by dragging and dropping or clicking"
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleClick();
        }
      }}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={acceptString}
        onChange={handleChange}
        className="hidden"
        aria-hidden="true"
      />

      <div
        className={classNames(
          'w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4 transition-all duration-300',
          'bg-gradient-to-br from-gold/20 to-sage/20',
          isDragging && 'scale-110'
        )}
      >
        <Upload
          size={28}
          className={classNames(
            'text-gold transition-transform duration-300',
            isDragging && '-translate-y-1'
          )}
        />
      </div>

      <p className="text-sm text-ivory font-medium mb-1">
        {isDragging ? 'Drop files here' : 'Drag & drop files here'}
      </p>
      <p className="text-xs text-fern mb-3">or click to browse</p>
      <p className="text-xs text-muted">
        {acceptedTypes.join(', ')} · Max {sizeMB}MB
      </p>
    </div>
  );
}

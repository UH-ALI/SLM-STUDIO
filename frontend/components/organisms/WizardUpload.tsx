'use client';

import { useState, useCallback } from 'react';
import { FileText, Upload } from 'lucide-react';
import { classNames } from '@/lib/utils';
import { FileUploadZone } from '@/components/molecules/FileUploadZone';
import { FileListItem } from '@/components/molecules/FileListItem';
import { Textarea } from '@/components/atoms/Textarea';
import { Button } from '@/components/atoms/Button';

interface WizardUploadProps {
  files: File[];
  textInput: string;
  onFilesChange: (files: File[]) => void;
  onTextChange: (text: string) => void;
  onContinue: () => void;
  onBack: () => void;
}

export function WizardUpload({
  files,
  textInput,
  onFilesChange,
  onTextChange,
  onContinue,
  onBack,
}: WizardUploadProps) {
  const [activeTab, setActiveTab] = useState<'upload' | 'text'>('upload');

  const handleFilesSelected = useCallback(
    (newFiles: File[]) => {
      onFilesChange([...files, ...newFiles]);
    },
    [files, onFilesChange]
  );

  const handleRemoveFile = useCallback(
    (index: number) => {
      onFilesChange(files.filter((_, i) => i !== index));
    },
    [files, onFilesChange]
  );

  const canContinue = files.length > 0 || textInput.trim().length > 0;

  return (
    <div className="space-y-6">
      {/* Tab switcher */}
      <div className="flex gap-2 p-1 bg-[#121B16]/60 rounded-xl">
        <button
          onClick={() => setActiveTab('upload')}
          className={classNames(
            'flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all',
            activeTab === 'upload'
              ? 'bg-gold/15 text-gold'
              : 'text-fern hover:text-ivory'
          )}
        >
          <Upload size={16} />
          Upload Files
        </button>
        <button
          onClick={() => setActiveTab('text')}
          className={classNames(
            'flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all',
            activeTab === 'text'
              ? 'bg-gold/15 text-gold'
              : 'text-fern hover:text-ivory'
          )}
        >
          <FileText size={16} />
          Enter Text
        </button>
      </div>

      {/* Upload tab */}
      {activeTab === 'upload' && (
        <div className="space-y-4">
          <FileUploadZone onFilesSelected={handleFilesSelected} />

          {files.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-fern uppercase tracking-wider">
                {files.length} file{files.length !== 1 ? 's' : ''} selected
              </p>
              {files.map((file, i) => (
                <FileListItem
                  key={`${file.name}-${i}`}
                  name={file.name}
                  size={file.size}
                  onRemove={() => handleRemoveFile(i)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Text tab */}
      {activeTab === 'text' && (
        <div>
          <p className="text-xs text-fern mb-3">
            Paste or type your training data directly
          </p>
          <Textarea
            placeholder="Enter your training data here..."
            value={textInput}
            onChange={(e) => onTextChange(e.target.value)}
            rows={12}
          />
        </div>
      )}

      {/* Navigation */}
      <div className="flex justify-between pt-4">
        <Button variant="secondary" onClick={onBack}>
          Back
        </Button>
        <Button onClick={onContinue} disabled={!canContinue}>
          Continue
        </Button>
      </div>
    </div>
  );
}

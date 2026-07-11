'use client';

import { useCallback } from 'react';
import { FileUploadZone } from '@/components/molecules/FileUploadZone';
import { FileListItem } from '@/components/molecules/FileListItem';
import { Button } from '@/components/atoms/Button';

interface WizardUploadProps {
  files: File[];
  textInput?: string;
  isSubmitting?: boolean;
  onFilesChange: (files: File[]) => void;
  onTextChange?: (text: string) => void;
  onContinue: () => void;
  onBack: () => void;
}

export function WizardUpload({
  files,
  isSubmitting = false,
  onFilesChange,
  onContinue,
  onBack,
}: WizardUploadProps) {
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

  const canContinue = files.length > 0;

  return (
    <div className="space-y-6">
      {/* Upload zone */}
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

      {/* Navigation */}
      <div className="flex justify-between pt-4">
        <Button variant="secondary" onClick={onBack} disabled={isSubmitting}>
          Back
        </Button>
        <Button onClick={onContinue} disabled={!canContinue} isLoading={isSubmitting}>
          Continue
        </Button>
      </div>
    </div>
  );
}

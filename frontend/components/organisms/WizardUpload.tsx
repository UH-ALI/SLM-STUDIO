'use client';

import { useCallback, useEffect, useState } from 'react';
import { Database, Check } from 'lucide-react';
import { FileUploadZone } from '@/components/molecules/FileUploadZone';
import { FileListItem } from '@/components/molecules/FileListItem';
import { Button } from '@/components/atoms/Button';
import { useProjectStore } from '@/stores/projectStore';
import { classNames } from '@/lib/utils';

interface WizardUploadProps {
  files: File[];
  textInput?: string;
  isSubmitting?: boolean;
  onFilesChange: (files: File[]) => void;
  onTextChange?: (text: string) => void;
  // [FEATURE] IDs of the user's previously uploaded datasets to attach to
  // this project, alongside (or instead of) uploading fresh files.
  selectedExistingDatasetIds: string[];
  onExistingDatasetsChange: (ids: string[]) => void;
  onContinue: () => void;
  onBack: () => void;
}

export function WizardUpload({
  files,
  isSubmitting = false,
  onFilesChange,
  selectedExistingDatasetIds,
  onExistingDatasetsChange,
  onContinue,
  onBack,
}: WizardUploadProps) {
  const { datasets, fetchDatasets } = useProjectStore();
  const [loadingDatasets, setLoadingDatasets] = useState(true);

  // [FEATURE] Load the user's existing datasets once, so they can reuse one
  // instead of being forced to upload the same file again for every project.
  useEffect(() => {
    fetchDatasets().finally(() => setLoadingDatasets(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  const toggleExistingDataset = (id: string) => {
    if (selectedExistingDatasetIds.includes(id)) {
      onExistingDatasetsChange(selectedExistingDatasetIds.filter((existingId) => existingId !== id));
    } else {
      onExistingDatasetsChange([...selectedExistingDatasetIds, id]);
    }
  };

  const canContinue = files.length > 0 || selectedExistingDatasetIds.length > 0;

  return (
    <div className="space-y-6">
      {/* Upload zone */}
      <div className="space-y-4">
        <FileUploadZone onFilesSelected={handleFilesSelected} />

        {files.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs text-fern uppercase tracking-wider">
              {files.length} new file{files.length !== 1 ? 's' : ''} selected
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

      {/* [FEATURE] Reuse a previously uploaded dataset */}
      {!loadingDatasets && datasets.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-fern uppercase tracking-wider">
            Or use a dataset you've already uploaded
          </p>
          <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
            {datasets.map((dataset) => {
              const selected = selectedExistingDatasetIds.includes(dataset.id);
              return (
                <button
                  key={dataset.id}
                  type="button"
                  onClick={() => toggleExistingDataset(dataset.id)}
                  className={classNames(
                    'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-colors',
                    selected
                      ? 'bg-gold/10 border border-gold/30'
                      : 'bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.06]'
                  )}
                >
                  <div
                    className={classNames(
                      'w-4 h-4 rounded flex items-center justify-center shrink-0 border',
                      selected ? 'bg-gold border-gold' : 'border-white/20'
                    )}
                  >
                    {selected && <Check size={11} className="text-void" strokeWidth={3} />}
                  </div>
                  <Database size={14} className="text-fern shrink-0" />
                  <span className="text-sm text-ivory/90 truncate">{dataset.name}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

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

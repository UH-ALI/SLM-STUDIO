'use client';

import { useEffect } from 'react';
import { Database, FileText, Clock } from 'lucide-react';
import { DashboardLayout } from '@/components/templates/DashboardLayout';
import { PageHeader } from '@/components/organisms/PageHeader';
import { useProjectStore } from '@/stores/projectStore';
import { formatFileSize } from '@/lib/utils';

export default function DatasetsPage() {
  const { datasets, fetchDatasets, isLoading } = useProjectStore();

  useEffect(() => {
    fetchDatasets();
  }, [fetchDatasets]);

  return (
    <DashboardLayout>
      <PageHeader
        title="Datasets"
        subtitle="Manage your training datasets"
      />

      <div className="glass-card">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-8 h-8 border-2 border-gold border-t-transparent rounded-full animate-spin" />
          </div>
        ) : datasets.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-gold/20 to-sage/20 flex items-center justify-center mb-4">
              <Database size={28} className="text-gold" />
            </div>
            <h3 className="text-lg font-semibold text-ivory mb-2">No Datasets</h3>
            <p className="text-sm text-fern max-w-sm">
              Upload your first dataset to get started with training.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-white/[0.06]">
            {datasets.map((dataset) => (
              <div
                key={dataset.id}
                className="flex items-center gap-4 p-4 hover:bg-white/[0.02] transition-colors"
              >
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-gold/20 to-sage/20 flex items-center justify-center flex-shrink-0">
                  <FileText size={20} className="text-gold" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-medium text-ivory truncate">
                    {dataset.name}
                  </h3>
                  <p className="text-xs text-fern">
                    {dataset.datasetType} · {formatFileSize(1024 * 1024)}
                  </p>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-muted">
                  <Clock size={12} />
                  <span>{new Date(dataset.createdAt).toLocaleDateString()}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

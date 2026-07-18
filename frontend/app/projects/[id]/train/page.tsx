"use client";

import React, { ErrorInfo } from 'react';
import { DashboardLayout } from "@/components/templates/DashboardLayout";
import { TrainingLayout } from "@/components/templates/TrainingLayout";
import { PageHeader } from "@/components/organisms/PageHeader";

interface TrainPageProps {
  params: { id: string };
}

class ErrorBoundary extends React.Component<{children: React.ReactNode}, {hasError: boolean, error: Error | null}> {
  constructor(props: {children: React.ReactNode}) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Training page caught error:", error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <DashboardLayout>
          <div className="p-4 sm:p-8 bg-red-900/50 text-white rounded-lg m-4 sm:m-8">
            <h2 className="text-xl font-bold mb-4">Training Page Render Error</h2>
            <pre className="whitespace-pre-wrap font-mono text-sm">{this.state.error?.toString()}</pre>
            <pre className="whitespace-pre-wrap font-mono text-xs mt-4 text-gray-300">{this.state.error?.stack}</pre>
          </div>
        </DashboardLayout>
      );
    }
    return this.props.children;
  }
}

export default function TrainPage({ params }: TrainPageProps) {
  const { id: _id } = params;

  return (
    <ErrorBoundary>
      <DashboardLayout>
        <PageHeader
          title="Training"
          subtitle="Monitor your model training progress"
        />
        <TrainingLayout>
          {/* TrainingLayout handles all the inner components */}
        </TrainingLayout>
      </DashboardLayout>
    </ErrorBoundary>
  );
}

"use client";

import { DashboardLayout } from "@/components/templates/DashboardLayout";
import { TrainingLayout } from "@/components/templates/TrainingLayout";
import { PageHeader } from "@/components/organisms/PageHeader";

interface TrainPageProps {
  params: { id: string };
}

export default function TrainPage({ params }: TrainPageProps) {
  const { id: _id } = params;

  return (
    <DashboardLayout>
      <PageHeader
        title="Training"
        subtitle="Monitor your model training progress"
      />
      <TrainingLayout>
        {/* TrainingLayout handles all the inner components */}
      </TrainingLayout>
    </DashboardLayout>
  );
}

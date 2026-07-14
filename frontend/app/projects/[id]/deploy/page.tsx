"use client";

import { DashboardLayout } from "@/components/templates/DashboardLayout";
import { DeployLayout } from "@/components/templates/DeployLayout";
import { DeployPanel } from "@/components/organisms/DeployPanel";
import { PageHeader } from "@/components/organisms/PageHeader";

interface DeployPageProps {
  params: { id: string };
}

export default function DeployPage({ params }: DeployPageProps) {
  const { id } = params;

  return (
    <DashboardLayout>
      <PageHeader
        title="Deploy"
        subtitle="Deploy and integrate your AI assistant"
      />
      <DeployLayout>
        <DeployPanel projectId={id} />
      </DeployLayout>
    </DashboardLayout>
  );
}

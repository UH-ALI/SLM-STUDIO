"use client";

import { DashboardLayout } from "@/components/templates/DashboardLayout";
import { PlaygroundLayout } from "@/components/templates/PlaygroundLayout";
import { PageHeader } from "@/components/organisms/PageHeader";

interface PlaygroundPageProps {
  params: { id: string };
}

export default function PlaygroundPage({ params }: PlaygroundPageProps) {
  const { id: _id } = params;

  return (
    <DashboardLayout>
      <PageHeader
        title="Playground"
        subtitle="Chat with your trained AI assistant"
      />
      <PlaygroundLayout />
    </DashboardLayout>
  );
}

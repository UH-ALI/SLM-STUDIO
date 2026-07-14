interface DeployLayoutProps {
  children: React.ReactNode;
}

export function DeployLayout({ children }: DeployLayoutProps) {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {children}
    </div>
  );
}

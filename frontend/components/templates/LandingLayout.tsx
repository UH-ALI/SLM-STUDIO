import { ToastContainer } from '@/components/organisms/ToastContainer';

interface LandingLayoutProps {
  children: React.ReactNode;
}

export function LandingLayout({ children }: LandingLayoutProps) {
  return (
    <div className="min-h-screen bg-void">
      {children}
      <ToastContainer />
    </div>
  );
}

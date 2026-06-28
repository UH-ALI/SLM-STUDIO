'use client';

import { useEffect, useState } from 'react';
import { useAuthStore } from '@/stores/authStore';

export function MSWProvider({ children }: { children: React.ReactNode }) {
  const [mswReady, setMswReady] = useState(false);

  useEffect(() => {
    const initMSW = async () => {
      if (
        typeof window !== 'undefined' &&
        process.env.NEXT_PUBLIC_USE_MSW === 'true'
      ) {
        const { worker } = await import('@/mocks/browser');
        await worker.start({
          onUnhandledRequest: 'bypass',
        });
        // Initialize auth after MSW is ready so the /users/me request is intercepted
        useAuthStore.getState().initialize();
        setMswReady(true);
      } else {
        // Initialize auth even without MSW
        useAuthStore.getState().initialize();
        setMswReady(true);
      }
    };

    initMSW();
  }, []);

  if (!mswReady) {
    return (
      <div className="min-h-screen bg-void flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-gold border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return <>{children}</>;
}

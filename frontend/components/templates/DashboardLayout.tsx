'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { usePathname } from 'next/navigation';
import { Sidebar } from '@/components/organisms/Sidebar';
import { ToastContainer } from '@/components/organisms/ToastContainer';
import { useUIStore } from '@/stores/uiStore';
import { classNames } from '@/lib/utils';

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const { sidebarExpanded } = useUIStore();
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-void">
      {/* Sidebar */}
      <Sidebar />

      {/* Main content */}
      <motion.main
        id="main-content"
        className={classNames(
          'min-h-screen transition-[margin] duration-300 ease-brand',
          sidebarExpanded ? 'lg:ml-[280px]' : 'lg:ml-[72px]'
        )}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <AnimatePresence mode="wait">
            <motion.div
              key={pathname}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </div>
      </motion.main>

      {/* Toast notifications */}
      <ToastContainer />
    </div>
  );
}

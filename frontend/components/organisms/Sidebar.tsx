'use client';

import { useRouter, usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard,
  Database,
  Brain,
  Settings,
  User,
  LogOut,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { classNames } from '@/lib/utils';
import { NavItem } from '@/components/molecules/NavItem';
import { Avatar } from '@/components/atoms/Avatar';
import { useAuthStore } from '@/stores/authStore';
import { useUIStore } from '@/stores/uiStore';

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', href: '/dashboard' },
  { icon: Database, label: 'Datasets', href: '/datasets' },
  { icon: Brain, label: 'Models', href: '/models' },
  { icon: Settings, label: 'Settings', href: '/settings' },
  { icon: User, label: 'Profile', href: '/profile' },
];

// Bug 7 fix: "Models" should stay highlighted on /models and all /projects/[id]/* sub-pages
function getIsActive(label: string, href: string, pathname: string): boolean {
  if (label === 'Models') {
    return pathname === '/models' || pathname.startsWith('/projects/');
  }
  return pathname === href;
}

export function Sidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const { user, logout } = useAuthStore();
  const { sidebarExpanded, toggleSidebar } = useUIStore();

  const handleNavigate = (href: string) => {
    router.push(href);
  };

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  return (
    <motion.aside
      className={classNames(
        'fixed left-0 top-0 h-full z-40 flex flex-col',
        'bg-[#121B16]/80 backdrop-blur-xl border-r border-white/[0.06]'
      )}
      animate={{ width: sidebarExpanded ? 280 : 72 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
    >
      {/* Logo */}
      <div className="flex items-center h-16 px-4 border-b border-white/[0.06]">
        <div
          className={classNames(
            'w-9 h-9 rounded-xl bg-gradient-to-br from-gold to-sage flex items-center justify-center flex-shrink-0'
          )}
        >
          <Brain size={20} className="text-void" />
        </div>
        <AnimatePresence>
          {sidebarExpanded && (
            <motion.span
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.2 }}
              className="ml-3 text-lg font-bold bg-gradient-to-r from-gold to-sage bg-clip-text text-transparent whitespace-nowrap"
            >
              SLM Studio
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      {/* Nav Items */}
      <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
        {navItems.map((item) => (
          <NavItem
            key={item.label}
            icon={item.icon}
            label={item.label}
            href={item.href}
            isActive={getIsActive(item.label, item.href, pathname)}
            isCollapsed={!sidebarExpanded}
            onClick={() => handleNavigate(item.href)}
          />
        ))}
      </nav>

      {/* Bottom section */}
      <div className="p-2 border-t border-white/[0.06]">
        {/* Toggle button */}
        <button
          onClick={toggleSidebar}
          className={classNames(
            'w-full flex items-center justify-center p-2.5 rounded-button text-fern',
            'hover:bg-white/[0.04] hover:text-ivory transition-colors mb-2',
            'focus-visible:outline-2 focus-visible:outline-gold focus-visible:outline-offset-2'
          )}
          aria-label={sidebarExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          {sidebarExpanded ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
        </button>

        {/* User section */}
        <div
          className={classNames(
            'flex items-center gap-3 p-2 rounded-button',
            'hover:bg-white/[0.04] transition-colors cursor-pointer'
          )}
          onClick={() => handleNavigate('/profile')}
        >
          <Avatar
            name={user?.fullName || 'User'}
            size="sm"
          />
          <AnimatePresence>
            {sidebarExpanded && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="flex-1 min-w-0"
              >
                <p className="text-sm text-ivory truncate">{user?.fullName || 'Demo User'}</p>
                <p className="text-xs text-muted truncate">{user?.email || ''}</p>
              </motion.div>
            )}
          </AnimatePresence>
          {sidebarExpanded && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleLogout();
              }}
              className="p-1.5 rounded-lg text-fern hover:text-rose hover:bg-rose/10 transition-colors"
              aria-label="Logout"
            >
              <LogOut size={14} />
            </button>
          )}
        </div>
      </div>
    </motion.aside>
  );
}

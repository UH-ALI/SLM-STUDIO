'use client';

import { User, Mail, Calendar, Shield } from 'lucide-react';
import { DashboardLayout } from '@/components/templates/DashboardLayout';
import { PageHeader } from '@/components/organisms/PageHeader';
import { Avatar } from '@/components/atoms/Avatar';
import { useAuthStore } from '@/stores/authStore';

export default function ProfilePage() {
  const { user } = useAuthStore();

  return (
    <DashboardLayout>
      <PageHeader
        title="Profile"
        subtitle="Your account information"
      />

      <div className="max-w-2xl">
        <div className="glass-card">
          {/* Header */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-5 mb-8">
            <Avatar name={user?.fullName || 'User'} size="lg" />
            <div>
              <h2 className="text-xl font-bold text-ivory">{user?.fullName || 'Demo User'}</h2>
              <p className="text-sm text-fern">{user?.email || 'demo@slmstudio.ai'}</p>
              <div className="flex items-center gap-2 mt-2">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-mint/10 border border-mint/20 text-xs text-mint">
                  <Shield size={10} />
                  Active
                </span>
              </div>
            </div>
          </div>

          {/* Details */}
          <div className="space-y-4 border-t border-white/[0.06] pt-6">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-lg bg-gold/10 flex items-center justify-center">
                <User size={18} className="text-gold" />
              </div>
              <div>
                <p className="text-xs text-muted uppercase tracking-wider">Username</p>
                <p className="text-sm text-ivory">{user?.username || 'demo_user'}</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-lg bg-sage/10 flex items-center justify-center">
                <Mail size={18} className="text-sage" />
              </div>
              <div>
                <p className="text-xs text-muted uppercase tracking-wider">Email</p>
                <p className="text-sm text-ivory">{user?.email || 'demo@slmstudio.ai'}</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-lg bg-mint/10 flex items-center justify-center">
                <Calendar size={18} className="text-mint" />
              </div>
              <div>
                <p className="text-xs text-muted uppercase tracking-wider">Joined</p>
                <p className="text-sm text-ivory">
                  {user?.createdAt
                    ? new Date(user.createdAt).toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                      })
                    : 'January 15, 2024'}
                </p>
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-8 pt-6 border-t border-white/[0.06]">
            <div className="text-center">
              <p className="font-mono text-xl font-semibold text-gold">6</p>
              <p className="text-xs text-muted">Projects</p>
            </div>
            <div className="text-center">
              <p className="font-mono text-xl font-semibold text-sage">3</p>
              <p className="text-xs text-muted">Datasets</p>
            </div>
            <div className="text-center">
              <p className="font-mono text-xl font-semibold text-mint">4</p>
              <p className="text-xs text-muted">Deployed</p>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

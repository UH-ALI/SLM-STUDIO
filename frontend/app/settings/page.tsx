'use client';

import { useState } from 'react';
import { User, Key, Bell, AlertTriangle } from 'lucide-react';
import { DashboardLayout } from '@/components/templates/DashboardLayout';
import { PageHeader } from '@/components/organisms/PageHeader';
import { Button } from '@/components/atoms/Button';
import { Input } from '@/components/atoms/Input';
import { useAuthStore } from '@/stores/authStore';
import { useUIStore } from '@/stores/uiStore';

export default function SettingsPage() {
  const { user } = useAuthStore();
  const { addToast } = useUIStore();
  const [activeTab, setActiveTab] = useState<'profile' | 'api' | 'notifications'>('profile');

  const handleSave = () => {
    addToast({ type: 'success', message: 'Settings saved' });
  };

  return (
    <DashboardLayout>
      <PageHeader
        title="Settings"
        subtitle="Manage your account and preferences"
      />

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar tabs */}
        <div className="lg:col-span-1">
          <nav className="glass-card !p-2 space-y-1">
            {[
              { id: 'profile' as const, label: 'Profile', icon: User },
              { id: 'api' as const, label: 'API Keys', icon: Key },
              { id: 'notifications' as const, label: 'Notifications', icon: Bell },
            ].map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-button text-sm font-medium transition-all ${
                    activeTab === tab.id
                      ? 'text-gold bg-gold/10'
                      : 'text-fern hover:text-ivory hover:bg-white/[0.04]'
                  }`}
                >
                  <Icon size={18} />
                  {tab.label}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Content */}
        <div className="lg:col-span-3 space-y-6">
          {/* Profile */}
          {activeTab === 'profile' && (
            <div className="glass-card">
              <h3 className="text-sm font-semibold text-ivory mb-1">Profile Settings</h3>
              <p className="text-xs text-fern mb-6">Update your personal information</p>
              <div className="space-y-4 max-w-md">
                <Input label="Full Name" defaultValue={user?.fullName || ''} />
                <Input label="Email" type="email" defaultValue={user?.email || ''} />
                <Input label="Username" defaultValue={user?.username || ''} />
                <Button onClick={handleSave}>Save Changes</Button>
              </div>
            </div>
          )}

          {/* API Keys */}
          {activeTab === 'api' && (
            <div className="glass-card">
              <h3 className="text-sm font-semibold text-ivory mb-1">API Keys</h3>
              <p className="text-xs text-fern mb-6">Manage your API access keys</p>
              <div className="bg-[#121B16]/60 rounded-xl p-4 border border-white/[0.06]">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted uppercase tracking-wider">Production Key</p>
                    <code className="text-sm font-mono text-gold">sk_live_••••••••••••</code>
                  </div>
                  <Button variant="secondary" size="sm">Reveal</Button>
                </div>
              </div>
            </div>
          )}

          {/* Notifications */}
          {activeTab === 'notifications' && (
            <div className="glass-card">
              <h3 className="text-sm font-semibold text-ivory mb-1">Notification Preferences</h3>
              <p className="text-xs text-fern mb-6">Choose what notifications you receive</p>
              <div className="space-y-3">
                {['Training completed', 'Training failed', 'Weekly summary'].map((item) => (
                  <label key={item} className="flex items-center gap-3 cursor-pointer">
                    <input type="checkbox" defaultChecked className="w-4 h-4 rounded border-void/20 text-gold" />
                    <span className="text-sm text-ivory">{item}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Danger Zone */}
          <div className="glass-card border-rose/20">
            <div className="flex items-center gap-3 mb-4">
              <AlertTriangle size={18} className="text-rose" />
              <h3 className="text-sm font-semibold text-rose">Danger Zone</h3>
            </div>
            <p className="text-xs text-fern mb-4">
              Once you delete your account, there is no going back.
            </p>
            <Button variant="danger">Delete Account</Button>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

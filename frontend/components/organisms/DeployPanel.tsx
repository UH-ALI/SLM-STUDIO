'use client';

import { useEffect, useState } from 'react';
import { Copy, Pause, Play, RotateCcw, Zap, Check, AlertTriangle, Palette } from 'lucide-react';
import { classNames } from '@/lib/utils';
import { Badge } from '@/components/atoms/Badge';
import { Button } from '@/components/atoms/Button';
import { useDeployStore, WidgetConfig } from '@/stores/deployStore';
import { useProjectStore } from '@/stores/projectStore';
import { useUIStore } from '@/stores/uiStore';

interface DeployPanelProps {
  projectId: string;
  className?: string;
}

type CodeTab = 'embed' | 'curl';

export function DeployPanel({ projectId, className }: DeployPanelProps) {
  const { config, usage, isLoading, fetchConfig, enableDeploy, disableDeploy, rotateKey, fetchUsage } =
    useDeployStore();
  const { activeProject, fetchProject } = useProjectStore();
  const { addToast } = useUIStore();

  const [activeTab, setActiveTab] = useState<CodeTab>('embed');
  const [copied, setCopied] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [originInput, setOriginInput] = useState('');
  const [isUpdatingConfig, setIsUpdatingConfig] = useState(false);

  // Widget appearance customization state
  const [widgetConfig, setWidgetConfig] = useState<Partial<WidgetConfig>>({
    primaryColor: '#4F46E5',
    bodyColor: '#F8F9FB',
    dotsColor: '#9CA3AF',
    botMessageColor: '#FFFFFF',
    userMessageColor: '',
    chatInputColor: '#FFFFFF',
    title: '',
    greeting: 'Hi! Ask me anything.',
  });

  useEffect(() => {
    fetchProject(projectId).catch(() => {});
    fetchConfig(projectId).catch(() => {});
    fetchUsage(projectId).catch(() => {});
  }, [projectId, fetchProject, fetchConfig, fetchUsage]);

  // Sync widgetConfig state when config loads from server
  useEffect(() => {
    if (config?.widgetConfig) {
      setWidgetConfig((prev) => ({ ...prev, ...config.widgetConfig }));
    }
  }, [config?.widgetConfig]);

  const handleCopy = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  };

  const handleEnable = async () => {
    setActionLoading(true);
    try {
      await enableDeploy(projectId, { isPublic: true });
      addToast({ type: 'success', message: 'Deployment enabled' });
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to enable deployment';
      addToast({ type: 'error', message: detail });
    } finally {
      setActionLoading(false);
    }
  };

  const handlePause = async () => {
    setActionLoading(true);
    try {
      await disableDeploy(projectId);
      addToast({ type: 'success', message: 'Deployment paused' });
    } catch {
      addToast({ type: 'error', message: 'Failed to pause deployment' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleRotate = async () => {
    setActionLoading(true);
    try {
      await rotateKey(projectId);
      addToast({ type: 'success', message: 'Deploy key rotated — the old key no longer works' });
    } catch {
      addToast({ type: 'error', message: 'Failed to rotate deploy key' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleAddOrigin = async () => {
    const trimmed = originInput.trim();
    if (!trimmed) return;
    const current = config?.allowedOrigins ?? [];
    if (current.includes(trimmed)) {
      setOriginInput('');
      return;
    }
    setActionLoading(true);
    try {
      await enableDeploy(projectId, { allowedOrigins: [...current, trimmed] });
      setOriginInput('');
    } catch {
      addToast({ type: 'error', message: 'Failed to add origin' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleRemoveOrigin = async (origin: string) => {
    const current = config?.allowedOrigins ?? [];
    setActionLoading(true);
    try {
      await enableDeploy(projectId, { allowedOrigins: current.filter((o) => o !== origin) });
    } catch {
      addToast({ type: 'error', message: 'Failed to remove origin' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleUpdateWidgetConfig = async () => {
    setIsUpdatingConfig(true);
    try {
      await enableDeploy(projectId, { widgetConfig });
      addToast({ type: 'success', message: 'Widget appearance updated' });
    } catch {
      addToast({ type: 'error', message: 'Failed to update widget appearance' });
    } finally {
      setIsUpdatingConfig(false);
    }
  };

  const isTrained = activeProject?.status === 'completed';
  const isPublic = config?.isPublic ?? false;

  const curlSnippet = config?.deployKey
    ? `curl -X POST ${(process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1').replace('/api/v1', '')}/deploy/${config.deployKey}/chat \\
  -H "Content-Type: application/json" \\
  -d '{"message": "Hello!"}'`
    : '';

  if (isLoading && !config) {
    return (
      <div className={classNames('glass-card text-center py-8', className)}>
        <p className="text-sm text-muted">Loading deployment status…</p>
      </div>
    );
  }

  // Hasn't been trained yet — show the gate instead of a deploy panel that
  // would just 400 on every action. Matches the backend's actual guard in
  // POST /projects/{id}/deploy (requires a completed TrainingJob).
  if (!isTrained) {
    return (
      <div className={classNames('glass-card text-center py-10 space-y-3', className)}>
        <AlertTriangle size={28} className="text-gold mx-auto" />
        <p className="text-sm font-medium text-ivory">Train this project before deploying</p>
        <p className="text-xs text-muted max-w-sm mx-auto">
          Deployment needs at least one completed training run so there&apos;s a model to serve.
        </p>
      </div>
    );
  }

  // Color input helper
  const colorField = (label: string, key: keyof WidgetConfig, placeholder = '#000000') => (
    <div>
      <label className="block text-xs text-fern mb-1.5">{label}</label>
      <div className="flex items-center gap-2">
        <input
          type="color"
          value={(widgetConfig[key] as string) || placeholder}
          onChange={(e) => setWidgetConfig((prev) => ({ ...prev, [key]: e.target.value }))}
          className="w-8 h-8 rounded-lg border border-white/[0.06] cursor-pointer bg-transparent p-0"
        />
        <input
          type="text"
          value={(widgetConfig[key] as string) || ''}
          onChange={(e) => setWidgetConfig((prev) => ({ ...prev, [key]: e.target.value }))}
          placeholder={placeholder}
          className="flex-1 bg-[#121B16]/60 border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-ivory font-mono placeholder:text-muted outline-none focus:border-gold/40"
        />
      </div>
    </div>
  );

  return (
    <div className={classNames('space-y-6', className)}>
      {/* Status */}
      <div className="glass-card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Badge variant={isPublic ? 'deployed' : 'ready'}>{isPublic ? 'Live' : 'Paused'}</Badge>
            <span className="text-sm text-fern">
              {isPublic ? 'Deployed and ready to receive chats' : 'Not currently public'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {isPublic ? (
              <Button variant="secondary" icon={Pause} size="sm" onClick={handlePause} disabled={actionLoading}>
                Pause
              </Button>
            ) : (
              <Button variant="primary" icon={Play} size="sm" onClick={handleEnable} disabled={actionLoading}>
                Go live
              </Button>
            )}
            {config?.deployKey && (
              <Button variant="secondary" icon={RotateCcw} size="sm" onClick={handleRotate} disabled={actionLoading}>
                Regenerate key
              </Button>
            )}
          </div>
        </div>

        {config?.publicChatUrl && (
          <div className="bg-[#121B16]/60 rounded-xl p-3 border border-white/[0.06]">
            <p className="text-[0.65rem] text-muted uppercase tracking-wider mb-1.5">Public Chat Endpoint</p>
            <div className="flex items-center gap-2">
              <code className="flex-1 text-xs font-mono text-gold break-all">{config.publicChatUrl}</code>
              <button
                onClick={() => handleCopy(config.publicChatUrl!, 'url')}
                className="flex-shrink-0 p-1.5 rounded-lg text-fern hover:text-gold hover:bg-gold/10 transition-colors"
                aria-label="Copy endpoint"
              >
                {copied === 'url' ? <Check size={14} className="text-mint" /> : <Copy size={14} />}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Integration Code */}
      {config?.embedScript && (
        <div className="glass-card">
          <h3 className="text-sm font-semibold text-ivory mb-3">Integration Code</h3>

          <div className="flex gap-1 p-1 bg-[#121B16]/60 rounded-xl mb-3">
            {(['embed', 'curl'] as CodeTab[]).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={classNames(
                  'flex-1 py-1.5 text-xs font-medium rounded-lg transition-all',
                  activeTab === tab ? 'bg-gold/15 text-gold' : 'text-fern hover:text-ivory'
                )}
              >
                {tab === 'embed' ? 'Embed Widget' : 'cURL'}
              </button>
            ))}
          </div>

          <div className="relative bg-[#0A0F0C] rounded-xl p-4 border border-white/[0.06] overflow-x-auto">
            <pre className="text-xs font-mono text-ivory/90 leading-relaxed whitespace-pre-wrap break-all">
              <code>{activeTab === 'embed' ? config.embedScript : curlSnippet}</code>
            </pre>
            <button
              onClick={() => handleCopy(activeTab === 'embed' ? config.embedScript! : curlSnippet, 'code')}
              className="absolute top-3 right-3 p-1.5 rounded-lg bg-white/[0.06] text-fern hover:text-gold transition-colors"
              aria-label="Copy code"
            >
              {copied === 'code' ? <Check size={14} className="text-mint" /> : <Copy size={14} />}
            </button>
          </div>
          <p className="text-xs text-muted mt-2">
            Paste this snippet before <code className="text-fern">&lt;/body&gt;</code> on any page to add the chat
            widget.
          </p>
        </div>
      )}

      {/* Widget Appearance Customization */}
      <div className="glass-card">
        <div className="flex items-center gap-2 mb-4">
          <Palette size={16} className="text-gold" />
          <h3 className="text-sm font-semibold text-ivory">Widget Appearance</h3>
        </div>

        <div className="space-y-4">
          {/* Text Fields */}
          <div>
            <label className="block text-xs text-fern mb-1.5">Widget Title</label>
            <input
              type="text"
              value={widgetConfig.title || ''}
              onChange={(e) => setWidgetConfig((prev) => ({ ...prev, title: e.target.value }))}
              placeholder={activeProject?.name || 'My Bot'}
              className="w-full bg-[#121B16]/60 border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-ivory placeholder:text-muted outline-none focus:border-gold/40"
            />
          </div>
          <div>
            <label className="block text-xs text-fern mb-1.5">Greeting Message</label>
            <input
              type="text"
              value={widgetConfig.greeting || ''}
              onChange={(e) => setWidgetConfig((prev) => ({ ...prev, greeting: e.target.value }))}
              placeholder="Hi! Ask me anything."
              className="w-full bg-[#121B16]/60 border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-ivory placeholder:text-muted outline-none focus:border-gold/40"
            />
          </div>

          {/* Color Fields */}
          <div className="grid grid-cols-2 gap-4">
            {colorField('Widget Title Bar Color', 'primaryColor', '#4F46E5')}
            {colorField('Chat Background Color', 'bodyColor', '#F8F9FB')}
            {colorField('Typing Indicator Dots', 'dotsColor', '#9CA3AF')}
            {colorField('Bot Message Bubble', 'botMessageColor', '#FFFFFF')}
            {colorField('User Message Bubble', 'userMessageColor', '#4F46E5')}
            {colorField('Message Input Area', 'chatInputColor', '#FFFFFF')}
          </div>

          <Button
            variant="primary"
            size="sm"
            onClick={handleUpdateWidgetConfig}
            disabled={isUpdatingConfig}
            className="w-full"
          >
            {isUpdatingConfig ? 'Saving…' : 'Save Appearance'}
          </Button>
        </div>
      </div>

      {/* Allowed Origins — opt-in restriction; empty list means any site can embed */}
      <div className="glass-card">
        <h3 className="text-sm font-semibold text-ivory mb-1">Allowed Origins</h3>
        <p className="text-xs text-muted mb-3">
          Optional. Leave empty to allow the widget on any site. Add domains to restrict it to only those.
        </p>
        <div className="flex gap-2 mb-3">
          <input
            type="text"
            value={originInput}
            onChange={(e) => setOriginInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handleAddOrigin();
              }
            }}
            placeholder="https://example.com"
            className="flex-1 bg-[#121B16]/60 border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-ivory placeholder:text-muted outline-none focus:border-gold/40"
          />
          <Button variant="secondary" size="sm" onClick={handleAddOrigin} disabled={actionLoading || !originInput.trim()}>
            Add
          </Button>
        </div>
        {config?.allowedOrigins && config.allowedOrigins.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {config.allowedOrigins.map((origin) => (
              <span
                key={origin}
                className="flex items-center gap-1.5 text-xs font-mono bg-[#121B16]/60 border border-white/[0.06] rounded-full px-3 py-1 text-fern"
              >
                {origin}
                <button
                  onClick={() => handleRemoveOrigin(origin)}
                  disabled={actionLoading}
                  className="text-muted hover:text-rose transition-colors"
                  aria-label={`Remove ${origin}`}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted">No restrictions — widget works on any site.</p>
        )}
      </div>

      {/* Usage Stats — real per-day message counts from the last 30 days */}
      <div className="glass-card">
        <h3 className="text-sm font-semibold text-ivory mb-3">Usage (last 30 days)</h3>
        {usage.length === 0 ? (
          <p className="text-xs text-muted">No messages yet — usage will appear here once the widget is live.</p>
        ) : (
          <div className="grid grid-cols-3 gap-3">
            <div className="glass-card !p-3 text-center">
              <p className="font-mono text-lg font-semibold text-gold">
                {usage.reduce((sum, d) => sum + d.messages, 0)}
              </p>
              <p className="text-[0.65rem] text-muted uppercase tracking-wider">Total Messages</p>
            </div>
            <div className="glass-card !p-3 text-center">
              <p className="font-mono text-lg font-semibold text-sage">{usage.length}</p>
              <p className="text-[0.65rem] text-muted uppercase tracking-wider">Active Days</p>
            </div>
            <div className="glass-card !p-3 text-center">
              <p className="font-mono text-lg font-semibold text-mint">
                {usage[0]?.messages ?? 0}
              </p>
              <p className="text-[0.65rem] text-muted uppercase tracking-wider">Most Recent Day</p>
            </div>
          </div>
        )}
      </div>

      {/* Model Version */}
      <div className="glass-card">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-gold/20 to-sage/20 flex items-center justify-center">
              <Zap size={18} className="text-gold" />
            </div>
            <div>
              <p className="text-sm font-medium text-ivory">Model</p>
              <p className="text-xs text-fern">{activeProject?.baseModelName || 'Unknown'}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

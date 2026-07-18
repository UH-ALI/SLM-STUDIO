'use client';

import { useEffect, useState } from 'react';
import { Copy, Pause, Play, RotateCcw, Zap, Check, AlertTriangle } from 'lucide-react';
import { classNames } from '@/lib/utils';
import { Badge } from '@/components/atoms/Badge';
import { Button } from '@/components/atoms/Button';
import { useDeployStore } from '@/stores/deployStore';
import { useProjectStore } from '@/stores/projectStore';
import { useUIStore } from '@/stores/uiStore';

interface DeployPanelProps {
  projectId: string;
  className?: string;
}

type CodeTab = 'embed' | 'curl';

// Picks readable text (near-black or white) against an arbitrary hex
// background, so the color-picker preview swatches and, in principle, any
// custom widget color stays legible regardless of what the user chooses.
function getContrastColor(hexColor: string) {
  if (!hexColor || !/^#[0-9A-Fa-f]{6}$/i.test(hexColor)) return '#FFFFFF';
  const r = parseInt(hexColor.slice(1, 3), 16);
  const g = parseInt(hexColor.slice(3, 5), 16);
  const b = parseInt(hexColor.slice(5, 7), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.5 ? '#111827' : '#FFFFFF';
}

export function DeployPanel({ projectId, className }: DeployPanelProps) {
  const { config, usage, isLoading, fetchConfig, enableDeploy, disableDeploy, rotateKey, fetchUsage } =
    useDeployStore();
  const { activeProject, fetchProject } = useProjectStore();
  const { addToast } = useUIStore();

  const [activeTab, setActiveTab] = useState<CodeTab>('embed');
  const [copied, setCopied] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [originInput, setOriginInput] = useState('');

  const [widgetConfig, setWidgetConfig] = useState<{
    title: string;
    greeting: string;
    primaryColor: string;
    bodyColor: string;
    dotsColor: string;
    botMessageColor: string;
    userMessageColor: string;
    chatInputColor: string;
    position: 'bottom-right' | 'bottom-left';
  }>({
    title: '',
    greeting: 'Hi! Ask me anything.',
    primaryColor: '#4F46E5',
    bodyColor: '#FFFFFF',
    dotsColor: '#9CA3AF',
    botMessageColor: '#2A3441',
    userMessageColor: '#4F46E5',
    chatInputColor: '#FFFFFF',
    position: 'bottom-right',
  });

  // Keep the color-picker form in sync whenever the server config loads/changes.
  useEffect(() => {
    if (config?.widgetConfig) {
      setWidgetConfig({
        title: config.widgetConfig.title || '',
        greeting: config.widgetConfig.greeting || 'Hi! Ask me anything.',
        primaryColor: config.widgetConfig.primaryColor || '#4F46E5',
        bodyColor: config.widgetConfig.bodyColor || '#FFFFFF',
        dotsColor: config.widgetConfig.dotsColor || '#9CA3AF',
        botMessageColor: config.widgetConfig.botMessageColor || '#2A3441',
        userMessageColor: config.widgetConfig.userMessageColor || config.widgetConfig.primaryColor || '#4F46E5',
        chatInputColor: config.widgetConfig.chatInputColor || '#FFFFFF',
        position: (config.widgetConfig.position as 'bottom-right' | 'bottom-left') || 'bottom-right',
      });
    }
  }, [config]);

  useEffect(() => {
    fetchProject(projectId).catch(() => {});
    fetchConfig(projectId).catch(() => {});
    fetchUsage(projectId).catch(() => {});
  }, [projectId, fetchProject, fetchConfig, fetchUsage]);

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
    setActionLoading(true);
    try {
      await enableDeploy(projectId, { widgetConfig });
      addToast({ type: 'success', message: 'Widget configuration updated' });
    } catch {
      addToast({ type: 'error', message: 'Failed to update widget configuration' });
    } finally {
      setActionLoading(false);
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

  return (
    <div className={classNames('space-y-6', className)}>
      {/* Status */}
      <div className="glass-card">
        <div className="flex flex-col gap-4 mb-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <Badge variant={isPublic ? 'deployed' : 'ready'}>{isPublic ? 'Live' : 'Paused'}</Badge>
            <span className="text-sm text-fern">
              {isPublic ? 'Deployed and ready to receive chats' : 'Not currently public'}
            </span>
          </div>
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
            {isPublic ? (
              <Button variant="secondary" icon={Pause} size="sm" className="w-full sm:w-auto" onClick={handlePause} disabled={actionLoading}>
                Pause
              </Button>
            ) : (
              <Button variant="primary" icon={Play} size="sm" className="w-full sm:w-auto" onClick={handleEnable} disabled={actionLoading}>
                Go live
              </Button>
            )}
            {config?.deployKey && (
              <Button variant="secondary" icon={RotateCcw} size="sm" className="w-full sm:w-auto" onClick={handleRotate} disabled={actionLoading}>
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

      {/* Allowed Origins — opt-in restriction; empty list means any site can embed */}
      <div className="glass-card">
        <h3 className="text-sm font-semibold text-ivory mb-1">Allowed Origins</h3>
        <p className="text-xs text-muted mb-3">
          Optional. Leave empty to allow the widget on any site. Add domains to restrict it to only those.
        </p>
        <div className="flex flex-col sm:flex-row gap-2 mb-3">
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
          <Button variant="secondary" size="sm" className="w-full sm:w-auto" onClick={handleAddOrigin} disabled={actionLoading || !originInput.trim()}>
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

      {/* Widget Customization */}
      <div className="glass-card">
        <h3 className="text-sm font-semibold text-ivory mb-1">Widget Customization</h3>
        <p className="text-xs text-muted mb-4">
          Customize the appearance and greeting of the chat widget on your website.
        </p>
        <div className="space-y-4 max-w-lg">
          <div>
            <label className="block text-xs text-fern mb-1.5">Widget Title</label>
            <input
              type="text"
              value={widgetConfig.title}
              onChange={(e) => setWidgetConfig((prev) => ({ ...prev, title: e.target.value }))}
              placeholder={activeProject?.name || 'Assistant'}
              className="w-full bg-[#121B16]/60 border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-ivory placeholder:text-muted outline-none focus:border-gold/40"
            />
          </div>
          <div>
            <label className="block text-xs text-fern mb-1.5">Greeting Message</label>
            <input
              type="text"
              value={widgetConfig.greeting}
              onChange={(e) => setWidgetConfig((prev) => ({ ...prev, greeting: e.target.value }))}
              placeholder="Hi! Ask me anything."
              className="w-full bg-[#121B16]/60 border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-ivory placeholder:text-muted outline-none focus:border-gold/40"
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-fern mb-1.5">Header Background</label>
              <div className="flex gap-2">
                <input
                  type="color"
                  value={widgetConfig.primaryColor}
                  onChange={(e) => setWidgetConfig((prev) => ({ ...prev, primaryColor: e.target.value }))}
                  className="w-8 h-8 rounded border-none cursor-pointer p-0 bg-transparent"
                />
                <input
                  type="text"
                  value={widgetConfig.primaryColor}
                  style={{ color: getContrastColor(widgetConfig.primaryColor), backgroundColor: widgetConfig.primaryColor }}
                  onChange={(e) => setWidgetConfig((prev) => ({ ...prev, primaryColor: e.target.value }))}
                  className="flex-1 border border-white/[0.06] rounded-lg px-3 py-1 text-sm font-mono outline-none uppercase transition-colors"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-fern mb-1.5">Chat Window Background</label>
              <div className="flex gap-2">
                <input
                  type="color"
                  value={widgetConfig.bodyColor}
                  onChange={(e) => setWidgetConfig((prev) => ({ ...prev, bodyColor: e.target.value }))}
                  className="w-8 h-8 rounded border-none cursor-pointer p-0 bg-transparent"
                />
                <input
                  type="text"
                  value={widgetConfig.bodyColor}
                  style={{ color: getContrastColor(widgetConfig.bodyColor), backgroundColor: widgetConfig.bodyColor }}
                  onChange={(e) => setWidgetConfig((prev) => ({ ...prev, bodyColor: e.target.value }))}
                  className="flex-1 border border-white/[0.06] rounded-lg px-3 py-1 text-sm font-mono outline-none uppercase transition-colors"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-fern mb-1.5">Typing Indicator</label>
              <div className="flex gap-2">
                <input
                  type="color"
                  value={widgetConfig.dotsColor}
                  onChange={(e) => setWidgetConfig((prev) => ({ ...prev, dotsColor: e.target.value }))}
                  className="w-8 h-8 rounded border-none cursor-pointer p-0 bg-transparent"
                />
                <input
                  type="text"
                  value={widgetConfig.dotsColor}
                  onChange={(e) => setWidgetConfig((prev) => ({ ...prev, dotsColor: e.target.value }))}
                  className="flex-1 bg-[#121B16]/60 border border-white/[0.06] rounded-lg px-3 py-1 text-sm font-mono text-ivory outline-none focus:border-gold/40 uppercase"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-fern mb-1.5">Bot Message Bubble</label>
              <div className="flex gap-2">
                <input
                  type="color"
                  value={widgetConfig.botMessageColor}
                  onChange={(e) => setWidgetConfig((prev) => ({ ...prev, botMessageColor: e.target.value }))}
                  className="w-8 h-8 rounded border-none cursor-pointer p-0 bg-transparent"
                />
                <input
                  type="text"
                  value={widgetConfig.botMessageColor}
                  style={{ color: getContrastColor(widgetConfig.botMessageColor), backgroundColor: widgetConfig.botMessageColor }}
                  onChange={(e) => setWidgetConfig((prev) => ({ ...prev, botMessageColor: e.target.value }))}
                  className="flex-1 border border-white/[0.06] rounded-lg px-3 py-1 text-sm font-mono outline-none uppercase transition-colors"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-fern mb-1.5">User Message Bubble</label>
              <div className="flex gap-2">
                <input
                  type="color"
                  value={widgetConfig.userMessageColor}
                  onChange={(e) => setWidgetConfig((prev) => ({ ...prev, userMessageColor: e.target.value }))}
                  className="w-8 h-8 rounded border-none cursor-pointer p-0 bg-transparent"
                />
                <input
                  type="text"
                  value={widgetConfig.userMessageColor}
                  style={{ color: getContrastColor(widgetConfig.userMessageColor), backgroundColor: widgetConfig.userMessageColor }}
                  onChange={(e) => setWidgetConfig((prev) => ({ ...prev, userMessageColor: e.target.value }))}
                  className="flex-1 border border-white/[0.06] rounded-lg px-3 py-1 text-sm font-mono outline-none uppercase transition-colors"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-fern mb-1.5">Message Input Area</label>
              <div className="flex gap-2">
                <input
                  type="color"
                  value={widgetConfig.chatInputColor}
                  onChange={(e) => setWidgetConfig((prev) => ({ ...prev, chatInputColor: e.target.value }))}
                  className="w-8 h-8 rounded border-none cursor-pointer p-0 bg-transparent"
                />
                <input
                  type="text"
                  value={widgetConfig.chatInputColor}
                  style={{ color: getContrastColor(widgetConfig.chatInputColor), backgroundColor: widgetConfig.chatInputColor }}
                  onChange={(e) => setWidgetConfig((prev) => ({ ...prev, chatInputColor: e.target.value }))}
                  className="flex-1 border border-white/[0.06] rounded-lg px-3 py-1 text-sm font-mono outline-none uppercase transition-colors"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-fern mb-1.5">Position</label>
              <select
                value={widgetConfig.position}
                onChange={(e) => setWidgetConfig((prev) => ({ ...prev, position: e.target.value as 'bottom-right' | 'bottom-left' }))}
                className="w-full h-[34px] bg-[#121B16]/60 border border-white/[0.06] rounded-lg px-3 py-1 text-sm text-ivory outline-none focus:border-gold/40 appearance-none"
              >
                <option value="bottom-right">Bottom Right</option>
                <option value="bottom-left">Bottom Left</option>
              </select>
            </div>
          </div>
          <div className="pt-2">
            <Button variant="secondary" size="sm" onClick={handleUpdateWidgetConfig} disabled={actionLoading}>
              Save Appearance
            </Button>
          </div>
        </div>
      </div>

      {/* Usage Stats — real per-day message counts from the last 30 days */}
      <div className="glass-card">
        <h3 className="text-sm font-semibold text-ivory mb-3">Usage (last 30 days)</h3>
        {usage.length === 0 ? (
          <p className="text-xs text-muted">No messages yet — usage will appear here once the widget is live.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
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

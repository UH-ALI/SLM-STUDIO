import * as LucideIcons from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { classNames } from '@/lib/utils';

const iconMap: Record<string, LucideIcon> = {
  home: LucideIcons.Home,
  dashboard: LucideIcons.LayoutDashboard,
  datasets: LucideIcons.Database,
  models: LucideIcons.Brain,
  settings: LucideIcons.Settings,
  profile: LucideIcons.User,
  logout: LucideIcons.LogOut,
  bell: LucideIcons.Bell,
  plus: LucideIcons.Plus,
  upload: LucideIcons.Upload,
  brain: LucideIcons.Brain,
  rocket: LucideIcons.Rocket,
  graduationCap: LucideIcons.GraduationCap,
  briefcase: LucideIcons.Briefcase,
  trendingUp: LucideIcons.TrendingUp,
  heartPulse: LucideIcons.HeartPulse,
  scale: LucideIcons.Scale,
  globe: LucideIcons.Globe,
  check: LucideIcons.Check,
  chevronRight: LucideIcons.ChevronRight,
  chevronLeft: LucideIcons.ChevronLeft,
  chevronDown: LucideIcons.ChevronDown,
  search: LucideIcons.Search,
  trash: LucideIcons.Trash2,
  edit: LucideIcons.Pencil,
  copy: LucideIcons.Copy,
  close: LucideIcons.X,
  alertCircle: LucideIcons.AlertCircle,
  alertTriangle: LucideIcons.AlertTriangle,
  info: LucideIcons.Info,
  thumbsUp: LucideIcons.ThumbsUp,
  thumbsDown: LucideIcons.ThumbsDown,
  arrowUp: LucideIcons.ArrowUp,
  sprout: LucideIcons.Sprout,
  sparkles: LucideIcons.Sparkles,
  shield: LucideIcons.Shield,
  lock: LucideIcons.Lock,
  key: LucideIcons.Key,
  moreHorizontal: LucideIcons.MoreHorizontal,
  moreVertical: LucideIcons.MoreVertical,
  eye: LucideIcons.Eye,
  eyeOff: LucideIcons.EyeOff,
  menu: LucideIcons.Menu,
  send: LucideIcons.Send,
  download: LucideIcons.Download,
  fileText: LucideIcons.FileText,
  folder: LucideIcons.Folder,
  star: LucideIcons.Star,
  zap: LucideIcons.Zap,
  activity: LucideIcons.Activity,
  terminal: LucideIcons.Terminal,
  code: LucideIcons.Code,
  cpu: LucideIcons.Cpu,
  server: LucideIcons.Server,
  clock: LucideIcons.Clock,
  calendar: LucideIcons.Calendar,
  refreshCw: LucideIcons.RefreshCw,
  play: LucideIcons.Play,
  pause: LucideIcons.Pause,
  stopCircle: LucideIcons.StopCircle,
  rotateCcw: LucideIcons.RotateCcw,
};

interface IconProps {
  name: string;
  size?: number;
  strokeWidth?: number;
  className?: string;
}

export function Icon({ name, size = 24, strokeWidth = 2, className }: IconProps) {
  const IconComponent = iconMap[name] || LucideIcons.HelpCircle;

  return (
    <IconComponent
      size={size}
      strokeWidth={strokeWidth}
      className={classNames('inline-block', className)}
    />
  );
}

import React from 'react';
import {
  LayoutDashboard,
  UploadCloud,
  Users,
  FileText,
  History,
  AlertTriangle,
  Settings,
  ShieldCheck,
  Building2,
  Calendar,
  Sparkles
} from 'lucide-react';

interface SidebarProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
  reviewCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, onSelectTab, reviewCount }) => {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'upload', label: 'Upload Reports', icon: UploadCloud },
    { id: 'monitoring', label: 'Guest Monitoring', icon: Users },
    { id: 'records', label: 'All Guest Records', icon: FileText },
    { id: 'history', label: 'Report History', icon: History },
    {
      id: 'review',
      label: 'Review Queue',
      icon: AlertTriangle,
      badge: reviewCount > 0 ? reviewCount : undefined
    },
    { id: 'settings', label: 'Settings', icon: Settings },
    { id: 'audit', label: 'Audit Log', icon: ShieldCheck },
  ];

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col flex-shrink-0 min-h-screen text-slate-300">
      {/* Brand & Tagline */}
      <div className="p-5 border-b border-slate-800/80">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-amber-600 flex items-center justify-center text-slate-950 font-black text-xl shadow-lg shadow-amber-500/20">
            S6
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-1.5">
              StayTrack
              <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">
                PRO
              </span>
            </h1>
            <p className="text-[11px] text-slate-400 font-medium">Daily Reports. Continuous Insights.</p>
          </div>
        </div>

        {/* Property Selector */}
        <div className="mt-4 px-3 py-2 rounded-lg bg-slate-800/60 border border-slate-700/50 flex items-center gap-2.5">
          <Building2 className="w-4 h-4 text-amber-400 shrink-0" />
          <div className="overflow-hidden">
            <div className="text-xs font-semibold text-slate-200 truncate">STUDIO 6 - STAFFORD, VA</div>
            <div className="text-[10px] text-slate-400 font-mono">Property #3756</div>
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        <div className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Operations
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? 'bg-amber-500 text-slate-950 font-semibold shadow-md shadow-amber-500/20'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/70'
              }`}
            >
              <div className="flex items-center gap-3">
                <Icon className={`w-4 h-4 ${isActive ? 'text-slate-950' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && (
                <span
                  className={`text-xs px-2 py-0.5 rounded-full font-bold ${
                    isActive ? 'bg-slate-950 text-amber-400' : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer / Operator Info */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/40">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-amber-400 text-xs">
            PP
          </div>
          <div className="overflow-hidden flex-1">
            <div className="text-xs font-semibold text-slate-200 truncate">Pratik Patel</div>
            <div className="text-[11px] text-slate-500 truncate">Motel Owner (Admin)</div>
          </div>
        </div>
      </div>
    </aside>
  );
};

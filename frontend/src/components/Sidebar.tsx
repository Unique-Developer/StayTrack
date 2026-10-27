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
  LogOut,
  X
} from 'lucide-react';
import { User } from '../types';
import { useProperty } from '../context/PropertyContext';
import { MotelSwitcher } from './MotelSwitcher';

interface SidebarProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
  reviewCount: number;
  user?: User | null;
  onLogout?: () => void;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  reviewCount,
  user,
  onLogout,
  mobileOpen = false,
  onMobileClose
}) => {
  const { currentPropertyId, currentProperty } = useProperty();

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

  const getInitials = (name?: string) => {
    if (!name) return 'U';
    const parts = name.trim().split(' ');
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  };

  const handleNavClick = (tab: string) => {
    onSelectTab(tab);
    if (onMobileClose) onMobileClose();
  };

  const sidebarContent = (
    <div className="flex flex-col h-full">
      {/* Brand & Tagline */}
      <div className="p-5 border-b border-slate-800/80">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-amber-600 flex items-center justify-center text-slate-950 font-black text-xl shadow-lg shadow-amber-500/20">
              {currentPropertyId === 2 ? 'M6' : 'S6'}
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

          {onMobileClose && (
            <button
              onClick={onMobileClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 md:hidden cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Motel Switcher Segmented Pills */}
        <div className="mt-4">
          <MotelSwitcher variant="sidebar" />
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
              onClick={() => handleNavClick(item.id)}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all cursor-pointer ${
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

      {/* Footer / Operator Info & Logout */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/40 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-amber-400 text-xs shrink-0 select-none">
              {getInitials(user?.full_name)}
            </div>
            <div className="overflow-hidden flex-1">
              <div className="text-xs font-semibold text-slate-200 truncate">
                {user?.full_name || 'Motel Staff'}
              </div>
              <div className="text-[11px] text-slate-500 truncate capitalize">
                {user?.role || 'User'} ({user?.email || 'Logged in'})
              </div>
            </div>
          </div>

          {onLogout && (
            <button
              onClick={onLogout}
              className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors cursor-pointer shrink-0"
              title="Sign Out"
              aria-label="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Persistent Sidebar */}
      <aside className="hidden md:flex w-64 bg-slate-900 border-r border-slate-800 flex-col flex-shrink-0 min-h-screen text-slate-300">
        {sidebarContent}
      </aside>

      {/* Mobile Slide-Over Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden animate-in fade-in duration-200">
          <div
            className="fixed inset-0 bg-black/80 backdrop-blur-sm"
            onClick={onMobileClose}
          />
          <aside className="relative w-72 max-w-[85vw] bg-slate-900 border-r border-slate-800 flex flex-col min-h-screen text-slate-300 shadow-2xl z-10 animate-in slide-in-from-left duration-200">
            {sidebarContent}
          </aside>
        </div>
      )}
    </>
  );
};

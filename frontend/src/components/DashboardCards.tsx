import React from 'react';
import {
  FileCheck2,
  CalendarDays,
  UserCheck,
  Flame,
  AlertTriangle,
  CalendarOff
} from 'lucide-react';
import { DashboardSummary } from '../types';

interface DashboardCardsProps {
  summary: DashboardSummary;
  onNavigate: (tab: string) => void;
}

export const DashboardCards: React.FC<DashboardCardsProps> = ({ summary, onNavigate }) => {
  const cards = [
    {
      title: 'Total Reports Imported',
      value: summary.total_reports_imported,
      subtext: `${summary.reporting_dates_covered} distinct dates`,
      icon: FileCheck2,
      color: 'from-blue-500/20 to-blue-600/10 text-blue-400 border-blue-500/30',
      actionTab: 'history'
    },
    {
      title: 'Reporting Dates Covered',
      value: `${summary.reporting_dates_covered}`,
      subtext: `${summary.window_coverage_pct}% rolling coverage`,
      icon: CalendarDays,
      color: 'from-cyan-500/20 to-cyan-600/10 text-cyan-400 border-cyan-500/30',
      actionTab: 'history'
    },
    {
      title: 'Unique Guest Identities',
      value: summary.unique_guest_identities,
      subtext: 'Reconciled across reports',
      icon: UserCheck,
      color: 'from-purple-500/20 to-purple-600/10 text-purple-400 border-purple-500/30',
      actionTab: 'records'
    },
    {
      title: 'Continuous-Stay Guests',
      value: summary.continuous_stay_count,
      subtext: '>= 30 days continuous (Mode A)',
      icon: Flame,
      color: 'from-amber-500/20 to-amber-600/10 text-amber-400 border-amber-500/30',
      actionTab: 'monitoring'
    },
    {
      title: 'Requiring Verification',
      value: summary.needs_verification_count,
      subtext: 'Needs owner review',
      icon: AlertTriangle,
      color: summary.needs_verification_count > 0
        ? 'from-rose-500/20 to-rose-600/10 text-rose-400 border-rose-500/30 animate-pulse'
        : 'from-slate-800 to-slate-900 text-slate-400 border-slate-700',
      actionTab: 'review'
    },
    {
      title: 'Missing Reporting Dates',
      value: summary.missing_reporting_dates_count,
      subtext: summary.missing_reporting_dates_count > 0 ? `${summary.missing_dates.join(', ')}` : 'Zero gaps detected',
      icon: CalendarOff,
      color: summary.missing_reporting_dates_count > 0
        ? 'from-amber-600/20 to-amber-700/10 text-amber-300 border-amber-500/40'
        : 'from-emerald-500/20 to-emerald-600/10 text-emerald-400 border-emerald-500/30',
      actionTab: 'history'
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
      {cards.map((c, i) => {
        const Icon = c.icon;
        return (
          <div
            key={i}
            onClick={() => onNavigate(c.actionTab)}
            className="group cursor-pointer rounded-xl bg-slate-900/90 border border-slate-800 p-4 transition-all duration-200 hover:border-slate-700 hover:bg-slate-850 hover:shadow-lg relative overflow-hidden"
          >
            {/* Top Row: Icon + Value */}
            <div className="flex items-center justify-between">
              <div className={`p-2.5 rounded-lg bg-gradient-to-br border ${c.color}`}>
                <Icon className="w-5 h-5" />
              </div>
              <div className="text-2xl font-black text-white tracking-tight">{c.value}</div>
            </div>

            {/* Bottom Row: Title + Subtext */}
            <div className="mt-3">
              <div className="text-xs font-semibold text-slate-300 group-hover:text-amber-400 transition-colors">
                {c.title}
              </div>
              <div className="text-[11px] text-slate-400 truncate mt-0.5" title={c.subtext}>
                {c.subtext}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

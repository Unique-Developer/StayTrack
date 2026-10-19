import React, { useState, useEffect } from 'react';
import { Settings, Save, RefreshCw, CheckCircle2, ShieldCheck, Database, Sliders } from 'lucide-react';
import { api } from '../services/api';
import { SystemSettings } from '../types';

export const SettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.getSettings()
      .then((res) => setSettings(res))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!settings) return;
    setSaving(true);
    setSuccess(false);

    try {
      const updated = await api.updateSettings(settings);
      setSettings(updated);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 4000);
    } catch (err: any) {
      alert(err.message || 'Failed to update settings');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
          <Settings className="w-6 h-6 text-amber-400" /> System & Analytics Settings
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Configure rolling window calculation rules, continuous stay thresholds, and property conventions.
        </p>
      </div>

      {success && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm flex items-center gap-3">
          <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
          <span>Settings saved successfully. Rolling window analytics recalculated!</span>
        </div>
      )}

      {loading ? (
        <div className="py-12 text-center text-slate-500 animate-pulse">Loading settings...</div>
      ) : settings ? (
        <form onSubmit={handleSave} className="space-y-6">
          {/* Card 1: Rolling Window & Analytics Parameters */}
          <div className="p-6 rounded-xl bg-slate-900 border border-slate-800 space-y-5">
            <h2 className="text-sm font-bold text-amber-400 uppercase tracking-wider flex items-center gap-2">
              <Sliders className="w-4 h-4" /> Analytics Parameters
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Rolling Window Size (Distinct Reporting Dates)
                </label>
                <input
                  type="number"
                  min={1}
                  max={365}
                  value={settings.rolling_window_days}
                  onChange={(e) => setSettings({ ...settings, rolling_window_days: parseInt(e.target.value) || 30 })}
                  className="w-full px-3.5 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white font-mono text-sm focus:border-amber-400 focus:outline-none"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  Default 30 distinct dates. Works from Day 1 without requiring 30 files.
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Mode A: Continuous Stay Threshold (Days)
                </label>
                <input
                  type="number"
                  min={1}
                  max={365}
                  value={settings.continuous_stay_days}
                  onChange={(e) => setSettings({ ...settings, continuous_stay_days: parseInt(e.target.value) || 30 })}
                  className="w-full px-3.5 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white font-mono text-sm focus:border-amber-400 focus:outline-none"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  Consecutive calendar days required for long-stay / tax exemption tracking.
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Mode B: Min Appearance Count (Reports)
                </label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={settings.min_appearance_days}
                  onChange={(e) => setSettings({ ...settings, min_appearance_days: parseInt(e.target.value) || 3 })}
                  className="w-full px-3.5 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white font-mono text-sm focus:border-amber-400 focus:outline-none"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  Distinct reporting dates required to flag repeated guest appearance patterns (e.g. 3, 7, 15).
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Departure Calculation Convention
                </label>
                <select
                  value={settings.departure_convention}
                  onChange={(e) => setSettings({ ...settings, departure_convention: e.target.value })}
                  className="w-full px-3.5 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white text-sm focus:border-amber-400 focus:outline-none"
                >
                  <option value="checkin_plus_nights">Check-in Date + Number of Nights (Standard)</option>
                </select>
                <p className="text-[11px] text-slate-500 mt-1">
                  Provisional departure calculation formula for departures reports.
                </p>
              </div>
            </div>
          </div>

          {/* Card 2: Property & Operations */}
          <div className="p-6 rounded-xl bg-slate-900 border border-slate-800 space-y-5">
            <h2 className="text-sm font-bold text-amber-400 uppercase tracking-wider flex items-center gap-2">
              <Database className="w-4 h-4" /> Property & Storage Configuration
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Property Timezone
                </label>
                <select
                  value={settings.property_timezone}
                  onChange={(e) => setSettings({ ...settings, property_timezone: e.target.value })}
                  className="w-full px-3.5 py-2 rounded-lg bg-slate-800 border border-slate-700 text-white text-sm focus:border-amber-400 focus:outline-none"
                >
                  <option value="America/New_York">Eastern Time (America/New_York)</option>
                  <option value="America/Chicago">Central Time (America/Chicago)</option>
                  <option value="America/Denver">Mountain Time (America/Denver)</option>
                  <option value="America/Los_Angeles">Pacific Time (America/Los_Angeles)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Permanent Retention Policy
                </label>
                <input
                  type="text"
                  disabled
                  value="7 Years (Permanent Audit Trail)"
                  className="w-full px-3.5 py-2 rounded-lg bg-slate-950 border border-slate-800 text-slate-400 text-sm cursor-not-allowed"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  Historical records outside active 30-day window remain permanently accessible.
                </p>
              </div>
            </div>
          </div>

          {/* Save Button */}
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-black text-sm shadow-lg shadow-amber-500/20 transition-all active:scale-[0.98] disabled:opacity-50"
            >
              {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              <span>{saving ? 'Saving & Recalculating...' : 'Save Settings & Recalculate'}</span>
            </button>
          </div>
        </form>
      ) : null}
    </div>
  );
};

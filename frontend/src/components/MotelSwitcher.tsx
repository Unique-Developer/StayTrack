import React, { useState, useRef, useEffect } from 'react';
import { Building2, ChevronDown, Check, Sparkles, Loader2 } from 'lucide-react';
import { useProperty } from '../context/PropertyContext';

interface MotelSwitcherProps {
  variant?: 'header' | 'sidebar' | 'inline';
}

export const MotelSwitcher: React.FC<MotelSwitcherProps> = ({ variant = 'header' }) => {
  const { properties, currentPropertyId, currentProperty, setCurrentPropertyId, isSwitchingProperty } = useProperty();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (id: number) => {
    if (id === currentPropertyId || isSwitchingProperty) return;
    setCurrentPropertyId(id);
    setIsOpen(false);
  };

  // If sidebar segmented pills variant
  if (variant === 'sidebar') {
    return (
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400 px-1">
          <span className="flex items-center gap-1.5">
            {isSwitchingProperty ? (
              <Loader2 className="w-3 h-3 text-amber-400 animate-spin" />
            ) : (
              <Building2 className="w-3 h-3 text-amber-400" />
            )}
            <span>{isSwitchingProperty ? 'Switching Motel...' : 'Switch Motel / Property'}</span>
          </span>
          <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300">
            {properties.length} Active
          </span>
        </div>
        <div className="grid grid-cols-2 gap-1.5 p-1 rounded-xl bg-slate-950/80 border border-slate-800">
          {properties.map((p) => {
            const isSelected = p.id === currentPropertyId;
            return (
              <button
                key={p.id}
                type="button"
                disabled={isSwitchingProperty}
                onClick={() => handleSelect(p.id)}
                className={`py-2 px-2.5 rounded-lg text-xs font-bold transition-all text-center flex flex-col items-center justify-center gap-0.5 cursor-pointer disabled:opacity-60 ${
                  isSelected
                    ? 'bg-gradient-to-r from-amber-500 to-amber-600 text-slate-950 shadow-md shadow-amber-500/25 font-black scale-[1.02]'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/80'
                }`}
              >
                <div className="flex items-center gap-1">
                  {isSelected && isSwitchingProperty && (
                    <Loader2 className="w-3 h-3 animate-spin text-slate-950" />
                  )}
                  <span className="truncate max-w-full leading-tight">
                    {p.property_code === 'MOTEL6' ? 'Motel 6' : 'Studio 6'}
                  </span>
                </div>
                <span
                  className={`text-[9px] font-mono leading-none ${
                    isSelected ? 'text-slate-950 font-bold opacity-80' : 'text-slate-500'
                  }`}
                >
                  #{p.property_code}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  // Header prominent dropdown variant
  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        disabled={isSwitchingProperty}
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2.5 px-3 py-1.5 rounded-xl bg-slate-800/95 hover:bg-slate-700/90 border border-amber-500/30 hover:border-amber-400/60 shadow-sm shadow-amber-500/10 text-xs font-semibold transition-all cursor-pointer group disabled:opacity-75"
        title="Switch between Studio 6 and Motel 6"
      >
        <div className="w-6 h-6 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 shrink-0 group-hover:scale-105 transition-transform">
          {isSwitchingProperty ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-400" />
          ) : (
            <Building2 className="w-3.5 h-3.5" />
          )}
        </div>
        <div className="flex flex-col text-left">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] uppercase font-bold text-amber-400 tracking-wider">
              {isSwitchingProperty ? 'Switching...' : 'Active Motel:'}
            </span>
            <span className={`w-1.5 h-1.5 rounded-full ${isSwitchingProperty ? 'bg-amber-400 animate-ping' : 'bg-emerald-400 animate-pulse'}`} />
          </div>
          <div className="flex items-center gap-1.5">
            <span className="font-extrabold text-white text-xs tracking-tight">
              {currentProperty?.name || 'Studio 6 - Stafford, VA'}
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-900 text-amber-300 border border-slate-700">
              #{currentProperty?.property_code || '3756'}
            </span>
          </div>
        </div>
        {isSwitchingProperty ? (
          <Loader2 className="w-4 h-4 text-amber-400 animate-spin ml-1" />
        ) : (
          <ChevronDown
            className={`w-4 h-4 text-slate-400 group-hover:text-amber-400 transition-transform duration-200 ml-1 ${
              isOpen ? 'rotate-180 text-amber-400' : ''
            }`}
          />
        )}
      </button>

      {isOpen && (
        <div className="absolute left-0 mt-2 w-72 rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl shadow-black/80 p-2 z-50 animate-in fade-in zoom-in-95 duration-150">
          <div className="px-3 py-2 border-b border-slate-800 mb-1 flex items-center justify-between">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="w-3 h-3 text-amber-400" /> Select Motel / Property
            </span>
            <span className="text-[10px] font-mono text-amber-400">{properties.length} Available</span>
          </div>
          <div className="space-y-1">
            {properties.map((p) => {
              const isSelected = p.id === currentPropertyId;
              return (
                <button
                  key={p.id}
                  type="button"
                  disabled={isSwitchingProperty}
                  onClick={() => handleSelect(p.id)}
                  className={`w-full flex items-center justify-between p-2.5 rounded-xl text-left transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-amber-500/15 border border-amber-500/40 text-amber-300 font-bold'
                      : 'hover:bg-slate-800/80 text-slate-300 hover:text-white border border-transparent'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center font-black text-xs ${
                        isSelected
                          ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/30'
                          : 'bg-slate-800 text-slate-400 border border-slate-700'
                      }`}
                    >
                      {p.property_code === 'MOTEL6' ? 'M6' : 'S6'}
                    </div>
                    <div>
                      <div className="font-bold text-xs text-white leading-tight">{p.name}</div>
                      <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                        Code: #{p.property_code} • {p.timezone}
                      </div>
                    </div>
                  </div>
                  {isSelected && (
                    isSwitchingProperty ? (
                      <Loader2 className="w-4 h-4 text-amber-400 animate-spin shrink-0 ml-2" />
                    ) : (
                      <Check className="w-4 h-4 text-amber-400 shrink-0 ml-2" />
                    )
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

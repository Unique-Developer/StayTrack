import React, { useState, useEffect, useRef } from 'react';
import { Calendar } from 'lucide-react';
import { formatMMDDYYYY } from '../utils/dateUtils';

export interface DateInputProps {
  value?: string | null; // Expected in YYYY-MM-DD (ISO) format
  onChange: (dateIso: string) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
  title?: string;
  id?: string;
}

export const DateInput: React.FC<DateInputProps> = ({
  value,
  onChange,
  placeholder = 'mm-dd-yyyy',
  className = '',
  disabled = false,
  title,
  id,
}) => {
  const toDisplay = (isoVal?: string | null): string => {
    if (!isoVal || !isoVal.trim()) return '';
    const formatted = formatMMDDYYYY(isoVal);
    return formatted === '—' ? '' : formatted;
  };

  const toIso = (displayVal: string): string => {
    const trimmed = displayVal.trim();
    if (!trimmed) return '';
    // Match MM-DD-YYYY or MM/DD/YYYY
    const match = /^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/.exec(trimmed);
    if (match) {
      const month = match[1].padStart(2, '0');
      const day = match[2].padStart(2, '0');
      const year = match[3];
      return `${year}-${month}-${day}`;
    }
    // Match YYYY-MM-DD
    if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
      return trimmed;
    }
    return '';
  };

  const [displayText, setDisplayText] = useState(() => toDisplay(value));
  const hiddenPickerRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setDisplayText(toDisplay(value));
  }, [value]);

  const handleTextChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const text = e.target.value;
    setDisplayText(text);
    const iso = toIso(text);
    if (iso) {
      onChange(iso);
    } else if (!text.trim()) {
      onChange('');
    }
  };

  const handleBlur = () => {
    const iso = toIso(displayText);
    if (iso) {
      setDisplayText(toDisplay(iso));
      onChange(iso);
    } else if (!displayText.trim()) {
      setDisplayText('');
      onChange('');
    } else {
      setDisplayText(toDisplay(value));
    }
  };

  const handleNativePickerChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const isoVal = e.target.value;
    if (isoVal) {
      setDisplayText(toDisplay(isoVal));
      onChange(isoVal);
    }
  };

  const openPicker = () => {
    if (disabled) return;
    try {
      if (hiddenPickerRef.current && typeof hiddenPickerRef.current.showPicker === 'function') {
        hiddenPickerRef.current.showPicker();
      } else {
        hiddenPickerRef.current?.click();
      }
    } catch {
      hiddenPickerRef.current?.focus();
    }
  };

  const pickerValue = value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : toIso(displayText);

  return (
    <div className={`relative inline-flex items-center ${disabled ? 'opacity-60 cursor-not-allowed' : ''}`}>
      <input
        id={id}
        type="text"
        value={displayText}
        onChange={handleTextChange}
        onBlur={handleBlur}
        placeholder={placeholder}
        disabled={disabled}
        title={title}
        maxLength={10}
        className={`${className} pr-8`}
      />

      <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center justify-center">
        <button
          type="button"
          onClick={openPicker}
          disabled={disabled}
          tabIndex={-1}
          aria-label="Open Calendar"
          className="text-slate-400 hover:text-amber-400 transition-colors p-0.5 rounded cursor-pointer"
        >
          <Calendar className="w-3.5 h-3.5" />
        </button>

        <input
          ref={hiddenPickerRef}
          type="date"
          value={pickerValue}
          onChange={handleNativePickerChange}
          disabled={disabled}
          tabIndex={-1}
          className="absolute inset-0 opacity-0 pointer-events-none w-0 h-0"
          aria-hidden="true"
        />
      </div>
    </div>
  );
};

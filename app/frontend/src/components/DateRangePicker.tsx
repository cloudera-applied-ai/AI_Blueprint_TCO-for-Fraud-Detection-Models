import { useState, useEffect } from 'react';
import { Calendar, ChevronDown } from 'lucide-react';
import { getDateRange } from '../api';

interface Props {
  startDate: string | null;
  endDate: string | null;
  onChange: (start: string | null, end: string | null) => void;
}

const PRESETS = [
  { label: 'All', days: 0 },
  { label: '90d', days: 90 },
  { label: '180d', days: 180 },
  { label: '1yr', days: 365 },
  { label: '2yr', days: 730 },
];

export function DateRangePicker({ startDate, endDate, onChange }: Props) {
  const [dataRange, setDataRange] = useState<{ min_date: string; max_date: string } | null>(null);
  const [showCustom, setShowCustom] = useState(false);
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');

  useEffect(() => {
    getDateRange().then((r) => {
      if (r.min_date && r.max_date) {
        setDataRange({ min_date: r.min_date, max_date: r.max_date });
      }
    }).catch(() => {});
  }, []);

  const handlePreset = (days: number) => {
    if (days === 0 || !dataRange) {
      onChange(null, null);
      setShowCustom(false);
      return;
    }
    const end = new Date(dataRange.max_date);
    const start = new Date(end);
    start.setDate(start.getDate() - days);
    onChange(formatDate(start), formatDate(end));
    setShowCustom(false);
  };

  const handleCustomApply = () => {
    if (customStart && customEnd) {
      onChange(customStart, customEnd);
      setShowCustom(false);
    }
  };

  const activeLabel = !startDate ? 'All' : PRESETS.find(p => {
    if (p.days === 0) return false;
    if (!dataRange) return false;
    const end = new Date(dataRange.max_date);
    const start = new Date(end);
    start.setDate(start.getDate() - p.days);
    return formatDate(start) === startDate && formatDate(end) === endDate;
  })?.label || 'Custom';

  return (
    <div className="flex items-center gap-1.5">
      <Calendar className="w-3.5 h-3.5 text-gray-500" />
      {PRESETS.map(p => (
        <button
          key={p.label}
          onClick={() => handlePreset(p.days)}
          className={`px-2 py-1 text-[11px] font-medium rounded-md transition-colors
            ${activeLabel === p.label
              ? 'bg-accent/20 text-accent'
              : 'text-gray-500 hover:text-gray-300 hover:bg-surface-3'
            }`}
        >
          {p.label}
        </button>
      ))}
      <div className="relative">
        <button
          onClick={() => {
            setShowCustom(!showCustom);
            if (startDate) setCustomStart(startDate);
            if (endDate) setCustomEnd(endDate);
          }}
          className={`px-2 py-1 text-[11px] font-medium rounded-md flex items-center gap-1 transition-colors
            ${activeLabel === 'Custom'
              ? 'bg-accent/20 text-accent'
              : 'text-gray-500 hover:text-gray-300 hover:bg-surface-3'
            }`}
        >
          Custom <ChevronDown className="w-3 h-3" />
        </button>
        {showCustom && (
          <div className="absolute right-0 top-full mt-1 z-50 bg-surface-2 border border-surface-4 rounded-lg p-3 shadow-xl min-w-[240px]">
            <div className="space-y-2">
              <div>
                <label className="text-[10px] text-gray-500 block mb-1">Start Date</label>
                <input
                  type="date"
                  value={customStart}
                  min={dataRange?.min_date}
                  max={dataRange?.max_date}
                  onChange={e => setCustomStart(e.target.value)}
                  className="w-full px-2 py-1.5 text-xs bg-surface-3 border border-surface-4 rounded-md text-gray-200
                             focus:outline-none focus:border-accent/50"
                />
              </div>
              <div>
                <label className="text-[10px] text-gray-500 block mb-1">End Date</label>
                <input
                  type="date"
                  value={customEnd}
                  min={dataRange?.min_date}
                  max={dataRange?.max_date}
                  onChange={e => setCustomEnd(e.target.value)}
                  className="w-full px-2 py-1.5 text-xs bg-surface-3 border border-surface-4 rounded-md text-gray-200
                             focus:outline-none focus:border-accent/50"
                />
              </div>
              <button
                onClick={handleCustomApply}
                disabled={!customStart || !customEnd}
                className="w-full px-3 py-1.5 text-xs font-medium bg-accent/20 text-accent rounded-md
                           hover:bg-accent/30 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Apply Range
              </button>
            </div>
            {startDate && (
              <div className="mt-2 pt-2 border-t border-surface-4 text-[10px] text-gray-500">
                Comparing to previous period of equal length
              </div>
            )}
          </div>
        )}
      </div>
      {startDate && endDate && (
        <span className="text-[10px] text-gray-500 ml-1">
          {startDate} to {endDate}
        </span>
      )}
    </div>
  );
}

function formatDate(d: Date): string {
  return d.toISOString().split('T')[0];
}

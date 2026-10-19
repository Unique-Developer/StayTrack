import React from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid
} from 'recharts';

interface TrendChartProps {
  data: Array<{
    date: string;
    display_date: string;
    departures_count: number;
  }>;
}

export const TrendChart: React.FC<TrendChartProps> = ({ data }) => {
  if (!data || data.length === 0) {
    return (
      <div className="h-64 flex flex-col items-center justify-center text-slate-500 border border-slate-800 rounded-xl bg-slate-900/40">
        <p className="text-sm">No trend data available yet.</p>
        <p className="text-xs text-slate-600 mt-1">Upload daily departure reports to see trends.</p>
      </div>
    );
  }

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="departuresGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#e29e21" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#e29e21" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.4} />
          <XAxis
            dataKey="display_date"
            stroke="#64748b"
            fontSize={12}
            tickLine={false}
            axisLine={{ stroke: '#334155' }}
          />
          <YAxis
            stroke="#64748b"
            fontSize={12}
            tickLine={false}
            axisLine={{ stroke: '#334155' }}
            allowDecimals={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#0f172a',
              borderColor: '#334155',
              borderRadius: '8px',
              fontSize: '12px',
              color: '#f8fafc',
            }}
            itemStyle={{ color: '#f6b840' }}
            formatter={(value: any) => [`${value} departures`, 'Guest Records']}
            labelFormatter={(label) => `Date: ${label}`}
          />
          <Area
            type="monotone"
            dataKey="departures_count"
            stroke="#e29e21"
            strokeWidth={2.5}
            fillOpacity={1}
            fill="url(#departuresGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

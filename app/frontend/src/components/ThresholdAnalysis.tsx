import { useState, useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, ReferenceLine, Legend,
} from 'recharts';
import { SlidersHorizontal, Target, AlertTriangle, ShieldCheck } from 'lucide-react';
import type { ThresholdAnalysisData, ThresholdPoint } from '../types';

interface Props {
  data: ThresholdAnalysisData;
}

export function ThresholdAnalysis({ data }: Props) {
  const [selectedThreshold, setSelectedThreshold] = useState(data.current_threshold);

  const selectedPoint: ThresholdPoint | null = useMemo(() => {
    // Find the closest point to the selected threshold
    let closest = data.curve[0];
    let minDist = Math.abs(closest.threshold - selectedThreshold);
    for (const p of data.curve) {
      const dist = Math.abs(p.threshold - selectedThreshold);
      if (dist < minDist) {
        closest = p;
        minDist = dist;
      }
    }
    return closest;
  }, [data.curve, selectedThreshold]);

  return (
    <div className="space-y-4">
      {/* Threshold Slider */}
      <div className="bg-surface-2 rounded-xl p-4 border border-surface-3">
        <h3 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
          <SlidersHorizontal className="w-4 h-4 text-accent" />
          Threshold Tuning
        </h3>
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-500 w-6">0.0</span>
            <input
              type="range"
              min="0.05"
              max="0.95"
              step="0.05"
              value={selectedThreshold}
              onChange={e => setSelectedThreshold(parseFloat(e.target.value))}
              className="flex-1 h-2 bg-surface-4 rounded-lg appearance-none cursor-pointer
                         [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4
                         [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:bg-accent
                         [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer"
            />
            <span className="text-xs text-gray-500 w-6">1.0</span>
          </div>
          <div className="text-center">
            <span className="text-2xl font-bold text-accent">{selectedThreshold.toFixed(2)}</span>
            <span className="text-xs text-gray-500 ml-2">threshold</span>
          </div>
        </div>
      </div>

      {/* Impact KPIs */}
      {selectedPoint && (
        <div className="grid grid-cols-4 gap-2">
          <MetricCard
            icon={<Target className="w-3.5 h-3.5" />}
            label="Precision"
            value={`${(selectedPoint.precision * 100).toFixed(1)}%`}
            detail={`${selectedPoint.tp} true positives`}
            color="accent"
          />
          <MetricCard
            icon={<ShieldCheck className="w-3.5 h-3.5" />}
            label="Recall"
            value={`${(selectedPoint.recall * 100).toFixed(1)}%`}
            detail={`${selectedPoint.missed} missed`}
            color="green"
          />
          <MetricCard
            icon={<AlertTriangle className="w-3.5 h-3.5" />}
            label="False Pos"
            value={String(selectedPoint.fp)}
            detail={`of ${selectedPoint.flagged} flagged`}
            color="amber"
          />
          <MetricCard
            icon={<SlidersHorizontal className="w-3.5 h-3.5" />}
            label="F1 Score"
            value={`${(selectedPoint.f1 * 100).toFixed(1)}%`}
            detail={`${selectedPoint.flagged} alerts`}
            color="red"
          />
        </div>
      )}

      {/* Confusion Matrix */}
      {selectedPoint && (
        <div className="bg-surface-2 rounded-xl p-4 border border-surface-3">
          <h3 className="text-sm font-medium text-gray-300 mb-3">Confusion Matrix</h3>
          <div className="grid grid-cols-2 gap-1.5 max-w-[280px] mx-auto">
            <div className="bg-fraud-green/10 border border-fraud-green/20 rounded-lg p-3 text-center">
              <div className="text-lg font-bold text-fraud-green">{selectedPoint.tp}</div>
              <div className="text-[10px] text-gray-500">True Positive</div>
            </div>
            <div className="bg-fraud-red/10 border border-fraud-red/20 rounded-lg p-3 text-center">
              <div className="text-lg font-bold text-fraud-red">{selectedPoint.fp}</div>
              <div className="text-[10px] text-gray-500">False Positive</div>
            </div>
            <div className="bg-fraud-amber/10 border border-fraud-amber/20 rounded-lg p-3 text-center">
              <div className="text-lg font-bold text-fraud-amber">{selectedPoint.fn}</div>
              <div className="text-[10px] text-gray-500">False Negative</div>
            </div>
            <div className="bg-fraud-green/10 border border-fraud-green/20 rounded-lg p-3 text-center">
              <div className="text-lg font-bold text-fraud-green">{selectedPoint.tn}</div>
              <div className="text-[10px] text-gray-500">True Negative</div>
            </div>
          </div>
        </div>
      )}

      {/* Precision/Recall/F1 Curve */}
      <div className="bg-surface-2 rounded-xl p-4 border border-surface-3">
        <h3 className="text-sm font-medium text-gray-300 mb-3">
          Precision / Recall / F1 vs Threshold
        </h3>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={data.curve}>
            <XAxis
              dataKey="threshold"
              tick={{ fill: '#6b7280', fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: '#2e2e3a' }}
              label={{ value: 'Threshold', position: 'insideBottomRight', offset: -5, fill: '#6b7280', fontSize: 10 }}
            />
            <YAxis
              tick={{ fill: '#6b7280', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              domain={[0, 1]}
            />
            <Tooltip
              contentStyle={{
                background: '#1a1a25',
                border: '1px solid #2e2e3a',
                borderRadius: '8px',
                fontSize: '11px',
              }}
              formatter={(value?: number, name?: string) => [
                `${((value ?? 0) * 100).toFixed(1)}%`,
                name ?? '',
              ]}
            />
            <Legend
              iconSize={8}
              wrapperStyle={{ fontSize: '10px', paddingTop: '8px' }}
            />
            <ReferenceLine
              x={selectedThreshold}
              stroke="#6366f1"
              strokeDasharray="4 4"
              strokeWidth={2}
            />
            <Line
              type="monotone" dataKey="precision" stroke="#10b981" strokeWidth={2}
              dot={false} name="Precision"
            />
            <Line
              type="monotone" dataKey="recall" stroke="#f59e0b" strokeWidth={2}
              dot={false} name="Recall"
            />
            <Line
              type="monotone" dataKey="f1" stroke="#ef4444" strokeWidth={2}
              dot={false} name="F1"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Score Distribution */}
      <div className="bg-surface-2 rounded-xl p-4 border border-surface-3">
        <h3 className="text-sm font-medium text-gray-300 mb-3">
          Score Distribution
        </h3>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={data.distribution}>
            <XAxis
              dataKey="bin_start"
              tick={{ fill: '#6b7280', fontSize: 9 }}
              tickLine={false}
              axisLine={{ stroke: '#2e2e3a' }}
              tickFormatter={v => String(v)}
            />
            <YAxis
              tick={{ fill: '#6b7280', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              contentStyle={{
                background: '#1a1a25',
                border: '1px solid #2e2e3a',
                borderRadius: '8px',
                fontSize: '11px',
              }}
              labelFormatter={v => `Score: ${v}`}
            />
            <Legend iconSize={8} wrapperStyle={{ fontSize: '10px' }} />
            <ReferenceLine
              x={selectedThreshold}
              stroke="#6366f1"
              strokeDasharray="4 4"
              strokeWidth={2}
            />
            <Bar dataKey="legitimate" stackId="a" fill="#10b981" fillOpacity={0.6} name="Legitimate" />
            <Bar dataKey="fraud" stackId="a" fill="#ef4444" fillOpacity={0.8} name="Fraud" />
          </BarChart>
        </ResponsiveContainer>
        <div className="text-center text-[10px] text-gray-500 mt-1">
          Sample: {data.sample_size.toLocaleString()} transactions
          ({data.fraud_count.toLocaleString()} fraud, {data.legit_count.toLocaleString()} legit)
        </div>
      </div>
    </div>
  );
}

function MetricCard({ icon, label, value, detail, color }: {
  icon: React.ReactNode;
  label: string;
  value: string;
  detail: string;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    accent: 'text-accent bg-accent/10',
    green: 'text-fraud-green bg-fraud-green/10',
    amber: 'text-fraud-amber bg-fraud-amber/10',
    red: 'text-fraud-red bg-fraud-red/10',
  };

  return (
    <div className="bg-surface-2 rounded-lg p-2.5 border border-surface-3">
      <div className={`p-1 rounded w-fit ${colorMap[color] || colorMap.accent}`}>
        {icon}
      </div>
      <div className="text-lg font-bold text-gray-100 mt-1">{value}</div>
      <div className="text-[10px] text-gray-500">{label}</div>
      <div className="text-[9px] text-gray-600 mt-0.5">{detail}</div>
    </div>
  );
}

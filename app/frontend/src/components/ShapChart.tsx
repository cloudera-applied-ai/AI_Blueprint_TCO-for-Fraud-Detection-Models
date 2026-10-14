import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from 'recharts';
import { Brain, AlertTriangle, CheckCircle } from 'lucide-react';
import type { ExplanationResult, ShapFeature } from '../types';

interface Props {
  data: ExplanationResult;
}

const FEATURE_LABELS: Record<string, string> = {
  amount: 'Transaction Amount',
  amount_scaled: 'Amount (scaled)',
  hour: 'Hour of Day',
  mcc: 'Merchant Category',
  merchant_state_encoded: 'Merchant State',
  merchant_name_encoded: 'Merchant',
  merchant_fraud_rate: 'Merchant Fraud Rate',
  mcc_fraud_rate: 'Category Fraud Rate',
  state_fraud_rate: 'State Fraud Rate',
  merchant_country_encoded: 'Merchant Country',
  country_fraud_rate: 'Country Fraud Rate',
  is_cross_border: 'Cross-Border',
  tx_count_last_1h: 'Txns Last Hour',
  tx_count_last_24h: 'Txns Last 24h',
  amount_last_24h: 'Amount Last 24h',
  tx_amount_zscore_user: 'Amount Z-Score (User)',
  tx_amount_zscore_merchant: 'Amount Z-Score (Merchant)',
  amount_to_avg_ratio: 'Amount / User Avg',
  is_out_of_state: 'Out of State',
  'chip_Chip Transaction': 'Chip Used',
  'chip_Online Transaction': 'Online',
  'chip_Swipe Transaction': 'Swiped',
  time_minutes: 'Time of Day',
  tx_hour_sin: 'Hour (sin)',
  tx_hour_cos: 'Hour (cos)',
};

export function ShapChart({ data }: Props) {
  if (!data || (!data.top_features && !data.narrative)) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-500 text-sm">
        No explanation data available
      </div>
    );
  }

  const riskColors = {
    HIGH: 'text-fraud-red',
    MEDIUM: 'text-fraud-amber',
    LOW: 'text-fraud-green',
  };

  const riskBg = {
    HIGH: 'bg-fraud-red/10 border-fraud-red/20',
    MEDIUM: 'bg-fraud-amber/10 border-fraud-amber/20',
    LOW: 'bg-fraud-green/10 border-fraud-green/20',
  };

  const chartData = (data.top_features || [])
    .slice(0, 10)
    .map((f: ShapFeature) => ({
      name: FEATURE_LABELS[f.feature] || f.feature,
      value: f.shap_value,
      rawValue: f.value,
      feature: f.feature,
    }))
    .reverse();

  return (
    <div className="space-y-4">
      {/* Score Header */}
      <div className={`rounded-xl p-4 border ${riskBg[data.risk_level as keyof typeof riskBg] || riskBg.LOW}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Brain className="w-5 h-5 text-accent" />
            <div>
              <div className="text-sm text-gray-400">
                Transaction #{data.transaction_id}
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className={`text-2xl font-bold ${riskColors[data.risk_level as keyof typeof riskColors] || 'text-gray-200'}`}>
                  {(data.fraud_score * 100).toFixed(1)}%
                </span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full
                  ${riskBg[data.risk_level as keyof typeof riskBg] || ''} ${riskColors[data.risk_level as keyof typeof riskColors] || ''}`}>
                  {data.risk_level} RISK
                </span>
              </div>
            </div>
          </div>
          {data.actual_fraud !== undefined && (
            <div className="text-right">
              <div className="text-xs text-gray-500">Actual</div>
              <div className="flex items-center gap-1 mt-0.5">
                {data.actual_fraud ? (
                  <>
                    <AlertTriangle className="w-3.5 h-3.5 text-fraud-red" />
                    <span className="text-sm text-fraud-red font-medium">Fraud</span>
                  </>
                ) : (
                  <>
                    <CheckCircle className="w-3.5 h-3.5 text-fraud-green" />
                    <span className="text-sm text-fraud-green font-medium">Legitimate</span>
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Transaction Summary */}
        {data.transaction_summary && (
          <div className="mt-3 pt-3 border-t border-white/5 grid grid-cols-3 gap-3 text-xs">
            <div>
              <span className="text-gray-500">Amount</span>
              <div className="text-gray-200 font-mono">${data.transaction_summary.amount?.toFixed(2)}</div>
            </div>
            <div>
              <span className="text-gray-500">Merchant</span>
              <div className="text-gray-200 truncate">{data.transaction_summary.merchant}</div>
            </div>
            <div>
              <span className="text-gray-500">State / Hour</span>
              <div className="text-gray-200">{data.transaction_summary.country ? `${data.transaction_summary.country}/` : ''}{data.transaction_summary.state} / {data.transaction_summary.hour}:00</div>
            </div>
          </div>
        )}
      </div>

      {/* SHAP Waterfall Chart */}
      {chartData.length > 0 && (
        <div className="bg-surface-2 rounded-xl p-4 border border-surface-3">
          <h3 className="text-sm font-medium text-gray-300 mb-3">
            Feature Contributions (SHAP)
          </h3>
          <ResponsiveContainer width="100%" height={Math.max(200, chartData.length * 28)}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 20 }}>
              <XAxis
                type="number"
                tick={{ fill: '#6b7280', fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: '#2e2e3a' }}
              />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fill: '#9ca3af', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                width={130}
              />
              <Tooltip
                contentStyle={{
                  background: '#1a1a25',
                  border: '1px solid #2e2e3a',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
                formatter={(value, _name, entry) => {
                  const v = typeof value === 'number' ? value : 0;
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  const raw = (entry as any)?.payload?.rawValue;
                  return [`SHAP: ${v.toFixed(4)} | Value: ${raw?.toFixed(2) ?? 'N/A'}`, 'Impact'];
                }}
              />
              <ReferenceLine x={0} stroke="#2e2e3a" />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {chartData.map((entry, index) => (
                  <Cell
                    key={index}
                    fill={entry.value > 0 ? '#ef4444' : '#10b981'}
                    fillOpacity={0.8}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="flex justify-center gap-4 mt-2 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <span className="w-3 h-2 rounded bg-fraud-red/80" /> Increases fraud risk
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-2 rounded bg-fraud-green/80" /> Decreases fraud risk
            </span>
          </div>
        </div>
      )}

      {/* Narrative */}
      {data.narrative && (
        <div className="bg-surface-2 rounded-xl p-4 border border-surface-3">
          <h3 className="text-sm font-medium text-gray-300 mb-2">Explanation</h3>
          <pre className="text-xs text-gray-400 whitespace-pre-wrap font-mono leading-relaxed">
            {data.narrative}
          </pre>
        </div>
      )}
    </div>
  );
}

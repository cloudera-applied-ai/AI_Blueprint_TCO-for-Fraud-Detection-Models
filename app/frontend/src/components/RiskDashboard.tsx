import { TrendingUp, TrendingDown, Users, Store, AlertTriangle, DollarSign, Activity, Globe, Download, Minus } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area, LineChart, Line, Legend } from 'recharts';
import type { DashboardData, ComparisonEntry, MonthlyTrend } from '../types';
import { downloadCSV } from '../api';

const COUNTRY_NAMES: Record<string, string> = {
  US: 'United States', CA: 'Canada', GB: 'United Kingdom', DE: 'Germany',
  FR: 'France', ES: 'Spain', IT: 'Italy', NL: 'Netherlands', SE: 'Sweden',
  PL: 'Poland', CH: 'Switzerland', AT: 'Austria', PT: 'Portugal', IE: 'Ireland',
  NO: 'Norway', DK: 'Denmark', FI: 'Finland', CZ: 'Czech Republic', GR: 'Greece',
  RO: 'Romania', HU: 'Hungary', BE: 'Belgium', BR: 'Brazil', AR: 'Argentina',
  CO: 'Colombia', CL: 'Chile', PE: 'Peru', EC: 'Ecuador', UY: 'Uruguay',
  JP: 'Japan', CN: 'China', RU: 'Russia',
};

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

interface Props {
  data: DashboardData;
  onMonthClick?: (year: number, month: number) => void;
}

export function RiskDashboard({ data, onMonthClick }: Props) {
  const { kpis, comparison } = data;

  return (
    <div className="space-y-4">
      {/* Comparison Period Banner */}
      {data.comparison_period && (
        <div className="text-[10px] text-gray-500 bg-surface-2 rounded-lg px-3 py-1.5 border border-surface-3">
          Comparing to previous period: {data.comparison_period.start} to {data.comparison_period.end}
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-3">
        <KPICard
          icon={<Activity className="w-4 h-4" />}
          label="Total Transactions"
          value={kpis.total_transactions?.toLocaleString() || '0'}
          color="accent"
          comparison={comparison?.total_transactions}
        />
        <KPICard
          icon={<AlertTriangle className="w-4 h-4" />}
          label="Fraud Detected"
          value={kpis.total_fraud?.toLocaleString() || '0'}
          subtitle={`${kpis.fraud_rate_pct || 0}% rate`}
          color="red"
          comparison={comparison?.total_fraud}
          invertDelta
        />
        <KPICard
          icon={<DollarSign className="w-4 h-4" />}
          label="Fraud Amount"
          value={`$${(kpis.total_fraud_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`}
          subtitle={`Avg $${(kpis.avg_fraud_amount || 0).toFixed(0)}`}
          color="amber"
          comparison={comparison?.total_fraud_amount}
          invertDelta
        />
        <KPICard
          icon={<Users className="w-4 h-4" />}
          label="Users / Merchants"
          value={`${kpis.unique_users?.toLocaleString() || 0}`}
          subtitle={`${kpis.unique_merchants || 0} merchants`}
          color="green"
        />
      </div>

      {/* Monthly Fraud Trend */}
      {data.monthly_trend && data.monthly_trend.length > 1 && (
        <div className="bg-surface-2 rounded-xl p-4 border border-surface-3">
          <h3 className="text-sm font-medium text-gray-300 mb-3 flex items-center justify-between">
            <span className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-accent" />
              Monthly Fraud Trend
            </span>
            {onMonthClick && (
              <span className="text-[10px] text-gray-500 font-normal">click a point to drill in</span>
            )}
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart
              data={data.monthly_trend.map(d => ({
                ...d,
                label: `${MONTH_NAMES[d.month - 1]} ${d.year}`,
              }))}
              margin={{ top: 5, right: 10, left: 0, bottom: 0 }}
            >
              <XAxis
                dataKey="label"
                tick={{ fill: '#6b7280', fontSize: 9 }}
                tickLine={false}
                axisLine={{ stroke: '#2e2e3a' }}
                interval={Math.max(0, Math.floor(data.monthly_trend.length / 8) - 1)}
              />
              <YAxis
                yAxisId="count"
                tick={{ fill: '#6b7280', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                yAxisId="rate"
                orientation="right"
                tick={{ fill: '#6b7280', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={v => `${v}%`}
              />
              <Tooltip
                contentStyle={{
                  background: '#1a1a25',
                  border: '1px solid #2e2e3a',
                  borderRadius: '8px',
                  fontSize: '11px',
                }}
                formatter={(value?: number, name?: string) => {
                  const v = value ?? 0;
                  const n = name ?? '';
                  if (n === 'Fraud Rate') return [`${v}%`, n];
                  if (n === 'Fraud $') return [`$${v.toLocaleString()}`, n];
                  return [v.toLocaleString(), n];
                }}
              />
              <Legend iconSize={8} wrapperStyle={{ fontSize: '10px' }} />
              <Line
                yAxisId="count"
                type="monotone"
                dataKey="fraud_count"
                stroke="#ef4444"
                strokeWidth={2}
                dot={onMonthClick ? { r: 4, fill: '#ef4444', style: { cursor: 'pointer' } } : false}
                activeDot={onMonthClick ? {
                  r: 7, fill: '#ef4444', stroke: '#fff', strokeWidth: 2,
                  style: { cursor: 'pointer' },
                  onClick: (_e: unknown, payload: { payload?: MonthlyTrend }) => {
                    const p = payload?.payload;
                    if (p && typeof p.year === 'number' && typeof p.month === 'number') {
                      onMonthClick(p.year, p.month);
                    }
                  },
                } : { r: 6, fill: '#ef4444', stroke: '#fff', strokeWidth: 2 }}
                name="Fraud Count"
              />
              <Line
                yAxisId="rate"
                type="monotone"
                dataKey="fraud_rate_pct"
                stroke="#f59e0b"
                strokeWidth={2}
                dot={false}
                strokeDasharray="4 4"
                name="Fraud Rate"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Top Fraud Merchants (default overview) */}
      {data.top_fraud_merchants && data.top_fraud_merchants.length > 0 && (
        <div className="bg-surface-2 rounded-xl p-4 border border-surface-3">
          <h3 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
            <Store className="w-4 h-4 text-fraud-amber" />
            Top Fraud Merchants
          </h3>
          <ResponsiveContainer width="100%" height={Math.max(200, data.top_fraud_merchants.slice(0, 10).length * 28)}>
            <BarChart data={data.top_fraud_merchants.slice(0, 10)} layout="vertical">
              <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis
                type="category"
                dataKey="merchant_name"
                tick={{ fill: '#9ca3af', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                width={120}
              />
              <Tooltip
                contentStyle={{
                  background: '#1a1a25',
                  border: '1px solid #2e2e3a',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
                formatter={(value, name) => {
                  if (name === 'Fraud Amount') return [`$${Number(value).toLocaleString()}`, name];
                  return [value, name];
                }}
              />
              <Bar dataKey="fraud_count" fill="#f59e0b" radius={[0, 4, 4, 0]} name="Fraud Count" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Hourly Fraud Pattern */}
      {data.hourly_pattern && (
        <div className="bg-surface-2 rounded-xl p-4 border border-surface-3">
          <h3 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-accent" />
            Fraud by Hour of Day
          </h3>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={data.hourly_pattern}>
              <defs>
                <linearGradient id="fraudGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="hour"
                tick={{ fill: '#6b7280', fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: '#2e2e3a' }}
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
                  fontSize: '12px',
                }}
                labelFormatter={(v) => `${v}:00`}
              />
              <Area
                type="monotone"
                dataKey="fraud_count"
                stroke="#ef4444"
                fill="url(#fraudGradient)"
                strokeWidth={2}
                name="Fraud Count"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Top Fraud Countries */}
      {data.top_fraud_countries && data.top_fraud_countries.length > 0 && (
        <div className="bg-surface-2 rounded-xl p-4 border border-surface-3">
          <h3 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
            <Globe className="w-4 h-4 text-accent" />
            Top Fraud Countries
          </h3>
          <ResponsiveContainer width="100%" height={Math.max(160, data.top_fraud_countries.slice(0, 10).length * 26)}>
            <BarChart data={data.top_fraud_countries.slice(0, 10)} layout="vertical">
              <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis
                type="category"
                dataKey="country"
                tick={{ fill: '#9ca3af', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={30}
              />
              <Tooltip
                contentStyle={{
                  background: '#1a1a25',
                  border: '1px solid #2e2e3a',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
                labelFormatter={(v) => COUNTRY_NAMES[v as string] || v}
              />
              <Bar dataKey="fraud_count" fill="#6366f1" radius={[0, 4, 4, 0]} name="Fraud Count" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Top Fraud Countries (group_by view) */}
      {data.by_country && data.by_country.length > 0 && (
        <div className="bg-surface-2 rounded-xl p-4 border border-surface-3">
          <h3 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
            <Globe className="w-4 h-4 text-accent" />
            Fraud by Country
          </h3>
          <ResponsiveContainer width="100%" height={Math.max(180, data.by_country.slice(0, 15).length * 26)}>
            <BarChart data={data.by_country.slice(0, 15)} layout="vertical">
              <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis
                type="category"
                dataKey="country"
                tick={{ fill: '#9ca3af', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={30}
              />
              <Tooltip
                contentStyle={{
                  background: '#1a1a25',
                  border: '1px solid #2e2e3a',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
                labelFormatter={(v) => COUNTRY_NAMES[v as string] || v}
              />
              <Bar dataKey="fraud_count" fill="#6366f1" radius={[0, 4, 4, 0]} name="Fraud Count" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Top Fraud States */}
      {data.top_fraud_states && data.top_fraud_states.length > 0 && (
        <div className="bg-surface-2 rounded-xl p-4 border border-surface-3">
          <h3 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
            <Store className="w-4 h-4 text-fraud-amber" />
            Top Fraud States
          </h3>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={data.top_fraud_states} layout="vertical">
              <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis
                type="category"
                dataKey="state"
                tick={{ fill: '#9ca3af', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={30}
              />
              <Tooltip
                contentStyle={{
                  background: '#1a1a25',
                  border: '1px solid #2e2e3a',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
              />
              <Bar dataKey="fraud_count" fill="#f59e0b" radius={[0, 4, 4, 0]} name="Fraud Count" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Top MCC Codes */}
      {data.top_fraud_mccs && data.top_fraud_mccs.length > 0 && (
        <div className="bg-surface-2 rounded-xl p-4 border border-surface-3">
          <h3 className="text-sm font-medium text-gray-300 mb-3">Top Fraud Categories (MCC)</h3>
          <div className="space-y-2">
            {data.top_fraud_mccs.map(mcc => (
              <div key={mcc.mcc} className="flex items-center justify-between text-xs">
                <span className="text-gray-400">MCC {mcc.mcc}</span>
                <div className="flex items-center gap-2">
                  <div className="w-24 h-1.5 bg-surface-4 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-fraud-red rounded-full"
                      style={{ width: `${Math.min(mcc.fraud_rate_pct * 10, 100)}%` }}
                    />
                  </div>
                  <span className="text-gray-300 w-12 text-right">{mcc.fraud_count}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top Fraud Users Bar Chart */}
      {data.by_user && data.by_user.length > 0 && (
        <div className="bg-surface-2 rounded-xl p-4 border border-surface-3">
          <h3 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
            <Users className="w-4 h-4 text-fraud-red" />
            Top Fraud Users
          </h3>
          <ResponsiveContainer width="100%" height={Math.max(180, data.by_user.slice(0, 10).length * 28)}>
            <BarChart data={data.by_user.slice(0, 10)} layout="vertical">
              <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis
                type="category"
                dataKey="user_id"
                tick={{ fill: '#9ca3af', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={45}
                tickFormatter={(v) => `#${v}`}
              />
              <Tooltip
                contentStyle={{
                  background: '#1a1a25',
                  border: '1px solid #2e2e3a',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
                formatter={(value, name) => {
                  if (name === 'Fraud Amount') return [`$${Number(value).toLocaleString()}`, name];
                  return [value, name];
                }}
                labelFormatter={(v) => `User #${v}`}
              />
              <Bar dataKey="fraud_count" fill="#ef4444" radius={[0, 4, 4, 0]} name="Fraud Count" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Top Fraud Merchants Bar Chart */}
      {data.by_merchant && data.by_merchant.length > 0 && (
        <div className="bg-surface-2 rounded-xl p-4 border border-surface-3">
          <h3 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
            <Store className="w-4 h-4 text-fraud-amber" />
            Top Fraud Merchants
          </h3>
          <ResponsiveContainer width="100%" height={Math.max(180, data.by_merchant.slice(0, 10).length * 28)}>
            <BarChart data={data.by_merchant.slice(0, 10)} layout="vertical">
              <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis
                type="category"
                dataKey="merchant_name"
                tick={{ fill: '#9ca3af', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                width={100}
              />
              <Tooltip
                contentStyle={{
                  background: '#1a1a25',
                  border: '1px solid #2e2e3a',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
              />
              <Bar dataKey="fraud_count" fill="#f59e0b" radius={[0, 4, 4, 0]} name="Fraud Count" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Group-by data tables (below charts for detailed view) */}
      {data.by_country && <GroupTable title="Fraud by Country" rows={data.by_country} labelKey="country" />}
      {data.by_state && <GroupTable title="Fraud by State/Region" rows={data.by_state} labelKey="state" />}
      {data.by_mcc && <GroupTable title="Fraud by MCC" rows={data.by_mcc} labelKey="mcc" />}
      {data.by_hour && <GroupTable title="Fraud by Hour" rows={data.by_hour} labelKey="hour" />}
      {data.by_merchant && <GroupTable title="Fraud by Merchant" rows={data.by_merchant} labelKey="merchant_name" />}
      {data.by_user && <GroupTable title="Fraud by User" rows={data.by_user} labelKey="user_id" />}
    </div>
  );
}

function KPICard({ icon, label, value, subtitle, color, comparison, invertDelta }: {
  icon: React.ReactNode;
  label: string;
  value: string;
  subtitle?: string;
  color: string;
  comparison?: ComparisonEntry;
  invertDelta?: boolean;
}) {
  const colorMap: Record<string, string> = {
    accent: 'text-accent bg-accent/10 border-accent/20',
    red: 'text-fraud-red bg-fraud-red/10 border-fraud-red/20',
    amber: 'text-fraud-amber bg-fraud-amber/10 border-fraud-amber/20',
    green: 'text-fraud-green bg-fraud-green/10 border-fraud-green/20',
  };

  const delta = comparison?.change_pct;
  const hasDelta = delta != null;
  // For fraud metrics, increase is bad (red), decrease is good (green)
  // invertDelta flips the color logic
  const deltaIsPositive = hasDelta && delta > 0;
  const deltaColor = !hasDelta ? '' :
    invertDelta
      ? (deltaIsPositive ? 'text-fraud-red' : 'text-fraud-green')
      : (deltaIsPositive ? 'text-fraud-green' : 'text-fraud-red');

  return (
    <div className="bg-surface-2 rounded-xl p-3 border border-surface-3">
      <div className="flex items-center gap-2 mb-2">
        <div className={`p-1.5 rounded-lg ${colorMap[color] || colorMap.accent}`}>
          {icon}
        </div>
        <span className="text-xs text-gray-500">{label}</span>
      </div>
      <div className="flex items-end gap-2">
        <div className="text-lg font-semibold text-gray-100">{value}</div>
        {hasDelta && (
          <div className={`flex items-center gap-0.5 text-xs font-medium ${deltaColor} mb-0.5`}>
            {delta === 0 ? (
              <Minus className="w-3 h-3" />
            ) : delta > 0 ? (
              <TrendingUp className="w-3 h-3" />
            ) : (
              <TrendingDown className="w-3 h-3" />
            )}
            <span>{delta > 0 ? '+' : ''}{delta.toFixed(1)}%</span>
          </div>
        )}
      </div>
      {subtitle && <div className="text-xs text-gray-500 mt-0.5">{subtitle}</div>}
    </div>
  );
}

function GroupTable({ title, rows, labelKey }: {
  title: string;
  rows: Record<string, unknown>[];
  labelKey: string;
}) {
  const hasAmount = rows.length > 0 && 'fraud_amount' in rows[0];

  return (
    <div className="bg-surface-2 rounded-xl p-4 border border-surface-3">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-gray-300">{title}</h3>
        <button
          onClick={() => downloadCSV(rows, `${title.replace(/\s+/g, '_').toLowerCase()}.csv`)}
          className="p-1.5 text-gray-500 hover:text-gray-300 hover:bg-surface-3 rounded-md transition-colors"
          title="Export CSV"
        >
          <Download className="w-3.5 h-3.5" />
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 border-b border-surface-4">
              <th className="text-left py-2 font-medium">{labelKey}</th>
              <th className="text-right py-2 font-medium">Total</th>
              <th className="text-right py-2 font-medium">Fraud</th>
              <th className="text-right py-2 font-medium">Rate %</th>
              {hasAmount && <th className="text-right py-2 font-medium">Fraud $</th>}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 15).map((row, i) => (
              <tr key={i} className="border-b border-surface-4/50">
                <td className="py-1.5 text-gray-300">{String(row[labelKey] ?? '')}</td>
                <td className="py-1.5 text-right text-gray-400">{(row.total as number)?.toLocaleString()}</td>
                <td className="py-1.5 text-right text-fraud-red">{(row.fraud_count as number)?.toLocaleString()}</td>
                <td className="py-1.5 text-right text-gray-300">{String(row.fraud_rate_pct ?? '')}%</td>
                {hasAmount && (
                  <td className="py-1.5 text-right text-fraud-amber">
                    ${(row.fraud_amount as number)?.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

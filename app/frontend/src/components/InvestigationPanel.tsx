import { FileText, Download, Store, AlertTriangle, Globe, Calendar, Users, Receipt, GitBranch } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import type { MerchantInvestigation, Transaction, Alert } from '../types';

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

interface Props {
  investigation: MerchantInvestigation;
  onTraceMerchant?: (merchantName: string) => void;
  onShowMerchantTransactions?: (merchantName: string) => void;
  onShowAllUserTransactions?: (userId: number) => void;
}

function formatDateNum(n: number | null | undefined) {
  if (!n) return '—';
  const s = String(n);
  if (s.length !== 8) return s;
  return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;
}

function formatMoney(v: number | null | undefined) {
  if (v == null) return '$0';
  return `$${v.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

function buildMarkdown(inv: MerchantInvestigation): string {
  const lines: string[] = [];
  const k = inv.kpis ?? {};
  lines.push(`# Fraud Investigation — ${inv.merchant_name}`);
  lines.push('');
  lines.push(`Generated ${new Date().toISOString()}`);
  lines.push('');
  lines.push('## Summary');
  lines.push('');
  lines.push(`- **Total transactions:** ${(k.total_transactions ?? 0).toLocaleString()}`);
  lines.push(`- **Fraud transactions:** ${(k.fraud_transactions ?? 0).toLocaleString()} (${k.fraud_rate_pct ?? 0}%)`);
  lines.push(`- **Fraud amount:** ${formatMoney(k.fraud_amount)}`);
  lines.push(`- **Total amount:** ${formatMoney(k.total_amount)}`);
  lines.push(`- **Unique users:** ${(k.unique_users ?? 0).toLocaleString()} (${(k.fraud_users ?? 0).toLocaleString()} touched fraud)`);
  lines.push(`- **First seen:** ${formatDateNum(k.first_seen)}`);
  lines.push(`- **Last seen:** ${formatDateNum(k.last_seen)}`);
  lines.push('');

  if (inv.geographic_spread?.length) {
    lines.push('## Geographic Spread');
    lines.push('');
    lines.push('| State | Country | Total | Fraud | Fraud $ |');
    lines.push('|---|---|---:|---:|---:|');
    inv.geographic_spread.forEach(g => {
      lines.push(`| ${g.merchant_state ?? '—'} | ${g.merchant_country ?? '—'} | ${g.total} | ${g.fraud_count} | ${formatMoney(g.fraud_amount)} |`);
    });
    lines.push('');
  }

  const cps = inv.trace?.counterparties ?? [];
  if (cps.length) {
    lines.push(`## Customers Affected (${cps.length})`);
    lines.push('');
    lines.push('| User | Shared txns | Shared fraud | Shared $ | Overall fraud rate |');
    lines.push('|---:|---:|---:|---:|---:|');
    cps.forEach(c => {
      const rate = c.user_total_transactions
        ? ((c.user_total_fraud ?? 0) / c.user_total_transactions * 100).toFixed(1)
        : '0.0';
      lines.push(`| ${c.user_id ?? '—'} | ${c.shared_transactions} | ${c.shared_fraud} | ${formatMoney(c.shared_fraud_amount)} | ${rate}% |`);
    });
    lines.push('');
  }

  if (inv.top_fraud_transactions?.length) {
    lines.push(`## Top Fraud Transactions (${inv.top_fraud_transactions.length} of ${inv.top_fraud_count ?? 0})`);
    lines.push('');
    lines.push('| Txn ID | User | Date | Amount | State | Country |');
    lines.push('|---:|---:|---|---:|---|---|');
    inv.top_fraud_transactions.forEach(t => {
      const date = `${t.year}-${String(t.month).padStart(2, '0')}-${String(t.day).padStart(2, '0')}`;
      lines.push(`| ${t.transaction_id} | ${t.user_id} | ${date} | ${formatMoney(t.amount)} | ${t.merchant_state ?? '—'} | ${t.merchant_country ?? '—'} |`);
    });
    lines.push('');
  }

  const alerts = (inv.patterns?.alerts ?? []) as Alert[];
  if (alerts.length) {
    lines.push(`## Behavioral Patterns (${alerts.length})`);
    lines.push('');
    alerts.forEach(a => {
      lines.push(`- **[${a.severity}] ${a.type}** — ${a.description}`);
    });
    lines.push('');
  }

  const ts = inv.time_series ?? [];
  if (ts.length) {
    lines.push('## Monthly Trend');
    lines.push('');
    lines.push('| Period | Total | Fraud | Fraud $ |');
    lines.push('|---|---:|---:|---:|');
    ts.forEach(p => {
      lines.push(`| ${p.year}-${String(p.month).padStart(2, '0')} | ${p.total} | ${p.fraud_count} | ${formatMoney(p.fraud_amount)} |`);
    });
    lines.push('');
  }

  return lines.join('\n');
}

function downloadMarkdown(inv: MerchantInvestigation) {
  const md = buildMarkdown(inv);
  const blob = new Blob([md], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const safeName = inv.merchant_name.replace(/[^a-z0-9]+/gi, '_').toLowerCase();
  const a = document.createElement('a');
  a.href = url;
  a.download = `investigation_${safeName}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

function KPI({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: 'red' | 'amber' | 'green' }) {
  const color = accent === 'red' ? 'text-fraud-red' : accent === 'amber' ? 'text-fraud-amber' : accent === 'green' ? 'text-fraud-green' : 'text-gray-100';
  return (
    <div className="bg-surface-2 rounded-lg p-2.5 border border-surface-3">
      <div className="text-[10px] text-gray-500 uppercase tracking-wide">{label}</div>
      <div className={`text-sm font-semibold ${color}`}>{value}</div>
      {sub && <div className="text-[10px] text-gray-600 mt-0.5">{sub}</div>}
    </div>
  );
}

function CustomerRow({ user_id, shared, sharedFraud, sharedAmount, overall, onClick }: {
  user_id: number | undefined;
  shared: number;
  sharedFraud: number;
  sharedAmount: number;
  overall: number;
  onClick?: () => void;
}) {
  const interactive = !!onClick;
  return (
    <tr
      onClick={onClick}
      className={`border-b border-surface-4/40 ${interactive ? 'cursor-pointer hover:bg-surface-3/50' : ''}`}
      title={interactive ? `Show all transactions for user ${user_id}` : undefined}
    >
      <td className={`py-1.5 px-2 font-mono text-[11px] ${interactive ? 'text-accent' : 'text-gray-200'}`}>#{user_id ?? '—'}</td>
      <td className="py-1.5 px-2 text-right text-gray-300 text-[11px]">{shared}</td>
      <td className="py-1.5 px-2 text-right text-fraud-red text-[11px]">{sharedFraud}</td>
      <td className="py-1.5 px-2 text-right text-fraud-amber text-[11px]">{formatMoney(sharedAmount)}</td>
      <td className={`py-1.5 px-2 text-right text-[11px] ${overall > 10 ? 'text-fraud-red' : overall > 2 ? 'text-fraud-amber' : 'text-gray-400'}`}>{overall.toFixed(1)}%</td>
    </tr>
  );
}

export function InvestigationPanel({
  investigation, onTraceMerchant, onShowMerchantTransactions, onShowAllUserTransactions,
}: Props) {
  if (investigation.error) {
    return (
      <div className="text-center py-8 text-gray-500 text-sm">
        <FileText className="w-8 h-8 mx-auto mb-2 opacity-40" />
        {investigation.error}
      </div>
    );
  }

  const k = investigation.kpis ?? ({} as MerchantInvestigation['kpis']);
  const cps = investigation.trace?.counterparties ?? [];
  const topTx = investigation.top_fraud_transactions ?? [];
  const alerts = (investigation.patterns?.alerts ?? []) as Alert[];
  const trend = (investigation.time_series ?? []).map(p => ({
    ...p,
    label: `${MONTH_NAMES[p.month - 1]} ${p.year}`,
  }));

  return (
    <div className="space-y-3">
      {/* Header + actions */}
      <div className="flex items-start gap-2">
        <div className="p-1.5 bg-accent/20 rounded">
          <Store className="w-4 h-4 text-accent" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[10px] uppercase tracking-wide text-gray-500">Merchant Investigation</div>
          <h2 className="text-sm font-semibold text-gray-100 truncate">{investigation.merchant_name}</h2>
          <div className="text-[10px] text-gray-600">
            {formatDateNum(k.first_seen)} → {formatDateNum(k.last_seen)}
          </div>
        </div>
        <div className="flex items-center gap-1">
          {onTraceMerchant && (
            <button
              onClick={() => onTraceMerchant(investigation.merchant_name)}
              title="Open in Trace panel"
              className="p-1.5 rounded text-gray-500 hover:text-accent hover:bg-surface-3"
            >
              <GitBranch className="w-3.5 h-3.5" />
            </button>
          )}
          {onShowMerchantTransactions && (
            <button
              onClick={() => onShowMerchantTransactions(investigation.merchant_name)}
              title="Show all fraud transactions"
              className="p-1.5 rounded text-gray-500 hover:text-accent hover:bg-surface-3"
            >
              <Receipt className="w-3.5 h-3.5" />
            </button>
          )}
          <button
            onClick={() => downloadMarkdown(investigation)}
            title="Export report (Markdown)"
            className="flex items-center gap-1 px-2 py-1.5 rounded text-[11px] text-accent border border-accent/30 hover:bg-accent/10"
          >
            <Download className="w-3 h-3" /> Export
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-2">
        <KPI label="Total txns" value={(k.total_transactions ?? 0).toLocaleString()} />
        <KPI label="Fraud txns" value={(k.fraud_transactions ?? 0).toLocaleString()} sub={`${k.fraud_rate_pct ?? 0}% rate`} accent="red" />
        <KPI label="Fraud amount" value={formatMoney(k.fraud_amount)} sub={`of ${formatMoney(k.total_amount)} total`} accent="amber" />
        <KPI label="Customers" value={(k.unique_users ?? 0).toLocaleString()} sub={`${(k.fraud_users ?? 0).toLocaleString()} touched fraud`} />
      </div>

      {/* Trend */}
      {trend.length > 1 && (
        <div className="bg-surface-2 rounded-lg p-3 border border-surface-3">
          <div className="text-[10px] uppercase tracking-wide text-gray-500 mb-2 flex items-center gap-1">
            <Calendar className="w-3 h-3" /> Monthly fraud trend
          </div>
          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={trend} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
              <XAxis dataKey="label" tick={{ fill: '#6b7280', fontSize: 9 }} interval={Math.max(0, Math.floor(trend.length / 8) - 1)} tickLine={false} axisLine={{ stroke: '#2e2e3a' }} />
              <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ background: '#1a1a25', border: '1px solid #2e2e3a', borderRadius: '8px', fontSize: '11px' }} />
              <Line type="monotone" dataKey="fraud_count" stroke="#ef4444" strokeWidth={2} dot={{ r: 3, fill: '#ef4444' }} name="Fraud Count" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Geo */}
      {investigation.geographic_spread?.length > 0 && (
        <div className="bg-surface-2 rounded-lg p-3 border border-surface-3">
          <div className="text-[10px] uppercase tracking-wide text-gray-500 mb-2 flex items-center gap-1">
            <Globe className="w-3 h-3" /> Geographic spread
          </div>
          <ResponsiveContainer width="100%" height={Math.max(80, investigation.geographic_spread.length * 22)}>
            <BarChart
              data={investigation.geographic_spread.map(g => ({
                ...g,
                label: [g.merchant_state, g.merchant_country].filter(Boolean).join(' · ') || '—',
              }))}
              layout="vertical"
              margin={{ top: 5, right: 10, left: 5, bottom: 0 }}
            >
              <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="label" tick={{ fill: '#9ca3af', fontSize: 11 }} tickLine={false} axisLine={false} width={70} />
              <Tooltip contentStyle={{ background: '#1a1a25', border: '1px solid #2e2e3a', borderRadius: '8px', fontSize: '11px' }} />
              <Bar dataKey="fraud_count" fill="#ef4444" name="Fraud" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Customers */}
      {cps.length > 0 && (
        <div className="bg-surface-2 rounded-lg p-3 border border-surface-3">
          <div className="text-[10px] uppercase tracking-wide text-gray-500 mb-2 flex items-center gap-1">
            <Users className="w-3 h-3" /> Customers affected ({cps.length})
            {onShowAllUserTransactions && (
              <span className="ml-auto normal-case tracking-normal text-gray-600">
                click a row to see all their transactions
              </span>
            )}
          </div>
          <div className="overflow-x-auto max-h-64 overflow-y-auto">
            <table className="w-full">
              <thead className="sticky top-0 bg-surface-2">
                <tr className="text-[10px] text-gray-500 border-b border-surface-4">
                  <th className="py-1 px-2 text-left font-medium">User</th>
                  <th className="py-1 px-2 text-right font-medium">Shared</th>
                  <th className="py-1 px-2 text-right font-medium">Fraud</th>
                  <th className="py-1 px-2 text-right font-medium">Fraud $</th>
                  <th className="py-1 px-2 text-right font-medium">Overall %</th>
                </tr>
              </thead>
              <tbody>
                {cps.slice(0, 25).map(c => (
                  <CustomerRow
                    key={c.user_id ?? Math.random()}
                    user_id={c.user_id}
                    shared={c.shared_transactions}
                    sharedFraud={c.shared_fraud}
                    sharedAmount={c.shared_fraud_amount}
                    overall={c.user_total_transactions ? (c.user_total_fraud ?? 0) / c.user_total_transactions * 100 : 0}
                    onClick={c.user_id != null && onShowAllUserTransactions
                      ? () => onShowAllUserTransactions(c.user_id!)
                      : undefined}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Top fraud transactions */}
      {topTx.length > 0 && (
        <div className="bg-surface-2 rounded-lg p-3 border border-surface-3">
          <div className="text-[10px] uppercase tracking-wide text-gray-500 mb-2 flex items-center gap-1">
            <Receipt className="w-3 h-3" /> Top fraud transactions ({topTx.length} of {investigation.top_fraud_count ?? 0})
          </div>
          <div className="overflow-x-auto max-h-64 overflow-y-auto">
            <table className="w-full">
              <thead className="sticky top-0 bg-surface-2">
                <tr className="text-[10px] text-gray-500 border-b border-surface-4">
                  <th className="py-1 px-2 text-left font-medium">Txn</th>
                  <th className="py-1 px-2 text-left font-medium">User</th>
                  <th className="py-1 px-2 text-left font-medium">Date</th>
                  <th className="py-1 px-2 text-right font-medium">Amount</th>
                  <th className="py-1 px-2 text-left font-medium">Geo</th>
                </tr>
              </thead>
              <tbody>
                {topTx.map((t: Transaction) => (
                  <tr key={t.transaction_id} className="border-b border-surface-4/40">
                    <td className="py-1.5 px-2 text-gray-300 font-mono text-[11px]">#{t.transaction_id}</td>
                    <td className="py-1.5 px-2 text-gray-300 font-mono text-[11px]">#{t.user_id}</td>
                    <td className="py-1.5 px-2 text-gray-400 text-[11px]">{t.year}-{String(t.month).padStart(2, '0')}-{String(t.day).padStart(2, '0')}</td>
                    <td className="py-1.5 px-2 text-right text-fraud-amber text-[11px]">{formatMoney(t.amount)}</td>
                    <td className="py-1.5 px-2 text-gray-400 text-[11px]">{[t.merchant_state, t.merchant_country].filter(Boolean).join(' · ') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Patterns */}
      {alerts.length > 0 && (
        <div className="bg-surface-2 rounded-lg p-3 border border-surface-3">
          <div className="text-[10px] uppercase tracking-wide text-gray-500 mb-2 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> Behavioral patterns ({alerts.length})
          </div>
          <div className="space-y-1.5">
            {alerts.slice(0, 10).map((a, i) => (
              <div key={i} className="flex items-start gap-2 text-[11px]">
                <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium uppercase ${
                  a.severity === 'HIGH' ? 'bg-fraud-red/20 text-fraud-red border border-fraud-red/30' :
                  a.severity === 'MEDIUM' ? 'bg-fraud-amber/20 text-fraud-amber border border-fraud-amber/30' :
                  'bg-surface-3 text-gray-400 border border-surface-4'
                }`}>
                  {a.severity}
                </span>
                <div className="flex-1">
                  <div className="text-gray-200">{a.type}</div>
                  <div className="text-gray-500">{a.description}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export { buildMarkdown as buildInvestigationMarkdown, downloadMarkdown as downloadInvestigationMarkdown };

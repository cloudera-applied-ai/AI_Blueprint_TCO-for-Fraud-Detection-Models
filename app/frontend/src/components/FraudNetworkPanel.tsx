import { Network, Store, User, AlertTriangle, MoveRight, Search, GitBranch, Receipt, FileText, ListChecks } from 'lucide-react';
import type {
  FraudNetworkTrace, FraudNetworkCounterparty, FraudNetworkSeed,
} from '../types';

interface Props {
  trace: FraudNetworkTrace;
  onTraceUser?: (userId: number) => void;
  onTraceMerchant?: (merchantName: string) => void;
  onShowUserTransactions?: (userId: number) => void;
  onShowMerchantTransactions?: (merchantName: string) => void;
  onShowAllUserTransactions?: (userId: number) => void;
  onShowAllMerchantTransactions?: (merchantName: string) => void;
  onInvestigateMerchant?: (merchantName: string) => void;
}

function formatAmount(v: number) {
  if (!v) return '$0';
  if (v >= 1000) return `$${(v / 1000).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}

function formatDate(n: number | null | undefined) {
  if (!n) return '—';
  const s = String(n);
  if (s.length !== 8) return s;
  return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;
}

function SeedCard({ seed }: { seed: FraudNetworkSeed }) {
  const label = seed.type === 'merchant' ? seed.merchant_name : `User ${seed.user_id}`;
  const Icon = seed.type === 'merchant' ? Store : User;
  const fraudRate = seed.total_transactions
    ? (seed.fraud_transactions / seed.total_transactions) * 100
    : 0;

  return (
    <div className="bg-surface-2 border border-accent/40 rounded-lg p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-accent/20 rounded">
            <Icon className="w-3.5 h-3.5 text-accent" />
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wide text-gray-500">Seed {seed.type}</div>
            <div className="text-sm font-medium text-gray-100 truncate max-w-[280px]">{label}</div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px] text-gray-500">Fraud rate</div>
          <div className={`text-sm font-mono ${fraudRate > 10 ? 'text-fraud-red' : fraudRate > 2 ? 'text-fraud-amber' : 'text-fraud-green'}`}>
            {fraudRate.toFixed(1)}%
          </div>
        </div>
      </div>
      <div className="grid grid-cols-4 gap-2 text-[10px]">
        <Stat label="Txns" value={seed.total_transactions.toLocaleString()} />
        <Stat label="Fraud" value={seed.fraud_transactions.toLocaleString()} accent="red" />
        <Stat label="Fraud $" value={formatAmount(seed.fraud_amount)} />
        <Stat
          label={seed.type === 'merchant' ? 'Users' : 'Merchants'}
          value={(seed.unique_users ?? seed.unique_merchants ?? 0).toLocaleString()}
        />
      </div>
      <div className="text-[10px] text-gray-600 mt-1">
        {formatDate(seed.first_seen)} &rarr; {formatDate(seed.last_seen)}
      </div>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: 'red' | 'amber' }) {
  const color = accent === 'red' ? 'text-fraud-red' : accent === 'amber' ? 'text-fraud-amber' : 'text-gray-200';
  return (
    <div className="bg-surface-1 rounded px-2 py-1">
      <div className="text-gray-500">{label}</div>
      <div className={`font-mono ${color}`}>{value}</div>
    </div>
  );
}

function CounterpartyRow({
  cp, maxShared, direction, onTrace, onShowTransactions, onShowAllTransactions, onInvestigate,
}: {
  cp: FraudNetworkCounterparty;
  maxShared: number;
  direction: 'merchant_to_users' | 'user_to_merchants';
  onTrace?: () => void;
  onShowTransactions?: () => void;
  onShowAllTransactions?: () => void;
  onInvestigate?: () => void;
}) {
  const isUserRow = direction === 'merchant_to_users';
  const label = isUserRow ? `User ${cp.user_id}` : (cp.merchant_name ?? '—');
  const sublabel = isUserRow
    ? `${cp.user_total_transactions ?? 0} txns across ${cp.user_unique_merchants ?? 0} merchants`
    : `${cp.merchant_state ?? ''}${cp.merchant_country ? ` · ${cp.merchant_country}` : ''}`;
  const Icon = isUserRow ? User : Store;

  const overallFraud = isUserRow
    ? (cp.user_total_fraud ?? 0)
    : (cp.merchant_total_fraud ?? 0);
  const overallTxns = isUserRow
    ? (cp.user_total_transactions ?? 0)
    : (cp.merchant_total_transactions ?? 0);
  const overallFraudRate = overallTxns ? (overallFraud / overallTxns) * 100 : 0;

  const sharedBar = maxShared > 0 ? (cp.shared_transactions / maxShared) * 100 : 0;
  const samples = cp.sample_fraud_transactions ?? [];
  const traceLabel = isUserRow ? 'Trace this user → merchants' : 'Trace this merchant → users';
  const txLabel = isUserRow ? 'Show fraud txns for this user' : 'Show fraud txns for this merchant';
  const allTxLabel = isUserRow ? 'Show ALL txns (valid + fraud) for this user' : 'Show ALL txns (valid + fraud) for this merchant';

  return (
    <div className="bg-surface-2 border border-surface-3 rounded-lg p-2.5 space-y-2 hover:border-accent/30 transition-colors">
      <div className="flex items-center gap-2">
        <div className="p-1 bg-surface-3 rounded">
          <Icon className="w-3 h-3 text-gray-400" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xs font-medium text-gray-100 truncate">{label}</div>
          <div className="text-[10px] text-gray-500 truncate">{sublabel}</div>
        </div>
        {cp.shared_fraud > 0 && (
          <div className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-fraud-red/20 border border-fraud-red/30">
            <AlertTriangle className="w-2.5 h-2.5 text-fraud-red" />
            <span className="text-[10px] font-mono text-fraud-red">{cp.shared_fraud}</span>
          </div>
        )}
        <div className="flex items-center gap-1">
          {onTrace && (
            <button
              onClick={onTrace}
              title={traceLabel}
              className="p-1 rounded text-gray-500 hover:text-accent hover:bg-surface-3"
            >
              <GitBranch className="w-3 h-3" />
            </button>
          )}
          {onShowTransactions && (
            <button
              onClick={onShowTransactions}
              title={txLabel}
              className="p-1 rounded text-gray-500 hover:text-accent hover:bg-surface-3"
            >
              <Receipt className="w-3 h-3" />
            </button>
          )}
          {onShowAllTransactions && (
            <button
              onClick={onShowAllTransactions}
              title={allTxLabel}
              className="p-1 rounded text-gray-500 hover:text-accent hover:bg-surface-3"
            >
              <ListChecks className="w-3 h-3" />
            </button>
          )}
          {onInvestigate && (
            <button
              onClick={onInvestigate}
              title="Build full investigation report"
              className="p-1 rounded text-gray-500 hover:text-accent hover:bg-surface-3"
            >
              <FileText className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-1.5 text-[10px]">
        <Stat label="Shared" value={cp.shared_transactions.toLocaleString()} />
        <Stat label="Shared $" value={formatAmount(cp.shared_amount)} />
        <Stat
          label="Overall fraud"
          value={`${overallFraudRate.toFixed(1)}%`}
          accent={overallFraudRate > 10 ? 'red' : overallFraudRate > 2 ? 'amber' : undefined}
        />
      </div>

      <div className="h-1 bg-surface-3 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${cp.shared_fraud > 0 ? 'bg-fraud-red/60' : 'bg-accent/40'}`}
          style={{ width: `${sharedBar}%` }}
        />
      </div>

      {samples.length > 0 && (
        <div className="pt-1 border-t border-surface-3/60">
          <div className="text-[9px] uppercase tracking-wide text-gray-500 mb-1">
            Top fraud transactions ({samples.length})
          </div>
          <div className="flex flex-wrap gap-1">
            {samples.map(s => (
              <div
                key={s.transaction_id}
                className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-surface-1 border border-surface-3 text-[10px] font-mono text-gray-300"
                title={`Transaction ${s.transaction_id}`}
              >
                <span className="text-gray-500">#{s.transaction_id}</span>
                <span className="text-fraud-amber">{formatAmount(s.amount)}</span>
                <span className="text-gray-600">{s.date}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function FraudNetworkPanel({
  trace, onTraceUser, onTraceMerchant, onShowUserTransactions, onShowMerchantTransactions,
  onShowAllUserTransactions, onShowAllMerchantTransactions, onInvestigateMerchant,
}: Props) {
  if (trace.error) {
    return (
      <div className="text-center py-8 text-gray-500 text-sm">
        <Network className="w-8 h-8 mx-auto mb-2 opacity-40" />
        {trace.error}
      </div>
    );
  }

  if (!trace.seed) {
    return (
      <div className="text-center py-12 text-gray-500 text-sm">
        <Network className="w-10 h-10 mx-auto mb-3 opacity-30" />
        <p className="text-gray-400">No trace yet</p>
        <p className="text-[11px] text-gray-600 mt-2 max-w-[280px] mx-auto leading-relaxed">
          Ask the agent to trace a merchant or user, or click the trace icon on a counterparty
          to populate this view.
        </p>
      </div>
    );
  }

  const { seed, counterparties, summary, direction } = trace;
  const maxShared = Math.max(1, ...counterparties.map(c => c.shared_transactions));
  const seedSideLabel = direction === 'merchant_to_users' ? 'Merchant' : 'User';
  const targetSideLabel = direction === 'merchant_to_users' ? 'Customers' : 'Merchants';
  const isUserSide = direction === 'merchant_to_users';

  const seedTxAction = seed.type === 'merchant'
    ? (seed.merchant_name && onShowMerchantTransactions
        ? () => onShowMerchantTransactions(seed.merchant_name!)
        : undefined)
    : (seed.user_id != null && onShowUserTransactions
        ? () => onShowUserTransactions(seed.user_id!)
        : undefined);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Network className="w-4 h-4 text-accent" />
        <h2 className="text-sm font-semibold text-gray-100">
          Fraud Trace &mdash; {seedSideLabel} <MoveRight className="w-3 h-3 inline text-gray-500 mx-1" /> {targetSideLabel}
        </h2>
        {trace.fraud_only && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-fraud-red/10 border border-fraud-red/30 text-fraud-red">
            fraud only
          </span>
        )}
        <div className="ml-auto flex items-center gap-1.5">
          {seed.type === 'merchant' && seed.merchant_name && onInvestigateMerchant && (
            <button
              onClick={() => onInvestigateMerchant(seed.merchant_name!)}
              className="flex items-center gap-1 px-2 py-1 rounded text-[10px] text-accent hover:bg-accent/10 border border-accent/30"
              title="Build full investigation report"
            >
              <FileText className="w-3 h-3" /> Report
            </button>
          )}
          {seedTxAction && (
            <button
              onClick={seedTxAction}
              className="flex items-center gap-1 px-2 py-1 rounded text-[10px] text-accent hover:bg-accent/10 border border-accent/30"
              title={`Show all fraud transactions for this ${seed.type}`}
            >
              <Search className="w-3 h-3" /> All txns
            </button>
          )}
        </div>
      </div>

      <SeedCard seed={seed} />

      <div className="grid grid-cols-3 gap-2 text-[10px]">
        <Stat label="Returned" value={String(summary.counterparties_returned)} />
        <Stat label="With fraud" value={String(summary.fraud_heavy_counterparties)} accent="red" />
        <Stat label="Shared fraud $" value={formatAmount(summary.total_shared_fraud_amount)} />
      </div>

      <div className="pt-1">
        <div className="text-[10px] uppercase tracking-wide text-gray-500 mb-1.5">
          Connected {targetSideLabel.toLowerCase()} ({counterparties.length})
        </div>
        <div className="space-y-1.5 max-h-[520px] overflow-y-auto pr-1">
          {counterparties.map((cp, i) => {
            const onTrace = isUserSide
              ? (cp.user_id != null && onTraceUser ? () => onTraceUser(cp.user_id!) : undefined)
              : (cp.merchant_name && onTraceMerchant ? () => onTraceMerchant(cp.merchant_name!) : undefined);
            const onShowTx = isUserSide
              ? (cp.user_id != null && onShowUserTransactions ? () => onShowUserTransactions(cp.user_id!) : undefined)
              : (cp.merchant_name && onShowMerchantTransactions ? () => onShowMerchantTransactions(cp.merchant_name!) : undefined);
            const onShowAllTx = isUserSide
              ? (cp.user_id != null && onShowAllUserTransactions ? () => onShowAllUserTransactions(cp.user_id!) : undefined)
              : (cp.merchant_name && onShowAllMerchantTransactions ? () => onShowAllMerchantTransactions(cp.merchant_name!) : undefined);
            const onInvestigate = !isUserSide && cp.merchant_name && onInvestigateMerchant
              ? () => onInvestigateMerchant(cp.merchant_name!)
              : undefined;
            return (
              <CounterpartyRow
                key={cp.user_id ?? cp.merchant_name ?? i}
                cp={cp}
                maxShared={maxShared}
                direction={direction}
                onTrace={onTrace}
                onShowTransactions={onShowTx}
                onShowAllTransactions={onShowAllTx}
                onInvestigate={onInvestigate}
              />
            );
          })}
          {counterparties.length === 0 && (
            <div className="text-center text-xs text-gray-500 py-4">
              No connected counterparties found
              {trace.fraud_only && ' with fraud. Try disabling fraud_only.'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

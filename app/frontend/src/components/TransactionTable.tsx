import { AlertTriangle, CheckCircle, Download } from 'lucide-react';
import type { Transaction } from '../types';
import { downloadCSV } from '../api';

interface Props {
  transactions: Transaction[];
}

export function TransactionTable({ transactions }: Props) {
  if (!transactions || transactions.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-500 text-sm">
        No transactions to display
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-300">
          Transactions ({transactions.length})
        </h3>
        <button
          onClick={() => downloadCSV(
            transactions as unknown as Record<string, unknown>[],
            'transactions_export.csv',
          )}
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-[11px] font-medium text-gray-400
                     bg-surface-2 border border-surface-4 rounded-md
                     hover:text-gray-200 hover:border-accent/50 hover:bg-surface-3 transition-colors"
          title="Export to CSV"
        >
          <Download className="w-3 h-3" />
          Export CSV
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 border-b border-surface-4">
              <th className="text-left py-2 px-2 font-medium">ID</th>
              <th className="text-left py-2 px-2 font-medium">User</th>
              <th className="text-left py-2 px-2 font-medium">Merchant</th>
              <th className="text-left py-2 px-2 font-medium">Location</th>
              <th className="text-right py-2 px-2 font-medium">Amount</th>
              <th className="text-center py-2 px-2 font-medium">Time</th>
              <th className="text-center py-2 px-2 font-medium">Date</th>
              <th className="text-center py-2 px-2 font-medium">Type</th>
              <th className="text-center py-2 px-2 font-medium" title="Confirmed fraud label — red = fraud, green = legitimate">
                Fraud Label
              </th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((tx) => (
              <tr
                key={tx.transaction_id}
                className={`border-b border-surface-4/50 hover:bg-surface-3/50
                  ${tx.is_fraud ? 'bg-fraud-red/5' : ''}`}
              >
                <td className="py-2 px-2 text-gray-400 font-mono">{tx.transaction_id}</td>
                <td className="py-2 px-2 text-gray-300">{tx.user_id}</td>
                <td className="py-2 px-2 text-gray-300 max-w-[120px] truncate" title={tx.merchant_name}>
                  {tx.merchant_name}
                </td>
                <td className="py-2 px-2 text-gray-400">{tx.merchant_country ? `${tx.merchant_country}/${tx.merchant_state}` : tx.merchant_state}</td>
                <td className="py-2 px-2 text-right text-gray-200 font-mono">
                  ${typeof tx.amount === 'number' ? tx.amount.toFixed(2) : tx.amount}
                </td>
                <td className="py-2 px-2 text-center text-gray-400">
                  {String(tx.hour).padStart(2, '0')}:{String(tx.minute).padStart(2, '0')}
                </td>
                <td className="py-2 px-2 text-center text-gray-400">
                  {tx.year}-{String(tx.month).padStart(2, '0')}-{String(tx.day).padStart(2, '0')}
                </td>
                <td className="py-2 px-2 text-center">
                  <ChipBadge type={tx.use_chip} />
                </td>
                <td className="py-2 px-2 text-center">
                  {tx.is_fraud ? (
                    <span
                      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium
                                 text-fraud-red bg-fraud-red/10"
                      title="Confirmed fraudulent transaction"
                    >
                      <AlertTriangle className="w-3 h-3" />
                      Fraud
                    </span>
                  ) : (
                    <span
                      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium
                                 text-fraud-green bg-fraud-green/10"
                      title="Legitimate transaction"
                    >
                      <CheckCircle className="w-3 h-3" />
                      Legit
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ChipBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    'Chip Transaction': 'bg-fraud-green/10 text-fraud-green',
    'Online Transaction': 'bg-accent/10 text-accent',
    'Swipe Transaction': 'bg-fraud-amber/10 text-fraud-amber',
  };

  const labels: Record<string, string> = {
    'Chip Transaction': 'Chip',
    'Online Transaction': 'Online',
    'Swipe Transaction': 'Swipe',
  };

  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${colors[type] || 'bg-surface-3 text-gray-400'}`}>
      {labels[type] || type}
    </span>
  );
}

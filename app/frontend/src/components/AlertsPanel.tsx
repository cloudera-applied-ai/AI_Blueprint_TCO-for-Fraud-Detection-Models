import { AlertTriangle, Zap, MapPin, TrendingUp, Moon } from 'lucide-react';
import type { AlertsResult, Alert } from '../types';

interface Props {
  data: AlertsResult;
}

const ALERT_ICONS: Record<string, React.ReactNode> = {
  velocity: <Zap className="w-4 h-4" />,
  geo_anomaly: <MapPin className="w-4 h-4" />,
  amount_spike: <TrendingUp className="w-4 h-4" />,
  late_night: <Moon className="w-4 h-4" />,
};

const ALERT_COLORS: Record<string, string> = {
  HIGH: 'border-fraud-red/30 bg-fraud-red/5',
  MEDIUM: 'border-fraud-amber/30 bg-fraud-amber/5',
  LOW: 'border-surface-4 bg-surface-3/50',
};

const SEVERITY_BADGE: Record<string, string> = {
  HIGH: 'bg-fraud-red/20 text-fraud-red',
  MEDIUM: 'bg-fraud-amber/20 text-fraud-amber',
  LOW: 'bg-surface-4 text-gray-400',
};

export function AlertsPanel({ data }: Props) {
  if (!data) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-500 text-sm">
        No alert data available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="bg-surface-2 rounded-xl p-4 border border-surface-3">
        <h3 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-fraud-amber" />
          {data.entity} - Alert Analysis
        </h3>
        <div className="grid grid-cols-3 gap-3">
          <div className="text-center">
            <div className="text-2xl font-bold text-fraud-red">{data.summary?.high || 0}</div>
            <div className="text-xs text-gray-500">High Severity</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-fraud-amber">{data.summary?.medium || 0}</div>
            <div className="text-xs text-gray-500">Medium Severity</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-400">{data.summary?.total_transactions_analyzed || 0}</div>
            <div className="text-xs text-gray-500">Txns Analyzed</div>
          </div>
        </div>
      </div>

      {/* Alert List */}
      {data.alerts && data.alerts.length > 0 ? (
        <div className="space-y-2">
          {data.alerts.map((alert, i) => (
            <AlertCard key={i} alert={alert} />
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500 text-sm">
          No suspicious patterns detected
        </div>
      )}
    </div>
  );
}

function AlertCard({ alert }: { alert: Alert }) {
  return (
    <div className={`rounded-lg p-3 border ${ALERT_COLORS[alert.severity] || ALERT_COLORS.LOW}
                     ${alert.severity === 'HIGH' ? 'animate-pulse-glow' : ''}`}>
      <div className="flex items-start gap-3">
        <div className={`p-1.5 rounded-lg flex-shrink-0
          ${alert.severity === 'HIGH' ? 'bg-fraud-red/10 text-fraud-red' :
            alert.severity === 'MEDIUM' ? 'bg-fraud-amber/10 text-fraud-amber' :
            'bg-surface-4 text-gray-400'}`}>
          {ALERT_ICONS[alert.type] || <AlertTriangle className="w-4 h-4" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium text-gray-300 capitalize">
              {alert.type.replace(/_/g, ' ')}
            </span>
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${SEVERITY_BADGE[alert.severity] || ''}`}>
              {alert.severity}
            </span>
            {alert.is_fraud && (
              <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-fraud-red/20 text-fraud-red">
                CONFIRMED FRAUD
              </span>
            )}
          </div>
          <p className="text-xs text-gray-400 leading-relaxed">{alert.description}</p>
          <div className="flex items-center gap-3 mt-1.5 text-[10px] text-gray-500">
            {alert.amount && <span>Amount: ${alert.amount.toFixed(2)}</span>}
            {alert.total_amount && <span>Total: ${alert.total_amount.toFixed(2)}</span>}
            {alert.transaction_id && <span>TX #{alert.transaction_id}</span>}
            {alert.transaction_ids && <span>{alert.transaction_ids.length} transactions</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

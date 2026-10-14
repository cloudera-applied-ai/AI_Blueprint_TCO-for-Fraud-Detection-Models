import { useState, useCallback, useEffect } from 'react';
import { Shield, BarChart3, AlertTriangle, Search, Trash2, Settings, SlidersHorizontal, FlaskConical, Network } from 'lucide-react';
import { ChatPanel } from './components/ChatPanel';
import { RiskDashboard } from './components/RiskDashboard';
import { TransactionTable } from './components/TransactionTable';
import { ShapChart } from './components/ShapChart';
import { AlertsPanel } from './components/AlertsPanel';
import { SettingsPanel } from './components/SettingsPanel';
import { ExperimentLab } from './components/ExperimentLab';
import { DateRangePicker } from './components/DateRangePicker';
import { ThresholdAnalysis } from './components/ThresholdAnalysis';
import { CostCounter } from './components/CostCounter';
import { FraudNetworkPanel } from './components/FraudNetworkPanel';
import { InvestigationPanel } from './components/InvestigationPanel';
import { sendChat, getDashboard, clearSession, getHealth, getThresholdAnalysis, getSessionUsage, refreshPricing, traceFraudNetwork, getMerchantInvestigation } from './api';
import type {
  ChatMessage, ToolCall, RightPanelView, DashboardData,
  ExplanationResult, AlertsResult, Transaction, ThresholdAnalysisData,
  CostEstimate, ExperimentResult, FraudNetworkTrace, MerchantInvestigation,
} from './types';

const SESSION_ID = `session_${Date.now()}`;

const QUICK_ACTIONS = [
  { label: 'Risk Overview', prompt: 'Show me the fraud risk dashboard overview' },
  { label: 'Top Fraud Users', prompt: 'Which users have the most fraudulent transactions?' },
  { label: 'Recent Fraud', prompt: 'Show me the 10 most recent fraudulent transactions' },
  { label: 'Pattern Detection', prompt: 'Detect fraud patterns for user 42' },
  { label: 'Trace Merchant Fraud', prompt: 'Trace fraud from the merchant with the most fraudulent transactions — show me which customers were affected.' },
];

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [rightPanel, setRightPanel] = useState<RightPanelView>(null);
  const [health, setHealth] = useState<{ database: boolean; model: boolean } | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [backendConnected, setBackendConnected] = useState<boolean | null>(null);
  const [backendMode, setBackendMode] = useState<string | null>(null);
  const [dateStart, setDateStart] = useState<string | null>(null);
  const [dateEnd, setDateEnd] = useState<string | null>(null);
  const [sessionCost, setSessionCost] = useState<CostEstimate | null>(null);
  const [experimentResult, setExperimentResult] = useState<ExperimentResult | null>(null);

  const loadDashboard = useCallback((start?: string | null, end?: string | null) => {
    getDashboard(
      'all',
      undefined,
      start || undefined,
      end || undefined,
    ).then((data) => {
      setRightPanel({ type: 'dashboard', data: data as unknown as DashboardData });
    }).catch(() => {});
  }, []);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
    loadDashboard();
    getSessionUsage(SESSION_ID).then(setSessionCost).catch(() => {});
    fetch('/frontend/config/environment')
      .then(r => r.json())
      .then(data => {
        setBackendConnected(data.mode === 'proxy' || data.mode === 'embedded');
        setBackendMode(data.mode);
      })
      .catch(() => setBackendConnected(false));
  }, [loadDashboard]);

  const handleDateChange = (start: string | null, end: string | null) => {
    setDateStart(start);
    setDateEnd(end);
    loadDashboard(start, end);
  };

  const traceFromUser = useCallback((userId: number) => {
    setRightPanel({ type: 'trace', data: { error: `Loading trace for user ${userId}…` } as unknown as FraudNetworkTrace });
    traceFraudNetwork({
      user_id: userId,
      direction: 'user_to_merchants',
      fraud_only: true,
      max_counterparties: 25,
    })
      .then(d => setRightPanel({ type: 'trace', data: d as unknown as FraudNetworkTrace }))
      .catch(err => {
        const msg = err instanceof Error ? err.message : 'Trace failed';
        setRightPanel({ type: 'trace', data: { error: msg } as unknown as FraudNetworkTrace });
      });
  }, []);

  const investigateMerchant = useCallback((merchantName: string) => {
    setRightPanel({
      type: 'investigation',
      data: { error: `Building report for ${merchantName}…`, merchant_name: merchantName } as unknown as MerchantInvestigation,
    });
    getMerchantInvestigation(merchantName)
      .then(d => setRightPanel({ type: 'investigation', data: d as unknown as MerchantInvestigation }))
      .catch(err => {
        const msg = err instanceof Error ? err.message : 'Investigation failed';
        setRightPanel({
          type: 'investigation',
          data: { error: msg, merchant_name: merchantName } as unknown as MerchantInvestigation,
        });
      });
  }, []);

  const traceFromMerchant = useCallback((merchantName: string) => {
    setRightPanel({ type: 'trace', data: { error: `Loading trace for ${merchantName}…` } as unknown as FraudNetworkTrace });
    traceFraudNetwork({
      merchant_name: merchantName,
      direction: 'merchant_to_users',
      fraud_only: true,
      max_counterparties: 25,
    })
      .then(d => setRightPanel({ type: 'trace', data: d as unknown as FraudNetworkTrace }))
      .catch(err => {
        const msg = err instanceof Error ? err.message : 'Trace failed';
        setRightPanel({ type: 'trace', data: { error: msg } as unknown as FraudNetworkTrace });
      });
  }, []);

  const showFraudTransactions = useCallback((filters: { user_id?: number; merchant_name?: string }) => {
    import('./api').then(({ queryTransactions }) => {
      queryTransactions({
        ...filters,
        is_fraud: true,
        limit: 100,
        order_by: 'amount_desc',
      })
        .then(d => setRightPanel({ type: 'transactions', data: d.transactions as unknown as Transaction[] }))
        .catch(() => {});
    });
  }, []);

  const showAllTransactions = useCallback((filters: { user_id?: number; merchant_name?: string }) => {
    import('./api').then(({ queryTransactions }) => {
      queryTransactions({
        ...filters,
        limit: 100,
        order_by: 'date_desc',
      })
        .then(d => setRightPanel({ type: 'transactions', data: d.transactions as unknown as Transaction[] }))
        .catch(() => {});
    });
  }, []);

  const handleMonthClick = useCallback((year: number, month: number) => {
    const mm = String(month).padStart(2, '0');
    const lastDay = new Date(year, month, 0).getDate();
    const start = `${year}-${mm}-01`;
    const end = `${year}-${mm}-${String(lastDay).padStart(2, '0')}`;
    import('./api').then(({ queryTransactions }) => {
      queryTransactions({
        is_fraud: true,
        start_date: start,
        end_date: end,
        limit: 50,
        order_by: 'amount_desc',
      }).then(d => {
        setRightPanel({ type: 'transactions', data: d.transactions as unknown as Transaction[] });
      }).catch(() => {});
    });
  }, []);

  const updateRightPanel = useCallback((toolCalls: ToolCall[]) => {
    if (!toolCalls?.length) return;

    // The agent may finish with a tool that has no visualization (or an
    // explain call after a score) — walk backwards to the most recent tool
    // call we know how to render instead of only checking the very last one.
    const VISUALIZED_TOOLS = new Set([
      'get_risk_dashboard', 'query_transactions', 'explain_prediction',
      'score_transaction', 'detect_alert_patterns', 'investigate_merchant',
      'trace_fraud_network',
    ]);
    const lastTool = [...toolCalls].reverse().find(tc => tc.args && VISUALIZED_TOOLS.has(tc.tool));
    if (!lastTool) return;
    switch (lastTool.tool) {
      case 'get_risk_dashboard':
        getDashboard(
          (lastTool.args.time_period as string) || 'all',
          lastTool.args.group_by as string,
          dateStart || undefined,
          dateEnd || undefined,
        ).then(data => setRightPanel({ type: 'dashboard', data: data as unknown as DashboardData }))
          .catch(() => {});
        break;

      case 'query_transactions':
        import('./api').then(({ queryTransactions }) => {
          queryTransactions(lastTool.args).then(data => {
            setRightPanel({ type: 'transactions', data: data.transactions as unknown as Transaction[] });
          }).catch(() => {});
        });
        break;

      case 'explain_prediction':
      case 'score_transaction': {
        // Raw transaction_data scoring has no stored transaction to re-fetch,
        // so the SHAP panel can only be shown when an ID was passed. Prefer
        // this call's ID, falling back to an earlier score/explain call's.
        const txId = (lastTool.args.transaction_id as number | undefined) ??
          [...toolCalls].reverse()
            .find(tc => tc.args?.transaction_id &&
              (tc.tool === 'score_transaction' || tc.tool === 'explain_prediction'))
            ?.args.transaction_id as number | undefined;
        if (txId) {
          import('./api').then(({ explainTransaction }) => {
            explainTransaction(txId).then(data => {
              setRightPanel({ type: 'explanation', data: data as unknown as ExplanationResult });
            }).catch(() => {});
          });
        }
        break;
      }

      case 'detect_alert_patterns':
        import('./api').then(({ getAlerts }) => {
          getAlerts(
            lastTool.args.user_id as number | undefined,
            lastTool.args.merchant_name as string | undefined,
            (lastTool.args.pattern_type as string) || 'all',
          ).then(data => {
            setRightPanel({ type: 'alerts', data: data as unknown as AlertsResult });
          }).catch(() => {});
        });
        break;

      case 'investigate_merchant': {
        const name = lastTool.args.merchant_name as string | undefined;
        if (name) investigateMerchant(name);
        break;
      }

      case 'trace_fraud_network':
        traceFraudNetwork({
          merchant_name: lastTool.args.merchant_name as string | undefined,
          user_id: lastTool.args.user_id as number | undefined,
          direction: lastTool.args.direction as 'merchant_to_users' | 'user_to_merchants' | 'auto' | undefined,
          fraud_only: lastTool.args.fraud_only as boolean | undefined,
          max_counterparties: lastTool.args.max_counterparties as number | undefined,
        }).then(data => {
          setRightPanel({ type: 'trace', data: data as unknown as FraudNetworkTrace });
        }).catch(() => {});
        break;
    }
  }, [dateStart, dateEnd, investigateMerchant]);

  const handleSendMessage = useCallback(async (message: string) => {
    const userMsg: ChatMessage = { role: 'user', content: message, timestamp: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const result = await sendChat(message, SESSION_ID);

      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: result.response,
        tool_calls: result.tool_calls,
        timestamp: Date.now(),
        guard: result.guard,
      };
      setMessages(prev => [...prev, assistantMsg]);

      if (result.usage?.session) {
        setSessionCost(result.usage.session);
      }

      // Update right panel based on tool calls
      updateRightPanel(result.tool_calls);
    } catch (err) {
      const errorMsg: ChatMessage = {
        role: 'assistant',
        content: `Sorry, I encountered an error: ${err instanceof Error ? err.message : 'Unknown error'}. Please make sure the backend server is running.`,
        timestamp: Date.now(),
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  }, [updateRightPanel]);

  const handleClearChat = async () => {
    setMessages([]);
    setSessionCost(null);
    await clearSession(SESSION_ID).catch(() => {});
  };

  return (
    <div className="h-screen flex flex-col bg-surface-0 font-sans">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 bg-surface-1 border-b border-surface-3">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-accent/10 rounded-lg">
            <Shield className="w-5 h-5 text-accent" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-gray-100">Fraud Detection AI</h1>
            <p className="text-xs text-gray-500">Conversational fraud analysis powered by NVIDIA RAPIDS + NIMS + XGBoost + SHAP</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs">
            {backendConnected !== null && (
              <>
                <span className={`w-2 h-2 rounded-full ${backendConnected ? 'bg-fraud-green' : 'bg-fraud-red'}`} />
                <span className="text-gray-500">
                  {backendMode === 'embedded' ? 'API' : backendConnected ? 'Backend' : 'Backend'}
                </span>
              </>
            )}
            {health && (
              <>
                <span className={`w-2 h-2 rounded-full ${health.database ? 'bg-fraud-green' : 'bg-fraud-red'}`} />
                <span className="text-gray-500">DB</span>
                <span className={`w-2 h-2 rounded-full ${health.model ? 'bg-fraud-green' : 'bg-fraud-red'}`} />
                <span className="text-gray-500">Model</span>
              </>
            )}
          </div>
          <CostCounter
            usage={sessionCost}
            onRefreshPricing={async () => {
              await refreshPricing();
              const fresh = await getSessionUsage(SESSION_ID);
              setSessionCost(fresh);
            }}
          />
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="p-2 text-gray-400 hover:text-gray-200 rounded-lg hover:bg-surface-3"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Left: Chat Panel (58%) */}
        <div className="w-[58%] flex flex-col border-r border-surface-3">
          {/* Quick Actions */}
          <div className="px-4 py-2 border-b border-surface-3 flex items-center gap-2 overflow-x-auto">
            {QUICK_ACTIONS.map(action => (
              <button
                key={action.label}
                onClick={() => handleSendMessage(action.prompt)}
                disabled={isLoading}
                className="flex-shrink-0 px-3 py-1.5 text-xs font-medium text-gray-400
                           bg-surface-2 border border-surface-4 rounded-full
                           hover:text-gray-200 hover:border-accent/50 hover:bg-surface-3
                           disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {action.label}
              </button>
            ))}
            <button
              onClick={handleClearChat}
              className="flex-shrink-0 p-1.5 text-gray-500 hover:text-fraud-red rounded-lg hover:bg-surface-3 ml-auto"
              title="Clear chat"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>

          <ChatPanel
            messages={messages}
            isLoading={isLoading}
            onSendMessage={handleSendMessage}
          />
        </div>

        {/* Right: Dynamic Visualization (42%) */}
        <div className="w-[42%] flex flex-col bg-surface-1 overflow-hidden">
          {/* Panel Tabs + Date Picker */}
          <div className="px-4 py-2 border-b border-surface-3 space-y-2">
            <div className="flex items-center gap-1">
              <button
                onClick={() => loadDashboard(dateStart, dateEnd)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md flex items-center gap-1.5
                           ${rightPanel?.type === 'dashboard' ? 'bg-accent/20 text-accent' : 'text-gray-400 hover:text-gray-200 hover:bg-surface-3'}`}
              >
                <BarChart3 className="w-3.5 h-3.5" /> Dashboard
              </button>
              <button
                onClick={() => {
                  import('./api').then(({ queryTransactions }) => {
                    queryTransactions({ is_fraud: true, limit: 20, order_by: 'amount_desc' })
                      .then(d => setRightPanel({ type: 'transactions', data: d.transactions as unknown as Transaction[] }))
                      .catch(() => {});
                  });
                }}
                className={`px-3 py-1.5 text-xs font-medium rounded-md flex items-center gap-1.5
                           ${rightPanel?.type === 'transactions' ? 'bg-accent/20 text-accent' : 'text-gray-400 hover:text-gray-200 hover:bg-surface-3'}`}
              >
                <Search className="w-3.5 h-3.5" /> Transactions
              </button>
              <button
                onClick={() => {
                  import('./api').then(({ getAlerts }) => {
                    getAlerts(42).then(d => setRightPanel({ type: 'alerts', data: d as unknown as AlertsResult })).catch(() => {});
                  });
                }}
                className={`px-3 py-1.5 text-xs font-medium rounded-md flex items-center gap-1.5
                           ${rightPanel?.type === 'alerts' ? 'bg-accent/20 text-accent' : 'text-gray-400 hover:text-gray-200 hover:bg-surface-3'}`}
              >
                <AlertTriangle className="w-3.5 h-3.5" /> Alerts
              </button>
              <button
                onClick={() => {
                  getThresholdAnalysis().then(d => {
                    setRightPanel({ type: 'threshold', data: d as unknown as ThresholdAnalysisData });
                  }).catch(() => {});
                }}
                className={`px-3 py-1.5 text-xs font-medium rounded-md flex items-center gap-1.5
                           ${rightPanel?.type === 'threshold' ? 'bg-accent/20 text-accent' : 'text-gray-400 hover:text-gray-200 hover:bg-surface-3'}`}
              >
                <SlidersHorizontal className="w-3.5 h-3.5" /> Threshold
              </button>
              <button
                onClick={() => setRightPanel({ type: 'experiment', data: experimentResult })}
                className={`px-3 py-1.5 text-xs font-medium rounded-md flex items-center gap-1.5
                           ${rightPanel?.type === 'experiment' ? 'bg-accent/20 text-accent' : 'text-gray-400 hover:text-gray-200 hover:bg-surface-3'}`}
              >
                <FlaskConical className="w-3.5 h-3.5" /> Retrain
              </button>
              <button
                onClick={() => {
                  // Don't auto-load anything. The panel populates only when the operator
                  // explicitly traces something — via chat, a drill-in icon, or a Report button.
                  if (rightPanel?.type !== 'trace') {
                    setRightPanel({ type: 'trace', data: {} as unknown as FraudNetworkTrace });
                  }
                }}
                title="Open the Trace panel — populated when you trace a merchant or user from chat or drill-in"
                className={`px-3 py-1.5 text-xs font-medium rounded-md flex items-center gap-1.5
                           ${rightPanel?.type === 'trace' ? 'bg-accent/20 text-accent' : 'text-gray-400 hover:text-gray-200 hover:bg-surface-3'}`}
              >
                <Network className="w-3.5 h-3.5" /> Trace
              </button>
            </div>
            {/* Date Range Picker - shown for dashboard view */}
            {(rightPanel?.type === 'dashboard' || !rightPanel) && (
              <DateRangePicker
                startDate={dateStart}
                endDate={dateEnd}
                onChange={handleDateChange}
              />
            )}
          </div>

          {/* Panel Content */}
          <div className="flex-1 overflow-y-auto p-4">
            {!rightPanel && (
              <div className="flex items-center justify-center h-full text-gray-500 text-sm">
                <div className="text-center">
                  <Shield className="w-12 h-12 mx-auto mb-3 opacity-20" />
                  <p>Start a conversation to see visualizations</p>
                  <p className="text-xs mt-1 text-gray-600">Ask about fraud patterns, transactions, or risk analysis</p>
                </div>
              </div>
            )}
            {rightPanel?.type === 'dashboard' && (
              <RiskDashboard data={rightPanel.data} onMonthClick={handleMonthClick} />
            )}
            {rightPanel?.type === 'transactions' && <TransactionTable transactions={rightPanel.data} />}
            {rightPanel?.type === 'explanation' && <ShapChart data={rightPanel.data} />}
            {rightPanel?.type === 'alerts' && <AlertsPanel data={rightPanel.data} />}
            {rightPanel?.type === 'threshold' && <ThresholdAnalysis data={rightPanel.data} />}
            {rightPanel?.type === 'trace' && (
              <FraudNetworkPanel
                trace={rightPanel.data}
                onTraceUser={traceFromUser}
                onTraceMerchant={traceFromMerchant}
                onShowUserTransactions={(uid) => showFraudTransactions({ user_id: uid })}
                onShowMerchantTransactions={(name) => showFraudTransactions({ merchant_name: name })}
                onShowAllUserTransactions={(uid) => showAllTransactions({ user_id: uid })}
                onShowAllMerchantTransactions={(name) => showAllTransactions({ merchant_name: name })}
                onInvestigateMerchant={investigateMerchant}
              />
            )}
            {rightPanel?.type === 'investigation' && (
              <InvestigationPanel
                investigation={rightPanel.data}
                onTraceMerchant={traceFromMerchant}
                onShowMerchantTransactions={(name) => showFraudTransactions({ merchant_name: name })}
                onShowAllUserTransactions={(uid) => showAllTransactions({ user_id: uid })}
              />
            )}
            {rightPanel?.type === 'experiment' && (
              <ExperimentLab
                result={experimentResult}
                onResult={(r) => {
                  setExperimentResult(r);
                  setRightPanel({ type: 'experiment', data: r });
                }}
              />
            )}
          </div>
        </div>
      </div>

      {/* Settings Modal */}
      {showSettings && (
        <SettingsPanel
          onClose={() => setShowSettings(false)}
          onBackendChange={(connected) => {
            setBackendConnected(connected);
            setBackendMode(connected ? 'proxy' : 'disconnected');
            // Re-check health now that backend may have changed
            getHealth().then(setHealth).catch(() => setHealth(null));
          }}
        />
      )}
    </div>
  );
}
